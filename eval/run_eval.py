"""QC-3B deterministic eval / regression runner.

Loads and permanently validates the QC-3A case corpus, runs each selected case
through the real QuoteCheck route handler, applies only the QC-3A deterministic
(Layer A) checks, writes a timestamped JSONL run artifact and a Markdown summary,
and exits non-zero when any selected case fails deterministic evaluation.

Layer A only. This runner establishes schema validity, metadata provenance,
explicit uncertainty-marker values, deterministic forbidden-term violations, and
structured line-item counts. It establishes nothing about faithfulness,
hallucination, explanation quality, usefulness, or semantic uncertainty
calibration — those remain the human responsibility defined in eval/rubric.md.

Usage
-----
    python -m eval.run_eval --validate-only
    python -m eval.run_eval --mode demo
    python -m eval.run_eval --mode demo --case-id REG-001 --case-id REG-002
    python -m eval.run_eval --mode openai --allow-paid      # billed; explicit opt-in

Mode / config sequencing
------------------------
backend.core.config freezes USE_OPENAI / MODEL / OPENAI_API_KEY / APP_RUN_LOG_PATH
from os.environ at first import, and backend.app calls load_dotenv("backend/.env")
at import (which does not override already-set vars). So main() parses args, then
sets QUOTECHECK_USE_OPENAI and a throwaway QUOTECHECK_LOG_PATH, and only then
imports the backend analysis path. One invocation == one mode; per-mode reporting
means running the suite twice.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from eval.corpus import (
    CASES_DIR,
    TERMSETS_PATH,
    Case,
    Corpus,
    CorpusError,
    load_corpus,
)
from eval.graders import (
    CheckResult,
    PRICE_GUARD_CHECK,
    grade_check,
    grade_metadata_complete,
    grade_schema_valid,
    schema_valid_execution_failure,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS_DIR = REPO_ROOT / "eval" / "results"

COST_GUARD_MESSAGE = (
    "Refusing to run OpenAI mode without --allow-paid.\n"
    "`--mode openai` makes one billed OpenAI API call per selected case. Re-run with\n"
    "`--mode openai --allow-paid` to authorize billed inference. No API call was made."
)

INTERPRETATION_BOUNDARY = (
    "Passing deterministic invariants does not establish semantic correctness, "
    "faithfulness, usefulness, or absence of unsupported inference. Those require "
    "the human rubric (`eval/rubric.md`)."
)


# --------------------------------------------------------------------------- #
# Per-case result
# --------------------------------------------------------------------------- #

@dataclass
class CaseResult:
    case_id: str
    domain: str
    categories: tuple[str, ...]
    mode: str
    prompt_version: str | None
    model: str | None
    schema_pass: bool
    check_results: list[CheckResult]
    latency_ms: int | None
    execution_error: str | None
    rationale: str
    regression_origin: str | None = None

    @property
    def deterministic_pass(self) -> bool:
        return (
            self.schema_pass
            and self.execution_error is None
            and all(cr.passed for cr in self.check_results)
        )

    @property
    def failed_checks(self) -> list[str]:
        return [cr.label for cr in self.check_results if not cr.passed]

    def to_record(self, run_timestamp: str) -> dict:
        rec = {
            "case_id": self.case_id,
            "domain": self.domain,
            "categories": list(self.categories),
            "mode": self.mode,
            "prompt_version": self.prompt_version,
            "model": self.model,
            "schema_pass": self.schema_pass,
            "deterministic_pass": self.deterministic_pass,
            "failed_checks": self.failed_checks,
            "check_results": [cr.to_dict() for cr in self.check_results],
            "latency_ms": self.latency_ms,
            "execution_error": self.execution_error,
            "human_review_status": "not_reviewed",
            "rationale": self.rationale,
            "run_timestamp": run_timestamp,
        }
        if self.regression_origin is not None:
            rec["regression_origin"] = self.regression_origin
        return rec


# --------------------------------------------------------------------------- #
# Execution adapter (route handler boundary)
# --------------------------------------------------------------------------- #

def format_execution_error(exc: BaseException) -> str:
    """Readable one-line error, surfacing HTTPException status_code / detail.

    fastapi.HTTPException carries `status_code` and `detail`; we read them via
    getattr so this stays import-free of fastapi.
    """
    base = f"{type(exc).__name__}: {exc}"
    parts = [base]
    status = getattr(exc, "status_code", None)
    if status is not None:
        parts.append(f"status_code={status}")
    detail = getattr(exc, "detail", None)
    if detail is not None and str(detail) and str(detail) not in base:
        parts.append(f"detail={detail!r}")
    return " | ".join(parts)


def run_case(
    analyze_fn,
    request_cls,
    result_cls,
    case: Case,
    *,
    mode: str,
    expected_model: str,
    expected_prompt_version: str,
    termsets: dict,
) -> CaseResult:
    """Run one case through the analyzer entry point and grade it.

    A failure in one case (analyzer exception, route HTTPException, schema break)
    produces a result record and never aborts the suite.
    """
    try:
        result = analyze_fn(request_cls(quote_text=case.quote_text))
    except Exception as exc:  # noqa: BLE001 - deliberately broad; recorded, not raised
        err = format_execution_error(exc)
        return CaseResult(
            case_id=case.case_id,
            domain=case.domain,
            categories=case.categories,
            mode=mode,
            prompt_version=None,
            model=None,
            schema_pass=False,
            check_results=[schema_valid_execution_failure(err)],
            latency_ms=None,
            execution_error=err,
            rationale=case.rationale,
            regression_origin=case.regression_origin,
        )

    checks: list[CheckResult] = [grade_schema_valid(result, result_cls)]
    checks.extend(
        grade_metadata_complete(
            result,
            mode=mode,
            expected_model=expected_model,
            expected_prompt_version=expected_prompt_version,
        )
    )

    must_not = list(case.must_not)
    if PRICE_GUARD_CHECK not in must_not:
        must_not.append(PRICE_GUARD_CHECK)

    for chk in list(case.must) + must_not:
        checks.append(grade_check(chk, result, quote_text=case.quote_text, termsets=termsets))

    return CaseResult(
        case_id=case.case_id,
        domain=case.domain,
        categories=case.categories,
        mode=mode,
        prompt_version=result.metadata.prompt_version,
        model=result.metadata.model,
        schema_pass=checks[0].passed,
        check_results=checks,
        latency_ms=result.metadata.latency_ms,
        execution_error=None,
        rationale=case.rationale,
        regression_origin=case.regression_origin,
    )


# --------------------------------------------------------------------------- #
# Aggregation / reporting (pure)
# --------------------------------------------------------------------------- #

def suite_exit_code(results: list[CaseResult]) -> int:
    return 0 if results and all(r.deterministic_pass for r in results) else 1


def aggregate_by_domain(results: list[CaseResult]) -> list[dict]:
    rows: dict[str, dict] = {}
    for r in results:
        row = rows.setdefault(r.domain, {"key": r.domain, "cases": 0, "passed": 0, "failed": 0})
        row["cases"] += 1
        row["passed" if r.deterministic_pass else "failed"] += 1
    return [rows[k] for k in sorted(rows)]


def aggregate_by_category(results: list[CaseResult]) -> list[dict]:
    rows: dict[str, dict] = {}
    for r in results:
        for cat in r.categories:
            row = rows.setdefault(cat, {"key": cat, "cases": 0, "passed": 0, "failed": 0})
            row["cases"] += 1
            row["passed" if r.deterministic_pass else "failed"] += 1
    return [rows[k] for k in sorted(rows)]


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile: sorted[ceil(q/100 * n) - 1], q in [0, 100].

    q <= 0 returns the min, q >= 100 returns the max. Returns None for no data.
    """
    if not values:
        return None
    s = sorted(values)
    if q <= 0:
        return float(s[0])
    if q >= 100:
        return float(s[-1])
    rank = math.ceil(q / 100.0 * len(s))
    return float(s[max(1, rank) - 1])


def _rate(num: int, den: int) -> str:
    return f"{(100.0 * num / den):.1f}%" if den else "n/a"


def build_summary_md(
    results: list[CaseResult],
    *,
    run_timestamp: str,
    mode: str,
    model: str,
    prompt_version: str,
    selected_case_ids: list[str],
    total_corpus: int,
    jsonl_name: str,
) -> str:
    total = len(results)
    schema_passes = sum(1 for r in results if r.schema_pass)
    det_passes = sum(1 for r in results if r.deterministic_pass)
    exec_errors = [r for r in results if r.execution_error is not None]
    filtered = len(selected_case_ids) != total_corpus

    L: list[str] = []
    L.append(f"# QuoteCheck deterministic eval — {mode} mode — {run_timestamp}")
    L.append("")
    L.append(
        "Layer A only. Deterministic invariants from the QC-3A specification. "
        "This report makes no semantic-quality claim — see *Interpretation boundary* below."
    )
    L.append("")

    L.append("## Run metadata")
    L.append("")
    L.append(f"- Timestamp (UTC): `{run_timestamp}`")
    L.append(f"- Mode: `{mode}`")
    L.append(f"- Model: `{model}`")
    L.append(f"- Prompt version: `{prompt_version}`")
    L.append(f"- Run artifact: `{jsonl_name}`")
    if filtered:
        L.append(f"- Selected cases ({total}/{total_corpus}): {', '.join(selected_case_ids)}")
    else:
        L.append(f"- Selected cases: all {total}")
    L.append("")

    L.append("## Overall results")
    L.append("")
    L.append(f"- Total cases run: {total}")
    L.append(f"- Schema passes: {schema_passes}/{total} ({_rate(schema_passes, total)})")
    L.append(
        f"- Deterministic invariant passes: {det_passes}/{total} ({_rate(det_passes, total)})"
    )
    L.append(f"- Execution errors: {len(exec_errors)}")
    L.append("")

    L.append("## Failures by domain")
    L.append("")
    L.append("| Domain | Cases | Passed | Failed |")
    L.append("|---|---|---|---|")
    for row in aggregate_by_domain(results):
        L.append(f"| {row['key']} | {row['cases']} | {row['passed']} | {row['failed']} |")
    L.append("")

    L.append("## Failures by category")
    L.append("")
    L.append("_A case with multiple categories is counted in every applicable row._")
    L.append("")
    L.append("| Category | Cases | Passed | Failed |")
    L.append("|---|---|---|---|")
    for row in aggregate_by_category(results):
        L.append(f"| {row['key']} | {row['cases']} | {row['passed']} | {row['failed']} |")
    L.append("")

    L.append("## Failed cases")
    L.append("")
    failed = [r for r in results if not r.deterministic_pass]
    if not failed:
        L.append("_None — every selected case passed deterministic evaluation._")
    else:
        for r in failed:
            L.append(f"### {r.case_id} ({r.domain})")
            if r.execution_error:
                L.append(f"- Execution error: `{r.execution_error}`")
            for cr in r.check_results:
                if not cr.passed:
                    L.append(f"- `{cr.label}` — {cr.message}")
            L.append("")
    L.append("")

    L.append("## Historical regressions")
    L.append("")
    for reg_id in ("REG-001", "REG-002"):
        rr = next((r for r in results if r.case_id == reg_id), None)
        if rr is None:
            L.append(f"- **{reg_id}**: not in this run")
            continue
        status = "PASS" if rr.deterministic_pass else "FAIL"
        detail = "" if rr.deterministic_pass else f" — failed: {', '.join(rr.failed_checks)}"
        L.append(f"- **{reg_id}**: {status}{detail}")
    L.append("")

    L.append("## Latency")
    L.append("")
    lats = [float(r.latency_ms) for r in results if isinstance(r.latency_ms, int)]
    if not lats:
        L.append("_No latency data (no successful cases)._")
    elif mode == "openai":
        p50 = percentile(lats, 50)
        p95 = percentile(lats, 95)
        L.append("Percentiles use the nearest-rank method: `sorted[ceil(q/100 * n) - 1]`.")
        L.append("")
        L.append(f"- n = {len(lats)}")
        L.append(f"- p50: {p50:.0f} ms")
        L.append(f"- p95: {p95:.0f} ms")
    else:
        L.append(
            "_Demo mode: local wall-clock only. This is not provider-performance "
            "evidence — the Demo analyzer does no network I/O._"
        )
        L.append("")
        L.append(f"- n = {len(lats)}")
        L.append(f"- min / mean / max: {min(lats):.0f} / {statistics.fmean(lats):.0f} / {max(lats):.0f} ms")
    L.append("")

    L.append("## Human review")
    L.append("")
    L.append("Semantic rubric status: **not reviewed in this automated run.**")
    L.append("")
    L.append(
        "Layer B (faithfulness, unsupported inference, uncertainty calibration, "
        "explanation quality, actionability, professional-boundary discipline) is scored "
        "by a human against [`eval/rubric.md`](../rubric.md). This run did not score it."
    )
    L.append("")

    L.append("## Interpretation boundary")
    L.append("")
    L.append(INTERPRETATION_BOUNDARY)
    L.append("")

    return "\n".join(L)


# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #

def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_artifacts(
    results: list[CaseResult],
    *,
    results_dir: Path,
    run_timestamp: str,
    mode: str,
    model: str,
    prompt_version: str,
    selected_case_ids: list[str],
    total_corpus: int,
) -> tuple[Path, Path]:
    results_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = results_dir / f"run_{run_timestamp}.jsonl"
    md_path = results_dir / f"summary_{run_timestamp}.md"

    with jsonl_path.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r.to_record(run_timestamp), ensure_ascii=False) + "\n")

    md = build_summary_md(
        results,
        run_timestamp=run_timestamp,
        mode=mode,
        model=model,
        prompt_version=prompt_version,
        selected_case_ids=selected_case_ids,
        total_corpus=total_corpus,
        jsonl_name=jsonl_path.name,
    )
    md_path.write_text(md, encoding="utf-8")
    return jsonl_path, md_path


# --------------------------------------------------------------------------- #
# Case selection
# --------------------------------------------------------------------------- #

def select_cases(corpus: Corpus, args: argparse.Namespace) -> list[Case]:
    cases = list(corpus.cases)
    if args.case_id:
        wanted = list(dict.fromkeys(args.case_id))
        known = {c.case_id for c in corpus.cases}
        missing = [cid for cid in wanted if cid not in known]
        if missing:
            raise SystemExit(f"unknown --case-id value(s): {', '.join(missing)}")
        cases = [c for c in cases if c.case_id in set(wanted)]
    if args.domain:
        cases = [c for c in cases if c.domain in set(args.domain)]
    if args.category:
        cats = set(args.category)
        cases = [c for c in cases if cats.intersection(c.categories)]
    if not cases:
        raise SystemExit("no cases selected after applying filters")
    return cases


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m eval.run_eval",
        description="QC-3B deterministic eval / regression runner (Layer A only).",
    )
    p.add_argument("--mode", choices=["demo", "openai"], default="demo",
                   help="analyzer mode (default: demo, zero cost)")
    p.add_argument("--allow-paid", action="store_true",
                   help="authorize billed OpenAI inference (required with --mode openai)")
    p.add_argument("--case-id", action="append", default=[], metavar="ID",
                   help="restrict the run to this case id (repeatable)")
    p.add_argument("--domain", action="append", default=[], metavar="DOMAIN",
                   help="restrict the run to this domain (repeatable)")
    p.add_argument("--category", action="append", default=[], metavar="CATEGORY",
                   help="restrict the run to cases carrying this category (repeatable)")
    p.add_argument("--validate-only", action="store_true",
                   help="validate the corpus and exit; no analyzer calls")
    p.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR),
                   help=f"where to write run artifacts (default: {DEFAULT_RESULTS_DIR})")
    return p


def run_validate_only(args: argparse.Namespace) -> int:
    try:
        corpus = load_corpus(CASES_DIR, TERMSETS_PATH)
    except CorpusError as e:
        print("CORPUS INVALID\n")
        print(str(e))
        return 1

    cases = corpus.cases
    domains = sorted({c.domain for c in cases})
    categories = sorted({cat for c in cases for cat in c.categories})
    checks_used = sorted(
        {chk["check"] for c in cases for chk in list(c.must) + list(c.must_not)}
    )
    termsets_used = sorted(
        {chk["termset"] for c in cases for chk in list(c.must) + list(c.must_not)
         if chk.get("check") == "forbidden_terms"}
    )
    reg_counts = {rid: sum(1 for c in cases if c.case_id == rid) for rid in ("REG-001", "REG-002")}

    print(f"[1] JSON parse            : {len(cases)}/{len(cases)} case files parsed")
    print(f"[2] case_id uniqueness    : {len({c.case_id for c in cases})} unique / {len(cases)} cases")
    print(f"[3] domain values         : all valid — {domains}")
    print(f"[4] category values       : all valid — {categories}")
    print(f"[5] corpus size           : {len(cases)} (required 24-30)")
    print(f"[6] REG-001 / REG-002     : {reg_counts['REG-001']} / {reg_counts['REG-002']} occurrence(s)")
    print(f"[7] quote_text uniqueness : {len({' '.join(c.quote_text.split()) for c in cases})} distinct")
    print(f"[8] check vocabulary      : {checks_used}")
    print(f"[9] termsets resolve      : {termsets_used}")
    print("[10] termset mode source  : ok (mode only in termsets.json; no per-case override)")
    print("[11] category consistency : enforced (clean_itemized, professional_confirmation_*, cross_domain_trap)")
    print(f"\nOK — {len(cases)} cases, {len(domains)} domains, {len(categories)} categories, 0 errors.")
    return 0


def run_suite(args: argparse.Namespace) -> int:
    # Backend imported only here, after env is set by main().
    from backend.app import analyze
    from backend.core.config import DEMO_ANALYZER_MODEL, MODEL
    from backend.core.prompt import PROMPT_VERSION
    from backend.core.schema import AnalyzeRequest, QuoteCheckResult

    try:
        corpus = load_corpus(CASES_DIR, TERMSETS_PATH)
    except CorpusError as e:
        print("CORPUS INVALID — aborting before any analyzer call.\n", file=sys.stderr)
        print(str(e), file=sys.stderr)
        return 2

    cases = select_cases(corpus, args)
    expected_model = MODEL if args.mode == "openai" else DEMO_ANALYZER_MODEL

    if args.mode == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            print("ERROR: --mode openai requires OPENAI_API_KEY to be set.", file=sys.stderr)
            return 2
        print(f"OpenAI mode: {len(cases)} selected case(s); configured model = {MODEL!r}.")
        print("WARNING: this will make one billed OpenAI API call per selected case.")

    run_timestamp = utc_stamp()
    results: list[CaseResult] = []
    for case in cases:
        results.append(
            run_case(
                analyze,
                AnalyzeRequest,
                QuoteCheckResult,
                case,
                mode=args.mode,
                expected_model=expected_model,
                expected_prompt_version=PROMPT_VERSION,
                termsets=corpus.termsets,
            )
        )

    jsonl_path, md_path = write_artifacts(
        results,
        results_dir=Path(args.results_dir),
        run_timestamp=run_timestamp,
        mode=args.mode,
        model=expected_model,
        prompt_version=PROMPT_VERSION,
        selected_case_ids=[c.case_id for c in cases],
        total_corpus=len(corpus.cases),
    )

    total = len(results)
    det_passes = sum(1 for r in results if r.deterministic_pass)
    schema_passes = sum(1 for r in results if r.schema_pass)
    print(f"\nWrote {jsonl_path}")
    print(f"Wrote {md_path}")
    print(
        f"{schema_passes}/{total} schema-valid; {det_passes}/{total} deterministic cases pass."
    )
    code = suite_exit_code(results)
    if code != 0:
        print(
            "Exit non-zero: one or more selected cases failed deterministic evaluation "
            "(known Demo-mode gaps are retained, not suppressed)."
        )
    return code


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.validate_only:
        return run_validate_only(args)

    # Cost-control boundary: refuse OpenAI mode without explicit authorization,
    # before the application / analyzer execution path is ever invoked.
    if args.mode == "openai" and not args.allow_paid:
        print(COST_GUARD_MESSAGE, file=sys.stderr)
        return 2

    # Establish mode + a throwaway app-run log path BEFORE importing backend.
    os.environ["QUOTECHECK_USE_OPENAI"] = "1" if args.mode == "openai" else "0"
    tmp = tempfile.NamedTemporaryFile(
        prefix="quotecheck_eval_applog_", suffix=".jsonl", delete=False
    )
    tmp.close()
    os.environ["QUOTECHECK_LOG_PATH"] = tmp.name
    try:
        return run_suite(args)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

"""Corpus loading and permanent validation for the QC-3A case corpus.

QC-3A validated the corpus with a throwaway script. QC-3B makes the structural
checks permanent: the runner fails fast, before any analyzer call, if the corpus
or termset file is malformed. A malformed corpus means the eval suite itself is
broken; that is different from a case whose expectations the current analyzer
fails to meet (which is a normal, reportable result).

The check vocabulary enforced here is exactly what the 27 cases currently use:

    forbidden_terms    -> {check, termset}          (shared termset name only)
    uncertainty_marker -> {check, marker, expected}
    line_items_where   -> {check, property, value, min_count}
                          property in {vague_or_confusing, evidence_needed_nonempty}

Anything outside that surface (topic_present, line_items_where.risk_level /
max_count, inline forbidden_terms terms/mode/fields, per-case termset mode
override) is an unknown/unsupported shape and fails validation. Support is added
later only alongside a real case that needs it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Marker names come from the application contract, not a hardcoded list, so the
# runner stays correct if the schema legitimately changes. schema.py imports only
# pydantic + stdlib, so this is cheap and has no config/dotenv/network side effect.
from backend.core.schema import UncertaintyMarkers

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = REPO_ROOT / "eval" / "cases"
TERMSETS_PATH = REPO_ROOT / "eval" / "termsets.json"

VALID_DOMAINS = {
    "automotive",
    "hvac_appliance",
    "plumbing_home",
    "electronics_repair",
    "contractor_vendor",
    "generic_service",
}

VALID_CATEGORIES = {
    "clean_itemized",
    "vague_bundled_charge",
    "missing_scope_or_quantity",
    "conditional_work",
    "price_present",
    "noisy_input",
    "cross_domain_trap",
    "professional_confirmation_expected",
    "professional_confirmation_not_expected",
}

VALID_MARKERS = set(UncertaintyMarkers.model_fields)  # 3 booleans, from the contract

# evidence_needed_nonempty is a derived predicate (list non-empty), not a schema
# field, so this set is the QC-3A vocabulary rather than something derivable.
VALID_LINE_ITEM_PROPERTIES = {"vague_or_confusing", "evidence_needed_nonempty"}

VALID_TERMSET_MODES = {"absolute", "not_in_source"}

# cross_domain_trap requires a domain-leakage guard specifically (a not_in_source
# domain termset), not merely any forbidden_terms entry — REG-002 also carries an
# absolute price_judgment guard, which must not by itself satisfy the rule.
DOMAIN_LEAKAGE_TERMSETS = {"vehicle_domain", "trade_domain"}

REQUIRED_TOP_LEVEL = {
    "case_id",
    "domain",
    "categories",
    "rationale",
    "quote_text",
    "deterministic_expectations",
    "semantic_expectations",
}
OPTIONAL_TOP_LEVEL = {"regression_origin"}

REQUIRED_SEMANTIC_KEYS = {
    "should_identify",
    "should_preserve_uncertainty",
    "must_not_invent",
    "notes",
}

REG_CASE_IDS = ("REG-001", "REG-002")

CORPUS_MIN = 24
CORPUS_MAX = 30


class CorpusError(Exception):
    """Raised when the corpus or termset file is structurally invalid.

    The message is a newline-joined list of every problem found, so a maintainer
    sees all of them at once rather than one per run.
    """


@dataclass(frozen=True)
class Termset:
    name: str
    mode: str
    fields: str
    terms: tuple[str, ...]


@dataclass(frozen=True)
class Case:
    case_id: str
    domain: str
    categories: tuple[str, ...]
    rationale: str
    quote_text: str
    must: tuple[dict, ...]
    must_not: tuple[dict, ...]
    semantic_expectations: dict
    regression_origin: str | None
    source_path: Path
    raw: dict = field(repr=False, default_factory=dict)


@dataclass(frozen=True)
class Corpus:
    cases: tuple[Case, ...]
    termsets: dict[str, Termset]

    def by_id(self, case_id: str) -> Case | None:
        for c in self.cases:
            if c.case_id == case_id:
                return c
        return None


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #

def load_termsets(path: Path | str = TERMSETS_PATH) -> dict[str, Termset]:
    """Parse termsets.json. Raises CorpusError on any structural problem."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CorpusError(f"termsets file not found: {path}")
    except json.JSONDecodeError as e:
        raise CorpusError(f"termsets file is not valid JSON: {path}: {e}")

    if not isinstance(data, dict):
        raise CorpusError("termsets.json must be a JSON object")

    errors: list[str] = []
    termsets: dict[str, Termset] = {}
    for name, spec in data.items():
        if name == "_comment":
            continue
        if not isinstance(spec, dict):
            errors.append(f"termset {name!r}: expected an object")
            continue
        local: list[str] = []
        mode = spec.get("mode")
        fields = spec.get("fields")
        terms = spec.get("terms")
        if mode not in VALID_TERMSET_MODES:
            local.append(f"mode {mode!r} not in {sorted(VALID_TERMSET_MODES)}")
        # analysis_text is the only field group the runner implements; every
        # current termset declares it. all_text is intentionally not supported.
        if fields != "analysis_text":
            local.append(f"fields {fields!r} unsupported (only 'analysis_text')")
        if not isinstance(terms, list) or not terms or not all(
            isinstance(t, str) and t.strip() for t in terms
        ):
            local.append("'terms' must be a non-empty list of non-empty strings")
        if local:
            errors.extend(f"termset {name!r}: {m}" for m in local)
            continue
        termsets[name] = Termset(name=name, mode=mode, fields=fields, terms=tuple(terms))

    if errors:
        raise CorpusError("termsets.json invalid:\n  - " + "\n  - ".join(errors))
    return termsets


def _load_case_dicts(cases_dir: Path | str = CASES_DIR) -> list[tuple[Path, Any]]:
    cases_dir = Path(cases_dir)
    out: list[tuple[Path, Any]] = []
    paths = sorted(cases_dir.glob("*.json"))
    if not paths:
        raise CorpusError(f"no case files found under {cases_dir}")
    for p in paths:
        try:
            out.append((p, json.loads(p.read_text(encoding="utf-8"))))
        except json.JSONDecodeError as e:
            out.append((p, e))
    return out


def load_corpus(
    cases_dir: Path | str = CASES_DIR,
    termsets_path: Path | str = TERMSETS_PATH,
) -> Corpus:
    """Load and permanently validate the corpus. Raises CorpusError if invalid."""
    termsets = load_termsets(termsets_path)
    loaded = _load_case_dicts(cases_dir)

    parse_errors = [
        f"{p.name}: not valid JSON: {obj}" for p, obj in loaded if isinstance(obj, json.JSONDecodeError)
    ]
    case_dicts = [(p, obj) for p, obj in loaded if not isinstance(obj, json.JSONDecodeError)]

    errors = list(parse_errors)
    errors.extend(validate_corpus([obj for _, obj in case_dicts], termsets))
    if errors:
        raise CorpusError(
            "corpus validation failed:\n  - " + "\n  - ".join(errors)
        )

    cases = tuple(_build_case(p, obj) for p, obj in case_dicts)
    return Corpus(cases=cases, termsets=termsets)


def _build_case(path: Path, obj: dict) -> Case:
    det = obj.get("deterministic_expectations", {})
    return Case(
        case_id=obj["case_id"],
        domain=obj["domain"],
        categories=tuple(obj["categories"]),
        rationale=obj["rationale"],
        quote_text=obj["quote_text"],
        must=tuple(det.get("must", [])),
        must_not=tuple(det.get("must_not", [])),
        semantic_expectations=obj["semantic_expectations"],
        regression_origin=obj.get("regression_origin"),
        source_path=path,
        raw=obj,
    )


# --------------------------------------------------------------------------- #
# Validation (pure — operates on parsed dicts, no filesystem)
# --------------------------------------------------------------------------- #

def validate_corpus(cases: list[dict], termsets: dict[str, Termset]) -> list[str]:
    """Return a list of human-readable problems. Empty list == valid.

    Pure: takes already-parsed case dicts and a termset map. ``load_corpus`` does
    the IO and turns a non-empty return into a ``CorpusError``.
    """
    errors: list[str] = []

    # ---- corpus size (QC-3A contract: 24..30 inclusive) --------------------
    n = len(cases)
    if n < CORPUS_MIN or n > CORPUS_MAX:
        errors.append(
            f"corpus size {n} outside the required range [{CORPUS_MIN}, {CORPUS_MAX}]"
        )

    seen_ids: dict[str, int] = {}
    seen_quotes: dict[str, str] = {}

    for idx, case in enumerate(cases):
        tag = f"case[{idx}]"
        if not isinstance(case, dict):
            errors.append(f"{tag}: expected a JSON object")
            continue

        cid = case.get("case_id")
        if isinstance(cid, str) and cid.strip():
            tag = cid
            seen_ids[cid] = seen_ids.get(cid, 0) + 1
        else:
            errors.append(f"{tag}: 'case_id' missing or empty")

        # ---- top-level key set -------------------------------------------
        keys = set(case.keys())
        missing = REQUIRED_TOP_LEVEL - keys
        extra = keys - REQUIRED_TOP_LEVEL - OPTIONAL_TOP_LEVEL
        if missing:
            errors.append(f"{tag}: missing top-level fields: {sorted(missing)}")
        if extra:
            errors.append(f"{tag}: unexpected top-level fields: {sorted(extra)}")

        # ---- domain -----------------------------------------------------
        if case.get("domain") not in VALID_DOMAINS:
            errors.append(
                f"{tag}: domain {case.get('domain')!r} not in {sorted(VALID_DOMAINS)}"
            )

        # ---- categories ----------------------------------------------------
        cats = case.get("categories")
        if not isinstance(cats, list) or not cats:
            errors.append(f"{tag}: 'categories' must be a non-empty list")
            cats = []
        else:
            for c in cats:
                if c not in VALID_CATEGORIES:
                    errors.append(f"{tag}: category {c!r} not in {sorted(VALID_CATEGORIES)}")

        # ---- rationale / quote_text -------------------------------------
        if not _nonempty_str(case.get("rationale")):
            errors.append(f"{tag}: 'rationale' missing or empty")
        quote = case.get("quote_text")
        if not _nonempty_str(quote):
            errors.append(f"{tag}: 'quote_text' missing or empty")
        else:
            norm = " ".join(quote.split())
            if norm in seen_quotes:
                errors.append(
                    f"{tag}: duplicate quote_text (normalized) also in {seen_quotes[norm]}"
                )
            else:
                seen_quotes[norm] = tag

        # ---- semantic_expectations ------------------------------------
        sem = case.get("semantic_expectations")
        if not isinstance(sem, dict):
            errors.append(f"{tag}: 'semantic_expectations' must be an object")
        else:
            sem_missing = REQUIRED_SEMANTIC_KEYS - set(sem.keys())
            if sem_missing:
                errors.append(f"{tag}: semantic_expectations missing keys: {sorted(sem_missing)}")

        # ---- deterministic_expectations shape ------------------------
        det = case.get("deterministic_expectations")
        must: list = []
        must_not: list = []
        if not isinstance(det, dict) or "must" not in det or "must_not" not in det:
            errors.append(f"{tag}: 'deterministic_expectations' must have 'must' and 'must_not'")
        else:
            must = det["must"] if isinstance(det["must"], list) else []
            must_not = det["must_not"] if isinstance(det["must_not"], list) else []
            if not isinstance(det["must"], list):
                errors.append(f"{tag}: deterministic_expectations.must must be a list")
            if not isinstance(det["must_not"], list):
                errors.append(f"{tag}: deterministic_expectations.must_not must be a list")

        for i, chk in enumerate(must):
            errors.extend(_validate_check(f"{tag}.must[{i}]", chk, termsets, in_must_not=False))
        for i, chk in enumerate(must_not):
            errors.extend(_validate_check(f"{tag}.must_not[{i}]", chk, termsets, in_must_not=True))

        # ---- regression_origin placement -----------------------------
        is_reg = cid in REG_CASE_IDS
        has_origin = _nonempty_str(case.get("regression_origin"))
        if is_reg and not has_origin:
            errors.append(f"{tag}: regression case must carry a non-empty 'regression_origin'")
        if not is_reg and "regression_origin" in keys:
            errors.append(f"{tag}: 'regression_origin' is only allowed on {list(REG_CASE_IDS)}")

        # ---- category -> expectation consistency --------------------
        errors.extend(_validate_category_consistency(tag, cats, must, must_not))

    # ---- cross-case invariants ------------------------------------------
    for cid, count in seen_ids.items():
        if count > 1:
            errors.append(f"case_id {cid!r} appears {count} times (must be unique)")
    for reg_id in REG_CASE_IDS:
        count = seen_ids.get(reg_id, 0)
        if count != 1:
            errors.append(f"{reg_id} must appear exactly once, found {count}")

    return errors


def _nonempty_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _validate_check(
    tag: str, chk: Any, termsets: dict[str, Termset], *, in_must_not: bool
) -> list[str]:
    if not isinstance(chk, dict):
        return [f"{tag}: check must be an object"]
    name = chk.get("check")
    keys = set(chk.keys())

    if name == "forbidden_terms":
        errs = []
        allowed = {"check", "termset"}
        extra = keys - allowed
        if extra:
            errs.append(
                f"{tag}: forbidden_terms accepts only {sorted(allowed)}; "
                f"unsupported keys {sorted(extra)} (inline terms / mode / fields are not implemented)"
            )
        ts = chk.get("termset")
        if not isinstance(ts, str) or not ts:
            errs.append(f"{tag}: forbidden_terms requires a 'termset' name")
        elif ts not in termsets:
            errs.append(f"{tag}: forbidden_terms termset {ts!r} does not resolve in termsets.json")
        return errs

    if name == "uncertainty_marker":
        errs = []
        allowed = {"check", "marker", "expected"}
        extra = keys - allowed
        if extra:
            errs.append(f"{tag}: uncertainty_marker accepts only {sorted(allowed)}; got extra {sorted(extra)}")
        if chk.get("marker") not in VALID_MARKERS:
            errs.append(
                f"{tag}: uncertainty_marker marker {chk.get('marker')!r} not in {sorted(VALID_MARKERS)}"
            )
        if not isinstance(chk.get("expected"), bool):
            errs.append(f"{tag}: uncertainty_marker 'expected' must be a boolean")
        return errs

    if name == "line_items_where":
        errs = []
        allowed = {"check", "property", "value", "min_count"}
        extra = keys - allowed
        if extra:
            errs.append(
                f"{tag}: line_items_where accepts only {sorted(allowed)}; "
                f"unsupported keys {sorted(extra)} (risk_level / max_count are not implemented)"
            )
        if chk.get("property") not in VALID_LINE_ITEM_PROPERTIES:
            errs.append(
                f"{tag}: line_items_where property {chk.get('property')!r} "
                f"not in {sorted(VALID_LINE_ITEM_PROPERTIES)}"
            )
        if not isinstance(chk.get("value"), bool):
            errs.append(f"{tag}: line_items_where 'value' must be a boolean")
        mc = chk.get("min_count")
        if not isinstance(mc, int) or isinstance(mc, bool) or mc < 0:
            errs.append(f"{tag}: line_items_where 'min_count' must be an integer >= 0")
        return errs

    return [
        f"{tag}: unknown check type {name!r} "
        f"(supported: forbidden_terms, uncertainty_marker, line_items_where)"
    ]


def _find_marker(checks: list, marker: str, expected: bool) -> bool:
    return any(
        isinstance(c, dict)
        and c.get("check") == "uncertainty_marker"
        and c.get("marker") == marker
        and c.get("expected") is expected
        for c in checks
    )


def _validate_category_consistency(
    tag: str, categories: list, must: list, must_not: list
) -> list[str]:
    errs: list[str] = []
    cats = set(categories)

    if "clean_itemized" in cats:
        if not _find_marker(must, "ambiguous_items_present", False):
            errs.append(f"{tag}: clean_itemized requires must: ambiguous_items_present == false")
        if not _find_marker(must, "missing_quote_context", False):
            errs.append(f"{tag}: clean_itemized requires must: missing_quote_context == false")

    if "professional_confirmation_expected" in cats:
        if not _find_marker(must, "needs_professional_confirmation", True):
            errs.append(
                f"{tag}: professional_confirmation_expected requires must: "
                "needs_professional_confirmation == true"
            )

    if "professional_confirmation_not_expected" in cats:
        if not _find_marker(must, "needs_professional_confirmation", False):
            errs.append(
                f"{tag}: professional_confirmation_not_expected requires must: "
                "needs_professional_confirmation == false"
            )

    if "cross_domain_trap" in cats:
        has_leakage_guard = any(
            isinstance(c, dict)
            and c.get("check") == "forbidden_terms"
            and c.get("termset") in DOMAIN_LEAKAGE_TERMSETS
            for c in must_not
        )
        if not has_leakage_guard:
            errs.append(
                f"{tag}: cross_domain_trap requires must_not to contain at least one "
                f"forbidden_terms guard using a domain-leakage termset {sorted(DOMAIN_LEAKAGE_TERMSETS)}"
            )

    return errs

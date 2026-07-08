# Examples

Real input/output pairs captured from QuoteCheck's Demo-mode `/analyze` endpoint
(`QUOTECHECK_USE_OPENAI=0`, the default, zero-cost, no API key). Every `.json` file
here was produced by an actual local request — none are hand-written.

**Demo mode is a deterministic keyword-based stub** (`backend/core/stub_analyzer.py`),
not an LLM. It recognizes a small, fixed set of keywords per domain (vehicle: brake/
tyre; AC/appliance: air conditioning/compressor/refrigerant/hvac/appliance; home
maintenance: plumbing/electrical/contractor/handyman/renovation; plus a generic
vague-charge catch-all) and falls back to a single "needs clarification" item when
none match. These are **sample reports demonstrating the product's shape and
behavior, not accuracy claims** — Demo mode does not understand a quote the way an
LLM or a human would. OpenAI mode (opt-in, real model calls) is documented in the
root [`README.md`](../README.md#demo-mode-vs-openai-mode).

**No price benchmarking or market evidence is implemented or claimed anywhere in
these outputs.** Every response's `disclaimer` and `overall_summary` say so
explicitly.

## Original sample

- [`sample_quote.txt`](sample_quote.txt) / [`sample_output.json`](sample_output.json)
  — the frontend's built-in pre-filled sample (from TASK-007). A vehicle quote that
  hits the brake, tyre, and generic-charge paths in one input.

## Sample pack (TASK-008)

| Input | Output | Demonstrates |
|---|---|---|
| [`quote_vehicle_service.txt`](quote_vehicle_service.txt) | [`outputs/vehicle_service.json`](outputs/vehicle_service.json) | A fuller, multi-line itemized vehicle estimate (brake + tyre + a bundled shop-supplies charge) — 3 line items, safety-critical framing, vague-charge flag on the bundled fee. |
| [`quote_ac_repair.txt`](quote_ac_repair.txt) | [`outputs/ac_repair.json`](outputs/ac_repair.json) | AC/appliance repair (compressor + refrigerant) — domain-appropriate explanation and evidence requests (diagnostic report, unit warranty status, refrigerant type/quantity), no vehicle language. |
| [`quote_home_maintenance.txt`](quote_home_maintenance.txt) | [`outputs/home_maintenance.json`](outputs/home_maintenance.json) | A home contractor/maintenance visit (plumbing + electrical + handyman) — domain-appropriate explanation and evidence requests (scope of work, materials list, labor-hours estimate). |
| [`quote_parts_labour_misc.txt`](quote_parts_labour_misc.txt) | [`outputs/parts_labour_misc.json`](outputs/parts_labour_misc.json) | A parts quote built around vague "labour"/"miscellaneous"/"other charges" wording — the generic vague-charge catch-all fires, `vague_or_confusing: true`, evidence request asks for an itemized breakdown. |
| [`quote_vague_missing_details.txt`](quote_vague_missing_details.txt) | [`outputs/vague_missing_details.json`](outputs/vague_missing_details.json) | A genuinely vague quote with no part names, measurements, or recognizable keywords at all — falls through to the stub's low-confidence "needs clarification" fallback, showing the uncertainty-handling path honestly rather than guessing. |

Every output's `metadata.model` is `quotecheck-demo-analyzer`, confirming it came
from Demo mode, not an OpenAI call. `request_id` / `created_at` / `latency_ms` will
differ on any fresh run — that's expected, not a discrepancy.

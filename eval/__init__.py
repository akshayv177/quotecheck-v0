"""QuoteCheck evaluation harness (QC-3B).

This package holds the executable deterministic eval / regression runner for the
QC-3A case corpus. It implements Layer A only — mechanically checkable invariants.
Layer B (faithfulness, unsupported inference, usefulness, calibration) stays human
and is scored against ``eval/rubric.md``. Passing every deterministic invariant in
here establishes nothing about semantic correctness.
"""

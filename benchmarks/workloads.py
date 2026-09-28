"""Fixed, deterministic benchmark workloads (SCALE-001).

The exact text is committed here so later scalability tickets can replay the
same inputs. Each workload carries a stable id; its sha256 and length are
recorded in every results file so drift is detectable.

These are benchmark fixtures only; they do not change QuoteCheck semantics.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from backend.core.schema import MAX_QUOTE_TEXT_CHARS


@dataclass(frozen=True)
class Workload:
    workload_id: str
    description: str
    text: str

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def describe(self) -> dict:
        return {
            "workload_id": self.workload_id,
            "description": self.description,
            "chars": self.chars,
            "sha256": self.sha256,
        }


_SHORT = "AC service visit. Gas top-up and general checkup. Total Rs 2,800. Misc charges extra."

# A representative pasted quote: header, several itemised lines with a mix of
# clear, vague, and conditional items, a total, and approval language.
_NORMAL = """CoolAir Services - Quotation #QA-2231
Customer site: 2nd floor office, split AC units x3

1. Deep cleaning of indoor and outdoor units (3 units) - Rs 2,400
2. Refrigerant gas top-up, unit 2 (pressure found low) - Rs 3,200
3. Compressor capacitor replacement, unit 1 - Rs 1,450
4. PCB inspection and repair if required - to be confirmed after testing
5. Drain pipe re-routing and insulation - Rs 900
6. Service / handling / misc charges - Rs 750

Labour included. Parts warranty 90 days on replaced parts only.
Total estimate: Rs 8,700 + applicable taxes (PCB work extra if needed).
Please approve so we can schedule the technician this week."""

_NEAR_MAX_HEADER = (
    "CoolAir Services - Annual Maintenance Quote #QA-9004\n"
    "Scope: preventive maintenance and repairs, split AC units across 3 floors\n\n"
)
_NEAR_MAX_FOOTER = (
    "\nAll prices subject to site inspection. Misc / sundry charges billed at actuals.\n"
    "Total to be confirmed after survey. Please approve to proceed."
)
_NEAR_MAX_TARGET_CHARS = 11_500


def _near_max_text() -> str:
    """Deterministic ~11.5k-char single-trade (HVAC) quote of numbered line items.

    Deliberately one trade: mixing vehicle/HVAC/plumbing/electrical vocabulary
    makes the current Demo analyzer exceed the schema's verification-question
    cap and return HTTP 500 (a pre-existing defect recorded in the SCALE-001
    review bundle). This fixture measures length scaling, not that defect.
    """
    items = [
        "AC unit {n}: deep cleaning of indoor and outdoor coils - Rs {p}",
        "AC unit {n}: refrigerant gas top-up after pressure check - Rs {p}",
        "AC unit {n}: fan motor capacitor replacement - Rs {p}",
        "AC unit {n}: drain pipe flushing and insulation repair - Rs {p}",
        "AC unit {n}: service / handling / misc charges - Rs {p}",
        "AC unit {n}: PCB repair if required - price after diagnosis",
    ]
    body = []
    n = 1
    length = len(_NEAR_MAX_HEADER) + len(_NEAR_MAX_FOOTER)
    while True:
        line = f"{n}. " + items[(n - 1) % len(items)].format(n=n, p=250 + (n * 37) % 4000) + "\n"
        if length + len(line) > _NEAR_MAX_TARGET_CHARS:
            break
        body.append(line)
        length += len(line)
        n += 1
    return _NEAR_MAX_HEADER + "".join(body) + _NEAR_MAX_FOOTER


WORKLOADS = {
    w.workload_id: w
    for w in (
        Workload("short", "one-line informal quote", _SHORT),
        Workload("normal", "representative itemised multi-line quote", _NORMAL),
        Workload("near_max", "deterministic near-maximum-length itemised quote", _near_max_text()),
    )
}

assert all(0 < w.chars <= MAX_QUOTE_TEXT_CHARS for w in WORKLOADS.values())

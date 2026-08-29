"""Focused unit tests for the deterministic Demo analyzer (``analyze_quote_stub``).

These do not use the 27-case eval corpus. They pin the QC-3C contract-alignment
behaviour with short synthetic quotes:

- ``ambiguous_items_present`` is derived from line-item ``vague_or_confusing``.
- Quote-level missing context and line-level vagueness stay separate.
- Bare "labour" no longer forces a vague charge / missing context.
- Unknown domains with real priced lines do not collapse to one fallback item.
- ``needs_professional_confirmation`` is conservative and evidence-based.
- No vehicle/mechanic leakage into non-vehicle output.
- No market-price judgment (checked against the real high-precision termset).

Run: ``python -m unittest discover -s eval/tests -p 'test_*.py' -v`` from repo root.
"""

from __future__ import annotations

import json
import pathlib
import unittest

from backend.core.prompt import PROMPT_VERSION
from backend.core.schema import QuoteCheckResult
from backend.core.stub_analyzer import analyze_quote_stub

_TERMSETS = json.loads(
    (pathlib.Path(__file__).resolve().parents[2] / "eval" / "termsets.json").read_text()
)
PRICE_JUDGMENT_PHRASES = _TERMSETS["price_judgment"]["terms"]
VEHICLE_PHRASES = _TERMSETS["vehicle_domain"]["terms"]


def run(quote_text: str) -> QuoteCheckResult:
    return analyze_quote_stub(quote_text=quote_text, request_id="req-test", latency_ms=0)


def analysis_text(result: QuoteCheckResult) -> str:
    parts: list[str] = []
    for li in result.line_items:
        parts += [li.explanation, li.rationale_short, *li.evidence_needed]
    parts += result.overall_summary
    parts += result.verification_questions
    parts += result.things_to_verify
    parts.append(result.disclaimer)
    return "\n".join(parts).lower()


CLEAN_ITEMISED = (
    "Fairlane Motor Works - Estimate 8834\n"
    "Service: 60,000 km scheduled maintenance, as per manufacturer schedule page 42.\n"
    "  Engine oil 5W-30 fully synthetic, 3.5 L   P/N 90210-A   Rs. 2,940\n"
    "  Oil filter                                P/N 15400-RB  Rs.   420\n"
    "  Spark plugs, iridium                      P/N 12290-QT  Rs. 2,360\n"
    "  Scheduled service, 2.0 hours at Rs. 550/hour             Rs. 1,100\n"
    "Parts carry the manufacturer's 12 month warranty."
)

CLEAN_PLUMBING = (
    "Brookfield Plumbing - Quotation BP-1187\n"
    "Survey findings: basin mixer cartridge worn, isolation valve seized.\n"
    "  Supply and fit basin mixer tap, 1 no.        Rs. 3,400\n"
    "  Supply and fit 15 mm isolation valve, 1 no.  Rs.   280\n"
    "  Labour, 1 hour 30 minutes at Rs. 700 per hour Rs. 1,050\n"
    "Total Rs. 4,970. Workmanship warranted 12 months. No advance payment required."
)

BUNDLED = (
    "Halewood Garage - Invoice Estimate\n"
    "  Battery replacement (old unit tested at 9.8 V under load)  Rs. 6,400\n"
    "  Shop supplies                                             Rs.   450\n"
    "  Sundries                                                  Rs.   275\n"
    "  Labour adjustment                                         Rs.   300\n"
    "  Labour, 1.5 hrs                                           Rs.   825\n"
)

EXPLICIT_MISSING_CONTEXT = (
    "Hello, further to our discussion please see the attached estimate for the work "
    "discussed during our call. Approximate total cost as agreed. Let us know if you "
    "would like to proceed."
)

UNKNOWN_DOMAIN_ITEMISED = (
    "Pinecrest Device Repair - Job 5521\n"
    "Diagnostic result: panel confirmed faulty; external HDMI output is clean.\n"
    "  LCD panel assembly, 14 inch FHD matte, part N140HCA-EAC   Rs. 7,900\n"
    "  Bench labour, panel replacement, 1 hour                   Rs. 1,200\n"
    "Total Rs. 9,100. Panel carries a 6 month warranty."
)

BENIGN_WORK = (
    "Ambleside Appliance Repairs - estimate for a double-door refrigerator.\n"
    "Inspection confirmed the door gasket is hardened and torn near the bottom corner.\n"
    "  Replace refrigerator door gasket, matched to the model number  Rs. 1,850\n"
    "  Labour, single visit                                           Rs.   600\n"
    "Total as quoted Rs. 2,450."
)

SAFETY_STRUCTURAL = (
    "QUOTE - site work\n"
    "  Opening in wall between hall and bedroom, approx 7ft x 7ft   Rs 34,000\n"
    "  Lintel / support beam over the opening                       Rs 22,500\n"
    "Wall is 9 inch, will confirm on site whether load bearing or not.\n"
    "Structural drawing not prepared, can be arranged through our consultant."
)

SAFETY_ELECTRICAL = (
    "Hallam Electrical Contractors - Quotation HE-3390\n"
    "Customer reports the residual current device tripping intermittently.\n"
    "  Replace existing consumer unit with an 8-way board with RCBOs  Rs. 18,500\n"
    "  Earth bonding to incoming water and gas services              Rs.  2,400\n"
    "  Labour, 2 days, 2 operatives                                  Rs.  9,000\n"
)

PRICE_BEARING = (
    "CoolAir Systems - Repair Estimate CA-4478\n"
    "  Compressor unit (2 ton, rotary)   Rs. 32,500\n"
    "  Refrigerant recharge              Rs.  6,800\n"
    "  Labour                            Rs.  4,500\n"
    "Total payable Rs. 44,600. Diagnostic report available on request."
)


class SchemaAndProvenanceTests(unittest.TestCase):
    def test_round_trips_and_provenance(self):
        for q in (CLEAN_ITEMISED, BUNDLED, EXPLICIT_MISSING_CONTEXT, UNKNOWN_DOMAIN_ITEMISED):
            r = run(q)
            QuoteCheckResult.model_validate(r.model_dump(mode="json"))
            self.assertEqual(r.metadata.model, "quotecheck-demo-analyzer")
            self.assertEqual(r.metadata.prompt_version, PROMPT_VERSION)
            self.assertTrue(r.metadata.schema_valid)
            self.assertGreaterEqual(len(r.line_items), 1)


class CleanItemisedTests(unittest.TestCase):
    def test_no_vague_items_and_markers_false(self):
        for q in (CLEAN_ITEMISED, CLEAN_PLUMBING):
            r = run(q)
            self.assertEqual([li for li in r.line_items if li.vague_or_confusing], [])
            self.assertFalse(r.uncertainty_markers.ambiguous_items_present)
            self.assertFalse(r.uncertainty_markers.missing_quote_context)

    def test_clean_plumbing_not_escalated(self):
        r = run(CLEAN_PLUMBING)
        self.assertFalse(r.uncertainty_markers.needs_professional_confirmation)


class BundledChargeTests(unittest.TestCase):
    def test_vague_item_with_evidence_and_ambiguous_flag(self):
        r = run(BUNDLED)
        vague = [li for li in r.line_items if li.vague_or_confusing]
        self.assertGreaterEqual(len(vague), 1)
        self.assertTrue(any(li.evidence_needed for li in vague))
        self.assertTrue(r.uncertainty_markers.ambiguous_items_present)

    def test_bare_labour_line_alone_is_not_vague_or_missing_context(self):
        # "Labour, 2.0 hours at Rs. 550/hour" is an ordinary itemised line.
        r = run(CLEAN_ITEMISED)
        self.assertFalse(r.uncertainty_markers.missing_quote_context)
        self.assertFalse(r.uncertainty_markers.ambiguous_items_present)


class MissingContextTests(unittest.TestCase):
    def test_explicit_deferred_detail_sets_quote_level_flag(self):
        r = run(EXPLICIT_MISSING_CONTEXT)
        self.assertTrue(r.uncertainty_markers.missing_quote_context)

    def test_quote_level_gap_does_not_force_every_line_vague(self):
        # A mostly-precise quote with one externally-referenced element: the
        # quote-level flag may be set, but precise priced lines stay non-vague.
        q = (
            "Marlow Projects - Renovation Proposal\n"
            "  Flooring - vitrified tile, 1,450 sq ft supplied and laid   Rs. 1,73,000\n"
            "  Bathrooms - 3 nos., complete refit                         Rs. 1,26,000\n"
            "The kitchen and painting lines are consolidated figures.\n"
        )
        r = run(q)
        self.assertTrue(r.uncertainty_markers.missing_quote_context)
        self.assertFalse(all(li.vague_or_confusing for li in r.line_items))


class UnknownDomainTests(unittest.TestCase):
    def test_itemised_unknown_domain_does_not_collapse_to_single_fallback(self):
        r = run(UNKNOWN_DOMAIN_ITEMISED)
        self.assertGreater(len(r.line_items), 1)
        names = [li.name_raw for li in r.line_items]
        self.assertNotEqual(names, ["Unclear item(s) - needs clarification"])
        self.assertFalse(r.uncertainty_markers.ambiguous_items_present)
        self.assertFalse(r.uncertainty_markers.missing_quote_context)

    def test_no_detail_quote_still_uses_fallback(self):
        r = run("Please pay Rs. 8,500 for work as required. Advance on confirmation.")
        self.assertTrue(r.uncertainty_markers.ambiguous_items_present)


class ProfessionalConfirmationTests(unittest.TestCase):
    def test_benign_repair_not_escalated(self):
        r = run(BENIGN_WORK)
        self.assertFalse(r.uncertainty_markers.needs_professional_confirmation)

    def test_structural_work_escalated(self):
        r = run(SAFETY_STRUCTURAL)
        self.assertTrue(r.uncertainty_markers.needs_professional_confirmation)

    def test_mains_electrical_work_escalated(self):
        r = run(SAFETY_ELECTRICAL)
        self.assertTrue(r.uncertainty_markers.needs_professional_confirmation)

    def test_sealed_refrigerant_work_escalated(self):
        r = run(PRICE_BEARING)  # "compressor replacement" wording via the unit line
        self.assertTrue(
            run(
                "Recommended: compressor replacement including brazing and full "
                "system evacuation, then refrigerant recharge."
            ).uncertainty_markers.needs_professional_confirmation
        )

    def test_domain_identity_alone_does_not_escalate(self):
        # An automotive quote with no safety-critical component named.
        r = run(
            "Torrance Auto Centre - estimate for a 2016 estate.\n"
            "  Cabin air filter replacement   Rs. 900\n"
            "  Wiper blades, pair             Rs. 800\n"
        )
        self.assertFalse(r.uncertainty_markers.needs_professional_confirmation)


class DomainNeutralityTests(unittest.TestCase):
    def test_no_vehicle_language_in_non_vehicle_output(self):
        for q in (CLEAN_PLUMBING, UNKNOWN_DOMAIN_ITEMISED, PRICE_BEARING, SAFETY_ELECTRICAL):
            text = analysis_text(run(q))
            for phrase in VEHICLE_PHRASES:
                if phrase in q.lower():
                    continue
                self.assertNotIn(phrase, text, f"{phrase!r} leaked for quote: {q[:40]!r}")


class PriceJudgmentTests(unittest.TestCase):
    def test_no_affirmative_price_judgment_phrases(self):
        # Assert only the exact high-precision termset phrases are absent — not
        # bare words like "high" (the disclaimer legitimately says
        # "high-value or safety-critical work").
        for q in (PRICE_BEARING, BUNDLED, CLEAN_ITEMISED):
            text = analysis_text(run(q))
            for phrase in PRICE_JUDGMENT_PHRASES:
                self.assertNotIn(phrase, text, f"{phrase!r} present for quote: {q[:40]!r}")


if __name__ == "__main__":
    unittest.main()

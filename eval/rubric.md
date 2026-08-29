# QuoteCheck semantic rubric (Layer B)

For the qualities that deterministic checks cannot establish honestly. A human reads one
`/analyze` response against its case file in [`cases/`](cases/) and scores six
dimensions.

This rubric is not implemented in code, and should not be. Everything here requires
reading the quote and the output and judging them together.

See [`README.md`](README.md) for the Layer A / Layer B split and the deterministic
vocabulary.

---

## Scale

Three levels. Deliberately coarse — a finer scale would imply a precision a single
reviewer does not have.

| Score | Meaning |
|---|---|
| **2 — pass** | A careful reviewer has no objection. The output is grounded, calibrated, and useful for this quote. |
| **1 — mixed / needs review** | Defensible but flawed: imprecise, overreaching in a minor way, unhelpfully generic, or partially unsupported. Not misleading enough to call a failure, not clean enough to pass. |
| **0 — fail** | A clear violation. A user acting on this output could be misled about their quote. |

## Gates

Two dimensions are gates. **A score of 0 on Faithfulness or on Unsupported inference
fails the case outright**, regardless of the other four scores. Fluent, actionable,
well-structured output built on something the quote never said is worse than unhelpful
output, and the rubric must not let four good scores average that away.

## Reporting

- Report **per-dimension distributions** (how many 0s, 1s, 2s) and the list of every case
  scoring 0, with the reviewer's one-line reason.
- Report gate failures separately and by name.
- State the sample size next to any aggregate. It is 27.
- **Do not average the six dimensions into a single number.** Do not report a mean to a
  decimal place, do not compute a percentage that mixes dimensions, and do not present
  any of it as a benchmark score. The scale is ordinal and the sample is a coverage
  instrument, not a statistical sample.
- Layer A and Layer B results are reported separately and never combined into one
  headline number.

---

## Dimension 1 — Faithfulness *(gate)*

**Does the output stay grounded in the submitted quote?**

Every line item, amount, part, symptom, and scope claim in the output should be traceable
to the quote text. Reordering, summarizing, and plain-language restatement are fine.
Silently adding specifics is not.

| | |
|---|---|
| **2** | Every claim traces to the quote. Restatements preserve meaning. Nothing is quietly added or dropped. |
| **1** | Broadly faithful, but one item is stretched — a scope described more definitely than the quote states it, or a real line item omitted from the report. |
| **0** | The output describes work, parts, symptoms, or amounts the quote does not contain, or contradicts what it does contain. |

## Dimension 2 — Unsupported inference *(gate)*

**Did it invent a fault, part, work, evidence, vendor intent, or price judgment?**

This is where the two historical regressions live. It covers four failures:

- **Invented diagnosis** — asserting a cause the quote never established ("the compressor
  has failed" when the quote says only "not cooling").
- **Invented vendor intent** — asserting the vendor is upselling, padding, or acting in
  bad faith. QuoteCheck flags what is unclear; it does not read motives.
- **Price judgment without benchmarking** — any claim that an amount is high, low, fair,
  or a good deal. QuoteCheck has no price data. Saying the *basis* for a charge is
  missing is correct and expected; saying the *amount* is wrong is the regression.
- **Cross-domain import** — vocabulary, evidence requests, or disclaimers borrowed from a
  domain the quote is not about.

Score this dimension after the deterministic `price_judgment` and leakage checks, not
instead of them: those catch blatant phrasings only, and hedged or paraphrased inference
is exactly what is left for a human here.

| | |
|---|---|
| **2** | No invented fault, part, evidence, motive, or price judgment. Domain vocabulary matches the quote's actual domain. |
| **1** | One borderline inference — a probable cause stated a little too confidently, or a mild implication about cost or vendor behaviour, without an outright claim. |
| **0** | An invented fault/part/measurement, an assertion about vendor motive, any market-fairness or magnitude claim about price, or terminology imported from an unrelated domain. |

## Dimension 3 — Uncertainty calibration

**Does uncertain source language stay uncertain?**

Quotes hedge constantly: "if required", "may need replacement", "subject to inspection",
"estimate may vary", "additional work after opening". Those hedges are information, and
they must survive into the output. The failure runs both ways — a conditional line
reported as settled work, or a fully specified line hedged into fog.

Also covers the three uncertainty markers: are `ambiguous_items_present`,
`missing_quote_context`, and `needs_professional_confirmation` set the way this quote
actually warrants, not reflexively?

| | |
|---|---|
| **2** | Conditional work is still conditional. Definite work is not hedged. Confidence values and markers are consistent with what the quote supports. |
| **1** | One conditional item reads more settled than the quote states, or one clear item is hedged without cause, or a marker is set without much basis. |
| **0** | Conditional work is presented as decided, missing information is filled in with a confident guess, or the markers contradict the quote (a complete quote flagged as missing context, or a bare one-line quote flagged as complete). |

## Dimension 4 — Explanation quality

**Are line-item explanations understandable without claiming more than the quote
supports?**

`explanation` is the product's primary field: what the item is and why a vendor might
recommend it, for a non-expert. It fails by being unreadable, by being empty
boilerplate, or by buying readability with invented certainty.

| | |
|---|---|
| **2** | A non-expert learns what the item is and why it might be recommended. Plain language, no jargon left unexplained, no overclaiming. |
| **1** | Correct but thin or generic — restates the line-item name, or explains at a level that leaves the reader no better informed. |
| **0** | Wrong, incomprehensible, empty, or readable only because it asserts things the quote does not support. |

## Dimension 5 — Actionability

**Are evidence requests and vendor questions useful?**

`verification_questions` should be sendable to the vendor as written. `things_to_verify`
should name real gaps. `evidence_needed` should name evidence that exists and would
change the decision. The common failure is generic boilerplate that fits any quote and
therefore helps with none.

| | |
|---|---|
| **2** | Questions are specific to this quote and sendable as written. Evidence requested is obtainable and decision-relevant. |
| **1** | Reasonable but generic — would fit almost any quote in this domain, or asks for something the quote already states. |
| **0** | Useless, unanswerable, irrelevant to the quote, or asks for evidence that could not exist for this kind of work. |

## Dimension 6 — Professional-boundary discipline

**Does it avoid replacing a qualified professional or making safety determinations it
cannot support?**

QuoteCheck helps a user interrogate a quote. It does not decide what is safe, does not
authorize skipping work, and does not substitute for inspection. The disclaimer must be
present and must not name a trade the quote has nothing to do with.

The mirror failure matters as much: escalating every benign quote to "consult a
professional" is not caution, it is noise that erodes the signal on the cases that need
it.

| | |
|---|---|
| **2** | Stays inside the boundary. Professional confirmation is recommended where the work is genuinely technical or safety-sensitive, and not reflexively elsewhere. Disclaimer present and domain-appropriate. |
| **1** | Boundary held, but escalation is reflexive or the disclaimer is generic to the point of being ignorable. |
| **0** | Makes a safety determination ("this is safe to defer", "this is not urgent"), tells the user to skip safety-relevant work, names an unrelated trade, or omits the disclaimer. |

---

## Review procedure

1. Read `quote_text` from the case file **before** reading the output. Note what the
   quote does and does not state.
2. Read the response.
3. Score dimensions 1–6. Record a one-line reason for every 0 and every 1.
4. Check the case's `semantic_expectations` — `should_identify`,
   `should_preserve_uncertainty`, `must_not_invent`, `notes`. These are anchors, not a
   checklist: an output that finds a real issue the case did not anticipate is not
   thereby wrong.
5. If either gate scored 0, mark the case failed and say which gate.

Reviewer notes belong with the scores. A 0 without a reason is not a finding.

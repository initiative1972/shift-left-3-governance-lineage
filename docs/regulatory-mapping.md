# Regulatory mapping — classification, lineage & auditable evidence

> General information only. **Not compliance or legal advice.** Verify all
> regulatory facts against [apra.gov.au](https://www.apra.gov.au). Personal
> portfolio project, public sources only, synthetic data only.

This capstone project fuses data engineering with governance: it turns ODCS
classification + OpenLineage into **continuous, automated compliance evidence**.

## Status of the standards (verified)

- **CPS 234 Information Security** — in force since 1 July 2019. Requires, among
  other things, classification of information assets by criticality and
  sensitivity, and systematic testing/assurance of controls.
- **CPS 230 Operational Risk Management** — fully in force (commenced 1 July 2025;
  transition ended 1 July 2026); emphasis on *evidence of effective
  implementation*.

## How this project evidences the expectations

| Expectation (paraphrased) | How this project evidences it |
|---|---|
| **Classify information assets** by sensitivity/criticality (CPS 234) | ODCS contracts declare `classification` + sensitivity per field; the report compiles the register automatically. |
| **Know where sensitive data flows** | OpenLineage column lineage traces each PII field across datasets; the report shows actual propagation, not a diagram someone drew. |
| **Systematic, independent control testing** → continuous assurance (CPS 234) | The report is regenerated every run; `--strict` turns "no undeclared PII in a mart" into an enforced CI gate. |
| **Evidence of effective implementation**, not assertion (CPS 230) | Every job run emits timestamped lineage; the report is a durable, reproducible artefact an auditor can inspect. |
| Detect **control failures** (misclassification) | The engine flags PII that reaches a dataset without being classified there — a gap a manual review routinely misses. |

## Connection to the wider portfolio

- **"Prove It"** (APRA series) — evidence over assertion. This is that thesis in code.
- **"Trust by Design"** (Responsible AI) — lineage + classification *is* the trust
  layer; the ODCS v3.2.0 AI-usage fields bridge directly to responsible-AI governance.
- **Projects 1 & 2** — reuses the ODCS contracts (Project 1) and the CI discipline
  (Project 2).

## What this does *not* claim

A small, synthetic demonstration of governance *mechanics* — not a compliance
programme, not a data catalogue, and not advice. It shows one concrete way to
produce the classification-and-lineage evidence APRA's framework expects.

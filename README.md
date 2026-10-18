# shift-left-3-governance-lineage
# Governance & Lineage Engine

> A pipeline that doesn't just move data — it emits the classification and lineage evidence an auditor would ask for, automatically. And it catches PII that nobody tagged.

[![compliance](https://initiative1972/shift-left-3-governance-lineage/actions/workflows/compliance.yml/badge.svg)](../../actions/workflows/compliance.yml)

Project 3 — the capstone — of a shift-left data-engineering portfolio. It fuses engineering with governance: **ODCS contracts** (what's classified as what) + **OpenLineage** (who touched what, and how data flows) are merged into an **automated compliance evidence report** — and the engine **detects undeclared PII** by following column-level lineage.

Runs end-to-end locally in minutes on **DuckDB** — no cloud account. Marquez (for the visual lineage graph) is optional.

---

## The idea in one picture

```
ODCS contracts ──────────────┐   (classification: PII, sensitivity, AI-usage)
  classification + semantics  │
                              ▼
pipeline (DuckDB) ──▶ OpenLineage events ──▶ lineage/events.jsonl ──▶ Marquez UI (optional)
  raw → stg → dim/fct → 360     (schema + column lineage)                │
                              │                                          │
                              ▼                                          ▼
                     ┌──────────────────────────────────────────────────────┐
                     │   compliance report generator                        │
                     │   merges "what's classified" + "where it flows"       │
                     │   → register · propagation map · GOVERNANCE GAPS       │
                     └──────────────────────────────────────────────────────┘
```

## What makes this different

Most lineage demos draw a pretty graph. This one **produces evidence and finds problems**:

- **CPS 234 classification register** — compiled automatically from the contracts.
- **PII propagation map** — where each classified field *actually* flows, from column-level lineage (not a hand-drawn diagram).
- **Governance-gap detection (the headline)** — the pipeline carries `email` and `full_name` into the `customer_360` mart, where the contract **forgot to classify them**. The engine flags it **HIGH**, tracing it back to `dim_customer`. A manual review misses this; lineage doesn't.
- **A CI gate** — `--strict` mode makes "no undeclared PII may reach a mart" an enforced, evidenced rule.
- **AI-usage context** — ODCS v3.2.0 fields declare how AI/agents may use `customer_360`, bridging to responsible-AI governance.

## Quickstart (runs locally in ~2 minutes, no cloud account)

```bash
make setup
make demo      # run the pipeline; emit OpenLineage events to lineage/events.jsonl
make report    # merge contracts + lineage → reports/compliance-report.md (+ .html)
```

Open `reports/compliance-report.md`. Full walkthrough of what to look for:
[`scenarios/01-pii-lineage-evidence.md`](scenarios/01-pii-lineage-evidence.md).

Enforce it as a gate:
```bash
make report-strict   # exits non-zero while the deliberate PII gap exists
```

See the visual lineage graph (optional):
```bash
make marquez-up
MARQUEZ_URL=http://localhost:5000 make demo
# open http://localhost:3000
```

## The money shot

![governance gap detected](docs/governance-gap.png)

> *(Add the capture once you've run it: the **Governance Gaps** table flagging
> `customer_360.email` as undeclared PII, plus the Marquez graph of `email`
> flowing raw → stg → dim → 360. This is the whole pitch: continuous automated
> evidence, and a control failure caught by the machine.)*

## The data model

```
raw_customers ─▶ stg_customers ─▶ dim_customer ─┐
                                                 ├─▶ customer_360   (PII lands here)
raw_accounts ─────▶ stg_accounts ─┐              │
raw_transactions ─▶ stg_transactions ─▶ fct_transactions ─┘
```

- `dim_customer` is the **governed master** — `email`, `dob`, `full_name`, and `tax_file_number` are classified here (`tax_file_number` = PII / Critical / restricted).
- `tax_file_number` is **dropped** before `customer_360` — the report proves it never reaches the mart.
- `email` / `full_name` **do** reach `customer_360` — and the report proves the mart's contract failed to classify them.

All data is **synthetic** (`seeds/`), including fake names, emails and TFNs.

## Engineering decisions & trade-offs

- **Explicit OpenLineage 2.0.2 events, not only the client library.** The emitter
  builds spec-compliant event JSON and writes it to `lineage/events.jsonl` (and
  POSTs to Marquez if `MARQUEZ_URL` is set). For a *governance* project this is a
  feature: the evidence is plain, inspectable JSON, and report generation has zero
  coupling to any client version. The official `openlineage-python` client is a
  drop-in alternative (commented in `requirements.txt`).
- **Classification propagation over *carrying* transforms only.** PII is
  propagated along `IDENTITY`/`DIRECT` column edges but **not** through
  `AGGREGATION` — so `total_spend` (a sum of `amount`) is correctly *not* treated
  as PII, while `email` copied forward *is*. The nuance is what makes the gap
  detection trustworthy.
- **Standalone runner + Airflow DAG, same emitter.** `make demo` runs a plain
  Python pipeline for instant reproducibility; `airflow/dags/` has the
  orchestration-grade variant using the identical lineage emitter, so the evidence
  is the same in both modes.
- **DuckDB, local.** The patterns are warehouse-agnostic; DuckDB keeps it runnable
  anywhere in minutes.

## What's simplified (honest scope)

- Column lineage is **declared** in `pipeline/transforms.py` rather than parsed
  from SQL. In production you'd derive it (e.g. via the OpenLineage dbt/SQL
  integrations); declaring it keeps the mapping explicit and auditable for a demo.
- Small synthetic dataset; a handful of jobs — enough to show the mechanism, not a
  production warehouse.
- The included `docker-compose.yml` for Marquez is a convenience; the canonical
  setup is Marquez's own `./docker/up.sh`.

## Regulatory mapping

Maps to **CPS 234** (information-asset classification + systematic control
assurance → continuous automated evidence) and **CPS 230** (evidence of effective
implementation). See [`docs/regulatory-mapping.md`](docs/regulatory-mapping.md).
*Not compliance advice.*

## Tech

- **Contracts:** ODCS v3.2.0 (classification + AI-usage context)
- **Lineage:** OpenLineage 2.0.2 events → Marquez 0.54.x (optional UI)
- **Engine:** DuckDB (local, zero-config)
- **Orchestration:** standalone Python runner + Apache Airflow DAG variant
- **Report:** Python (stdlib + PyYAML) → Markdown + HTML
- **CI:** GitHub Actions (pipeline + report as a build artefact)

## License

MIT — see [LICENSE](LICENSE).

# Scenario — "show me the lineage of this PII field, and prove nobody mishandled it"

**Claim being demonstrated:** *"A pipeline that doesn't just move data — it emits the classification and lineage evidence an auditor would ask for, automatically — and flags PII that nobody tagged."*

## Steps to reproduce

```bash
make setup
make demo      # runs the pipeline, emits OpenLineage events
make report    # merges contracts + lineage into the evidence report
```

Open `reports/compliance-report.md` (or `.html`).

## What to look for (the money shots)

### 1. The classification register (CPS 234)
Section 1 lists every classified field, its sensitivity, and the contract it came
from — `tax_file_number` shows as **PII / Critical / restricted**.

### 2. PII propagation
Section 2 traces where each classified field actually flows. You'll see:

```
dim_customer.email (PII, sensitivity High) flows to: customer_360, dim_customer, stg_customers, raw_customers
tax_file_number (PII, Critical) flows to: dim_customer, stg_customers, raw_customers
```

Note that `tax_file_number` does **not** reach `customer_360` — it's dropped at
the mart boundary. `email` **does**. That difference is computed from column
lineage, not guessed.

### 3. The governance gap (the headline)
Section 3 flags a **HIGH** gap:

```
| HIGH | customer_360 | email     | dim_customer.email     | Field carries PII (via lineage) but is NOT classified in its contract. |
| HIGH | customer_360 | full_name | dim_customer.full_name | Field carries PII (via lineage) but is NOT classified in its contract. |
```

An analyst built `customer_360` and forgot to classify the PII they carried
forward. The engine caught it — by following lineage, not by anyone remembering.
This is the difference between *point-in-time manual audit* and *continuous
automated evidence*.

### 4. Use it as a CI gate
```bash
make report-strict   # exits non-zero because HIGH gaps exist
```
Wire this into CI and "no undeclared PII may reach a mart" becomes an enforced,
evidenced rule. Fix it by classifying `email`/`full_name` in
`contracts/customer_360.odcs.yaml`, re-run, and the gate goes green.

### 5. (Optional) the visual lineage graph
```bash
make marquez-up
MARQUEZ_URL=http://localhost:5000 make demo
# open http://localhost:3000 and explore the job/dataset graph
```

> 📸 **Capture for the README:** the governance-gap table and the Marquez graph of
> `email` flowing raw → staging → dim → customer_360.

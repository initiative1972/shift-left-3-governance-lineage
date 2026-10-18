# Automated Compliance Evidence Report

*Generated: 2026-10-18 08:19:39 UTC*  ·  *Source: ODCS contracts + OpenLineage events*

> Continuous, automated evidence of data classification, lineage and processing — the kind of artefact an auditor asks for, produced by the pipeline itself.

- Jobs observed: **6**
- Declared classified fields: **17**
- Fields carrying PII (by lineage): **14**
- **Governance gaps (HIGH): 2**

## 1. Information Asset Classification Register (CPS 234)

| Dataset | Field | Classification | Sensitivity | Restricted | Source contract |
|---|---|---|---|---|---|
| customer_360 | customer_id | internal | Low | - | customer_360.odcs.yaml |
| customer_360 | total_spend | internal | Low | - | customer_360.odcs.yaml |
| customer_360 | txn_count | internal | Low | - | customer_360.odcs.yaml |
| dim_customer | customer_id | internal | Low | - | customers.odcs.yaml |
| dim_customer | dob | PII | High | - | customers.odcs.yaml |
| dim_customer | email | PII | High | - | customers.odcs.yaml |
| dim_customer | full_name | PII | Medium | - | customers.odcs.yaml |
| dim_customer | tax_file_number | PII | Critical | yes | customers.odcs.yaml |
| stg_accounts | account_id | internal | Low | - | accounts.odcs.yaml |
| stg_accounts | account_type | internal | Low | - | accounts.odcs.yaml |
| stg_accounts | customer_id | internal | Low | - | accounts.odcs.yaml |
| stg_accounts | opened_date | internal | Low | - | accounts.odcs.yaml |
| stg_transactions | account_id | internal | Low | - | transactions.odcs.yaml |
| stg_transactions | amount | internal | Low | - | transactions.odcs.yaml |
| stg_transactions | currency | internal | Low | - | transactions.odcs.yaml |
| stg_transactions | transaction_id | internal | Low | - | transactions.odcs.yaml |
| stg_transactions | txn_date | internal | Low | - | transactions.odcs.yaml |

## 2. PII Propagation Map (where classified data actually flows)

- **dim_customer.dob** (PII, sensitivity High) flows to: dim_customer, raw_customers, stg_customers
- **dim_customer.email** (PII, sensitivity High) flows to: customer_360, dim_customer, raw_customers, stg_customers
- **dim_customer.full_name** (PII, sensitivity Medium) flows to: customer_360, dim_customer, raw_customers, stg_customers
- **dim_customer.tax_file_number** (PII, sensitivity Critical) flows to: dim_customer, raw_customers, stg_customers

## 3. Governance Gaps Detected

| Severity | Dataset | Field | Inherited from | Finding |
|---|---|---|---|---|
| HIGH | customer_360 | email | dim_customer.email | Field carries PII (via lineage) but is NOT classified in its contract. |
| HIGH | customer_360 | full_name | dim_customer.full_name | Field carries PII (via lineage) but is NOT classified in its contract. |
| INFO | raw_customers | dob | dim_customer.dob | PII present in an ungoverned dataset (no contract). |
| INFO | raw_customers | email | dim_customer.email | PII present in an ungoverned dataset (no contract). |
| INFO | raw_customers | full_name | dim_customer.full_name | PII present in an ungoverned dataset (no contract). |
| INFO | raw_customers | tax_file_number | dim_customer.tax_file_number | PII present in an ungoverned dataset (no contract). |
| INFO | stg_customers | dob | dim_customer.dob | PII present in an ungoverned dataset (no contract). |
| INFO | stg_customers | email | dim_customer.email | PII present in an ungoverned dataset (no contract). |
| INFO | stg_customers | full_name | dim_customer.full_name | PII present in an ungoverned dataset (no contract). |
| INFO | stg_customers | tax_file_number | dim_customer.tax_file_number | PII present in an ungoverned dataset (no contract). |

## 4. Processing Evidence (jobs that touched classified data)

| Job | Runs | Inputs | Outputs | Touched classified fields |
|---|---|---|---|---|
| build_customer_360 | 1 | dim_customer, fct_transactions | customer_360 | customer_360.email, customer_360.full_name, dim_customer.dob, dim_customer.email, dim_customer.full_name, dim_customer.tax_file_number |
| build_dim_customer | 1 | stg_customers | dim_customer | dim_customer.dob, dim_customer.email, dim_customer.full_name, dim_customer.tax_file_number, stg_customers.dob, stg_customers.email, stg_customers.full_name, stg_customers.tax_file_number |
| build_fct_transactions | 1 | stg_accounts, stg_transactions | fct_transactions | - |
| ingest_accounts | 1 | raw_accounts | stg_accounts | - |
| ingest_customers | 1 | raw_customers | stg_customers | raw_customers.dob, raw_customers.email, raw_customers.full_name, raw_customers.tax_file_number, stg_customers.dob, stg_customers.email, stg_customers.full_name, stg_customers.tax_file_number |
| ingest_transactions | 1 | raw_transactions | stg_transactions | - |

## 5. Declared AI-Usage Context (ODCS v3.2.0)

- **customer_360**
  - `aiUsage`: Permitted as feature source for the churn propensity model. PII fields MUST NOT be sent to LLM prompts or external inference endpoints.
  - `aiDataZone`: internal-only

---
*This report is generated automatically from version-controlled contracts and emitted lineage. It is evidence of control operation, not legal or compliance advice. Synthetic data only.*

# Payments ETL with Data-Quality Quarantine

A portfolio project by **Mahesh M**: a small but complete payments ETL pipeline - extract, validate, transform, load - where every bad row is quarantined with its reasons and the load is reconciled back to the source.

> **Demo project.** All data is synthetic and randomly generated (fixed seed). It does not come from any real company, payment processor or employer, and the numbers are not real-world metrics.

## What it does

Reads three monthly payment CSV extracts (plus customer and FX reference data), applies validation rules, loads a clean star-schema warehouse in SQLite, quarantines failures, then proves the load with post-load SQL checks and a source-to-warehouse row reconciliation.

```
data/payments_2026-0*.csv        raw monthly extracts (defects injected on purpose)
        |
        v
extract -> validate -> transform -> load        quarantine
  CSVs     7 rules    currency norm,   sqlite      rejects
                      dedupe, USD conv warehouse   (row + reasons)
        |
        v
post-load SQL checks + reconciliation report (sample_output.md)
```

## The validation rules

| Rule | Action |
|---|---|
| `duplicate_payment_id` | Quarantine (keep first occurrence) |
| `non_positive_amount` / `unparseable_amount` | Quarantine |
| `unknown_currency` | Quarantine (code not in the FX table) |
| `unknown_customer` | Quarantine (referential integrity) |
| `malformed_date` / `future_date` | Quarantine |
| `missing_reference` | Quarantine |
| Mixed-case currency codes | **Not** a reject - normalised to upper case in transform |

## The warehouse

[`sql/warehouse_schema.sql`](sql/warehouse_schema.sql): `dim_customers`, `dim_fx_rates`, `fact_payments` (USD-converted amounts, constraints on positivity and referential integrity) and `rejects` (the original CSV line plus every failed rule).

## Run it

Requires Python 3.8+ only (built-in `sqlite3`, no installs).

```bash
python scripts/run_pipeline.py    # generates data/*.csv on first run
```

The full run report is written to [`sample_output.md`](sample_output.md): load log, reject counts by rule, post-load checks (all zero violations) and the month-by-month reconciliation where loaded + quarantined must equal the source row count.

## Example output

```text
- payments_2026-01.csv: 133 rows read, 122 loaded, 11 quarantined
check[duplicate payment_ids in fact_payments]: OK
recon 2026-01: source=133 loaded=122 quarantined=11 balanced=True
```

## Layout

```
sql/warehouse_schema.sql     table definitions with constraints
scripts/generate_sources.py  deterministic synthetic sources + injected defects
scripts/run_pipeline.py      the ETL itself
data/*.csv                   generated sources (committed for transparency)
sample_output.md             generated run report
```

## Possible extensions

Config-driven rules with severity levels (warn vs reject), an alerts table fed by the post-load checks, incremental loads with watermarks, and a dbt-style test layer.

---
Author: Mahesh M. Released under the MIT License.

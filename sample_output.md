# Pipeline run report (synthetic data)

Produced by `scripts/run_pipeline.py`. All input data is synthetic.

## Load log

- `payments_2026-01.csv`: 133 rows read, 122 loaded, 11 quarantined
- `payments_2026-02.csv`: 133 rows read, 121 loaded, 12 quarantined
- `payments_2026-03.csv`: 133 rows read, 121 loaded, 12 quarantined

Warehouse now holds **364** payments; **35** rows quarantined in `rejects`.

## Reject reasons

| Reason | Rows |
|---|---|
| duplicate_payment_id | 6 |
| future_date | 4 |
| malformed_date | 3 |
| missing_reference | 4 |
| non_positive_amount | 6 |
| unknown_currency | 7 |
| unknown_customer | 6 |

## Post-load data-quality checks (all must be zero)

| Check | Violations |
|---|---|
| duplicate payment_ids in fact_payments | 0 |
| payments with unknown customer in fact_payments | 0 |
| non-positive amounts in fact_payments | 0 |
| unknown currencies in fact_payments | 0 |
| future-dated payments in fact_payments | 0 |
| payments missing a reference | 0 |

## Source-to-warehouse reconciliation

| Month | Source rows | Loaded | Quarantined | Loaded + quarantined = source |
|---|---|---|---|---|
| 2026-01 | 133 | 122 | 11 | yes |
| 2026-02 | 133 | 121 | 12 | yes |
| 2026-03 | 133 | 121 | 12 | yes |

## Warehouse totals

- Total loaded: **$1,181,632.68 USD** across 364 payments

| Month | Payments | USD total |
|---|---|---|
| 2026-01 | 122 | $377,214.32 |
| 2026-02 | 121 | $397,890.19 |
| 2026-03 | 121 | $406,528.17 |

| Currency | Payments | USD total |
|---|---|---|
| USD | 100 | $368,346.47 |
| GBP | 100 | $443,975.06 |
| EUR | 84 | $365,514.99 |
| INR | 80 | $3,796.16 |

-- Warehouse schema for the payments ETL demo.
-- SQLite dialect; plain enough to port to Postgres or SQL Server.

CREATE TABLE IF NOT EXISTS dim_customers (
    customer_id   TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    country       TEXT NOT NULL,
    signup_date   TEXT NOT NULL  -- ISO yyyy-mm-dd
);

CREATE TABLE IF NOT EXISTS dim_fx_rates (
    currency  TEXT PRIMARY KEY,
    usd_rate  REAL NOT NULL     -- multiply source amount by this to get USD
);

CREATE TABLE IF NOT EXISTS fact_payments (
    payment_id   TEXT PRIMARY KEY,
    customer_id  TEXT NOT NULL REFERENCES dim_customers (customer_id),
    amount_src   REAL NOT NULL CHECK (amount_src > 0),
    currency     TEXT NOT NULL REFERENCES dim_fx_rates (currency),
    amount_usd   REAL NOT NULL CHECK (amount_usd > 0),
    payment_date TEXT NOT NULL,  -- ISO yyyy-mm-dd, never in the future
    method       TEXT NOT NULL,
    reference    TEXT NOT NULL
);

-- Quarantine: rows that failed validation, with every reason they failed.
CREATE TABLE IF NOT EXISTS rejects (
    source_file  TEXT NOT NULL,
    raw_row      TEXT NOT NULL,  -- original CSV line, preserved verbatim
    reasons      TEXT NOT NULL   -- pipe-separated rule codes
);

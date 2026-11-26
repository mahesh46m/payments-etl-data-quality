"""Payments ETL with data-quality quarantine.

extract   raw CSV payment files + dimension files
validate  parse and rule-check every row; quarantine failures with reasons
transform normalise currency codes, dedupe on payment_id, convert to USD
load      warehouse tables (sqlite)
check     post-load SQL data-quality checks + source-to-warehouse reconciliation

Run generate_sources.py first (or let this script run it for you).
Writes sample_output.md with the full run report.
"""
import csv
import sqlite3
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB = ROOT / "warehouse.db"
SCHEMA = ROOT / "sql" / "warehouse_schema.sql"

MAX_DATE = date(2026, 3, 31)  # "today" for the synthetic run


def parse_date(raw: str):
    try:
        y, m, d = (int(part) for part in raw.split("-"))
        return date(y, m, d)
    except (ValueError, AttributeError):
        return None


def main() -> None:
    if not (DATA / "customers.csv").exists():
        import generate_sources  # noqa: PLC0415 - sibling script

        generate_sources.main()

    con = sqlite3.connect(DB)
    con.executescript(SCHEMA.read_text())
    con.executescript(
        "DELETE FROM fact_payments; DELETE FROM rejects; "
        "DELETE FROM dim_customers; DELETE FROM dim_fx_rates;"
    )

    # --- load dimensions -------------------------------------------------
    with (DATA / "customers.csv").open() as fh:
        for row in csv.DictReader(fh):
            con.execute(
                "INSERT INTO dim_customers VALUES (?, ?, ?, ?)",
                (row["customer_id"], row["customer_name"], row["country"],
                 row["signup_date"]),
            )
    with (DATA / "fx_rates.csv").open() as fh:
        for row in csv.DictReader(fh):
            con.execute(
                "INSERT INTO dim_fx_rates VALUES (?, ?)",
                (row["currency"].upper(), float(row["usd_rate"])),
            )

    known_customers = {
        r[0] for r in con.execute("SELECT customer_id FROM dim_customers")
    }
    fx = dict(con.execute("SELECT currency, usd_rate FROM dim_fx_rates"))

    # --- extract + validate + transform + load ---------------------------
    log = []
    seen_ids = set()
    totals_src = {}   # month -> count of rows read
    totals_loaded = {}
    reason_counts = {}
    payment_files = sorted(DATA.glob("payments_*.csv"))
    for path in payment_files:
        month = path.stem.replace("payments_", "")
        read = loaded = rejected = 0
        with path.open() as fh:
            for row in csv.DictReader(fh):
                read += 1
                reasons = []
                pid = row["payment_id"].strip()
                amount_raw = row["amount"].strip()
                currency = row["currency"].strip().upper()
                pay_date = parse_date(row["payment_date"].strip())
                customer = row["customer_id"].strip()
                reference = row["reference"].strip()

                if pid in seen_ids:
                    reasons.append("duplicate_payment_id")
                try:
                    amount = float(amount_raw)
                    if amount <= 0:
                        reasons.append("non_positive_amount")
                except ValueError:
                    amount = None
                    reasons.append("unparseable_amount")
                if currency not in fx:
                    reasons.append("unknown_currency")
                if customer not in known_customers:
                    reasons.append("unknown_customer")
                if pay_date is None:
                    reasons.append("malformed_date")
                elif pay_date > MAX_DATE:
                    reasons.append("future_date")
                if not reference:
                    reasons.append("missing_reference")

                if reasons:
                    rejected += 1
                    for reason in reasons:
                        reason_counts[reason] = reason_counts.get(reason, 0) + 1
                    con.execute(
                        "INSERT INTO rejects VALUES (?, ?, ?)",
                        (path.name, ",".join(row.values()), "|".join(reasons)),
                    )
                    continue

                seen_ids.add(pid)
                amount_usd = round(amount * fx[currency], 2)
                con.execute(
                    "INSERT INTO fact_payments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (pid, customer, amount, currency, amount_usd,
                     str(pay_date), row["method"].strip(), reference),
                )
                loaded += 1
        totals_src[month] = read
        totals_loaded[month] = loaded
        log.append(
            f"- `{path.name}`: {read} rows read, {loaded} loaded, {rejected} quarantined"
        )

    con.commit()

    # --- post-load SQL data-quality checks --------------------------------
    checks = [
        ("duplicate payment_ids in fact_payments",
         "SELECT COUNT(*) FROM (SELECT payment_id FROM fact_payments "
         "GROUP BY payment_id HAVING COUNT(*) > 1)"),
        ("payments with unknown customer in fact_payments",
         "SELECT COUNT(*) FROM fact_payments f LEFT JOIN dim_customers c "
         "ON f.customer_id = c.customer_id WHERE c.customer_id IS NULL"),
        ("non-positive amounts in fact_payments",
         "SELECT COUNT(*) FROM fact_payments WHERE amount_src <= 0 OR amount_usd <= 0"),
        ("unknown currencies in fact_payments",
         "SELECT COUNT(*) FROM fact_payments f LEFT JOIN dim_fx_rates x "
         "ON f.currency = x.currency WHERE x.currency IS NULL"),
        ("future-dated payments in fact_payments",
         f"SELECT COUNT(*) FROM fact_payments WHERE payment_date > '{MAX_DATE}'"),
        ("payments missing a reference",
         "SELECT COUNT(*) FROM fact_payments WHERE reference = ''"),
    ]
    check_rows = []
    for label, sql in checks:
        (count,) = con.execute(sql).fetchone()
        check_rows.append((label, count))

    # --- reconciliation: source row counts vs warehouse --------------------
    recon_rows = []
    for month in totals_src:
        (wh,) = con.execute(
            "SELECT COUNT(*) FROM fact_payments WHERE payment_date LIKE ?",
            (f"{month}%",),
        ).fetchone()
        (rj,) = con.execute(
            "SELECT COUNT(*) FROM rejects WHERE source_file = ?",
            (f"payments_{month}.csv",),
        ).fetchone()
        recon_rows.append((month, totals_src[month], wh, rj, wh + rj == totals_src[month]))

    (total_usd,) = con.execute("SELECT ROUND(SUM(amount_usd), 2) FROM fact_payments").fetchone()
    (n_loaded,) = con.execute("SELECT COUNT(*) FROM fact_payments").fetchone()
    (n_rejects,) = con.execute("SELECT COUNT(*) FROM rejects").fetchone()
    by_currency = con.execute(
        "SELECT currency, COUNT(*), ROUND(SUM(amount_usd), 2) FROM fact_payments "
        "GROUP BY currency ORDER BY 2 DESC"
    ).fetchall()
    by_month = con.execute(
        "SELECT substr(payment_date, 1, 7) m, COUNT(*), ROUND(SUM(amount_usd), 2) "
        "FROM fact_payments GROUP BY m ORDER BY m"
    ).fetchall()
    con.close()

    # --- report ------------------------------------------------------------
    out = [
        "# Pipeline run report (synthetic data)",
        "",
        "Produced by `scripts/run_pipeline.py`. All input data is synthetic.",
        "",
        "## Load log",
        "",
        *log,
        "",
        f"Warehouse now holds **{n_loaded}** payments; **{n_rejects}** rows quarantined in `rejects`.",
        "",
        "## Reject reasons",
        "",
        "| Reason | Rows |",
        "|---|---|",
        *[(f"| {reason} | {count} |") for reason, count in sorted(reason_counts.items())],
        "",
        "## Post-load data-quality checks (all must be zero)",
        "",
        "| Check | Violations |",
        "|---|---|",
        *[(f"| {label} | {count} |") for label, count in check_rows],
        "",
        "## Source-to-warehouse reconciliation",
        "",
        "| Month | Source rows | Loaded | Quarantined | Loaded + quarantined = source |",
        "|---|---|---|---|---|",
        *[
            (f"| {m} | {s} | {w} | {r} | {'yes' if ok else 'NO - BREAK'} |")
            for m, s, w, r, ok in recon_rows
        ],
        "",
        "## Warehouse totals",
        "",
        f"- Total loaded: **${total_usd:,.2f} USD** across {n_loaded} payments",
        "",
        "| Month | Payments | USD total |",
        "|---|---|---|",
        *[(f"| {m} | {c} | ${v:,.2f} |") for m, c, v in by_month],
        "",
        "| Currency | Payments | USD total |",
        "|---|---|---|",
        *[(f"| {c} | {n} | ${v:,.2f} |") for c, n, v in by_currency],
        "",
    ]
    (ROOT / "sample_output.md").write_text("\n".join(out) + "\n")

    print("\n".join(log))
    print(f"loaded={n_loaded} rejected={n_rejects} total_usd={total_usd:,.2f}")
    for label, count in check_rows:
        status = "OK" if count == 0 else f"FAIL ({count})"
        print(f"  check[{label}]: {status}")
    for m, s, w, r, ok in recon_rows:
        print(f"  recon {m}: source={s} loaded={w} quarantined={r} balanced={ok}")


if __name__ == "__main__":
    main()

"""Generate deterministic synthetic source files for the payments ETL demo.

All data is randomly generated with a fixed seed. It does not come from any
real company or payment system, and the numbers are not real-world metrics.

Known defects are injected on purpose so the pipeline's validation and
quarantine logic can be verified end to end.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 11
DATA = Path(__file__).resolve().parents[1] / "data"

CURRENCIES = {"USD": 1.0, "EUR": 1.09, "GBP": 1.27, "INR": 0.012}
METHODS = ["ach", "wire", "card", "check"]
COUNTRIES = ["US", "US", "US", "DE", "GB", "IN"]


def daterange_month(year: int, month: int) -> list:
    first = date(year, month, 1)
    last = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def main() -> None:
    rng = random.Random(SEED)
    DATA.mkdir(exist_ok=True)

    customers = []
    for i in range(1, 41):
        customers.append(
            {
                "customer_id": f"C{i:03d}",
                "customer_name": f"Customer {i:03d}",
                "country": rng.choice(COUNTRIES),
                "signup_date": str(date(2023, 1, 1) + timedelta(days=rng.randint(0, 900))),
            }
        )
    with (DATA / "customers.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(customers[0]))
        w.writeheader()
        w.writerows(customers)

    with (DATA / "fx_rates.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["currency", "usd_rate"])
        for cur, rate in CURRENCIES.items():
            w.writerow([cur, rate])

    pid = 5000
    injected = {
        "duplicate_rows": 0,
        "negative_amount": 0,
        "unknown_currency": 0,
        "unknown_customer": 0,
        "malformed_date": 0,
        "future_date": 0,
        "missing_reference": 0,
        "mixed_case_currency": 0,
    }
    for month in (1, 2, 3):
        rows = []
        days = daterange_month(2026, month)
        for _ in range(120):
            pid += 1
            rows.append(
                [
                    f"P{pid}",
                    rng.choice([c["customer_id"] for c in customers]),
                    round(rng.uniform(50, 8000), 2),
                    rng.choice(list(CURRENCIES)),
                    str(rng.choice(days)),
                    rng.choice(METHODS),
                    f"INV-{rng.randint(10000, 99999)}",
                ]
            )
        # Inject defects: 2 duplicate rows (same payment_id, same content).
        for _ in range(2):
            rows.append(list(rng.choice(rows)))
            injected["duplicate_rows"] += 1
        # 2 negative amounts.
        for _ in range(2):
            r = list(rng.choice(rows))
            r[0] = f"P{pid + rng.randint(1, 999)}x"
            r[2] = -abs(r[2])
            rows.append(r)
            injected["negative_amount"] += 1
        # 2 unknown currency codes.
        for _ in range(2):
            r = list(rng.choice(rows))
            r[0] = f"P{pid + rng.randint(1, 999)}y"
            r[3] = "XXX"
            rows.append(r)
            injected["unknown_currency"] += 1
        # 2 payments for customers that do not exist.
        for _ in range(2):
            r = list(rng.choice(rows))
            r[0] = f"P{pid + rng.randint(1, 999)}z"
            r[1] = "C999"
            rows.append(r)
            injected["unknown_customer"] += 1
        # 1 malformed date.
        r = list(rng.choice(rows))
        r[0] = f"P{pid + rng.randint(1, 999)}m"
        r[4] = "2026-13-40"
        rows.append(r)
        injected["malformed_date"] += 1
        # 1 future-dated payment.
        r = list(rng.choice(rows))
        r[0] = f"P{pid + rng.randint(1, 999)}f"
        r[4] = "2099-01-01"
        rows.append(r)
        injected["future_date"] += 1
        # 1 missing reference.
        r = list(rng.choice(rows))
        r[0] = f"P{pid + rng.randint(1, 999)}r"
        r[6] = ""
        rows.append(r)
        injected["missing_reference"] += 1
        # 2 mixed-case currency codes (should be normalised, not rejected).
        for _ in range(2):
            r = list(rng.choice(rows))
            r[0] = f"P{pid + rng.randint(1, 999)}c"
            r[3] = r[3].lower()
            rows.append(r)
            injected["mixed_case_currency"] += 1

        rng.shuffle(rows)
        path = DATA / f"payments_2026-{month:02d}.csv"
        with path.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(
                ["payment_id", "customer_id", "amount", "currency",
                 "payment_date", "method", "reference"]
            )
            w.writerows(rows)
        print(f"wrote {path.name}: {len(rows)} rows")
    print("injected defects:", injected)


if __name__ == "__main__":
    main()

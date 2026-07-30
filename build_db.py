"""
build_db.py
Loads every CSV in ./data into a single SQLite database (dataco.db).

Date columns are normalised to ISO 'YYYY-MM-DD' on the way in, so every
query downstream can slice them with plain substr() and get real months.

Run with:
    .venv\\Scripts\\python.exe build_db.py
"""

from pathlib import Path
import sqlite3
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = ROOT / "dataco.db"

DATE_COLUMNS = {"order_date", "shipping_date"}

INDEXES = [
    ("order_item", "order_id"),
    ("order_item", "product_id"),
    ("orders", "customer_id"),
    ("orders", "destination_id"),
    ("orders", "order_date"),
    ("product", "category_id"),
    ("category", "department_id"),
    ("customer", "customer_address_id"),
    ("customer", "customer_segment_id"),
    ("shipping_destination", "region_id"),
    ("shipping_destination", "order_country_id"),
    ("region", "market_id"),
]


def normalise_dates(df: pd.DataFrame, table: str) -> pd.DataFrame:
    for col in df.columns:
        if col.lower() not in DATE_COLUMNS:
            continue

        raw = df[col].astype("string")
        try:
            parsed = pd.to_datetime(raw, errors="coerce", format="mixed")
        except (ValueError, TypeError):
            parsed = pd.to_datetime(raw, errors="coerce")

        n_raw_null = int(raw.isna().sum())
        bad = int(parsed.isna().sum()) - n_raw_null
        total = len(df)
        df[col] = parsed.dt.strftime("%Y-%m-%d")

        span = ""
        if parsed.notna().any():
            span = f"  [{parsed.min():%Y-%m-%d} .. {parsed.max():%Y-%m-%d}]"
        note = f"  ({bad:,} unparsed)" if bad > 0 else ""
        print(f"        {table}.{col}: {total - bad:,}/{total:,} parsed{span}{note}")
    return df


def main() -> None:
    if not DATA_DIR.is_dir():
        sys.exit(f"[X] Folder not found: {DATA_DIR}")

    csv_files = sorted(DATA_DIR.glob("*.csv"))
    if not csv_files:
        sys.exit(f"[X] No CSV files found in {DATA_DIR}")

    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"[i] Removed old {DB_PATH.name}")

    conn = sqlite3.connect(DB_PATH)
    print(f"[i] Writing to {DB_PATH.name}\n")

    for path in csv_files:
        table = path.stem.lower()
        df = pd.read_csv(path)
        df.columns = [c.strip() for c in df.columns]
        df = normalise_dates(df, table)
        df.to_sql(table, conn, if_exists="replace", index=False)
        print(f"    {table:<24} {len(df):>8,} rows  {len(df.columns):>3} cols")

    print("\n[i] Creating indexes")
    cur = conn.cursor()
    existing = {r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    for table, column in INDEXES:
        if table not in existing:
            continue
        cols = {r[1] for r in cur.execute(f'PRAGMA table_info("{table}")')}
        if column not in cols:
            continue
        cur.execute(
            f'CREATE INDEX IF NOT EXISTS ix_{table}_{column} ON "{table}"("{column}")'
        )
    conn.commit()

    try:
        total, rows = cur.execute("SELECT SUM(sales), COUNT(*) FROM order_item").fetchone()
        print(f"\n[OK] order_item: {rows:,} rows | SUM(sales) = {total:,.2f}")
    except sqlite3.Error:
        print("\n[!] Could not read order_item.")

    try:
        n, lo, hi = cur.execute(
            """
            SELECT COUNT(DISTINCT substr(order_date, 1, 7)),
                   MIN(order_date), MAX(order_date)
            FROM   orders WHERE order_date IS NOT NULL
            """
        ).fetchone()
        print(f"[OK] orders: {n} distinct months, {lo} .. {hi}")
        if n and n > 120:
            print("[!]  Too many distinct months - dates did not parse cleanly.")
    except sqlite3.Error:
        print("[!] Could not check order_date.")

    conn.close()
    print(f"\n[DONE] {len(csv_files)} tables written to {DB_PATH.name}")


if __name__ == "__main__":
    main()

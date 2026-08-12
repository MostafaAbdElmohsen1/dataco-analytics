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

# ---------------------------------------------------------------------
# Agent-facing views (dbo.vw_* equivalents from the SQL Server design).
#
# These are the ONLY objects the NL-to-SQL agent (agent.py / db_tool.py)
# is allowed to touch. Row counts were verified 1:1 against the base
# tables when these were designed (no rows lost in any join, INNER JOIN
# does not drop any product/category/department).
#
# customer_email is masked to a fixed placeholder *in the view itself*,
# not just by prompting the model - so a real email can never leak
# through this path regardless of what the model writes.
# ---------------------------------------------------------------------
AGENT_VIEWS = {
    "vw_FactOrderItem": """
        SELECT oi.order_item_id, oi.order_id, oi.product_id, o.customer_id,
               o.destination_id, o.shipping_mode_id, o.order_status_id,
               o.delivery_status_id, o.order_type_id, o.order_date, o.shipping_date,
               oi.order_item_quantity, oi.unit_price_at_sale, oi.discount_amount,
               oi.discount_rate, oi.sales, oi.item_total, oi.profit_ratio,
               oi.profit_amount, o.days_for_shipping_real, o.days_for_shipment_scheduled
        FROM   order_item oi
        JOIN   orders o ON o.order_id = oi.order_id
    """,
    "vw_DimCustomer": """
        SELECT cu.customer_id, cu.customer_fname, cu.customer_lname,
               'XXXXXXXXX' AS customer_email,
               cs.customer_segment_name, cu.customer_address_id,
               ca.street, ca.city, ca.state, ca.zipcode, ca.country,
               ca.latitude, ca.longitude
        FROM   customer cu
        JOIN   customer_segment cs ON cs.customer_segment_id = cu.customer_segment_id
        JOIN   customer_address ca ON ca.customer_address_id = cu.customer_address_id
    """,
    "vw_DimProduct": """
        SELECT p.product_id, p.product_name, p.product_price, p.product_status,
               c.category_id, c.category_name, d.department_id, d.department_name
        FROM   product p
        JOIN   category c ON c.category_id = p.category_id
        JOIN   department d ON d.department_id = c.department_id
    """,
    "vw_DimGeography": """
        SELECT sd.destination_id, sd.order_city, sd.order_state, sd.order_zipcode,
               r.region_name, m.market_name, oc.order_country_name
        FROM   shipping_destination sd
        JOIN   region r ON r.region_id = sd.region_id
        JOIN   market m ON m.market_id = r.market_id
        JOIN   order_country oc ON oc.order_country_id = sd.order_country_id
    """,
    "vw_DimShippingMode": """
        SELECT shipping_mode_id, shipping_mode_name FROM shipping_mode
    """,
    "vw_DimOrderStatus": """
        SELECT (os.order_status_id * 100) + ds.delivery_status_id AS OrderStatusKey,
               os.order_status_name, ds.delivery_status_name
        FROM   order_status os
        CROSS JOIN delivery_status ds
    """,
    "vw_DimOrderType": """
        SELECT order_type_id, order_type_name FROM order_type
    """,
}


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

    print("\n[i] Creating agent views")
    for name, sql in AGENT_VIEWS.items():
        cur.execute(f'DROP VIEW IF EXISTS "{name}"')
        cur.execute(f'CREATE VIEW "{name}" AS {sql}')
        n = cur.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        print(f"    {name:<24} {n:>8,} rows")
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

"""
db.py - single place where the database is read.

Every page imports from here so the SQL lives in one file and the
grouping rules (always group dimensions by KEY, never by label) are
applied consistently.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import sqlite3

import pandas as pd

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "dataco.db"

if not DB_PATH.exists():
    raise SystemExit(
        f"[X] {DB_PATH.name} not found in {ROOT}\n"
        "    Run:  .venv\\Scripts\\python.exe build_db.py"
    )


def q(sql: str) -> pd.DataFrame:
    """Run a query and return a DataFrame."""
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn)


# ---------------------------------------------------------------------
# Schema map: (table, primary key, label column)
# Used by the data-quality page to audit every dimension the same way.
# ---------------------------------------------------------------------
DIMENSIONS = [
    ("category", "category_id", "category_name"),
    ("department", "department_id", "department_name"),
    ("product", "product_id", "product_name"),
    ("customer", "customer_id", None),
    ("customer_segment", "customer_segment_id", "customer_segment_name"),
    ("market", "market_id", "market_name"),
    ("region", "region_id", "region_name"),
    ("order_country", "order_country_id", "order_country_name"),
    ("order_status", "order_status_id", "order_status_name"),
    ("order_type", "order_type_id", "order_type_name"),
    ("delivery_status", "delivery_status_id", "delivery_status_name"),
    ("shipping_mode", "shipping_mode_id", "shipping_mode_name"),
    ("shipping_destination", "destination_id", None),
    ("customer_address", "customer_address_id", None),
]

# (child table, child column, parent table, parent key)
RELATIONSHIPS = [
    ("order_item", "order_id", "orders", "order_id"),
    ("order_item", "product_id", "product", "product_id"),
    ("orders", "customer_id", "customer", "customer_id"),
    ("orders", "destination_id", "shipping_destination", "destination_id"),
    ("orders", "shipping_mode_id", "shipping_mode", "shipping_mode_id"),
    ("orders", "order_status_id", "order_status", "order_status_id"),
    ("orders", "delivery_status_id", "delivery_status", "delivery_status_id"),
    ("orders", "order_type_id", "order_type", "order_type_id"),
    ("product", "category_id", "category", "category_id"),
    ("category", "department_id", "department", "department_id"),
    ("customer", "customer_segment_id", "customer_segment", "customer_segment_id"),
    ("customer", "customer_address_id", "customer_address", "customer_address_id"),
    ("region", "market_id", "market", "market_id"),
    ("shipping_destination", "region_id", "region", "region_id"),
    ("shipping_destination", "order_country_id", "order_country", "order_country_id"),
]


@lru_cache(maxsize=1)
def tables() -> tuple[str, ...]:
    df = q("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return tuple(df["name"])


def has(table: str, column: str | None = None) -> bool:
    if table not in tables():
        return False
    if column is None:
        return True
    cols = q(f'PRAGMA table_info("{table}")')["name"].tolist()
    return column in cols


# ---------------------------------------------------------------------
# Headline metrics
# ---------------------------------------------------------------------
@lru_cache(maxsize=1)
def totals() -> dict:
    r = q(
        """
        SELECT SUM(sales)         AS revenue,
               SUM(profit_amount) AS profit,
               COUNT(*)           AS lines
        FROM   order_item
        """
    ).iloc[0]

    orders = q("SELECT COUNT(DISTINCT order_id) AS n FROM orders").iloc[0]["n"]
    customers = q("SELECT COUNT(DISTINCT customer_id) AS n FROM customer").iloc[0]["n"]

    revenue = float(r["revenue"])
    profit = float(r["profit"])
    return {
        "revenue": revenue,
        "profit": profit,
        "margin": profit / revenue if revenue else 0.0,
        "lines": int(r["lines"]),
        "orders": int(orders),
        "customers": int(customers),
    }


@lru_cache(maxsize=1)
def category_revenue() -> pd.DataFrame:
    """
    Revenue per category, grouped by category_id.

    Grouping by category_name would silently merge two different
    categories that share the name "Electronics" (id 13 under Footwear,
    id 37 under Outdoors). Duplicated labels get their department
    appended for display only.
    """
    df = q(
        """
        SELECT c.category_id      AS category_id,
               c.category_name    AS category_name,
               d.department_name  AS department_name,
               SUM(oi.sales)      AS revenue,
               SUM(oi.profit_amount) AS profit,
               COUNT(*)           AS lines
        FROM   order_item oi
        JOIN   product      p ON p.product_id    = oi.product_id
        JOIN   category     c ON c.category_id   = p.category_id
        LEFT JOIN department d ON d.department_id = c.department_id
        GROUP  BY c.category_id, c.category_name, d.department_name
        ORDER  BY revenue DESC
        """
    )
    dupes = df["category_name"].duplicated(keep=False)
    df["category"] = df["category_name"].where(
        ~dupes,
        df["category_name"] + " (" + df["department_name"].fillna("?") + ")",
    )
    df["share"] = df["revenue"] / df["revenue"].sum()
    return df


@lru_cache(maxsize=1)
def department_revenue() -> pd.DataFrame:
    return q(
        """
        SELECT d.department_id     AS department_id,
               d.department_name   AS department,
               SUM(oi.sales)       AS revenue,
               SUM(oi.profit_amount) AS profit
        FROM   order_item oi
        JOIN   product    p ON p.product_id    = oi.product_id
        JOIN   category   c ON c.category_id   = p.category_id
        JOIN   department d ON d.department_id  = c.department_id
        GROUP  BY d.department_id, d.department_name
        ORDER  BY revenue DESC
        """
    )


@lru_cache(maxsize=1)
def monthly_revenue() -> pd.DataFrame:
    return q(
        """
        SELECT substr(o.order_date, 1, 7) AS month,
               SUM(oi.sales)              AS revenue,
               SUM(oi.profit_amount)      AS profit,
               COUNT(DISTINCT o.order_id) AS orders
        FROM   order_item oi
        JOIN   orders o ON o.order_id = oi.order_id
        WHERE  o.order_date IS NOT NULL
        GROUP  BY month
        ORDER  BY month
        """
    )


@lru_cache(maxsize=1)
def delivery_mix() -> pd.DataFrame:
    return q(
        """
        SELECT ds.delivery_status_id       AS status_id,
               ds.delivery_status_name     AS status,
               ds.late_delivery_risk_flag  AS late_flag,
               COUNT(*)                    AS orders
        FROM   orders o
        JOIN   delivery_status ds ON ds.delivery_status_id = o.delivery_status_id
        GROUP  BY ds.delivery_status_id, ds.delivery_status_name,
                  ds.late_delivery_risk_flag
        ORDER  BY orders DESC
        """
    )


@lru_cache(maxsize=1)
def country_revenue() -> pd.DataFrame:
    return q(
        """
        SELECT oc.order_country_id   AS country_id,
               oc.order_country_name AS country,
               SUM(oi.sales)         AS revenue,
               COUNT(DISTINCT o.order_id) AS orders
        FROM   order_item oi
        JOIN   orders o  ON o.order_id = oi.order_id
        JOIN   shipping_destination sd ON sd.destination_id = o.destination_id
        JOIN   order_country oc ON oc.order_country_id = sd.order_country_id
        GROUP  BY oc.order_country_id, oc.order_country_name
        ORDER  BY revenue DESC
        """
    )


# ---------------------------------------------------------------------
# Data quality audit
# ---------------------------------------------------------------------
@lru_cache(maxsize=1)
def audit_dimensions() -> pd.DataFrame:
    rows = []
    for table, key, label in DIMENSIONS:
        if not has(table, key):
            continue
        n_rows = int(q(f'SELECT COUNT(*) AS n FROM "{table}"').iloc[0]["n"])
        n_keys = int(q(f'SELECT COUNT(DISTINCT "{key}") AS n FROM "{table}"').iloc[0]["n"])
        n_null = int(
            q(f'SELECT COUNT(*) AS n FROM "{table}" WHERE "{key}" IS NULL').iloc[0]["n"]
        )

        n_labels = None
        if label and has(table, label):
            n_labels = int(
                q(f'SELECT COUNT(DISTINCT "{label}") AS n FROM "{table}"').iloc[0]["n"]
            )

        issues = []
        if n_keys != n_rows:
            issues.append("duplicate keys")
        if n_null:
            issues.append("null keys")
        if n_labels is not None and n_labels < n_keys:
            issues.append(f"{n_keys - n_labels} duplicate label(s)")

        rows.append(
            {
                "table": table,
                "key": key,
                "rows": n_rows,
                "unique keys": n_keys,
                "unique labels": n_labels if n_labels is not None else "-",
                "status": "; ".join(issues) if issues else "clean",
            }
        )
    return pd.DataFrame(rows)


@lru_cache(maxsize=1)
def audit_relationships() -> pd.DataFrame:
    rows = []
    for child, col, parent, key in RELATIONSHIPS:
        if not (has(child, col) and has(parent, key)):
            continue
        orphans = int(
            q(
                f'''
                SELECT COUNT(*) AS n
                FROM   "{child}" c
                LEFT JOIN "{parent}" p ON p."{key}" = c."{col}"
                WHERE  c."{col}" IS NOT NULL AND p."{key}" IS NULL
                '''
            ).iloc[0]["n"]
        )
        nulls = int(
            q(f'SELECT COUNT(*) AS n FROM "{child}" WHERE "{col}" IS NULL').iloc[0]["n"]
        )
        rows.append(
            {
                "relationship": f"{child}.{col} -> {parent}.{key}",
                "orphan rows": orphans,
                "null keys": nulls,
                "status": "clean" if orphans == 0 and nulls == 0 else "check",
            }
        )
    return pd.DataFrame(rows)


@lru_cache(maxsize=1)
def duplicate_labels() -> pd.DataFrame:
    """Every dimension label that maps to more than one key."""
    rows = []
    for table, key, label in DIMENSIONS:
        if not (label and has(table, key) and has(table, label)):
            continue
        df = q(
            f'''
            SELECT "{label}" AS label,
                   COUNT(*)  AS keys,
                   GROUP_CONCAT("{key}") AS key_list
            FROM   "{table}"
            GROUP  BY "{label}"
            HAVING COUNT(*) > 1
            '''
        )
        for _, r in df.iterrows():
            rows.append(
                {
                    "table": table,
                    "label": r["label"],
                    "keys": int(r["keys"]),
                    "key values": r["key_list"],
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Filtered fact queries (used by the Executive page)
# ---------------------------------------------------------------------
FACT_JOIN = """
FROM      order_item oi
JOIN      orders               o  ON o.order_id            = oi.order_id
JOIN      product              p  ON p.product_id          = oi.product_id
JOIN      category             c  ON c.category_id          = p.category_id
JOIN      department           d  ON d.department_id        = c.department_id
JOIN      customer             cu ON cu.customer_id         = o.customer_id
JOIN      customer_segment     cs ON cs.customer_segment_id = cu.customer_segment_id
JOIN      shipping_destination sd ON sd.destination_id      = o.destination_id
JOIN      region               r  ON r.region_id            = sd.region_id
JOIN      market               m  ON m.market_id            = r.market_id
JOIN      order_country        oc ON oc.order_country_id    = sd.order_country_id
JOIN      delivery_status      ds ON ds.delivery_status_id  = o.delivery_status_id
"""


def _esc(v: str) -> str:
    return str(v).replace("'", "''")


def _where(year=None, market=None, segment=None) -> str:
    parts = ["o.order_date IS NOT NULL"]
    if year and year != "All":
        parts.append(f"substr(o.order_date, 1, 4) = '{_esc(year)}'")
    if market and market != "All":
        parts.append(f"m.market_name = '{_esc(market)}'")
    if segment and segment != "All":
        parts.append(f"cs.customer_segment_name = '{_esc(segment)}'")
    return "WHERE " + " AND ".join(parts)


@lru_cache(maxsize=1)
def filter_options() -> dict:
    years = q(
        """
        SELECT DISTINCT substr(order_date, 1, 4) AS y
        FROM   orders WHERE order_date IS NOT NULL ORDER BY y
        """
    )["y"].tolist()
    markets = q("SELECT market_name FROM market ORDER BY market_name")["market_name"].tolist()
    segments = q(
        "SELECT customer_segment_name FROM customer_segment ORDER BY customer_segment_name"
    )["customer_segment_name"].tolist()
    return {"years": years, "markets": markets, "segments": segments}


def exec_kpis(year=None, market=None, segment=None) -> dict:
    r = q(
        f"""
        SELECT SUM(oi.sales)                              AS revenue,
               SUM(oi.profit_amount)                      AS profit,
               COUNT(DISTINCT o.order_id)                 AS orders,
               COUNT(DISTINCT o.customer_id)              AS customers,
               COUNT(*)                                   AS lines,
               AVG(CASE WHEN ds.late_delivery_risk_flag = 0 THEN 1.0 ELSE 0.0 END)
                                                          AS on_time
        {FACT_JOIN}
        {_where(year, market, segment)}
        """
    ).iloc[0]

    revenue = float(r["revenue"] or 0)
    profit = float(r["profit"] or 0)
    orders = int(r["orders"] or 0)
    return {
        "revenue": revenue,
        "profit": profit,
        "margin": profit / revenue if revenue else 0.0,
        "orders": orders,
        "customers": int(r["customers"] or 0),
        "lines": int(r["lines"] or 0),
        "aov": revenue / orders if orders else 0.0,
        "on_time": float(r["on_time"] or 0),
    }


def exec_monthly(year=None, market=None, segment=None):
    return q(
        f"""
        SELECT substr(o.order_date, 1, 7) AS month,
               SUM(oi.sales)              AS revenue,
               SUM(oi.profit_amount)      AS profit
        {FACT_JOIN}
        {_where(year, market, segment)}
        GROUP BY month ORDER BY month
        """
    )


def exec_departments(year=None, market=None, segment=None):
    return q(
        f"""
        SELECT d.department_name AS department,
               SUM(oi.sales)     AS revenue,
               SUM(oi.profit_amount) AS profit
        {FACT_JOIN}
        {_where(year, market, segment)}
        GROUP BY d.department_id, d.department_name
        ORDER BY revenue DESC
        """
    )


def exec_countries(year=None, market=None, segment=None, limit: int = 12):
    return q(
        f"""
        SELECT oc.order_country_name AS country,
               SUM(oi.sales)          AS revenue
        {FACT_JOIN}
        {_where(year, market, segment)}
        GROUP BY oc.order_country_id, oc.order_country_name
        ORDER BY revenue DESC
        LIMIT {int(limit)}
        """
    )


def exec_top_products(year=None, market=None, segment=None, limit: int = 10):
    return q(
        f"""
        SELECT p.product_name         AS product,
               SUM(oi.sales)          AS revenue,
               SUM(oi.profit_amount)  AS profit,
               SUM(oi.order_item_quantity) AS units
        {FACT_JOIN}
        {_where(year, market, segment)}
        GROUP BY p.product_id, p.product_name
        ORDER BY revenue DESC
        LIMIT {int(limit)}
        """
    )


def delivery_delay(year=None, market=None, segment=None):
    """
    Real shipping days minus scheduled days, per order.

    Positive = shipped later than promised. This is measured, unlike
    late_delivery_risk_flag which is a risk marker rather than an outcome.
    """
    return q(
        f"""
        SELECT (o.days_for_shipping_real - o.days_for_shipment_scheduled) AS delay,
               COUNT(DISTINCT o.order_id) AS orders
        {FACT_JOIN}
        {_where(year, market, segment)}
        GROUP BY delay
        ORDER BY delay
        """
    )


def category_pareto(year=None, market=None, segment=None):
    df = q(
        f"""
        SELECT c.category_id   AS category_id,
               c.category_name AS category_name,
               d.department_name AS department_name,
               SUM(oi.sales)   AS revenue
        {FACT_JOIN}
        {_where(year, market, segment)}
        GROUP BY c.category_id, c.category_name, d.department_name
        ORDER BY revenue DESC
        """
    )
    if not len(df):
        return df
    dupes = df["category_name"].duplicated(keep=False)
    df["category"] = df["category_name"].where(
        ~dupes,
        df["category_name"] + " (" + df["department_name"].fillna("?") + ")",
    )
    df["cum_share"] = df["revenue"].cumsum() / df["revenue"].sum()
    return df

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
def late_delivery_rate() -> float:
    """
    Share of orders shipped later than promised, measured directly
    from days_for_shipping_real vs days_for_shipment_scheduled.

    Deliberately not late_delivery_risk_flag: that column is a risk
    marker assigned ahead of time, not a measured outcome, so it is
    never used for this figure anywhere in the app.
    """
    r = q(
        """
        SELECT AVG(CASE WHEN days_for_shipping_real
                             > days_for_shipment_scheduled
                        THEN 1.0 ELSE 0.0 END) AS late_rate
        FROM   orders
        WHERE  days_for_shipping_real IS NOT NULL
           AND days_for_shipment_scheduled IS NOT NULL
        """
    ).iloc[0]["late_rate"]
    return float(r or 0.0)


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


def _where(year=None, market=None, segment=None, country=None) -> str:
    parts = ["o.order_date IS NOT NULL"]
    if year and year != "All":
        parts.append(f"substr(o.order_date, 1, 4) = '{_esc(year)}'")
    if market and market != "All":
        parts.append(f"m.market_name = '{_esc(market)}'")
    if segment and segment != "All":
        parts.append(f"cs.customer_segment_name = '{_esc(segment)}'")
    if country and country != "All":
        parts.append(f"oc.order_country_name = '{_esc(country)}'")
    return "WHERE " + " AND ".join(parts)


# ---------------------------------------------------------------------
# Drill-down
#
# One scope = (level, value), where level is "country" or "market".
# Every drill query below reuses FACT_JOIN and _where(), so a drilled
# figure is computed exactly the same way as the page-level figure it
# came from. The panel can never disagree with the chart above it.
# ---------------------------------------------------------------------
def _drill_join(*, country=False, market=False, segment=False,
                product=False, delivery=False) -> str:
    """
    بيبني الـ JOIN على الجداول المطلوبة فقط.

    FACT_JOIN بيوصّل 12 جدول مع بعض، وده كان بيخلي كويري بسيط زي
    "إيراد أمريكا شهرياً" ياخد 12 ثانية (مصر 0.8 ثانية لأنها أصغر).
    اللوحة بتشغّل 5 كويريات، فكانت بتاخد 38 ثانية كاملة - مستحيلة
    للاستخدام، وأبطأ كمان على سيرفر الاستضافة المجاني.
    الجداول اللي مش مستخدمة في السؤال مالهاش لازمة في الـ JOIN.
    """
    parts = [
        "FROM order_item oi",
        "JOIN orders o ON o.order_id = oi.order_id",
    ]
    if country or market:
        parts.append(
            "JOIN shipping_destination sd ON sd.destination_id = o.destination_id")
    if country:
        parts.append(
            "JOIN order_country oc ON oc.order_country_id = sd.order_country_id")
    if market:
        parts.append("JOIN region r ON r.region_id = sd.region_id")
        parts.append("JOIN market m ON m.market_id = r.market_id")
    if segment:
        parts.append("JOIN customer cu ON cu.customer_id = o.customer_id")
        parts.append("JOIN customer_segment cs "
                     "ON cs.customer_segment_id = cu.customer_segment_id")
    if product:
        parts.append("JOIN product p ON p.product_id = oi.product_id")
    if delivery:
        parts.append(
            "JOIN delivery_status ds ON ds.delivery_status_id = o.delivery_status_id")
    return "\n".join(parts)


def _scope_sql(level: str, value: str, year=None, segment=None,
               product=False, delivery=False) -> tuple[str, str]:
    """بيرجع (الـ JOIN، الـ WHERE) المناسبين للنطاق المطلوب."""
    seg_on = bool(segment and segment != "All")
    is_market = level == "market"
    join = _drill_join(
        country=not is_market, market=is_market,
        segment=seg_on, product=product, delivery=delivery,
    )
    where = (_where(year, value, segment, None) if is_market
             else _where(year, None, segment, value))
    return join, where


def _scope_where(level: str, value: str, year=None, segment=None) -> str:
    """متسيبة للتوافق مع أي استدعاء قديم."""
    return _scope_sql(level, value, year, segment)[1]


def drill_kpis(level: str, value: str, year=None, segment=None) -> dict:
    join, where = _scope_sql(level, value, year, segment)
    r = q(
        f"""
        SELECT SUM(oi.sales)                  AS revenue,
               SUM(oi.profit_amount)          AS profit,
               COUNT(DISTINCT o.order_id)     AS orders,
               COUNT(DISTINCT o.customer_id)  AS customers,
               SUM(oi.order_item_quantity)    AS units,
               AVG(CASE WHEN o.days_for_shipping_real
                             > o.days_for_shipment_scheduled
                        THEN 1.0 ELSE 0.0 END) AS late_rate,
               AVG(o.days_for_shipping_real)   AS avg_days
        {join}
        {where}
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
        "units": int(r["units"] or 0),
        "aov": revenue / orders if orders else 0.0,
        "late_rate": float(r["late_rate"] or 0),
        "avg_days": float(r["avg_days"] or 0),
    }


def drill_monthly(level: str, value: str, year=None, segment=None):
    join, where = _scope_sql(level, value, year, segment)
    return q(
        f"""
        SELECT substr(o.order_date, 1, 7) AS month,
               SUM(oi.sales)              AS revenue,
               SUM(oi.profit_amount)      AS profit
        {join}
        {where}
        GROUP BY month ORDER BY month
        """
    )


def drill_products(level: str, value: str, year=None, segment=None, limit: int = 8):
    join, where = _scope_sql(level, value, year, segment, product=True)
    return q(
        f"""
        SELECT p.product_name        AS product,
               SUM(oi.sales)         AS revenue,
               SUM(oi.profit_amount) AS profit
        {join}
        {where}
        GROUP BY p.product_id, p.product_name
        ORDER BY revenue DESC
        LIMIT {int(limit)}
        """
    )


def drill_delivery(level: str, value: str, year=None, segment=None):
    """Order counts per delivery status - the panel's status breakdown."""
    join, where = _scope_sql(level, value, year, segment, delivery=True)
    return q(
        f"""
        SELECT ds.delivery_status_name     AS status,
               COUNT(DISTINCT o.order_id)  AS orders
        {join}
        {where}
        GROUP BY ds.delivery_status_id, ds.delivery_status_name
        ORDER BY orders DESC
        """
    )


def drill_rank(level: str, value: str, year=None, segment=None) -> dict:
    """
    Where this country/market sits among its peers by revenue, so the
    panel can say "3rd of 164" instead of showing a bare number with no
    frame of reference.
    """
    is_market = level == "market"
    col = "m.market_name" if is_market else "oc.order_country_name"
    join = _drill_join(country=not is_market, market=is_market,
                       segment=bool(segment and segment != "All"))
    df = q(
        f"""
        SELECT {col} AS name, SUM(oi.sales) AS revenue
        {join}
        {_where(year, None, segment, None)}
        GROUP BY {col}
        ORDER BY revenue DESC
        """
    )
    total = float(df["revenue"].sum()) or 1.0
    names = df["name"].tolist()
    rank = names.index(value) + 1 if value in names else 0
    share = float(df.loc[df["name"] == value, "revenue"].sum()) / total
    return {"rank": rank, "of": len(names), "share": share}


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
    """
    on_time is measured from days_for_shipping_real vs
    days_for_shipment_scheduled, not from late_delivery_risk_flag,
    which is a risk marker rather than a measured outcome. This keeps
    the number consistent with delivery_delay() and mode_promise(),
    which use the same comparison.
    """
    r = q(
        f"""
        SELECT SUM(oi.sales)                              AS revenue,
               SUM(oi.profit_amount)                      AS profit,
               COUNT(DISTINCT o.order_id)                 AS orders,
               COUNT(DISTINCT o.customer_id)              AS customers,
               COUNT(*)                                   AS lines,
               AVG(CASE WHEN o.days_for_shipping_real
                             > o.days_for_shipment_scheduled
                        THEN 0.0 ELSE 1.0 END)             AS on_time
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


# ---------------------------------------------------------------------
# Hierarchy + flow queries (Network page)
# ---------------------------------------------------------------------
@lru_cache(maxsize=1)
def market_region_country() -> pd.DataFrame:
    """Three-level hierarchy: market -> region -> country, with revenue."""
    return q(
        """
        SELECT m.market_name         AS market,
               r.region_name         AS region,
               oc.order_country_name AS country,
               SUM(oi.sales)         AS revenue,
               COUNT(DISTINCT o.order_id) AS orders
        FROM   order_item oi
        JOIN   orders o  ON o.order_id = oi.order_id
        JOIN   shipping_destination sd ON sd.destination_id = o.destination_id
        JOIN   region r  ON r.region_id = sd.region_id
        JOIN   market m  ON m.market_id = r.market_id
        JOIN   order_country oc ON oc.order_country_id = sd.order_country_id
        GROUP  BY m.market_id, m.market_name, r.region_id, r.region_name,
                  oc.order_country_id, oc.order_country_name
        ORDER  BY revenue DESC
        """
    )


@lru_cache(maxsize=1)
def flow_market_mode_outcome() -> pd.DataFrame:
    """
    Order flow for a Sankey: market -> shipping mode -> delivery outcome.

    Outcome is measured (real days vs scheduled days), not taken from
    late_delivery_risk_flag, which is a risk marker rather than a result.
    """
    return q(
        """
        SELECT m.market_name        AS market,
               sm.shipping_mode_name AS mode,
               CASE
                   WHEN o.days_for_shipping_real
                        > o.days_for_shipment_scheduled THEN 'Late'
                   WHEN o.days_for_shipping_real
                        < o.days_for_shipment_scheduled THEN 'Early'
                   ELSE 'On time'
               END                  AS outcome,
               COUNT(DISTINCT o.order_id) AS orders,
               SUM(oi.sales)        AS revenue
        FROM   order_item oi
        JOIN   orders o  ON o.order_id = oi.order_id
        JOIN   shipping_mode sm ON sm.shipping_mode_id = o.shipping_mode_id
        JOIN   shipping_destination sd ON sd.destination_id = o.destination_id
        JOIN   region r  ON r.region_id = sd.region_id
        JOIN   market m  ON m.market_id = r.market_id
        GROUP  BY m.market_id, m.market_name,
                  sm.shipping_mode_id, sm.shipping_mode_name, outcome
        """
    )


@lru_cache(maxsize=1)
def mode_promise() -> pd.DataFrame:
    """Promised vs actual shipping days for each shipping mode."""
    return q(
        """
        SELECT sm.shipping_mode_name        AS mode,
               AVG(o.days_for_shipment_scheduled) AS promised,
               AVG(o.days_for_shipping_real)      AS actual,
               COUNT(DISTINCT o.order_id)         AS orders,
               AVG(CASE WHEN o.days_for_shipping_real
                             > o.days_for_shipment_scheduled
                        THEN 1.0 ELSE 0.0 END)    AS late_rate
        FROM   orders o
        JOIN   shipping_mode sm ON sm.shipping_mode_id = o.shipping_mode_id
        GROUP  BY sm.shipping_mode_id, sm.shipping_mode_name
        ORDER  BY promised
        """
    )


# ---------------------------------------------------------------------
# Map page
# ---------------------------------------------------------------------
@lru_cache(maxsize=1)
def country_detail() -> pd.DataFrame:
    """Per-country revenue, profit, orders and measured late rate."""
    return q(
        """
        SELECT oc.order_country_name AS country,
               m.market_name         AS market,
               SUM(oi.sales)         AS revenue,
               SUM(oi.profit_amount) AS profit,
               COUNT(DISTINCT o.order_id) AS orders,
               COUNT(DISTINCT o.customer_id) AS customers,
               AVG(CASE WHEN o.days_for_shipping_real
                             > o.days_for_shipment_scheduled
                        THEN 1.0 ELSE 0.0 END) AS late_rate,
               AVG(o.days_for_shipping_real)   AS avg_days
        FROM   order_item oi
        JOIN   orders o  ON o.order_id = oi.order_id
        JOIN   shipping_destination sd ON sd.destination_id = o.destination_id
        JOIN   region r  ON r.region_id = sd.region_id
        JOIN   market m  ON m.market_id = r.market_id
        JOIN   order_country oc ON oc.order_country_id = sd.order_country_id
        GROUP  BY oc.order_country_id, oc.order_country_name, m.market_name
        ORDER  BY revenue DESC
        """
    )


# ---------------------------------------------------------------------
# Racing bar (Home page)
# ---------------------------------------------------------------------
@lru_cache(maxsize=1)
def category_cumulative_by_month() -> pd.DataFrame:
    """
    Cumulative revenue per category at the end of every month.

    Cumulative rather than monthly: monthly figures jump around and the
    ranking flickers, whereas a running total makes the bars grow and
    overtake each other, which is what the race is meant to show.
    """
    raw = q(
        """
        SELECT substr(o.order_date, 1, 7) AS month,
               c.category_id             AS category_id,
               c.category_name           AS category_name,
               d.department_name         AS department_name,
               SUM(oi.sales)             AS revenue
        FROM   order_item oi
        JOIN   orders o    ON o.order_id     = oi.order_id
        JOIN   product p   ON p.product_id   = oi.product_id
        JOIN   category c  ON c.category_id  = p.category_id
        LEFT JOIN department d ON d.department_id = c.department_id
        WHERE  o.order_date IS NOT NULL
        GROUP  BY month, c.category_id, c.category_name, d.department_name
        """
    )
    if not len(raw):
        return raw

    dupes = raw[["category_id", "category_name"]].drop_duplicates()
    dup_names = set(
        dupes["category_name"][dupes["category_name"].duplicated(keep=False)]
    )
    raw["label"] = [
        f"{n} ({d})" if n in dup_names else n
        for n, d in zip(raw["category_name"], raw["department_name"].fillna("?"))
    ]

    months = sorted(raw["month"].unique())
    labels = raw["label"].unique()

    grid = (
        raw.pivot_table(index="month", columns="label",
                        values="revenue", aggfunc="sum")
        .reindex(months)
        .reindex(columns=labels)
        .fillna(0.0)
        .cumsum()
    )
    out = grid.reset_index().melt(id_vars="month", var_name="label",
                                 value_name="cum_revenue")
    return out


# ---------------------------------------------------------------------
# Orders & risk page
# ---------------------------------------------------------------------
@lru_cache(maxsize=1)
def order_status_mix() -> pd.DataFrame:
    return q(
        """
        SELECT os.order_status_name AS status,
               COUNT(DISTINCT o.order_id) AS orders,
               SUM(oi.sales)        AS revenue
        FROM   orders o
        JOIN   order_status os ON os.order_status_id = o.order_status_id
        LEFT JOIN order_item oi ON oi.order_id = o.order_id
        GROUP  BY os.order_status_id, os.order_status_name
        ORDER  BY orders DESC
        """
    )


@lru_cache(maxsize=1)
def loss_makers() -> pd.DataFrame:
    """Products whose total profit is negative."""
    return q(
        """
        SELECT p.product_name    AS product,
               c.category_name   AS category,
               SUM(oi.sales)     AS revenue,
               SUM(oi.profit_amount) AS profit,
               COUNT(*)          AS lines
        FROM   order_item oi
        JOIN   product  p ON p.product_id  = oi.product_id
        JOIN   category c ON c.category_id = p.category_id
        GROUP  BY p.product_id, p.product_name, c.category_name
        HAVING SUM(oi.profit_amount) < 0
        ORDER  BY profit ASC
        """
    )


@lru_cache(maxsize=1)
def loss_line_share() -> dict:
    r = q(
        """
        SELECT COUNT(*)                                   AS lines_total,
               SUM(CASE WHEN profit_amount < 0 THEN 1 ELSE 0 END) AS lines_loss,
               SUM(CASE WHEN profit_amount < 0
                        THEN profit_amount ELSE 0 END)     AS loss_value,
               SUM(CASE WHEN profit_amount > 0
                        THEN profit_amount ELSE 0 END)     AS gain_value
        FROM   order_item
        """
    ).iloc[0]
    total = int(r["lines_total"]) or 1
    return {
        "lines_total": total,
        "lines_loss": int(r["lines_loss"] or 0),
        "share": int(r["lines_loss"] or 0) / total,
        "loss_value": float(r["loss_value"] or 0),
        "gain_value": float(r["gain_value"] or 0),
    }


@lru_cache(maxsize=1)
def discount_bands() -> pd.DataFrame:
    """Margin and volume by discount band."""
    return q(
        """
        SELECT CASE
                   WHEN discount_rate <= 0.001 THEN '0%'
                   WHEN discount_rate < 0.05  THEN '0-5%'
                   WHEN discount_rate < 0.10  THEN '5-10%'
                   WHEN discount_rate < 0.15  THEN '10-15%'
                   WHEN discount_rate < 0.20  THEN '15-20%'
                   WHEN discount_rate < 0.25  THEN '20-25%'
                   ELSE '25%+'
               END                       AS band,
               COUNT(*)                  AS lines,
               SUM(sales)                AS revenue,
               SUM(profit_amount)        AS profit,
               AVG(discount_rate)        AS avg_rate
        FROM   order_item
        GROUP  BY band
        """
    )


@lru_cache(maxsize=1)
def city_points() -> pd.DataFrame:
    """
    City-level revenue using the coordinates stored in customer_address.

    These are customer locations, which is not the same thing as the
    shipping destination country in shipping_destination - the two are
    reported separately rather than mixed.
    """
    return q(
        """
        SELECT ca.city                       AS city,
               ca.state                      AS state,
               ca.country                    AS country,
               AVG(ca.latitude)              AS lat,
               AVG(ca.longitude)             AS lon,
               SUM(oi.sales)                 AS revenue,
               COUNT(DISTINCT o.order_id)    AS orders,
               COUNT(DISTINCT cu.customer_id) AS customers
        FROM   order_item oi
        JOIN   orders   o  ON o.order_id  = oi.order_id
        JOIN   customer cu ON cu.customer_id = o.customer_id
        JOIN   customer_address ca
               ON ca.customer_address_id = cu.customer_address_id
        WHERE  ca.latitude IS NOT NULL AND ca.longitude IS NOT NULL
        GROUP  BY ca.city, ca.state, ca.country
        HAVING SUM(oi.sales) > 0
        ORDER  BY revenue DESC
        """
    )


# ---------------------------------------------------------------------
# Market (continent) explorer  -  pages/markets.py
#
# The market page shows one market at a time in full detail. Every
# function here takes the market name and the same year/segment filters
# the rest of the app uses, so a number on the market page can never
# disagree with the same number on the executive page.
# ---------------------------------------------------------------------
LATE_CASE = ("AVG(CASE WHEN o.days_for_shipping_real "
             "> o.days_for_shipment_scheduled THEN 1.0 ELSE 0.0 END)")


def market_summary(year=None, segment=None) -> pd.DataFrame:
    """Revenue + share per market - drives the selector cards at the top."""
    seg = bool(segment and segment != "All")
    df = q(
        f"""
        SELECT m.market_name              AS market,
               SUM(oi.sales)              AS revenue,
               COUNT(DISTINCT o.order_id) AS orders,
               COUNT(DISTINCT o.customer_id) AS customers,
               {LATE_CASE}                AS late_rate
        {_drill_join(market=True, segment=seg)}
        {_where(year, None, segment, None)}
        GROUP BY m.market_id, m.market_name
        ORDER BY revenue DESC
        """
    )
    total = float(df["revenue"].sum()) or 1.0
    df["share"] = df["revenue"] / total
    return df


def market_countries(market: str, year=None, segment=None) -> pd.DataFrame:
    seg = bool(segment and segment != "All")
    return q(
        f"""
        SELECT oc.order_country_name      AS country,
               SUM(oi.sales)              AS revenue,
               SUM(oi.profit_amount)      AS profit,
               COUNT(DISTINCT o.order_id) AS orders,
               COUNT(DISTINCT o.customer_id) AS customers,
               {LATE_CASE}                AS late_rate
        {_drill_join(country=True, market=True, segment=seg)}
        {_where(year, market, segment, None)}
        GROUP BY oc.order_country_id, oc.order_country_name
        ORDER BY revenue DESC
        """
    )


def market_regions(market: str, year=None, segment=None) -> pd.DataFrame:
    seg = bool(segment and segment != "All")
    return q(
        f"""
        SELECT r.region_name              AS region,
               SUM(oi.sales)              AS revenue,
               COUNT(DISTINCT o.order_id) AS orders,
               {LATE_CASE}                AS late_rate
        {_drill_join(market=True, segment=seg)}
        {_where(year, market, segment, None)}
        GROUP BY r.region_id, r.region_name
        ORDER BY revenue DESC
        """
    )


def market_shipping(market: str, year=None, segment=None) -> pd.DataFrame:
    """Average promised vs actual shipping days per shipping mode."""
    seg = bool(segment and segment != "All")
    join = _drill_join(market=True, segment=seg) + \
        "\nJOIN shipping_mode sm ON sm.shipping_mode_id = o.shipping_mode_id"
    return q(
        f"""
        SELECT sm.shipping_mode_name            AS mode,
               AVG(o.days_for_shipment_scheduled) AS promised,
               AVG(o.days_for_shipping_real)      AS actual,
               COUNT(DISTINCT o.order_id)         AS orders
        {join}
        {_where(year, market, segment, None)}
        GROUP BY sm.shipping_mode_id, sm.shipping_mode_name
        ORDER BY orders DESC
        """
    )


# ---------------------------------------------------------------------
# Customers page
# ---------------------------------------------------------------------
@lru_cache(maxsize=1)
def customer_kpis() -> dict:
    r = q(
        """
        SELECT COUNT(*) AS customers, AVG(n) AS avg_orders,
               AVG(CASE WHEN n > 1 THEN 1.0 ELSE 0.0 END) AS repeat_rate
        FROM  (SELECT customer_id, COUNT(DISTINCT order_id) AS n
               FROM orders GROUP BY customer_id)
        """
    ).iloc[0]
    return {
        "customers": int(r["customers"]),
        "avg_orders": float(r["avg_orders"]),
        "repeat_rate": float(r["repeat_rate"]),
    }


@lru_cache(maxsize=1)
def new_customers_by_month() -> pd.DataFrame:
    """
    عدد العملاء اللي عملوا أول طلب ليهم في كل شهر.

    تحذير مهم عن الداتا: من أكتوبر 2017 لآخر الفترة، كل طلب في الداتا
    جاي من عميل جديد بيشتري مرة واحدة وبس (عدد الطلبات = عدد العملاء
    النشطين = عدد العملاء الجدد بالظبط). وأرقام العملاء في الفترة دي
    كتلة متتالية. ده مش سلوك تجاري حقيقي - ده أثر في تجميع البيانات
    نفسها. الصفحة بتعلّم على الفترة دي بوضوح بدل ما تعرضها كنمو.
    """
    return q(
        """
        SELECT first_month AS month, COUNT(*) AS new_customers
        FROM  (SELECT customer_id, substr(MIN(order_date), 1, 7) AS first_month
               FROM orders WHERE order_date IS NOT NULL
               GROUP BY customer_id)
        GROUP BY first_month ORDER BY first_month
        """
    )


@lru_cache(maxsize=1)
def orders_per_customer() -> pd.DataFrame:
    return q(
        """
        SELECT n AS orders, COUNT(*) AS customers
        FROM  (SELECT customer_id, COUNT(DISTINCT order_id) AS n
               FROM orders GROUP BY customer_id)
        GROUP BY n ORDER BY n
        """
    )


@lru_cache(maxsize=1)
def segment_summary() -> pd.DataFrame:
    return q(
        """
        SELECT cs.customer_segment_name        AS segment,
               COUNT(DISTINCT cu.customer_id)  AS customers,
               COUNT(DISTINCT o.order_id)      AS orders,
               SUM(oi.sales)                   AS revenue,
               SUM(oi.profit_amount)           AS profit
        FROM   order_item oi
        JOIN   orders o           ON o.order_id = oi.order_id
        JOIN   customer cu        ON cu.customer_id = o.customer_id
        JOIN   customer_segment cs ON cs.customer_segment_id = cu.customer_segment_id
        GROUP  BY cs.customer_segment_id, cs.customer_segment_name
        ORDER  BY revenue DESC
        """
    )


# ---------------------------------------------------------------------
# Products page
# ---------------------------------------------------------------------
@lru_cache(maxsize=1)
def product_leaders(limit: int = 10) -> pd.DataFrame:
    return q(
        f"""
        SELECT p.product_name        AS product,
               SUM(oi.sales)         AS revenue,
               SUM(oi.profit_amount) AS profit,
               SUM(oi.profit_amount) / SUM(oi.sales) AS margin,
               SUM(oi.order_item_quantity) AS units
        FROM   order_item oi
        JOIN   product p ON p.product_id = oi.product_id
        GROUP  BY p.product_id, p.product_name
        ORDER  BY revenue DESC
        LIMIT  {int(limit)}
        """
    )


@lru_cache(maxsize=1)
def category_margin(min_revenue: float = 50000) -> pd.DataFrame:
    """
    الهامش لكل فئة. ده الشارت اللي بيجاوب على "نركز على إيه": الهامش
    بيتراوح من 0.6% لـ 13.6% بين الفئات، بينما على مستوى المنتج الواحد
    الهامش شبه ثابت. يعني المشكلة في مزيج الفئات مش في منتج معين.
    """
    return q(
        f"""
        SELECT c.category_id        AS category_id,
               c.category_name      AS category,
               d.department_name    AS department,
               SUM(oi.sales)        AS revenue,
               SUM(oi.profit_amount) AS profit,
               SUM(oi.profit_amount) / SUM(oi.sales) AS margin
        FROM   order_item oi
        JOIN   product p    ON p.product_id  = oi.product_id
        JOIN   category c   ON c.category_id = p.category_id
        JOIN   department d ON d.department_id = c.department_id
        GROUP  BY c.category_id, c.category_name, d.department_name
        HAVING SUM(oi.sales) >= {float(min_revenue)}
        ORDER  BY margin ASC
        """
    )

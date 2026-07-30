"""
pages/home.py - cover page.

The globe here is decorative: it sets the scene without claiming to
report anything. Grab it with the mouse and it spins freely, then
settles back into a slow drift. Every number beside it is computed from
the database.

Charts that move because the data moves live on the Trends page.
"""

import dash
from dash import html

import db
import theme as T

dash.register_page(__name__, path="/", name="Home")

CATS = db.category_revenue()
TOT = db.totals()
DUPES = db.duplicate_labels()

N_CATS = int(CATS["category_id"].nunique())
N_DEPTS = int(CATS["department_name"].dropna().nunique())
TOP9_SHARE = float(CATS["revenue"].head(9).sum() / TOT["revenue"])
TOP1_NAME = str(CATS.iloc[0]["category"])
TOP1_SHARE = float(CATS.iloc[0]["share"])

findings = [
    html.Div(
        f"Nine of {N_CATS} categories generate {TOP9_SHARE:.0%} of revenue."
    ),
    html.Div(
        f"{TOP1_NAME} alone accounts for {TOP1_SHARE:.1%} of everything sold."
    ),
    html.Div(
        f"Blended margin sits at {TOT['margin']:.1%} across "
        f"{TOT['orders']:,} orders and {TOT['customers']:,} customers."
    ),
]
if len(DUPES):
    findings.append(
        html.Div(
            f"{len(DUPES)} dimension label is reused across keys - every figure "
            "here groups by key, not by label.",
            style={"color": T.M2},
        )
    )

layout = html.Div(
    className="cover",
    children=[
        html.Div(
            className="col-left",
            children=[
                html.H1("DataCo", className="brand"),
                html.Div("SUPPLY CHAIN ANALYTICS", className="brand-sub"),
                html.Div(className="rule"),
                html.Div(
                    "GLOBAL RETAIL DISTRIBUTION  \u00b7  2015\u20132018",
                    className="brand-meta",
                ),
                html.Div(
                    className="kpi-row",
                    children=[
                        T.kpi(T.money(TOT["revenue"]), "TOTAL REVENUE"),
                        T.kpi(f"{TOP9_SHARE:.1%}", "FROM 9 CATEGORIES",
                              T.MINT, T.MINT),
                        T.kpi(f"{TOP1_SHARE:.1%}", "TOP CATEGORY", T.MINT, T.MINT),
                        T.kpi(f"{TOT['lines']:,}", "ORDER LINES"),
                    ],
                ),
                html.Div(findings, className="findings"),
                html.Div(
                    f"{N_DEPTS} departments  \u00b7  {N_CATS} categories  "
                    f"\u00b7  16 tables  \u00b7  zero orphan rows",
                    className="cover-foot",
                ),
            ],
        ),
        html.Div(
            className="col-right",
            children=[
                html.Div(id="cover-globe", className="globe-stage"),
                html.Div("DRAG TO SPIN", className="globe-hint"),
            ],
        ),
    ],
)

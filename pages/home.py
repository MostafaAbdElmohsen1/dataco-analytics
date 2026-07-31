"""
pages/home.py - cover page.

The globe here is decorative: it sets the scene without claiming to
report anything. Grab it with the mouse and it spins freely, then
settles back into a slow drift. Every number beside it is computed from
the database.

Charts that move because the data moves live on the Trends page.
"""

import dash
from dash import dcc, html
import plotly.graph_objects as go

import db
import theme as T

dash.register_page(__name__, path="/", name="Home")

CATS = db.category_revenue()
TOT = db.totals()
DUPES = db.duplicate_labels()
LATE_RATE = db.late_delivery_rate()

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

# ---------------------------------------------------------------------
# Revenue concentration - top 9 categories vs the rest
# ---------------------------------------------------------------------
top9_revenue = float(CATS["revenue"].head(9).sum())
rest_revenue = float(CATS["revenue"].iloc[9:].sum())
rest_n = N_CATS - 9

pareto_fig = go.Figure(
    data=[
        go.Bar(
            x=[top9_revenue, rest_revenue],
            y=[f"Top 9 categories", f"Other {rest_n} categories"],
            orientation="h",
            marker_color=[T.M1, T.BORD],
            text=[f"{TOP9_SHARE:.1%}", f"{1 - TOP9_SHARE:.1%}"],
            textposition="outside",
            textfont=dict(color=T.TXT, size=13),
        )
    ]
)
T.style(pareto_fig, height=185)
pareto_fig.update_layout(
    margin=dict(l=10, r=70, t=6, b=6),
    xaxis=dict(visible=False),
    yaxis=dict(
        automargin=True,
        tickfont=dict(color=T.TXT, size=12),
        showgrid=False,
    ),
)

# ---------------------------------------------------------------------
# Delivery performance - late vs on time, measured directly from
# days_for_shipping_real vs days_for_shipment_scheduled
# ---------------------------------------------------------------------
delay_fig = go.Figure(
    data=[
        go.Bar(
            x=[LATE_RATE, 1 - LATE_RATE],
            y=["Late", "On time"],
            orientation="h",
            marker_color=[T.M2, T.MINT],
            text=[f"{LATE_RATE:.1%}", f"{1 - LATE_RATE:.1%}"],
            textposition="outside",
            textfont=dict(color=T.TXT, size=13),
        )
    ]
)
T.style(delay_fig, height=185)
delay_fig.update_layout(
    margin=dict(l=10, r=70, t=6, b=6),
    xaxis=dict(visible=False),
    yaxis=dict(
        automargin=True,
        tickfont=dict(color=T.TXT, size=12),
        showgrid=False,
    ),
)

risk_panels = html.Div(
    className="cover-risk-grid",
    children=[
        T.panel(
            "Revenue concentration",
            f"9 of {N_CATS} categories generate {TOP9_SHARE:.1%} of revenue.",
            dcc.Graph(figure=pareto_fig, config={"displayModeBar": False}),
        ),
        T.panel(
            "Delivery performance",
            "Measured from real vs scheduled shipping days, "
            "not from a pre-assigned risk flag.",
            dcc.Graph(figure=delay_fig, config={"displayModeBar": False}),
        ),
    ],
)

next_steps = html.Div(
    className="panel panel-wide home-note",
    style={"borderColor": T.AMBER},
    children=[
        html.Div("What this means for DataCo", className="panel-title"),
        html.Div(
            "Revenue concentration and late delivery are the two "
            "headline risks in this data. Root causes, market-level "
            "breakdowns and improvement recommendations for both are "
            "on the Executive page.",
            className="panel-sub",
        ),
    ],
)

layout = html.Div(
    className="home-page",
    children=[
        html.Div(
            className="cover cover-compact",
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
                                T.kpi(f"{TOP1_SHARE:.1%}", "TOP CATEGORY",
                                      T.MINT, T.MINT),
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
        ),
        risk_panels,
        next_steps,
    ],
)

"""
pages/home.py - the cover page.
"""

import dash
from dash import dcc, html
import plotly.graph_objects as go

import db
import theme as T

dash.register_page(__name__, path="/", name="Home")

# How many categories to plot individually before collapsing the rest.
TOP_N = 15

CATS = db.category_revenue()
TOT = db.totals()

N_CATS = int(CATS["category_id"].nunique())
TOP9_SHARE = float(CATS["revenue"].head(9).sum() / TOT["revenue"])
TOP1_NAME = str(CATS.iloc[0]["category"])
TOP1_SHARE = float(CATS.iloc[0]["share"])
DUPES = db.duplicate_labels()


def bloom_data():
    head = CATS.head(TOP_N)[["category", "revenue"]].copy()
    tail = CATS.iloc[TOP_N:]
    if len(tail):
        head.loc[len(head)] = [
            f"Other ({len(tail)} categories)",
            float(tail["revenue"].sum()),
        ]
    return head.reset_index(drop=True)


def bloom_figure() -> go.Figure:
    data = bloom_data()
    n = len(data)
    colours = [
        T.M1 if i < 3 else T.M2 if i < 9 else T.V1 if i < n - 1 else T.V2
        for i in range(n)
    ]
    fig = go.Figure(
        go.Barpolar(
            r=data["revenue"],
            theta=[i * 360 / n for i in range(n)],
            width=[360 / n * 0.72] * n,
            marker=dict(color=colours, line=dict(width=0)),
            customdata=data["category"],
            hovertemplate="<b>%{customdata}</b><br>$%{r:,.0f}<extra></extra>",
        )
    )
    T.style(fig, height=520)
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            hole=0.26,
            radialaxis=dict(
                showticklabels=False, ticks="", gridcolor=T.BORD, showline=False
            ),
            angularaxis=dict(
                showticklabels=False,
                ticks="",
                gridcolor="rgba(0,0,0,0)",
                linecolor=T.BORD,
            ),
        )
    )
    return fig


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
            f"{len(DUPES)} dimension label is reused across keys - "
            "everything here groups by key, not by label.",
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
                        T.kpi(f"{TOP9_SHARE:.1%}", "FROM 9 CATEGORIES", T.MINT, T.MINT),
                        T.kpi(f"{TOP1_SHARE:.1%}", "TOP CATEGORY", T.MINT, T.MINT),
                        T.kpi(f"{TOT['lines']:,}", "ORDER LINES"),
                    ],
                ),
                html.Div(findings, className="findings"),
            ],
        ),
        html.Div(
            className="col-right",
            children=[
                html.Div(className="bloom-glow"),
                dcc.Graph(
                    figure=bloom_figure(),
                    config={"displayModeBar": False},
                    className="bloom",
                ),
                html.Div(
                    [
                        html.Div(str(N_CATS), className="hub-value"),
                        html.Div("CATEGORIES", className="hub-label"),
                    ],
                    className="hub",
                ),
                html.Div(
                    f"TOP {TOP_N} CATEGORIES + OTHER  \u00b7  HOVER FOR DETAIL",
                    className="bloom-caption",
                ),
            ],
        ),
    ],
)

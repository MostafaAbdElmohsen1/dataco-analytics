"""
pages/home.py - the cover page.
"""

import dash
from dash import dcc, html
import plotly.graph_objects as go

import db
import theme as T

dash.register_page(__name__, path="/", name="Home")

CATS = db.category_revenue()
TOT = db.totals()

N_CATS = int(CATS["category_id"].nunique())
TOP9_SHARE = float(CATS["revenue"].head(9).sum() / TOT["revenue"])
TOP1_NAME = str(CATS.iloc[0]["category"])
TOP1_SHARE = float(CATS.iloc[0]["share"])
DUPES = db.duplicate_labels()


def treemap() -> go.Figure:
    """
    Department -> category treemap.

    A treemap suits this data far better than a radial chart: revenue is
    extremely concentrated, so on a radial scale most categories collapse
    into invisible slivers. Area encoding keeps every category readable
    while still showing the concentration.
    """
    d = CATS.copy()
    d["department_name"] = d["department_name"].fillna("Unassigned")

    labels, parents, values, kinds = [], [], [], []

    for dept, g in d.groupby("department_name", sort=False):
        labels.append(dept); parents.append(""); values.append(float(g["revenue"].sum()))
        kinds.append("Department")

    for _, r in d.iterrows():
        labels.append(r["category_name"])
        parents.append(r["department_name"])
        values.append(float(r["revenue"]))
        kinds.append("Category")

    fig = go.Figure(
        go.Treemap(
            labels=labels, parents=parents, values=values,
            customdata=kinds,
            branchvalues="total",
            tiling=dict(packing="squarify", pad=2),
            marker=dict(
                colors=values,
                colorscale=[[0, "#241436"], [0.25, T.V2], [0.55, T.V1],
                            [0.8, T.M2], [1, T.M1]],
                line=dict(color=T.BG, width=1.6),
                cornerradius=6,
            ),
            textinfo="label+percent root",
            textfont=dict(size=13, color="#ffffff",
                          family="Segoe UI, Arial, sans-serif"),
            hovertemplate=(
                "<b>%{label}</b><br>%{customdata}<br>"
                "%{value:$,.0f}<br>%{percentRoot:.1%} of revenue<extra></extra>"
            ),
            pathbar=dict(visible=True, thickness=18),
        )
    )
    T.style(fig, height=520)
    fig.update_layout(margin=dict(l=0, r=0, t=22, b=0))
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
                    figure=treemap(),
                    config={"displayModeBar": False},
                    className="bloom",
                ),
                html.Div(
                    f"{len(CATS['department_name'].dropna().unique())} DEPARTMENTS  "
                    f"\u00b7  {N_CATS} CATEGORIES  \u00b7  AREA IS REVENUE  "
                    f"\u00b7  CLICK TO OPEN A DEPARTMENT",
                    className="bloom-caption",
                ),
            ],
        ),
    ],
)

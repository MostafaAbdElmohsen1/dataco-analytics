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


RACE = db.category_cumulative_by_month()
TOP_N_RACE = 12


def race_figure() -> go.Figure:
    """
    Racing bar: cumulative revenue per category, one frame per month.

    Plotly keeps categorical axes in the order given, so each frame also
    sets yaxis.categoryarray. Without that the bars would change length
    but never change places, which defeats the point.
    """
    if not len(RACE):
        return T.style(go.Figure(), height=520)

    months = sorted(RACE["month"].unique())
    xmax = float(RACE["cum_revenue"].max()) * 1.16

    def slice_month(mth):
        d = (
            RACE[RACE["month"] == mth]
            .nlargest(TOP_N_RACE, "cum_revenue")
            .sort_values("cum_revenue")
        )
        return d

    def bar(d):
        top = float(d["cum_revenue"].max()) or 1.0
        colours = [
            T.M1 if v / top > 0.75 else T.M2 if v / top > 0.45
            else T.V1 if v / top > 0.2 else T.V2
            for v in d["cum_revenue"]
        ]
        return go.Bar(
            x=d["cum_revenue"], y=d["label"], orientation="h",
            marker=dict(color=colours, line=dict(width=0)),
            text=[T.money(v) for v in d["cum_revenue"]],
            textposition="outside",
            textfont=dict(size=12, color=T.DIM),
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:$,.0f} cumulative<extra></extra>",
        )

    first = slice_month(months[0])
    fig = go.Figure(
        data=[bar(first)],
        frames=[
            go.Frame(
                data=[bar(slice_month(m))],
                name=m,
                layout=go.Layout(
                    yaxis=dict(categoryorder="array",
                               categoryarray=list(slice_month(m)["label"])),
                    annotations=[
                        dict(xref="paper", yref="paper", x=0.99, y=0.06,
                             xanchor="right", showarrow=False, text=m,
                             font=dict(size=44, color="rgba(255,0,128,.30)",
                                       family="Segoe UI, Arial, sans-serif")),
                    ],
                ),
            )
            for m in months
        ],
    )

    T.style(fig, height=520)
    fig.update_layout(
        margin=dict(l=8, r=104, t=10, b=70),
        xaxis=dict(range=[0, xmax], gridcolor=T.BORD, zeroline=False,
                   linecolor="rgba(0,0,0,0)", tickprefix="$",
                   tickformat="~s", tickfont=dict(size=11)),
        yaxis=dict(categoryorder="array",
                   categoryarray=list(first["label"]),
                   gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)",
                   automargin=True, tickfont=dict(size=12)),
        annotations=[
            dict(xref="paper", yref="paper", x=0.99, y=0.06,
                 xanchor="right", showarrow=False, text=months[0],
                 font=dict(size=44, color="rgba(255,0,128,.30)",
                           family="Segoe UI, Arial, sans-serif")),
        ],
        updatemenus=[dict(
            type="buttons", direction="left",
            x=0, y=-0.14, xanchor="left", yanchor="top",
            pad=dict(t=0, r=8),
            bgcolor="rgba(21,12,34,.9)",
            bordercolor=T.BORD, borderwidth=1,
            font=dict(color=T.TXT, size=12),
            buttons=[
                dict(label="  Play  ", method="animate",
                     args=[None, dict(
                         frame=dict(duration=420, redraw=True),
                         transition=dict(duration=340, easing="cubic-in-out"),
                         fromcurrent=True, mode="immediate")]),
                dict(label="  Pause  ", method="animate",
                     args=[[None], dict(
                         frame=dict(duration=0, redraw=False),
                         mode="immediate")]),
            ],
        )],
        sliders=[dict(
            active=0, x=0.14, y=-0.10, len=0.86,
            pad=dict(t=6, b=6),
            currentvalue=dict(prefix="", visible=False),
            bgcolor=T.BORD, bordercolor="rgba(0,0,0,0)",
            activebgcolor=T.M1, tickcolor=T.BORD,
            font=dict(color=T.DIM, size=10),
            steps=[
                dict(label=(m if m.endswith(("-01", "-07")) else ""),
                     method="animate",
                     args=[[m], dict(frame=dict(duration=260, redraw=True),
                                     transition=dict(duration=220),
                                     mode="immediate")])
                for m in months
            ],
        )],
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
                    figure=race_figure(),
                    config={"displayModeBar": False},
                    className="bloom",
                ),
                html.Div(
                    f"CUMULATIVE REVENUE  \u00b7  TOP {TOP_N_RACE} OF {N_CATS} "
                    f"CATEGORIES  \u00b7  PRESS PLAY",
                    className="bloom-caption",
                ),
            ],
        ),
    ],
)

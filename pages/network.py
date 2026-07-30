"""
pages/network.py - global distribution network.

The globe is a plain <canvas> driven by assets/globe.js, which redraws
every frame with requestAnimationFrame. Rotation is continuous, not
stepped, and there is no external library involved.
"""

import dash
from dash import dcc, html
import plotly.graph_objects as go

import db
import geo
import theme as T

dash.register_page(__name__, path="/network", name="Network")

COUNTRIES = db.country_revenue()
TOT = db.totals()

MARKETS = db.q(
    """
    SELECT m.market_name              AS market,
           SUM(oi.sales)              AS revenue,
           COUNT(DISTINCT o.order_id) AS orders
    FROM   order_item oi
    JOIN   orders o  ON o.order_id = oi.order_id
    JOIN   shipping_destination sd ON sd.destination_id = o.destination_id
    JOIN   region r  ON r.region_id  = sd.region_id
    JOIN   market m  ON m.market_id  = r.market_id
    GROUP  BY m.market_id, m.market_name
    ORDER  BY revenue DESC
    """
)

N_COUNTRIES = int(COUNTRIES["country_id"].nunique())


def globe_points(n: int = 14) -> str:
    """Encode the top mapped countries as name~lat~lon~weight, pipe separated."""
    rows, mx = [], None
    for _, r in COUNTRIES.iterrows():
        ll = geo.lookup(r["country"])
        if ll is None:
            continue
        if mx is None:
            mx = float(r["revenue"])
        rows.append((str(r["country"]), ll[0], ll[1],
                     float(r["revenue"]) / mx, float(r["revenue"])))
        if len(rows) >= n:
            break
    return "|".join(f"{a}~{b}~{c}~{d:.4f}~{e:.0f}" for a, b, c, d, e in rows)


GLOBE_POINTS = globe_points()
N_MAPPED = len(GLOBE_POINTS.split("|")) if GLOBE_POINTS else 0
TOP10_SHARE = float(COUNTRIES["revenue"].head(10).sum() / COUNTRIES["revenue"].sum())


def market_donut() -> go.Figure:
    fig = go.Figure(
        go.Pie(
            labels=MARKETS["market"],
            values=MARKETS["revenue"],
            hole=0.62,
            sort=False,
            marker=dict(colors=T.CAT[: len(MARKETS)], line=dict(color=T.BG, width=2)),
            textinfo="percent",
            textfont=dict(size=12, color=T.TXT),
            hovertemplate="<b>%{label}</b><br>%{value:$,.0f}<br>%{percent}<extra></extra>",
        )
    )
    T.style(fig, height=300)
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="v", x=1.02, y=0.5, xanchor="left", yanchor="middle",
            font=dict(size=12, color=T.DIM),
        ),
        margin=dict(l=8, r=118, t=8, b=8),
    )
    return fig


def country_bars() -> go.Figure:
    d = COUNTRIES.head(12)
    fig = go.Figure(
        go.Bar(
            x=d["revenue"], y=d["country"], orientation="h",
            marker=dict(color=T.MINT, opacity=0.85, line=dict(width=0)),
            text=[T.money(v) for v in d["revenue"]],
            textposition="outside",
            textfont=dict(size=11, color=T.DIM),
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:$,.0f}<extra></extra>",
        )
    )
    T.style(fig, height=400)
    fig.update_layout(
        margin=dict(l=8, r=72, t=8, b=36),
        yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)",
                   linecolor="rgba(0,0,0,0)", automargin=True,
                   tickfont=dict(size=12)),
        xaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickprefix="$", tickformat="~s", tickfont=dict(size=11)),
    )
    return fig


layout = html.Div(
    className="page",
    children=[
        T.page_head(
            "Global distribution network",
            f"DataCo ships to {N_COUNTRIES} countries across "
            f"{len(MARKETS)} markets. The globe below is illustrative; "
            "every figure beside it comes from the database.",
        ),
        html.Div(
            className="kpi-row kpi-row-tight",
            children=[
                T.kpi(f"{N_COUNTRIES}", "DESTINATION COUNTRIES"),
                T.kpi(f"{len(MARKETS)}", "MARKETS", T.MINT, T.MINT),
                T.kpi(f"{TOP10_SHARE:.1%}", "FROM TOP 10 COUNTRIES", T.MINT, T.MINT),
                T.kpi(f"{TOT['orders']:,}", "ORDERS SHIPPED"),
            ],
        ),
        html.Div(
            className="panel-grid",
            children=[
                T.panel(
                    "Network in motion",
                    "One turn every 30 seconds. A shipment travels between the highest-revenue countries, one leg at a time.",
                    html.Div(
                        id="globe-data",
                        className="globe-wrap",
                        **{"data-points": GLOBE_POINTS},
                    ),
                    html.Div(
                        f"Hover a bubble for its revenue \u2014 rotation pauses "
                        f"while you read. Top {N_MAPPED} countries shown.",
                        className="globe-note",
                    ),
                ),
                T.panel(
                    "Revenue by market",
                    "Share of revenue across the five DataCo markets.",
                    dcc.Graph(figure=market_donut(), config={"displayModeBar": False}),
                ),
                T.panel(
                    "Top twelve destination countries",
                    f"Out of {N_COUNTRIES} countries served.",
                    dcc.Graph(figure=country_bars(), config={"displayModeBar": False}),
                    wide=True,
                ),
            ],
        ),
        html.Div(
            className="note",
            children=[
                html.Strong("On the globe. "),
                "Bubble positions and sizes come from the data: each marker is a "
                "destination country, sized by its revenue. The arcs between them "
                "are illustrative - the dataset records where orders went, not "
                "where they shipped from, so no real origin exists to draw.",
            ],
        ),
    ],
)

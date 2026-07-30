"""
pages/network.py - distribution network structure and flow.

Two charts do the work here:

  Sunburst  - the real three-level hierarchy in the data
              (market -> region -> country), area = revenue.
  Sankey    - where orders actually go and how they end up
              (market -> shipping mode -> measured outcome).

The outcome band is computed from days_for_shipping_real against
days_for_shipment_scheduled, so it is a measured result rather than the
late_delivery_risk_flag column, which is only a risk marker.
"""

import dash
from dash import dcc, html
import plotly.graph_objects as go

import db
import theme as T

dash.register_page(__name__, path="/network", name="Network")

HIER = db.market_region_country()
FLOW = db.flow_market_mode_outcome()
MODES = db.mode_promise()

N_COUNTRIES = int(HIER["country"].nunique())
N_REGIONS = int(HIER["region"].nunique())
N_MARKETS = int(HIER["market"].nunique())
LATE_RATE = float(
    FLOW.loc[FLOW["outcome"] == "Late", "orders"].sum() / FLOW["orders"].sum()
)


def sunburst() -> go.Figure:
    labels, parents, values, custom = [], [], [], []

    for mk, g in HIER.groupby("market", sort=False):
        labels.append(mk); parents.append(""); values.append(float(g["revenue"].sum()))
        custom.append("Market")

    for (mk, rg), g in HIER.groupby(["market", "region"], sort=False):
        labels.append(rg); parents.append(mk); values.append(float(g["revenue"].sum()))
        custom.append("Region")

    for _, r in HIER.iterrows():
        labels.append(r["country"]); parents.append(r["region"])
        values.append(float(r["revenue"])); custom.append("Country")

    fig = go.Figure(
        go.Sunburst(
            labels=labels, parents=parents, values=values,
            customdata=custom,
            branchvalues="total",
            maxdepth=2,
            insidetextorientation="radial",
            marker=dict(
                colors=values,
                colorscale=[[0, "#3B1B57"], [0.35, T.V2], [0.7, T.M2], [1, T.M1]],
                line=dict(color=T.BG, width=1.4),
            ),
            hovertemplate=(
                "<b>%{label}</b><br>%{customdata}<br>"
                "%{value:$,.0f}<br>%{percentRoot:.1%} of total<extra></extra>"
            ),
        )
    )
    T.style(fig, height=440)
    fig.update_layout(margin=dict(l=6, r=6, t=6, b=6),
                      font=dict(color=T.TXT, size=12))
    return fig


def sankey() -> go.Figure:
    markets = list(FLOW["market"].drop_duplicates())
    modes = list(FLOW["mode"].drop_duplicates())
    order = ["Early", "On time", "Late"]
    outcomes = [o for o in order if o in set(FLOW["outcome"])]

    nodes = markets + modes + outcomes
    idx = {n: i for i, n in enumerate(nodes)}

    node_colours = (
        [T.V1] * len(markets) + [T.M2] * len(modes)
        + [T.M1 if o == "Late" else T.MINT for o in outcomes]
    )

    src, tgt, val, lcol = [], [], [], []

    a = FLOW.groupby(["market", "mode"], as_index=False)["orders"].sum()
    for _, r in a.iterrows():
        src.append(idx[r["market"]]); tgt.append(idx[r["mode"]])
        val.append(int(r["orders"])); lcol.append("rgba(177,74,237,.26)")

    b = FLOW.groupby(["mode", "outcome"], as_index=False)["orders"].sum()
    for _, r in b.iterrows():
        src.append(idx[r["mode"]]); tgt.append(idx[r["outcome"]])
        val.append(int(r["orders"]))
        lcol.append("rgba(255,0,128,.30)" if r["outcome"] == "Late"
                    else "rgba(0,229,160,.22)")

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                label=nodes, pad=17, thickness=17,
                color=node_colours,
                line=dict(color=T.BG, width=0.5),
                hovertemplate="<b>%{label}</b><br>%{value:,} orders<extra></extra>",
            ),
            link=dict(
                source=src, target=tgt, value=val, color=lcol,
                hovertemplate="%{source.label} to %{target.label}"
                              "<br>%{value:,} orders<extra></extra>",
            ),
        )
    )
    T.style(fig, height=470)
    fig.update_layout(margin=dict(l=6, r=6, t=6, b=6),
                      font=dict(color=T.TXT, size=12.5))
    return fig


def promise_gap() -> go.Figure:
    d = MODES.copy()
    fig = go.Figure()
    fig.add_bar(
        y=d["mode"], x=d["promised"], orientation="h", name="Promised",
        marker=dict(color=T.V2, line=dict(width=0)),
        hovertemplate="<b>%{y}</b><br>promised %{x:.1f} days<extra></extra>",
    )
    fig.add_bar(
        y=d["mode"], x=d["actual"], orientation="h", name="Actual",
        marker=dict(color=T.M1, line=dict(width=0)),
        hovertemplate="<b>%{y}</b><br>actual %{x:.1f} days<extra></extra>",
    )
    for _, r in d.iterrows():
        fig.add_annotation(
            x=max(r["promised"], r["actual"]) + 0.22, y=r["mode"],
            text=f"{r['late_rate']:.0%} late", showarrow=False,
            xanchor="left", font=dict(color=T.DIM, size=11),
        )
    T.style(fig, height=300)
    fig.update_layout(
        barmode="group", bargap=0.28, bargroupgap=0.08,
        showlegend=True,
        legend=dict(orientation="h", y=1.16, x=0, font=dict(color=T.DIM, size=11.5)),
        margin=dict(l=8, r=96, t=34, b=36),
        yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)",
                   linecolor="rgba(0,0,0,0)", automargin=True,
                   tickfont=dict(size=12)),
        xaxis=dict(title=dict(text="days", font=dict(size=11, color=T.DIM)),
                   gridcolor=T.BORD, zeroline=False,
                   linecolor="rgba(0,0,0,0)", tickfont=dict(size=11)),
    )
    return fig


layout = html.Div(
    className="page",
    children=[
        T.page_head(
            "Distribution network",
            f"{N_MARKETS} markets, {N_REGIONS} regions, {N_COUNTRIES} destination "
            "countries. The flow diagram traces how orders reach customers and "
            "whether they arrive on time.",
        ),
        html.Div(
            className="kpi-row kpi-row-tight",
            children=[
                T.kpi(f"{N_MARKETS}", "MARKETS"),
                T.kpi(f"{N_REGIONS}", "REGIONS"),
                T.kpi(f"{N_COUNTRIES}", "COUNTRIES", T.MINT, T.MINT),
                T.kpi(f"{LATE_RATE:.1%}", "ORDERS ARRIVE LATE", T.M1, T.M1),
            ],
        ),
        html.Div(
            className="panel-grid",
            children=[
                T.panel(
                    "Revenue hierarchy",
                    "Market, then region, then country. Ring area is revenue - "
                    "click any ring to open it, click the centre to go back.",
                    dcc.Graph(figure=sunburst(), config={"displayModeBar": False}),
                ),
                T.panel(
                    "Promise against delivery",
                    "Average days promised next to average days actually taken, "
                    "per shipping mode.",
                    dcc.Graph(figure=promise_gap(), config={"displayModeBar": False}),
                ),
                T.panel(
                    "Order flow and outcome",
                    "Every order runs left to right: which market it came from, "
                    "which shipping mode carried it, and whether it beat, met or "
                    "missed the promised date. Band thickness is order count.",
                    dcc.Graph(figure=sankey(), config={"displayModeBar": False}),
                    wide=True,
                ),
            ],
        ),
        html.Div(
            className="note",
            children=[
                html.Strong("How late is measured. "),
                "An order counts as late when days_for_shipping_real exceeds "
                "days_for_shipment_scheduled. The dataset also carries a "
                "late_delivery_risk_flag column, but that marks predicted risk, "
                "not what happened, so it is not used for any figure here.",
            ],
        ),
    ],
)

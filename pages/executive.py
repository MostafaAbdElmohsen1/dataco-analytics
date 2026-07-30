"""
pages/executive.py - executive overview with interactive filters.

Three dropdowns (year, market, customer segment) drive every KPI and
chart on the page through a single callback.
"""

import dash
from dash import dcc, html, callback, Input, Output
import plotly.graph_objects as go

import db
import theme as T

dash.register_page(__name__, path="/executive", name="Executive")

OPTS = db.filter_options()


YEARS = ["All"] + [str(v) for v in OPTS["years"]]
MARKETS = ["All"] + [str(v) for v in OPTS["markets"]]
SEGMENTS = ["All"] + [str(v) for v in OPTS["segments"]]

T.register_pill_group("year", YEARS)
T.register_pill_group("market", MARKETS)
T.register_pill_group("segment", SEGMENTS)


layout = html.Div(
    className="page",
    children=[
        T.page_head(
            "Executive overview",
            "Revenue, margin and delivery performance across the DataCo network. "
            "Every figure below responds to the filters.",
        ),
        html.Div(
            className="filter-bar filter-sticky",
            children=[
                html.Div(
                    className="filter-grid",
                    children=[
                        T.pill_group("year", "YEAR", YEARS),
                        T.pill_group("market", "MARKET", MARKETS),
                        T.pill_group("segment", "CUSTOMER SEGMENT", SEGMENTS),
                    ],
                ),
                html.Div(
                    className="filter-foot",
                    children=[
                        html.Div(id="filter-summary", className="filter-summary"),
                        html.Button(
                            "Clear all filters",
                            id="f-reset",
                            n_clicks=0,
                            className="btn-reset",
                        ),
                    ],
                ),
            ],
        ),
        html.Div(id="exec-kpis", className="kpi-row kpi-row-tight"),
        html.Div(
            className="panel-grid",
            children=[
                T.panel(
                    "Monthly revenue and profit",
                    "Revenue bars with profit overlaid. Data ends mid-January 2018, so the final bar is a partial month.",
                    dcc.Graph(id="g-trend", config={"displayModeBar": False}),
                    wide=True,
                ),
                T.panel(
                    "Where the revenue concentrates",
                    "Bars are categories, largest first. The line is the running "
                    "total, so you can read straight off it how few categories "
                    "cover most of the revenue.",
                    dcc.Graph(id="g-pareto", config={"displayModeBar": False}),
                    wide=True,
                ),
                T.panel(
                    "Shipped later than promised",
                    "Actual shipping days minus promised days, per order. "
                    "Right of zero means the order shipped late.",
                    dcc.Graph(id="g-delay", config={"displayModeBar": False}),
                ),
                T.panel(
                    "Top countries by revenue",
                    "Highest twelve destination countries.",
                    dcc.Graph(id="g-country", config={"displayModeBar": False}),
                ),
                T.panel(
                    "Top ten products",
                    "Ranked by revenue, with margin per product.",
                    html.Div(id="t-products"),
                    wide=True,
                ),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------
@callback(
    Output(T.store_id("year"), "data", allow_duplicate=True),
    Output(T.store_id("market"), "data", allow_duplicate=True),
    Output(T.store_id("segment"), "data", allow_duplicate=True),
    Input("f-reset", "n_clicks"),
    prevent_initial_call=True,
)
def reset_filters(_):
    return "All", "All", "All"


@callback(
    Output("exec-kpis", "children"),
    Output("filter-summary", "children"),
    Output("g-trend", "figure"),
    Output("g-pareto", "figure"),
    Output("g-delay", "figure"),
    Output("g-country", "figure"),
    Output("t-products", "children"),
    Input(T.store_id("year"), "data"),
    Input(T.store_id("market"), "data"),
    Input(T.store_id("segment"), "data"),
)
def refresh(year, market, segment):
    k = db.exec_kpis(year, market, segment)

    kpis = [
        T.kpi(T.money(k["revenue"]), "REVENUE"),
        T.kpi(T.money(k["profit"]), "PROFIT", T.MINT, T.MINT),
        T.kpi(f"{k['margin']:.1%}", "MARGIN", T.MINT, T.MINT),
        T.kpi(f"{k['orders']:,}", "ORDERS"),
        T.kpi(T.money(k["aov"]), "AVG ORDER VALUE"),
        T.kpi(
            f"{k['on_time']:.1%}",
            "NOT FLAGGED LATE",
            T.MINT if k["on_time"] >= 0.5 else T.AMBER,
            T.MINT if k["on_time"] >= 0.5 else T.AMBER,
        ),
    ]

    # ---- trend ----
    m = db.exec_monthly(year, market, segment)
    trend = go.Figure()
    trend.add_bar(
        x=m["month"], y=m["revenue"], name="Revenue",
        marker=dict(color=T.V2, line=dict(width=0)),
        hovertemplate="<b>%{y:$,.0f}</b><extra>Revenue</extra>",
    )
    trend.add_scatter(
        x=m["month"], y=m["profit"], name="Profit", mode="lines+markers",
        line=dict(color=T.M1, width=2.6),
        marker=dict(size=5, color=T.M1),
        hovertemplate="<b>%{y:$,.0f}</b><extra>Profit</extra>",
    )
    T.style(trend, height=250, hovermode="x unified", bargap=0.30)
    trend.update_layout(
        margin=dict(l=70, r=16, t=8, b=44),
        xaxis=dict(type="date", gridcolor="rgba(0,0,0,0)", linecolor=T.BORD,
                   tickangle=0, tickfont=dict(size=11),
                   dtick="M3", tickformat="%b<br>%Y"),
        yaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickprefix="$", tickformat="~s", tickfont=dict(size=11)),
    )

    # ---- pareto ----
    pr = db.category_pareto(year, market, segment)
    pareto = go.Figure()
    if len(pr):
        show = pr.head(20)
        pareto.add_bar(
            x=show["category"], y=show["revenue"],
            marker=dict(
                color=[T.M1 if v <= 0.884 else T.V2 for v in show["cum_share"]],
                line=dict(width=0),
            ),
            name="",
            hovertemplate="<b>%{x}</b><br>%{y:$,.0f}<extra></extra>",
        )
        pareto.add_scatter(
            x=show["category"], y=show["cum_share"] * 100,
            yaxis="y2", mode="lines+markers", name="Running total",
            line=dict(color=T.MINT, width=2.4),
            marker=dict(size=6, color=T.MINT),
            hovertemplate="<b>%{x}</b><br>%{y:.1f}% of revenue so far<extra></extra>",
        )
        n80 = int((pr["cum_share"] < 0.8).sum()) + 1
        pareto.add_hline(y=80, yref="y2", line=dict(color=T.DIM, width=1, dash="dot"),
                         annotation_text=f"80% reached at category {n80}",
                         annotation_position="top left",
                         annotation_font=dict(color=T.DIM, size=11))
    T.style(pareto, height=380)
    pareto.update_layout(
        margin=dict(l=70, r=62, t=26, b=126),
        xaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor=T.BORD,
                   tickangle=-38, tickfont=dict(size=10.5)),
        yaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickprefix="$", tickformat="~s", tickfont=dict(size=11)),
        yaxis2=dict(overlaying="y", side="right", range=[0, 105],
                    ticksuffix="%", showgrid=False, tickfont=dict(size=11),
                    linecolor="rgba(0,0,0,0)"),
    )

    # ---- delivery delay ----
    dl = db.delivery_delay(year, market, segment)
    delay = go.Figure()
    if len(dl):
        delay.add_bar(
            x=dl["delay"], y=dl["orders"],
            marker=dict(
                color=[T.MINT if d <= 0 else T.M1 for d in dl["delay"]],
                line=dict(width=0),
            ),
            hovertemplate="%{x:+d} days<br>%{y:,} orders<extra></extra>",
        )
        late = float(dl.loc[dl["delay"] > 0, "orders"].sum())
        tot = float(dl["orders"].sum()) or 1.0
        delay.add_annotation(
            xref="paper", yref="paper", x=0.99, y=0.97,
            xanchor="right", showarrow=False,
            text=f"<b>{late / tot:.1%}</b> shipped late",
            font=dict(color=T.M1, size=15),
        )
    T.style(delay, height=340)
    delay.update_layout(
        margin=dict(l=64, r=16, t=12, b=44),
        bargap=0.16,
        xaxis=dict(title=dict(text="days late", font=dict(size=11, color=T.DIM)),
                   gridcolor="rgba(0,0,0,0)", linecolor=T.BORD,
                   zeroline=True, zerolinecolor=T.DIM, zerolinewidth=1,
                   tickfont=dict(size=11)),
        yaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickformat="~s", tickfont=dict(size=11)),
    )

    # ---- countries ----
    c = db.exec_countries(year, market, segment)
    ctry = go.Figure(
        go.Bar(
            x=c["revenue"], y=c["country"], orientation="h",
            marker=dict(color=T.MINT, line=dict(width=0), opacity=0.85),
            hovertemplate="<b>%{y}</b><br>%{x:$,.0f}<extra></extra>",
            text=[T.money(v) for v in c["revenue"]],
            textposition="outside",
            textfont=dict(size=11, color=T.DIM),
            cliponaxis=False,
        )
    )
    T.style(ctry, height=360)
    ctry.update_layout(
        margin=dict(l=8, r=64, t=8, b=36),
        yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)",
                   linecolor="rgba(0,0,0,0)", automargin=True,
                   tickfont=dict(size=12)),
        xaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickprefix="$", tickformat="~s", tickfont=dict(size=11)),
    )

    # ---- products ----
    p = db.exec_top_products(year, market, segment)
    if len(p):
        p = p.copy()
        p["margin"] = (p["profit"] / p["revenue"]).map(lambda v: f"{v:.1%}")
        p["revenue"] = p["revenue"].map(lambda v: f"${v:,.0f}")
        p["profit"] = p["profit"].map(lambda v: f"${v:,.0f}")
        p["units"] = p["units"].map(lambda v: f"{int(v):,}")
        p.columns = ["Product", "Revenue", "Profit", "Units", "Margin"]
        prod = T.table(p, max_rows=10)
    else:
        prod = html.Div("No rows match these filters.", className="empty")

    active = []
    if year != "All":
        active.append(f"Year {year}")
    if market != "All":
        active.append(market)
    if segment != "All":
        active.append(segment)
    summary = (
        "Filtered: " + "  \u00b7  ".join(active)
        if active else "No filters applied \u2014 showing all 37 months"
    )

    return kpis, summary, trend, pareto, delay, ctry, prod

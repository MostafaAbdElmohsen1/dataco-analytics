"""
pages/map.py - world map of destination performance.

Two layers on one map:

  choropleth  filled countries, colour = revenue
  bubbles     one marker per country, size = revenue,
              hover shows the full performance card

Country names in the data are Spanish, so geo.py maps them to ISO3
codes for the fill layer and to centroids for the bubble layer. Any
country without a mapping is reported rather than silently dropped.
"""

import dash
from dash import dcc, html, callback, Input, Output
import plotly.graph_objects as go

import db
import geo
import theme as T

dash.register_page(__name__, path="/map", name="World map")

DETAIL = db.country_detail()

# --- attach geography -------------------------------------------------
DETAIL = DETAIL.copy()
DETAIL["iso3"] = DETAIL["country"].map(geo.iso3)
DETAIL["latlon"] = DETAIL["country"].map(geo.lookup)
DETAIL["lat"] = DETAIL["latlon"].map(lambda v: v[0] if v else None)
DETAIL["lon"] = DETAIL["latlon"].map(lambda v: v[1] if v else None)
DETAIL["margin"] = DETAIL["profit"] / DETAIL["revenue"]

MAPPED = DETAIL.dropna(subset=["iso3"])
UNMAPPED = DETAIL[DETAIL["iso3"].isna()]

TOTAL_REV = float(DETAIL["revenue"].sum())
COVERAGE = float(MAPPED["revenue"].sum() / TOTAL_REV) if TOTAL_REV else 0.0

MARKETS = ["All"] + sorted(DETAIL["market"].dropna().unique().tolist())
METRIC_LABELS = {"Revenue": "revenue", "Margin": "margin", "Late rate": "late_rate"}
LEVELS = ["Countries", "Cities"]

# Where to centre and how far to zoom when a market is picked.
SCOPE = {
    "All":          dict(lat=12,  lon=8,    scale=1.0),
    "Africa":       dict(lat=2,   lon=20,   scale=2.3),
    "Europe":       dict(lat=54,  lon=16,   scale=3.4),
    "LATAM":        dict(lat=-14, lon=-62,  scale=1.9),
    "Pacific Asia": dict(lat=10,  lon=112,  scale=1.9),
    "USCA":         dict(lat=46,  lon=-98,  scale=2.2),
}
CITIES = db.city_points()
METRICS = list(METRIC_LABELS.keys())

T.register_pill_group("level", LEVELS)
T.register_pill_group("metric", METRICS)
T.register_pill_group("mkt", MARKETS)

SCALE = [
    [0.00, "#1B0F2B"],
    [0.18, "#3B1B57"],
    [0.40, T.V2],
    [0.65, T.V1],
    [0.85, T.M2],
    [1.00, T.M1],
]


def hover_card(r) -> str:
    return (
        f"<b>{r['country']}</b>"
        f"<br><span style='color:#9A8AB0'>{r['market']}</span>"
        f"<br>"
        f"<br>Revenue &nbsp;<b>${r['revenue']:,.0f}</b>"
        f"<br>Profit &nbsp;&nbsp;<b>${r['profit']:,.0f}</b>"
        f"<br>Margin &nbsp;&nbsp;<b>{r['margin']:.1%}</b>"
        f"<br>Orders &nbsp;&nbsp;<b>{int(r['orders']):,}</b>"
        f"<br>Customers &nbsp;<b>{int(r['customers']):,}</b>"
        f"<br>Late &nbsp;&nbsp;&nbsp;&nbsp;<b>{r['late_rate']:.1%}</b>"
        f"<br>Avg transit &nbsp;<b>{r['avg_days']:.1f} days</b>"
        "<extra></extra>"
    )


def _geo(market: str) -> dict:
    sc = SCOPE.get(market, SCOPE["All"])
    return dict(
        projection=dict(type="natural earth",
                        scale=sc["scale"],
                        rotation=dict(lon=sc["lon"])),
        center=dict(lat=sc["lat"], lon=sc["lon"]),
        bgcolor="rgba(0,0,0,0)",
        showland=True, landcolor="#150C22",
        showocean=True, oceancolor="#0B0614",
        showlakes=False,
        showcountries=True, countrycolor="#2E1B45",
        showsubunits=True, subunitcolor="#241436",
        showcoastlines=True, coastlinecolor="#3A2352",
        showframe=False,
    )


def city_card(r) -> str:
    return (
        f"<b>{r['city']}</b>"
        f"<br><span style='color:#9A8AB0'>{r['state']}, {r['country']}</span>"
        f"<br>"
        f"<br>Revenue &nbsp;<b>${r['revenue']:,.0f}</b>"
        f"<br>Orders &nbsp;&nbsp;<b>{int(r['orders']):,}</b>"
        f"<br>Customers &nbsp;<b>{int(r['customers']):,}</b>"
        "<extra></extra>"
    )


def build_map(market: str, metric: str, level: str) -> go.Figure:
    fig = go.Figure()

    if level == "Cities":
        c = CITIES.copy()
        if market != "All":
            keep = set(DETAIL.loc[DETAIL["market"] == market, "country"])
            if len(c) and keep:
                c = c[c["country"].isin(keep)] if c["country"].isin(keep).any() else c
        if not len(c):
            T.style(fig, height=620)
            fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), geo=_geo(market))
            return fig
        mx = float(c["revenue"].max()) or 1.0
        fig.add_scattergeo(
            lat=c["lat"], lon=c["lon"], mode="markers",
            marker=dict(
                size=4 + (c["revenue"] / mx) ** 0.55 * 26,
                color=c["revenue"],
                colorscale=SCALE,
                opacity=0.85,
                line=dict(color="#0B0614", width=0.6),
                colorbar=dict(
                    title=dict(text="revenue", font=dict(color=T.DIM, size=11)),
                    tickfont=dict(color=T.DIM, size=10.5), tickformat="~s",
                    thickness=11, len=0.55, x=0.99, y=0.5,
                    outlinewidth=0, bgcolor="rgba(0,0,0,0)",
                ),
            ),
            customdata=c.apply(city_card, axis=1),
            hovertemplate="%{customdata}",
            showlegend=False,
        )
        T.style(fig, height=620)
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            geo=_geo(market),
            hoverlabel=dict(bgcolor="rgba(21,12,34,.97)", bordercolor=T.M1,
                            font=dict(color=T.TXT, size=12.5,
                                      family="Segoe UI, Arial, sans-serif"),
                            align="left"),
        )
        return fig

    d = MAPPED if market == "All" else MAPPED[MAPPED["market"] == market]
    d = d.copy()
    if not len(d):
        return T.style(fig, height=620)

    if metric == "late_rate":
        z, cbar_title, cbar_fmt = d["late_rate"] * 100, "late %", ".0f"
    elif metric == "margin":
        z, cbar_title, cbar_fmt = d["margin"] * 100, "margin %", ".0f"
    else:
        z, cbar_title, cbar_fmt = d["revenue"], "revenue", "~s"

    fig.add_choropleth(
        locations=d["iso3"], z=z, locationmode="ISO-3",
        colorscale=SCALE,
        marker=dict(line=dict(color="#2E1B45", width=0.6)),
        colorbar=dict(
            title=dict(text=cbar_title, font=dict(color=T.DIM, size=11)),
            tickfont=dict(color=T.DIM, size=10.5), tickformat=cbar_fmt,
            thickness=11, len=0.55, x=0.99, y=0.5,
            outlinewidth=0, bgcolor="rgba(0,0,0,0)",
        ),
        customdata=d.apply(hover_card, axis=1),
        hovertemplate="%{customdata}",
    )

    b = d.dropna(subset=["lat", "lon"])
    if len(b):
        mx = float(b["revenue"].max()) or 1.0
        fig.add_scattergeo(
            lat=b["lat"], lon=b["lon"], mode="markers",
            marker=dict(size=6 + (b["revenue"] / mx) * 32, color=T.MINT,
                        opacity=0.5, line=dict(color="#0B0614", width=1)),
            customdata=b.apply(hover_card, axis=1),
            hovertemplate="%{customdata}",
            showlegend=False,
        )

    T.style(fig, height=620)
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        geo=_geo(market),
        hoverlabel=dict(bgcolor="rgba(21,12,34,.97)", bordercolor=T.M1,
                        font=dict(color=T.TXT, size=12.5,
                                  family="Segoe UI, Arial, sans-serif"),
                        align="left"),
    )
    return fig


def rank_table(market: str) -> object:
    d = DETAIL if market == "All" else DETAIL[DETAIL["market"] == market]
    d = d.head(12).copy()
    if not len(d):
        return html.Div("No countries match.", className="empty")
    out = d[["country", "revenue", "margin", "orders", "late_rate"]].copy()
    out["revenue"] = out["revenue"].map(lambda v: f"${v:,.0f}")
    out["margin"] = out["margin"].map(lambda v: f"{v:.1%}")
    out["orders"] = out["orders"].map(lambda v: f"{int(v):,}")
    out["late_rate"] = out["late_rate"].map(lambda v: f"{v:.0%}")
    out.columns = ["Country", "Revenue", "Margin", "Orders", "Late"]
    return T.table(out, max_rows=12)


layout = html.Div(
    className="page",
    children=[
        T.page_head(
            "World map",
            "Every destination country DataCo ships to. Hover a country for its "
            "full performance card - revenue, margin, orders, customers and "
            "measured late rate.",
        ),
        html.Div(
            className="filter-bar filter-sticky",
            children=[
                html.Div(
                    className="filter-grid",
                    children=[
                        T.pill_group("level", "LEVEL", LEVELS),
                        T.pill_group("metric", "COLOUR BY", METRICS),
                        T.pill_group("mkt", "MARKET", MARKETS),
                    ],
                ),
                html.Div(
                    className="filter-foot",
                    children=[
                        html.Div(
                            f"{len(MAPPED)} of {len(DETAIL)} countries placed on the "
                            f"map, covering {COVERAGE:.1%} of revenue.",
                            className="filter-summary",
                        ),
                    ],
                ),
            ],
        ),
        T.panel(
            "Destination performance",
            "Countries level fills each country by the selected metric. Cities "
            "level plots the real coordinates stored in customer_address, sized "
            "by revenue. Picking a market zooms the map to that region.",
            dcc.Graph(id="m-map", config={"displayModeBar": False,
                                          "scrollZoom": False}),
            wide=True,
        ),
        T.panel(
            "Top twelve destinations",
            "Same filter as the map.",
            html.Div(id="m-table"),
            wide=True,
        ),
        html.Div(
            className="note",
            children=[
                html.Strong("Geographic coverage. "),
                f"{len(MAPPED)} of {len(DETAIL)} countries have a mapped ISO code "
                f"and appear on the map, together accounting for {COVERAGE:.1%} of "
                "revenue. "
                + (
                    "Unmapped: " + ", ".join(UNMAPPED["country"].head(12)) + "."
                    if len(UNMAPPED) else "Every country in the data is mapped."
                )
                + " Unmapped countries are still counted in every total on the "
                "other pages - only the map layer needs a code.",
            ],
        ),
    ],
)


@callback(
    Output("m-map", "figure"),
    Output("m-table", "children"),
    Input(T.store_id("mkt"), "data"),
    Input(T.store_id("metric"), "data"),
    Input(T.store_id("level"), "data"),
)
def refresh(market, metric_label, level):
    metric = METRIC_LABELS.get(metric_label, "revenue")
    return build_map(market, metric, level), rank_table(market)

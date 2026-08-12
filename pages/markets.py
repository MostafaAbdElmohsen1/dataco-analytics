"""
pages/markets.py - Market explorer (continent drill-through).

صفحة واحدة بس، مش صفحة لكل قارة. فوق فيه 5 كروت للأسواق، وأول ما
تدوس على واحد كل اللي تحته يتبدل بتفاصيل السوق ده: دوله، مناطقه،
عملائه، تأخيره، منتجاته. تدوس على سوق تاني - الأول يختفي والتاني
يظهر مكانه.

ليه صفحة واحدة مش 5 صفحات: لو كل قارة ليها صفحة، هيبقى فيه 5 نسخ من
نفس الكود ولازم تتظبط 5 مرات مع أي تعديل. هنا الكود واحد والمحتوى
بيتبنى من الداتا حسب اللي المستخدم اختاره.

الأرقام كلها بتتحسب بنفس دوال db.py اللي بتحسب صفحة Executive، فرقم
هنا مستحيل يخالف نفس الرقم هناك.
"""

from __future__ import annotations

from urllib.parse import quote

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

import db
import theme as T

dash.register_page(__name__, path="/markets", name="Markets")

# رمز لكل سوق - شكل هندسي متسق مع أيقونات القايمة الجانبية
MARKET_GLYPH = {
    "Africa": "◈",
    "Europe": "▣",
    "LATAM": "◉",
    "Pacific Asia": "◐",
    "USCA": "△",
}

STATUS_COLOUR = {
    "Shipping on time": T.MINT,
    "Advance shipping": T.V1,
    "Late delivery": T.AMBER,
    "Shipping canceled": T.M1,
}

MARKETS = db.filter_options()["markets"]


# ---------------------------------------------------------------------
# selector cards
# ---------------------------------------------------------------------
def _cards(selected: str | None):
    summary = db.market_summary().set_index("market")
    cards = []
    for m in MARKETS:
        row = summary.loc[m] if m in summary.index else None
        revenue = T.money(row["revenue"]) if row is not None else "-"
        share = f"{row['share']:.1%} of revenue" if row is not None else ""
        cards.append(
            html.Button(
                id={"type": "market-card", "index": m},
                n_clicks=0,
                className="mkt-card mkt-card-on" if m == selected else "mkt-card",
                children=[
                    html.Div(MARKET_GLYPH.get(m, "◆"), className="mkt-glyph"),
                    html.Div(m, className="mkt-name"),
                    html.Div(revenue, className="mkt-rev"),
                    html.Div(share, className="mkt-share"),
                ],
            )
        )
    return cards


# ---------------------------------------------------------------------
# charts
# ---------------------------------------------------------------------
def _countries_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    top = df.head(12).iloc[::-1]
    if len(top):
        fig.add_bar(
            x=top["revenue"], y=top["country"], orientation="h",
            marker=dict(color=T.MINT, line=dict(width=0), opacity=0.9),
            text=[T.money(v) for v in top["revenue"]],
            textposition="outside", textfont=dict(color=T.DIM, size=10.5),
            cliponaxis=False,
            customdata=top[["orders", "customers"]].values,
            hovertemplate="<b>%{y}</b><br>%{x:$,.0f}<br>"
                          "%{customdata[0]:,} orders · %{customdata[1]:,} customers"
                          "<extra></extra>",
        )
    T.style(fig, height=360)
    fig.update_layout(
        margin=dict(l=10, r=86, t=8, b=30), bargap=0.3,
        xaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickprefix="$", tickformat="~s", tickfont=dict(size=10.5)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)",
                   automargin=True, tickfont=dict(size=11, color=T.TXT)),
    )
    return fig


def _regions_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    d = df.iloc[::-1]
    if len(d):
        fig.add_bar(
            x=d["revenue"], y=d["region"], orientation="h",
            marker=dict(color=T.V1, line=dict(width=0)),
            text=[T.money(v) for v in d["revenue"]],
            textposition="outside", textfont=dict(color=T.DIM, size=10.5),
            cliponaxis=False,
            customdata=d[["orders", "late_rate"]].values,
            hovertemplate="<b>%{y}</b><br>%{x:$,.0f}<br>"
                          "%{customdata[0]:,} orders · %{customdata[1]:.1%} late"
                          "<extra></extra>",
        )
    T.style(fig, height=250)
    fig.update_layout(
        margin=dict(l=10, r=86, t=8, b=30), bargap=0.36,
        xaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickprefix="$", tickformat="~s", tickfont=dict(size=10.5)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)",
                   automargin=True, tickfont=dict(size=11, color=T.TXT)),
    )
    return fig


def _month_dtick(n_months: int) -> str:
    """
    كثافة علامات المحور حسب طول المدة. علامة لكل شهر تمام لمدة قصيرة،
    لكن على 33 شهر بتبقى 33 تسمية متلزقة في بعض ومش مقروءة.
    """
    if n_months <= 14:
        return "M1"
    if n_months <= 40:
        return "M3"
    return "M6"


def _trend_chart(monthly: pd.DataFrame) -> go.Figure:
    """
    محور زمني حقيقي والشهور الناقصة بتفضل فاضية - نفس القاعدة اللي في
    لوحة التفاصيل: بيانات بعض الأسواق فيها فجوات، ووصل الخط فوقها
    بيخفيها ويقرا غلط.
    """
    fig = go.Figure()
    dtick = "M1"
    if len(monthly):
        d = monthly.copy()
        d["date"] = pd.to_datetime(d["month"] + "-01")
        d = d.set_index("date").reindex(
            pd.date_range(d["date"].min(), d["date"].max(), freq="MS"))
        dtick = _month_dtick(len(d))
        fig.add_scatter(
            x=d.index, y=d["revenue"], mode="lines+markers", name="Revenue",
            line=dict(color=T.M1, width=2), marker=dict(size=7, color=T.M1),
            connectgaps=False,
            hovertemplate="<b>%{y:$,.0f}</b><br>%{x|%b %Y}<extra></extra>",
        )
    T.style(fig, height=230, hovermode="x unified")
    fig.update_layout(
        margin=dict(l=60, r=34, t=10, b=40),
        xaxis=dict(type="date", dtick=dtick, gridcolor="rgba(0,0,0,0)",
                   linecolor=T.BORD, tickformat="%b<br>%Y", tickfont=dict(size=10)),
        yaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickprefix="$", tickformat="~s", tickfont=dict(size=10.5)),
    )
    return fig


def _delivery_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    d = df.iloc[::-1]
    if len(d):
        total = float(d["orders"].sum()) or 1.0
        fig.add_bar(
            x=d["orders"], y=d["status"], orientation="h",
            marker=dict(color=[STATUS_COLOUR.get(s, T.V2) for s in d["status"]],
                        line=dict(width=0)),
            text=[f"{v:,}  ({v / total:.0%})" for v in d["orders"]],
            textposition="outside", textfont=dict(color=T.DIM, size=10.5),
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:,} orders<extra></extra>",
        )
    T.style(fig, height=250)
    fig.update_layout(
        margin=dict(l=10, r=96, t=8, b=30), bargap=0.42,
        xaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickformat="~s", tickfont=dict(size=10.5)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)",
                   automargin=True, tickfont=dict(size=11, color=T.TXT)),
    )
    return fig


def _products_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    d = df.iloc[::-1]
    if len(d):
        names = [n if len(n) <= 34 else n[:32] + "\u2026" for n in d["product"]]
        fig.add_bar(
            x=d["revenue"], y=names, orientation="h",
            marker=dict(color=T.M2, line=dict(width=0)),
            text=[T.money(v) for v in d["revenue"]],
            textposition="outside", textfont=dict(color=T.DIM, size=10.5),
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:$,.0f}<extra></extra>",
        )
    T.style(fig, height=250)
    fig.update_layout(
        margin=dict(l=10, r=86, t=8, b=30), bargap=0.34,
        xaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickprefix="$", tickformat="~s", tickfont=dict(size=10.5)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)",
                   automargin=True, tickfont=dict(size=10.5, color=T.TXT)),
    )
    return fig


def _shipping_chart(df: pd.DataFrame) -> go.Figure:
    """
    الموعود مقابل الفعلي لكل طريقة شحن. سلسلتين بنفس الوحدة (أيام)
    فمحور واحد كفاية - ومعاهم legend لأن فيه أكتر من سلسلة.
    """
    fig = go.Figure()
    if len(df):
        fig.add_bar(x=df["mode"], y=df["promised"], name="Promised",
                    marker=dict(color=T.V2, line=dict(width=0)),
                    hovertemplate="<b>%{x}</b><br>%{y:.1f} days promised<extra></extra>")
        fig.add_bar(x=df["mode"], y=df["actual"], name="Actual",
                    marker=dict(color=T.M1, line=dict(width=0)),
                    hovertemplate="<b>%{x}</b><br>%{y:.1f} days actual<extra></extra>")
    T.style(fig, height=250, barmode="group")
    fig.update_layout(
        margin=dict(l=52, r=14, t=34, b=44), bargap=0.34, bargroupgap=0.12,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    font=dict(size=11, color=T.DIM)),
        xaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor=T.BORD,
                   tickfont=dict(size=10.5, color=T.TXT)),
        yaxis=dict(title=dict(text="days", font=dict(size=10.5, color=T.DIM)),
                   gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickfont=dict(size=10.5)),
    )
    return fig


# ---------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------
layout = html.Div(
    className="page",
    children=[
        dcc.Store(id="mkt-selected", data=None),
        T.page_head(
            "Markets",
            "Pick a market to open everything about it - its countries, "
            "regions, delivery performance and products. Choosing another "
            "market replaces what you see; nothing stacks up.",
        ),
        html.Div(id="mkt-cards", className="mkt-cards"),
        html.Div(id="mkt-body"),
    ],
)


@callback(Output("mkt-cards", "children"), Input("mkt-selected", "data"))
def render_cards(selected):
    return _cards(selected)


@callback(
    Output("mkt-selected", "data"),
    Input({"type": "market-card", "index": dash.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def pick_market(_clicks):
    """
    الكروت بتتولد من callback تاني، وأول ما تظهر في الصفحة Dash بيشغّل
    الـ callback ده وكأن حد داس عليها - فكانت أول قارة في القايمة
    (أفريقيا) بتتفتح لوحدها من غير ما المستخدم يدوس.
    الفرق إن الضغطة الحقيقية بيكون معاها n_clicks أكبر من صفر، فبنتأكد
    من القيمة نفسها مش من اسم العنصر بس.
    """
    trig = dash.ctx.triggered_id
    if not isinstance(trig, dict):
        return dash.no_update
    if not dash.ctx.triggered or not dash.ctx.triggered[0].get("value"):
        return dash.no_update
    return trig.get("index")


@callback(Output("mkt-body", "children"), Input("mkt-selected", "data"))
def render_body(market):
    if not market:
        return html.Div(
            className="mkt-empty",
            children="Choose a market above to see its full breakdown.",
        )

    try:
        k = db.drill_kpis("market", market)
        countries = db.market_countries(market)
        regions = db.market_regions(market)
        monthly = db.drill_monthly("market", market)
        delivery = db.drill_delivery("market", market)
        shipping = db.market_shipping(market)
        products = db.drill_products("market", market, limit=8)
        rank = db.drill_rank("market", market)
    except Exception as e:  # noqa: BLE001
        print(f"[markets] failed for {market!r}: {e!r}")
        return html.Div("Couldn't load this market.", className="empty")

    late_colour = T.MINT if k["late_rate"] < 0.5 else T.AMBER
    question = (f"اديني ملخص كامل عن سوق {market}: الإيرادات والأرباح "
                f"وأهم الدول ونسبة التأخير")

    tbl = countries.copy()
    tbl["revenue"] = tbl["revenue"].map(lambda v: f"${v:,.0f}")
    tbl["profit"] = tbl["profit"].map(lambda v: f"${v:,.0f}")
    tbl["late_rate"] = tbl["late_rate"].map(lambda v: f"{v:.1%}")
    tbl["orders"] = tbl["orders"].map(lambda v: f"{int(v):,}")
    tbl["customers"] = tbl["customers"].map(lambda v: f"{int(v):,}")
    tbl.columns = ["Country", "Revenue", "Profit", "Orders", "Customers", "Late"]

    return html.Div(
        className="mkt-detail",
        children=[
            html.Div(
                className="mkt-detail-head",
                children=[
                    html.Div(market, className="mkt-detail-title"),
                    html.Div(
                        f"{len(countries)} countries · {len(regions)} regions · "
                        f"ranked {rank['rank']} of {rank['of']} by revenue "
                        f"· {rank['share']:.1%} of all revenue",
                        className="mkt-detail-sub",
                    ),
                ],
            ),
            html.Div(
                className="drill-tiles",
                children=[
                    T.kpi_tile(T.money(k["revenue"]), "REVENUE"),
                    T.kpi_tile(T.money(k["profit"]), "PROFIT", T.MINT),
                    T.kpi_tile(f"{k['margin']:.1%}", "MARGIN", T.MINT),
                    T.kpi_tile(f"{k['orders']:,}", "ORDERS"),
                    T.kpi_tile(f"{k['customers']:,}", "CUSTOMERS"),
                    T.kpi_tile(f"{k['late_rate']:.1%}", "SHIPPED LATE", late_colour),
                ],
            ),
            html.Div(
                className="panel-grid",
                children=[
                    T.panel("Revenue by month", None,
                            dcc.Graph(figure=_trend_chart(monthly),
                                      config={"displayModeBar": False}), wide=True),
                    T.panel("Top countries", "Highest twelve by revenue.",
                            dcc.Graph(figure=_countries_chart(countries),
                                      config={"displayModeBar": False}), wide=True),
                    T.panel("Regions", "Sub-regions inside this market.",
                            dcc.Graph(figure=_regions_chart(regions),
                                      config={"displayModeBar": False})),
                    T.panel("Delivery outcome", "Orders by delivery status.",
                            dcc.Graph(figure=_delivery_chart(delivery),
                                      config={"displayModeBar": False})),
                    T.panel("Promised vs actual shipping days",
                            "Both bars are in days, on one scale.",
                            dcc.Graph(figure=_shipping_chart(shipping),
                                      config={"displayModeBar": False})),
                    T.panel("Top products", "Highest eight by revenue.",
                            dcc.Graph(figure=_products_chart(products),
                                      config={"displayModeBar": False})),
                    T.panel("Every country in this market", None,
                            T.table(tbl, max_rows=60), wide=True),
                ],
            ),
            html.Div(
                className="drill-foot",
                children=[
                    dcc.Link(f"Ask the Data about {market} →",
                             href=f"/chat?q={quote(question)}",
                             className="drill-ask"),
                ],
            ),
        ],
    )

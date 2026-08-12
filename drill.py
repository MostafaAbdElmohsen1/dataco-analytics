"""
drill.py - لوحة التفاصيل (drill-down panel).

مكوّن واحد مشترك: تديله (level, value) - يعني "country/Egipto" أو
"market/Africa" - وبيرجعلك لوحة كاملة فيها أرقام الكيان ده وشارتاته.
أي صفحة تقدر تستخدمه، فمفيش تكرار كود بين Executive والخريطة.

قرارات تصميم مقصودة:

1) مفيش محورين في شارت واحد. الإيراد والربح فرق حجمهم كبير (الربح
   حوالي 10% من الإيراد)، فلو حطيناهم على شارت واحد بمحورين هيبقى
   مضلل - ده أشهر غلط في الداشبوردات. الحل: الشارت للإيراد بس،
   والربح والهامش أرقام في الأعلى.

2) حالات التسليم بأعمدة أفقية مش دائرة (pie). العين بتقارن الأطوال
   أدق بكتير من الزوايا، وأسماء الحالات بتبقى مقروءة على المحور بدل
   ما تعتمد على اللون وحده (مهم لأي حد عنده عمى ألوان).

3) كل رقم في اللوحة بيتحسب بنفس دوال db.py اللي بتحسب الصفحة نفسها،
   فمستحيل اللوحة تخالف الشارت اللي فوقها.
"""

from __future__ import annotations

from urllib.parse import quote

import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

import db
import theme as T

# ألوان حالات التسليم - ثابتة لكل حالة، مش حسب الترتيب.
# ده مهم: لو الترتيب اتغير حسب الأرقام، اللون لازم يفضل مع نفس الحالة.
STATUS_COLOUR = {
    "Shipping on time": T.MINT,
    "Advance shipping": T.V1,
    "Late delivery": T.AMBER,
    "Shipping canceled": T.M1,
}


def _tile(value: str, label: str, colour: str = T.TXT):
    return html.Div(
        className="drill-tile",
        children=[
            html.Div(value, className="drill-tile-value", style={"color": colour}),
            html.Div(label, className="drill-tile-label"),
        ],
    )


def _revenue_chart(monthly) -> go.Figure:
    """
    محور زمني حقيقي، والشهور الناقصة بتفضل فاضية (NaN) عن قصد.

    بيانات كل دولة متفرقة: المكسيك مثلاً عندها بيانات في يناير-مايو 2015
    وبعدين يناير-يونيو 2017، ومفيش حاجة بينهم. لو استخدمنا محور فئوي
    (category) الشهرين دول هيبانوا جنب بعض والخط هيوصّل بينهم كأنهم
    متتاليين - وده بيخفي فجوة سنة ونص. بالمحور الزمني + الفراغات،
    المسافة الحقيقية بتبان والخط بيتقطع فين ما مفيش بيانات.
    """
    fig = go.Figure()
    if len(monthly):
        d = monthly.copy()
        d["date"] = pd.to_datetime(d["month"] + "-01")
        # نمدّد المدى لكل الشهور بين أول وآخر شهر، والناقص يفضل NaN
        full = pd.date_range(d["date"].min(), d["date"].max(), freq="MS")
        d = d.set_index("date").reindex(full)

        fig.add_scatter(
            x=d.index, y=d["revenue"],
            mode="lines+markers", name="Revenue",
            line=dict(color=T.M1, width=2),
            marker=dict(size=7, color=T.M1),
            connectgaps=False,          # الخط يتقطع في الشهور الناقصة
            # من غير تظليل تحت الخط: التظليل كان بيعدّي فوق الفجوات
            # ويخليها تبان كأن فيها بيانات، وده بيلغي فايدة تقطيع الخط.
            hovertemplate="<b>%{y:$,.0f}</b><br>%{x|%b %Y}<extra></extra>",
        )
    T.style(fig, height=210, hovermode="x unified")
    fig.update_layout(
        margin=dict(l=58, r=34, t=10, b=38),
        # dtick="M1": علامة واحدة لكل شهر بالظبط. من غيرها Plotly بيحط
        # علامة كل نص شهر لما المدى قصير، فتظهر "Apr 2016" مرتين ورا بعض.
        xaxis=dict(type="date", dtick="M1", gridcolor="rgba(0,0,0,0)",
                   linecolor=T.BORD, tickformat="%b<br>%Y", tickfont=dict(size=10)),
        yaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickprefix="$", tickformat="~s", tickfont=dict(size=10.5)),
    )
    return fig


def _products_chart(products) -> go.Figure:
    fig = go.Figure()
    if len(products):
        d = products.iloc[::-1]  # الأكبر يبقى فوق
        names = [n if len(n) <= 34 else n[:32] + "…" for n in d["product"]]
        fig.add_bar(
            x=d["revenue"], y=names, orientation="h",
            marker=dict(color=T.V1, line=dict(width=0)),
            text=[T.money(v) for v in d["revenue"]],
            textposition="outside",
            textfont=dict(color=T.DIM, size=10.5),
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:$,.0f}<extra></extra>",
        )
    T.style(fig, height=230)
    fig.update_layout(
        margin=dict(l=10, r=78, t=8, b=26),
        bargap=0.34,
        xaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickprefix="$", tickformat="~s", tickfont=dict(size=10.5)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)",
                   tickfont=dict(size=10.5, color=T.TXT), automargin=True),
    )
    return fig


def _delivery_chart(delivery) -> go.Figure:
    fig = go.Figure()
    if len(delivery):
        d = delivery.iloc[::-1]
        total = float(d["orders"].sum()) or 1.0
        fig.add_bar(
            x=d["orders"], y=d["status"], orientation="h",
            marker=dict(
                color=[STATUS_COLOUR.get(s, T.V2) for s in d["status"]],
                line=dict(width=0),
            ),
            text=[f"{v:,}  ({v / total:.0%})" for v in d["orders"]],
            textposition="outside",
            textfont=dict(color=T.DIM, size=10.5),
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:,} orders<extra></extra>",
        )
    T.style(fig, height=230)
    fig.update_layout(
        margin=dict(l=10, r=96, t=8, b=26),
        bargap=0.42,
        xaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickformat="~s", tickfont=dict(size=10.5)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)",
                   tickfont=dict(size=10.5, color=T.TXT), automargin=True),
    )
    return fig


def panel(level: str, value: str, year=None, segment=None):
    """
    level: "country" أو "market"
    value: الاسم زي ما هو مخزّن في القاعدة (مثال: Egipto, Africa)
    """
    k = db.drill_kpis(level, value, year, segment)
    rank = db.drill_rank(level, value, year, segment)

    scope_word = "market" if level == "market" else "country"
    active = [f for f in (year if year and year != "All" else None,
                          segment if segment and segment != "All" else None) if f]
    context = f"{scope_word} · ranked {rank['rank']} of {rank['of']} by revenue " \
              f"· {rank['share']:.1%} of all revenue"
    if active:
        context += "  ·  filters: " + ", ".join(active)

    late_colour = T.MINT if k["late_rate"] < 0.5 else T.AMBER

    question = (
        f"اديني ملخص كامل عن {value}: الإيرادات والأرباح وعدد العملاء "
        f"ونسبة التأخير وأهم المنتجات"
    )

    return html.Div(
        className="drill",
        children=[
            html.Div(
                className="drill-head",
                children=[
                    html.Div(
                        children=[
                            html.Div(value, className="drill-title"),
                            html.Div(context, className="drill-context"),
                        ]
                    ),
                    # معرّف نمطي (pattern-matching) مش نص عادي: الزرار ده
                    # مش موجود في الصفحة وقت التحميل (بيتولد مع اللوحة)،
                    # و Dash بيتجاهل أي callback فيه Input على عنصر ناقص.
                    # الشكل ده بيشتغل حتى لو العدد صفر.
                    html.Button("✕", id={"type": "drill-close", "index": 0},
                                n_clicks=0, className="drill-close", title="Close"),
                ],
            ),
            html.Div(
                className="drill-tiles",
                children=[
                    _tile(T.money(k["revenue"]), "REVENUE"),
                    _tile(T.money(k["profit"]), "PROFIT", T.MINT),
                    _tile(f"{k['margin']:.1%}", "MARGIN", T.MINT),
                    _tile(f"{k['orders']:,}", "ORDERS"),
                    _tile(f"{k['customers']:,}", "CUSTOMERS"),
                    _tile(f"{k['late_rate']:.1%}", "SHIPPED LATE", late_colour),
                ],
            ),
            html.Div(
                className="drill-charts",
                children=[
                    html.Div(
                        className="drill-chart drill-chart-wide",
                        children=[
                            html.Div("Revenue by month", className="drill-chart-title"),
                            dcc.Graph(figure=_revenue_chart(
                                db.drill_monthly(level, value, year, segment)),
                                config={"displayModeBar": False}),
                        ],
                    ),
                    html.Div(
                        className="drill-chart",
                        children=[
                            html.Div("Top products", className="drill-chart-title"),
                            dcc.Graph(figure=_products_chart(
                                db.drill_products(level, value, year, segment)),
                                config={"displayModeBar": False}),
                        ],
                    ),
                    html.Div(
                        className="drill-chart",
                        children=[
                            html.Div("Delivery outcome", className="drill-chart-title"),
                            dcc.Graph(figure=_delivery_chart(
                                db.drill_delivery(level, value, year, segment)),
                                config={"displayModeBar": False}),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="drill-foot",
                children=[
                    dcc.Link(
                        f"Ask the Data about {value} →",
                        href=f"/chat?q={quote(question)}",
                        className="drill-ask",
                    ),
                ],
            ),
        ],
    )

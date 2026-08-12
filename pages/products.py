"""
pages/products.py - إيه اللي بيكسب، وإيه اللي بيخسّر، ونركز على إيه.

الصفحة دي مبنية على حاجة اكتشفتها في الداتا وهي أهم رقم في المشروع:
18.7% من سطور الطلبات بتخسر فلوس. الخسارة دي (3.88 مليون) بتاكل نص
المكسب الإجمالي (7.85 مليون) قبل ما يوصل للصافي (3.97 مليون).

وحاجة تانية مهمة: على مستوى المنتج الواحد الهامش شبه ثابت (أعلى 5
منتجات بالإيراد هم نفسهم أعلى 5 بالربح وبنفس الترتيب). الاختلاف
الحقيقي على مستوى الفئة: من 0.6% لـ 13.6% - فرق 20 ضعف. يعني
"نركز على إيه" إجابتها في الفئات مش في المنتجات.
"""

from __future__ import annotations

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

import db
import theme as T

dash.register_page(__name__, path="/products", name="Products")


def _reads(text: str):
    return html.Div(
        className="reads",
        children=[html.Span("What this tells you: ", className="reads-lead"), text],
    )


# ---------------------------------------------------------------------
def _leaders_chart(d: pd.DataFrame) -> go.Figure:
    d = d.iloc[::-1]
    names = [n if len(n) <= 38 else n[:36] + "…" for n in d["product"]]
    fig = go.Figure()
    fig.add_bar(
        x=d["revenue"], y=names, orientation="h",
        marker=dict(color=T.MINT, line=dict(width=0)),
        text=[T.money(v) for v in d["revenue"]],
        textposition="outside", textfont=dict(color=T.DIM, size=10.5),
        cliponaxis=False,
        customdata=d[["profit", "margin"]].values,
        hovertemplate="<b>%{y}</b><br>revenue %{x:$,.0f}<br>"
                      "profit %{customdata[0]:$,.0f} · margin %{customdata[1]:.1%}"
                      "<extra></extra>",
    )
    T.style(fig, height=340)
    fig.update_layout(
        margin=dict(l=10, r=86, t=8, b=28), bargap=0.3,
        xaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickprefix="$", tickformat="~s", tickfont=dict(size=10.5)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)",
                   automargin=True, tickfont=dict(size=10.5, color=T.TXT)),
    )
    return fig


def _profit_bridge(share: dict) -> go.Figure:
    """
    المكسب الإجمالي -> الخسارة -> الصافي.
    عمودين لفوق وعمود خسارة معلّق بينهم، فالعين تشوف الجزء اللي بيتاكل.
    """
    gain = float(share["gain_value"])
    loss = abs(float(share["loss_value"]))
    net = gain - loss

    fig = go.Figure()
    fig.add_bar(x=["Profit made on<br>the good lines"], y=[gain],
                marker=dict(color=T.MINT, line=dict(width=0)),
                text=[T.money(gain)], textposition="outside",
                textfont=dict(color=T.TXT, size=13),
                hovertemplate="<b>%{y:$,.0f}</b><extra></extra>")
    fig.add_bar(x=["Wiped out by<br>the losing lines"], y=[loss], base=[net],
                marker=dict(color=T.M1, line=dict(width=0)),
                text=["−" + T.money(loss)], textposition="outside",
                textfont=dict(color=T.TXT, size=13),
                hovertemplate="<b>-%{y:$,.0f}</b><extra></extra>")
    fig.add_bar(x=["What is actually<br>left"], y=[net],
                marker=dict(color=T.V1, line=dict(width=0)),
                text=[T.money(net)], textposition="outside",
                textfont=dict(color=T.TXT, size=13),
                hovertemplate="<b>%{y:$,.0f}</b><extra></extra>")
    T.style(fig, height=330)
    fig.update_layout(
        margin=dict(l=64, r=18, t=34, b=52), bargap=0.45,
        xaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor=T.BORD,
                   tickfont=dict(size=11, color=T.TXT)),
        yaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickprefix="$", tickformat="~s", tickfont=dict(size=10.5)),
    )
    return fig


def _margin_chart(cm: pd.DataFrame) -> go.Figure:
    """
    الهامش لكل فئة، مرتب من الأقل. اللون بيتغير عند المتوسط العام،
    فالفئات اللي تحت المتوسط بتبان فوراً من غير ما حد يقرا رقم.
    """
    overall = db.totals()["margin"]
    d = cm.copy()
    fig = go.Figure()
    fig.add_bar(
        x=d["category"], y=d["margin"] * 100,
        marker=dict(color=[T.M1 if m < overall else T.MINT for m in d["margin"]],
                    line=dict(width=0)),
        customdata=d[["revenue"]].values,
        hovertemplate="<b>%{x}</b><br>margin %{y:.1f}%<br>"
                      "revenue %{customdata[0]:$,.0f}<extra></extra>",
    )
    fig.add_hline(y=overall * 100, line=dict(color=T.DIM, width=1, dash="dot"),
                  annotation_text=f"company average {overall:.1%}",
                  annotation_position="top right",
                  annotation_font=dict(color=T.DIM, size=11))
    T.style(fig, height=380)
    fig.update_layout(
        margin=dict(l=58, r=18, t=28, b=132), bargap=0.28,
        xaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor=T.BORD,
                   tickangle=-40, tickfont=dict(size=10)),
        yaxis=dict(ticksuffix="%", gridcolor=T.BORD, zeroline=False,
                   linecolor="rgba(0,0,0,0)", tickfont=dict(size=10.5)),
    )
    return fig


def _focus_chart(cm: pd.DataFrame) -> go.Figure:
    """
    مصفوفة التركيز: الإيراد أفقي، الهامش رأسي، والحجم = الربح.
    الأربع أرباع بتقسم الفئات لأربع قرارات مختلفة.
    """
    overall = db.totals()["margin"]
    mid_rev = float(cm["revenue"].median())
    d = cm.copy()

    # نسمّي النقط المهمة بس. لو سمّينا الـ 33 فئة، الفئات الصغيرة
    # (وهي الأغلبية) بتتلزق على الشمال والأسماء بتركب فوق بعض ومحدش
    # يقدر يقرا حاجة. الباقي بيظهر اسمه لما تحط الماوس عليه.
    notable = set(d.nlargest(4, "revenue")["category"]) \
        | set(d.nsmallest(2, "margin")["category"]) \
        | set(d.nlargest(1, "margin")["category"])
    labels = [c if c in notable else "" for c in d["category"]]

    fig = go.Figure()
    fig.add_scatter(
        x=d["revenue"], y=d["margin"] * 100, mode="markers+text",
        text=labels, textposition="top center",
        textfont=dict(size=10, color=T.TXT),
        customdata=d["category"],
        marker=dict(
            size=(d["profit"].clip(lower=1) ** 0.5) / 22 + 9,
            color=[T.M1 if m < overall else T.MINT for m in d["margin"]],
            line=dict(width=1, color=T.BG), opacity=.9),
        hovertemplate="<b>%{customdata}</b><br>revenue %{x:$,.0f}<br>"
                      "margin %{y:.1f}%<extra></extra>",
    )
    fig.add_vline(x=mid_rev, line=dict(color=T.BORD, width=1))
    fig.add_hline(y=overall * 100, line=dict(color=T.BORD, width=1))
    # ملصقات الأرباع فوق منطقة الرسم نفسها (y>1) عشان ماتركبش على النقط
    for x, y, txt, col, anc in [
        (.01, 1.10, "small but profitable — grow these", T.MINT, "left"),
        (.99, 1.10, "your engine — protect these", T.MINT, "right"),
        (.01, -.16, "small and weak — ignore or drop", T.DIM, "left"),
        (.99, -.16, "big but thin — fix the margin here", T.M1, "right"),
    ]:
        fig.add_annotation(x=x, y=y, xref="paper", yref="paper", text=txt,
                           showarrow=False, xanchor=anc, yanchor="middle",
                           font=dict(size=11, color=col))
    T.style(fig, height=470)
    fig.update_layout(
        margin=dict(l=62, r=26, t=52, b=86),
        xaxis=dict(title=dict(text="revenue", font=dict(size=11, color=T.DIM)),
                   tickprefix="$", tickformat="~s", gridcolor=T.BORD,
                   zeroline=False, linecolor="rgba(0,0,0,0)", tickfont=dict(size=10.5)),
        yaxis=dict(title=dict(text="margin", font=dict(size=11, color=T.DIM)),
                   ticksuffix="%", gridcolor=T.BORD, zeroline=False,
                   linecolor="rgba(0,0,0,0)", tickfont=dict(size=10.5)),
    )
    return fig


# ---------------------------------------------------------------------
def _build():
    t = db.totals()
    share = db.loss_line_share()
    leaders = db.product_leaders(10)
    cm = db.category_margin()
    losers = db.loss_makers()

    worst = cm.iloc[0]
    best = cm.iloc[-1]

    lt = losers.copy()
    lt["revenue"] = lt["revenue"].map(lambda v: f"${v:,.0f}")
    lt["profit"] = lt["profit"].map(lambda v: f"-${abs(v):,.0f}")
    lt["lines"] = lt["lines"].map(lambda v: f"{int(v):,}")
    lt.columns = ["Product", "Category", "Revenue", "Total loss", "Order lines"]

    return html.Div(
        className="page",
        children=[
            T.page_head(
                "Products",
                "What sells, what actually makes money, and what quietly destroys "
                "it. Revenue and profit are not the same question.",
            ),
            html.Div(
                className="kpi-row kpi-row-tight",
                children=[
                    T.kpi(f"{t['lines']:,}", "ORDER LINES"),
                    T.kpi(f"{share['share']:.1%}", "OF LINES LOSE MONEY",
                          T.M1, T.M1),
                    T.kpi(T.money(abs(share["loss_value"])), "LOST ON THOSE LINES",
                          T.M1, T.M1),
                    T.kpi(f"{t['margin']:.1%}", "MARGIN LEFT", T.MINT, T.MINT),
                ],
            ),
            html.Div(
                className="panel-grid",
                children=[
                    T.panel(
                        "Where does the profit actually go?",
                        "Every order line either adds profit or takes it away. "
                        "These are the two totals, and what survives.",
                        dcc.Graph(figure=_profit_bridge(share),
                                  config={"displayModeBar": False}),
                        _reads(
                            f"This is the most important number on the site. "
                            f"{share['share']:.1%} of all order lines lose money, and "
                            f"together they wipe out {abs(share['loss_value']) / share['gain_value']:.0%} "
                            f"of everything the profitable lines earned. The company "
                            f"reports {T.money(t['profit'])} of profit - it earned "
                            f"{T.money(share['gain_value'])} and gave most of it back."
                        ),
                    ),
                    T.panel(
                        "Top ten products by revenue",
                        None,
                        dcc.Graph(figure=_leaders_chart(leaders),
                                  config={"displayModeBar": False}),
                        _reads(
                            "Hover any bar and you will see its profit and margin. "
                            "They all sit near the company average, which is the "
                            "point: at product level the margin barely moves, so "
                            "the best sellers are also the best earners. The "
                            "difference shows up one level up - in the categories."
                        ),
                    ),
                    T.panel(
                        "Margin by category - the real spread",
                        "Sorted from worst to best. Pink is below the company "
                        "average, green is above.",
                        dcc.Graph(figure=_margin_chart(cm),
                                  config={"displayModeBar": False}),
                        _reads(
                            f"Here is the answer to 'what should we fix'. "
                            f"{worst['category']} returns {worst['margin']:.1%} - "
                            f"practically nothing - while {best['category']} returns "
                            f"{best['margin']:.1%}. That is a {best['margin'] / max(worst['margin'], .001):.0f}x "
                            f"difference between two parts of the same company. "
                            f"Nothing at product level comes close to that spread."
                        ),
                        wide=True,
                    ),
                    T.panel(
                        "What to focus on",
                        "Each dot is a category. Right = brings in more money. "
                        "Up = keeps more of it. Bubble size = profit.",
                        dcc.Graph(figure=_focus_chart(cm),
                                  config={"displayModeBar": False}),
                        _reads(
                            "Read it by corner. Top-right categories earn a lot and "
                            "keep a lot - protect them. Bottom-right earn a lot and "
                            "keep little - this is where a small margin fix pays the "
                            "most, because the revenue is already there. Bottom-left "
                            "is small and weak; it costs attention and returns "
                            "little."
                        ),
                        wide=True,
                    ),
                    T.panel(
                        f"Products that lose money over the whole period "
                        f"({len(losers)} in total)",
                        "These sell, and still end up negative.",
                        T.table(lt, max_rows=20),
                        _reads(
                            "Only three products are net-negative across the whole "
                            "period, and the amounts are small. So the losses are "
                            "not caused by a few bad products - they are spread "
                            "thinly across many normal lines. That is why the "
                            "category view above matters more than this table."
                        ),
                        wide=True,
                    ),
                ],
            ),
        ],
    )


layout = _build

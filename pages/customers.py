"""
pages/customers.py - مين بيشتري، وهل بنكبر؟

الصفحة دي بتجاوب على سؤال واحد: العملاء. كل شارت فيها تحته جملة
بتقول "الشارت ده بيقولك إيه" بلغة عادية، عشان حد مش متعود على
الشارتات يفهم من غير شرح شفهي.

أهم حاجة في الصفحة: تحذير صادق عن فترة أكتوبر 2017 لآخر الداتا.
في الفترة دي كل طلب جاي من عميل جديد بيشتري مرة واحدة وبس، وأرقام
العملاء كتلة متتالية. ده أثر في تجميع البيانات مش نمو حقيقي، ولو
اتعرض كنمو هيبقى الرقم مضلل تماماً.
"""

from __future__ import annotations

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

import db
import theme as T

dash.register_page(__name__, path="/customers", name="Customers")

# أول شهر في الفترة المشبوهة - كل حاجة من هنا بتتعلّم في الشارت
ARTIFACT_FROM = "2017-10"


def _reads(text: str):
    """السطر اللي بيشرح الشارت بلغة عادية."""
    return html.Div(
        className="reads",
        children=[html.Span("What this tells you: ", className="reads-lead"), text],
    )


# ---------------------------------------------------------------------
def _new_customers_chart() -> go.Figure:
    d = db.new_customers_by_month().copy()
    d["date"] = pd.to_datetime(d["month"] + "-01")
    clean = d[d["month"] < ARTIFACT_FROM]
    flagged = d[d["month"] >= ARTIFACT_FROM]

    fig = go.Figure()
    fig.add_bar(
        x=clean["date"], y=clean["new_customers"], name="Real acquisition",
        marker=dict(color=T.V1, line=dict(width=0)),
        hovertemplate="<b>%{y:,}</b> new customers<br>%{x|%b %Y}<extra></extra>",
    )
    fig.add_bar(
        x=flagged["date"], y=flagged["new_customers"], name="Not real - see note",
        marker=dict(color="rgba(154,138,176,.45)", line=dict(width=0)),
        hovertemplate="<b>%{y:,}</b> new customers<br>%{x|%b %Y}"
                      "<br>data artifact - not real growth<extra></extra>",
    )
    if len(flagged):
        fig.add_vline(x=flagged["date"].iloc[0], line=dict(color=T.AMBER, width=1.5,
                                                           dash="dot"))
        fig.add_annotation(
            x=flagged["date"].iloc[0], y=1, yref="paper", yanchor="top",
            xanchor="right", showarrow=False,
            text="from here the data<br>stops being real  ",
            font=dict(color=T.AMBER, size=11),
        )
    T.style(fig, height=300, hovermode="x unified")
    fig.update_layout(
        margin=dict(l=62, r=18, t=34, b=44), bargap=0.18, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.03, x=0,
                    font=dict(size=11, color=T.DIM)),
        xaxis=dict(type="date", dtick="M3", gridcolor="rgba(0,0,0,0)",
                   linecolor=T.BORD, tickformat="%b<br>%Y", tickfont=dict(size=10)),
        yaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickformat="~s", tickfont=dict(size=10.5)),
    )
    return fig


def _repeat_chart(k: dict) -> go.Figure:
    repeat = k["repeat_rate"]
    fig = go.Figure()
    fig.add_bar(
        x=[repeat * 100, (1 - repeat) * 100],
        y=["Bought more than once", "Bought once only"],
        orientation="h",
        marker=dict(color=[T.MINT, T.M1], line=dict(width=0)),
        text=[f"{repeat:.0%}", f"{1 - repeat:.0%}"],
        textposition="outside", textfont=dict(color=T.TXT, size=14),
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>%{x:.1f}% of customers<extra></extra>",
    )
    T.style(fig, height=170)
    fig.update_layout(
        margin=dict(l=10, r=64, t=8, b=24), bargap=0.45,
        xaxis=dict(range=[0, 100], ticksuffix="%", gridcolor=T.BORD,
                   zeroline=False, linecolor="rgba(0,0,0,0)", tickfont=dict(size=10.5)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)",
                   automargin=True, tickfont=dict(size=12, color=T.TXT)),
    )
    return fig


def _orders_dist_chart() -> go.Figure:
    d = db.orders_per_customer()
    d = d[d["orders"] <= 12]
    fig = go.Figure()
    fig.add_bar(
        x=d["orders"], y=d["customers"],
        marker=dict(color=T.V2, line=dict(width=0)),
        hovertemplate="<b>%{y:,}</b> customers placed %{x} orders<extra></extra>",
    )
    T.style(fig, height=250)
    fig.update_layout(
        margin=dict(l=62, r=18, t=10, b=46), bargap=0.22,
        xaxis=dict(title=dict(text="orders placed", font=dict(size=11, color=T.DIM)),
                   dtick=1, gridcolor="rgba(0,0,0,0)", linecolor=T.BORD,
                   tickfont=dict(size=10.5)),
        yaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickformat="~s", tickfont=dict(size=10.5)),
    )
    return fig


def _segment_chart(seg: pd.DataFrame) -> go.Figure:
    d = seg.iloc[::-1]
    fig = go.Figure()
    fig.add_bar(
        x=d["revenue"], y=d["segment"], orientation="h",
        marker=dict(color=T.MINT, line=dict(width=0)),
        text=[T.money(v) for v in d["revenue"]],
        textposition="outside", textfont=dict(color=T.DIM, size=11),
        cliponaxis=False,
        customdata=d[["customers", "orders"]].values,
        hovertemplate="<b>%{y}</b><br>%{x:$,.0f}<br>"
                      "%{customdata[0]:,} customers · %{customdata[1]:,} orders"
                      "<extra></extra>",
    )
    T.style(fig, height=210)
    fig.update_layout(
        margin=dict(l=10, r=86, t=8, b=26), bargap=0.4,
        xaxis=dict(gridcolor=T.BORD, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickprefix="$", tickformat="~s", tickfont=dict(size=10.5)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)",
                   automargin=True, tickfont=dict(size=12, color=T.TXT)),
    )
    return fig


# ---------------------------------------------------------------------
def _build():
    k = db.customer_kpis()
    seg = db.segment_summary()
    t = db.totals()
    aov = t["revenue"] / t["orders"] if t["orders"] else 0

    tbl = seg.copy()
    tbl["margin"] = (tbl["profit"] / tbl["revenue"]).map(lambda v: f"{v:.1%}")
    tbl["rev_per_cust"] = (seg["revenue"] / seg["customers"]).map(lambda v: f"${v:,.0f}")
    tbl["revenue"] = tbl["revenue"].map(lambda v: f"${v:,.0f}")
    tbl["profit"] = tbl["profit"].map(lambda v: f"${v:,.0f}")
    tbl["customers"] = tbl["customers"].map(lambda v: f"{int(v):,}")
    tbl["orders"] = tbl["orders"].map(lambda v: f"{int(v):,}")
    tbl.columns = ["Segment", "Customers", "Orders", "Revenue", "Profit",
                   "Margin", "Revenue per customer"]

    return html.Div(
        className="page",
        children=[
            T.page_head(
                "Customers",
                "Who buys from Meridian, how often they come back, and whether the "
                "customer base is actually growing.",
            ),
            html.Div(
                className="kpi-row kpi-row-tight",
                children=[
                    T.kpi(f"{k['customers']:,}", "CUSTOMERS"),
                    T.kpi(f"{k['avg_orders']:.2f}", "ORDERS PER CUSTOMER"),
                    T.kpi(f"{k['repeat_rate']:.0%}", "CAME BACK", T.MINT, T.MINT),
                    T.kpi(T.money(aov), "AVG ORDER VALUE"),
                ],
            ),
            html.Div(
                className="panel-grid",
                children=[
                    T.panel(
                        "Are we winning new customers?",
                        "Customers whose very first order fell in that month.",
                        dcc.Graph(figure=_new_customers_chart(),
                                  config={"displayModeBar": False}),
                        _reads(
                            "Real acquisition ran high in 2015 and then fell away "
                            "almost completely by 2017 - the business kept selling, "
                            "but to people it already had. The grey bars are NOT "
                            "growth: from October 2017 every single order in the "
                            "data comes from a brand-new customer who buys once and "
                            "never returns, and the customer numbers run in one "
                            "unbroken block. That is how the dataset was assembled, "
                            "not what the business did."
                        ),
                        wide=True,
                    ),
                    T.panel(
                        "Do they come back?",
                        None,
                        dcc.Graph(figure=_repeat_chart(k),
                                  config={"displayModeBar": False}),
                        _reads(
                            f"{k['repeat_rate']:.0%} of customers placed more than "
                            f"one order, averaging {k['avg_orders']:.2f} orders each. "
                            "For a retailer that is healthy - most of the revenue "
                            "comes from people who already trust the company."
                        ),
                    ),
                    T.panel(
                        "How many orders does one customer place?",
                        "Each bar is a number of orders; its height is how many "
                        "customers placed exactly that many.",
                        dcc.Graph(figure=_orders_dist_chart(),
                                  config={"displayModeBar": False}),
                        _reads(
                            "The single biggest group ordered once and stopped. "
                            "After that the customers who do come back cluster "
                            "around three to five orders. Moving people out of the "
                            "'ordered once' bar is where growth is cheapest."
                        ),
                    ),
                    T.panel(
                        "Which type of customer brings the money?",
                        None,
                        dcc.Graph(figure=_segment_chart(seg),
                                  config={"displayModeBar": False}),
                        _reads(
                            "Consumer is the largest segment by revenue, but look at "
                            "the table below before deciding where to push: revenue "
                            "per customer is what tells you which segment is worth "
                            "chasing, not the total."
                        ),
                        wide=True,
                    ),
                    T.panel(
                        "The three segments side by side", None,
                        T.table(tbl, max_rows=10), wide=True,
                    ),
                ],
            ),
        ],
    )


layout = _build

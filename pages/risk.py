"""
pages/risk.py - order outcomes, fraud exposure and loss-making lines.

Three things the revenue pages cannot show:

  1. Order status mix, including the SUSPECTED_FRAUD status that the
     dataset carries but that never appears in a revenue chart.
  2. Products that lose money. profit_amount goes negative in this data,
     so total profit hides a real gross loss.
  3. Whether discounting is what causes the losses.
"""

import dash
from dash import dcc, html
import plotly.graph_objects as go

import db
import theme as T

dash.register_page(__name__, path="/risk", name="Orders & risk")

STATUS = db.order_status_mix()
LOSS = db.loss_makers()
SHARE = db.loss_line_share()
BANDS = db.discount_bands()
TOT = db.totals()

TOTAL_ORDERS = int(STATUS["orders"].sum()) if len(STATUS) else 0


def _status_rows(keyword: str):
    if not len(STATUS):
        return STATUS
    return STATUS[STATUS["status"].str.upper().str.contains(keyword)]


FRAUD = _status_rows("FRAUD")
FRAUD_ORDERS = int(FRAUD["orders"].sum()) if len(FRAUD) else 0
FRAUD_REV = float(FRAUD["revenue"].sum()) if len(FRAUD) else 0.0
FRAUD_SHARE = FRAUD_ORDERS / TOTAL_ORDERS if TOTAL_ORDERS else 0.0

CANCEL = _status_rows("CANCEL")
CANCEL_ORDERS = int(CANCEL["orders"].sum()) if len(CANCEL) else 0

GROSS_LOSS = abs(SHARE["loss_value"])


# ---------------------------------------------------------------------
def status_bars() -> go.Figure:
    d = STATUS.sort_values("orders")
    risky = d["status"].str.upper().str.contains("FRAUD|CANCEL|HOLD|REVIEW")
    colours = [T.M1 if r else T.V1 for r in risky]

    fig = go.Figure(
        go.Bar(
            x=d["orders"], y=d["status"], orientation="h",
            marker=dict(color=colours, line=dict(width=0)),
            text=[f"{v:,}" for v in d["orders"]],
            textposition="outside",
            textfont=dict(size=11, color=T.DIM),
            cliponaxis=False,
            customdata=(d["orders"] / TOTAL_ORDERS * 100),
            hovertemplate="<b>%{y}</b><br>%{x:,} orders"
                          "<br>%{customdata:.1f}% of all orders<extra></extra>",
        )
    )
    T.style(fig, height=380)
    fig.update_layout(
        margin=dict(l=8, r=80, t=8, b=36),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)",
                   automargin=True, tickfont=dict(size=11.5)),
        xaxis=dict(gridcolor=T.BORD, zeroline=False,
                   linecolor="rgba(0,0,0,0)", tickformat="~s",
                   tickfont=dict(size=11)),
    )
    return fig


def profit_waterfall() -> go.Figure:
    gain = SHARE["gain_value"]
    loss = SHARE["loss_value"]
    net = gain + loss

    fig = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "total"],
            x=["Profit on winning lines", "Loss on losing lines", "Net profit"],
            y=[gain, loss, None],
            text=[T.money(gain), T.money(loss), T.money(net)],
            textposition="outside",
            textfont=dict(size=12, color=T.TXT),
            connector=dict(line=dict(color=T.BORD, width=1)),
            increasing=dict(marker=dict(color=T.MINT)),
            decreasing=dict(marker=dict(color=T.M1)),
            totals=dict(marker=dict(color=T.V1)),
            hovertemplate="<b>%{x}</b><br>%{y:$,.0f}<extra></extra>",
        )
    )
    T.style(fig, height=340)
    fig.update_layout(
        margin=dict(l=64, r=16, t=28, b=52),
        xaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor=T.BORD,
                   tickfont=dict(size=11.5)),
        yaxis=dict(gridcolor=T.BORD, zeroline=True, zerolinecolor=T.DIM,
                   linecolor="rgba(0,0,0,0)", tickprefix="$",
                   tickformat="~s", tickfont=dict(size=11)),
    )
    return fig


def discount_effect() -> go.Figure:
    order = ["0%", "0-5%", "5-10%", "10-15%", "15-20%", "20-25%", "25%+"]
    d = BANDS.copy()
    d["band"] = d["band"].astype(str)
    d["rank"] = d["band"].map({b: i for i, b in enumerate(order)})
    d = d.dropna(subset=["rank"]).sort_values("rank")
    d["margin"] = d["profit"] / d["revenue"]

    fig = go.Figure()
    fig.add_bar(
        x=d["band"], y=d["revenue"], name="Revenue",
        marker=dict(color=T.V2, line=dict(width=0)),
        hovertemplate="<b>%{y:$,.0f}</b><extra>Revenue</extra>",
    )
    fig.add_scatter(
        x=d["band"], y=d["margin"] * 100, name="Margin",
        yaxis="y2", mode="lines+markers",
        line=dict(color=T.MINT, width=2.6),
        marker=dict(size=8, color=T.MINT),
        hovertemplate="<b>%{y:.1f}%</b><extra>Margin</extra>",
    )
    T.style(fig, height=340, hovermode="x unified")
    fig.update_layout(
        margin=dict(l=66, r=62, t=28, b=52),
        bargap=0.3,
        showlegend=True,
        legend=dict(orientation="h", y=1.18, x=0,
                    font=dict(color=T.DIM, size=11.5)),
        xaxis=dict(title=dict(text="discount band",
                              font=dict(size=11, color=T.DIM)),
                   gridcolor="rgba(0,0,0,0)", linecolor=T.BORD,
                   tickfont=dict(size=11.5)),
        yaxis=dict(gridcolor=T.BORD, zeroline=False,
                   linecolor="rgba(0,0,0,0)", tickprefix="$",
                   tickformat="~s", tickfont=dict(size=11)),
        yaxis2=dict(overlaying="y", side="right", ticksuffix="%",
                    showgrid=False, tickfont=dict(size=11),
                    linecolor="rgba(0,0,0,0)"),
    )
    return fig


def loss_table():
    if not len(LOSS):
        return html.Div("No product has a negative total profit.",
                        className="empty")
    d = LOSS.head(12).copy()
    d["margin"] = (d["profit"] / d["revenue"]).map(lambda v: f"{v:.1%}")
    d["revenue"] = d["revenue"].map(lambda v: f"${v:,.0f}")
    d["profit"] = d["profit"].map(lambda v: f"-${abs(v):,.0f}")
    d["lines"] = d["lines"].map(lambda v: f"{int(v):,}")
    d = d[["product", "category", "revenue", "profit", "margin", "lines"]]
    d.columns = ["Product", "Category", "Revenue", "Loss", "Margin", "Lines"]
    return T.table(d, max_rows=12)


layout = html.Div(
    className="page",
    children=[
        T.page_head(
            "Orders and risk",
            "What happens to an order after it is placed, and where profit "
            "leaks out. None of this is visible in a revenue chart.",
        ),
        html.Div(
            className="kpi-row kpi-row-tight",
            children=[
                T.kpi(f"{FRAUD_SHARE:.2%}", "ORDERS FLAGGED FRAUD", T.M1, T.M1),
                T.kpi(T.money(FRAUD_REV), "REVENUE ON FLAGGED ORDERS", T.M1, T.M1),
                T.kpi(f"{SHARE['share']:.1%}", "ORDER LINES LOSE MONEY",
                      T.AMBER, T.AMBER),
                T.kpi(T.money(GROSS_LOSS), "GROSS LOSS ABSORBED", T.AMBER, T.AMBER),
            ],
        ),
        html.Div(
            className="panel-grid",
            children=[
                T.panel(
                    "Order status mix",
                    "Every status in the data. Magenta marks the statuses that "
                    "need attention - fraud, cancellation, hold and review.",
                    dcc.Graph(figure=status_bars(),
                              config={"displayModeBar": False}),
                ),
                T.panel(
                    "Where profit goes",
                    "Reported profit is a net figure. Split into winning and "
                    "losing lines it becomes clear how much gross profit is "
                    "cancelled out before it reaches the bottom line.",
                    dcc.Graph(figure=profit_waterfall(),
                              config={"displayModeBar": False}),
                ),
                T.panel(
                    "Does discounting cause the losses?",
                    "Revenue by discount band with the margin line on top. If "
                    "discounting were the cause, margin would fall as the band "
                    "rises. Read the line, not the bars.",
                    dcc.Graph(figure=discount_effect(),
                              config={"displayModeBar": False}),
                    wide=True,
                ),
                T.panel(
                    f"Products losing money ({len(LOSS)} in total)",
                    "Ranked by total loss. These carry revenue but destroy "
                    "profit over the full period.",
                    loss_table(),
                    wide=True,
                ),
            ],
        ),
        html.Div(
            className="note",
            children=[
                html.Strong("Reading the fraud figure. "),
                "SUSPECTED_FRAUD is a status recorded in the source data, not a "
                "prediction made here. It means the order was flagged for review, "
                "not that fraud was proven. "
                f"{CANCEL_ORDERS:,} orders were cancelled outright, which is a "
                "separate status and counted separately.",
            ],
        ),
    ],
)

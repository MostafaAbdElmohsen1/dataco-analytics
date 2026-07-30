"""
pages/trends.py - charts that move because the data moves.

Racing bar: cumulative revenue per category, one frame per month, so the
bars grow and overtake each other across the three years of data.
"""

import dash
from dash import dcc, html
import plotly.graph_objects as go

import db
import theme as T

dash.register_page(__name__, path="/trends", name="Trends")

RACE = db.category_cumulative_by_month()
CATS = db.category_revenue()
MONTHLY = db.monthly_revenue()

N_CATS = int(CATS["category_id"].nunique())
TOP_N = 12


def race_figure() -> go.Figure:
    """
    Plotly keeps a categorical axis in the order it is given, so each
    frame also sets yaxis.categoryarray. Without that the bars change
    length but never change places, which defeats the point of a race.
    """
    if not len(RACE):
        return T.style(go.Figure(), height=560)

    months = sorted(RACE["month"].unique())
    xmax = float(RACE["cum_revenue"].max()) * 1.28

    def slice_month(mth):
        return (
            RACE[RACE["month"] == mth]
            .nlargest(TOP_N, "cum_revenue")
            .sort_values("cum_revenue")
        )

    def bar(d):
        top = float(d["cum_revenue"].max()) or 1.0
        colours = [
            T.M1 if v / top > 0.75 else T.M2 if v / top > 0.45
            else T.V1 if v / top > 0.20 else T.V2
            for v in d["cum_revenue"]
        ]
        return go.Bar(
            x=d["cum_revenue"], y=d["label"], orientation="h",
            marker=dict(color=colours, line=dict(width=0)),
            text=[T.money(v) for v in d["cum_revenue"]],
            textposition="outside",
            textfont=dict(size=11.5, color=T.TXT),
            constraintext="none",
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:$,.0f} cumulative<extra></extra>",
        )

    def year_stamp(m):
        return dict(xref="paper", yref="paper", x=0.985, y=0.08,
                    xanchor="right", showarrow=False, text=m,
                    font=dict(size=46, color="rgba(255,0,128,.26)",
                              family="Segoe UI, Arial, sans-serif"))

    first = slice_month(months[0])
    fig = go.Figure(
        data=[bar(first)],
        frames=[
            go.Frame(
                data=[bar(slice_month(m))], name=m,
                layout=go.Layout(
                    yaxis=dict(categoryorder="array",
                               categoryarray=list(slice_month(m)["label"])),
                    annotations=[year_stamp(m)],
                ),
            )
            for m in months
        ],
    )

    T.style(fig, height=560)
    fig.update_layout(
        margin=dict(l=8, r=132, t=12, b=76),
        xaxis=dict(range=[0, xmax], gridcolor=T.BORD, zeroline=False,
                   linecolor="rgba(0,0,0,0)", tickprefix="$",
                   tickformat="~s", tickfont=dict(size=11)),
        yaxis=dict(categoryorder="array", categoryarray=list(first["label"]),
                   gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)",
                   automargin=True, tickfont=dict(size=12)),
        annotations=[year_stamp(months[0])],
        updatemenus=[dict(
            type="buttons", direction="left",
            x=0, y=-0.11, xanchor="left", yanchor="top",
            pad=dict(t=0, r=8),
            bgcolor="rgba(21,12,34,.92)",
            bordercolor=T.BORD, borderwidth=1,
            font=dict(color=T.TXT, size=12),
            buttons=[
                dict(label="  Play  ", method="animate",
                     args=[None, dict(frame=dict(duration=380, redraw=True),
                                      transition=dict(duration=320,
                                                      easing="cubic-in-out"),
                                      fromcurrent=True, mode="immediate")]),
                dict(label="  Pause  ", method="animate",
                     args=[[None], dict(frame=dict(duration=0, redraw=False),
                                        mode="immediate")]),
            ],
        )],
        sliders=[dict(
            active=0, x=0.16, y=-0.075, len=0.84,
            pad=dict(t=4, b=4),
            currentvalue=dict(visible=False),
            bgcolor=T.BORD, bordercolor="rgba(0,0,0,0)",
            activebgcolor=T.M1, tickcolor=T.BORD,
            font=dict(color=T.DIM, size=10),
            steps=[
                dict(label=(m[:4] if m.endswith("-01") else ""),
                     method="animate",
                     args=[[m], dict(frame=dict(duration=240, redraw=True),
                                     transition=dict(duration=200),
                                     mode="immediate")])
                for m in months
            ],
        )],
    )
    return fig


def cumulative_total() -> go.Figure:
    d = MONTHLY.copy()
    d["cum"] = d["revenue"].cumsum()
    fig = go.Figure()
    fig.add_scatter(
        x=d["month"], y=d["cum"], mode="lines",
        line=dict(color=T.M1, width=2.6),
        fill="tozeroy", fillcolor="rgba(255,0,128,.10)",
        hovertemplate="<b>%{y:$,.0f}</b> cumulative<extra></extra>",
    )
    T.style(fig, height=300, hovermode="x unified")
    fig.update_layout(
        margin=dict(l=70, r=16, t=10, b=48),
        xaxis=dict(type="date", gridcolor="rgba(0,0,0,0)", linecolor=T.BORD,
                   dtick="M6", tickformat="%b<br>%Y", tickfont=dict(size=11)),
        yaxis=dict(gridcolor=T.BORD, zeroline=False,
                   linecolor="rgba(0,0,0,0)", tickprefix="$",
                   tickformat="~s", tickfont=dict(size=11)),
    )
    return fig


layout = html.Div(
    className="page",
    children=[
        T.page_head(
            "Trends over time",
            "How the revenue mix built up between January 2015 and January 2018. "
            "Press play and watch the categories overtake each other.",
        ),
        T.panel(
            "Category race",
            f"Cumulative revenue, top {TOP_N} of {N_CATS} categories, one frame "
            "per month. A running total is used rather than monthly figures - "
            "monthly values jump around and the ranking flickers.",
            dcc.Graph(figure=race_figure(), config={"displayModeBar": False}),
            wide=True,
        ),
        T.panel(
            "Cumulative revenue",
            "The same story as one line. The slope is the monthly run rate; "
            "it flattens at the end because the data stops mid-January 2018.",
            dcc.Graph(figure=cumulative_total(),
                      config={"displayModeBar": False}),
            wide=True,
        ),
    ],
)

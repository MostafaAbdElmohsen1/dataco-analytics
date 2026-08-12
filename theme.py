"""
theme.py - palette, chart styling and small reusable components.
"""

from __future__ import annotations

import plotly.graph_objects as go
from dash import html

# ---------------------------------------------------------------------
# palette
# ---------------------------------------------------------------------
BG = "#0B0614"
SURF = "#150C22"
RAISED = "#1E1130"
BORD = "#2E1B45"
TXT = "#F5F0FA"
DIM = "#9A8AB0"

M1 = "#FF0080"   # magenta - primary accent
M2 = "#FF4D9D"
V1 = "#B14AED"
V2 = "#7928CA"
MINT = "#00E5A0"  # positive / success
AMBER = "#FFB020"  # warning

SEQ = [M1, M2, V1, V2]
CAT = [M1, MINT, V1, M2, AMBER, V2]


# ---------------------------------------------------------------------
# plotly
# ---------------------------------------------------------------------
def style(fig: go.Figure, height: int = 340, **kwargs) -> go.Figure:
    fig.update_layout(
        template=None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        showlegend=False,
        font=dict(family="Segoe UI, Arial, sans-serif", color=DIM, size=12),
        hoverlabel=dict(
            bgcolor=SURF, bordercolor=M1, font=dict(color=TXT, size=13)
        ),
        xaxis=dict(gridcolor=BORD, zeroline=False, linecolor=BORD),
        yaxis=dict(gridcolor=BORD, zeroline=False, linecolor=BORD),
        **kwargs,
    )
    return fig


def money(x: float) -> str:
    x = float(x)
    if abs(x) >= 1_000_000:
        return f"${x / 1_000_000:,.2f}M"
    if abs(x) >= 1_000:
        return f"${x / 1_000:,.1f}K"
    return f"${x:,.0f}"


# ---------------------------------------------------------------------
# components
# ---------------------------------------------------------------------
def kpi(value: str, label: str, accent: str = M1, value_colour: str | None = None):
    return html.Div(
        className="kpi",
        children=[
            html.Div(className="kpi-bar", style={"background": accent}),
            html.Div(
                [
                    html.Div(
                        value,
                        className="kpi-value",
                        style={"color": value_colour or TXT},
                    ),
                    html.Div(label, className="kpi-label"),
                ]
            ),
        ],
    )


def kpi_tile(value: str, label: str, colour: str | None = None):
    """
    مربع رقم صغير - بيستخدم في لوحة التفاصيل وصفحة الأسواق.
    مختلف عن kpi() اللي فوق: ده أصغر وبيتحط في شبكة، وده بيتحط في صف.
    """
    return html.Div(
        className="drill-tile",
        children=[
            html.Div(value, className="drill-tile-value",
                     style={"color": colour or TXT}),
            html.Div(label, className="drill-tile-label"),
        ],
    )


def panel(title: str, subtitle: str | None, *children, wide: bool = False):
    head = [html.Div(title, className="panel-title")]
    if subtitle:
        head.append(html.Div(subtitle, className="panel-sub"))
    return html.Div(
        className="panel panel-wide" if wide else "panel",
        children=head + list(children),
    )


def page_head(title: str, subtitle: str):
    return html.Div(
        className="page-head",
        children=[
            html.H2(title, className="page-title"),
            html.Div(subtitle, className="page-subtitle"),
        ],
    )


def table(df, max_rows: int = 20, status_col: str | None = None):
    """Lightweight dark table. Colours a status column if given."""
    cols = list(df.columns)

    def cell(col, val):
        if status_col and col == status_col:
            ok = str(val).lower() == "clean"
            return html.Td(
                str(val),
                className="tag tag-ok" if ok else "tag tag-warn",
            )
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return html.Td(f"{val:,}" if float(val).is_integer() else f"{val:,.2f}",
                           className="num")
        return html.Td(str(val))

    return html.Table(
        className="tbl",
        children=[
            html.Thead(html.Tr([html.Th(c) for c in cols])),
            html.Tbody(
                [
                    html.Tr([cell(c, r[c]) for c in cols])
                    for _, r in df.head(max_rows).iterrows()
                ]
            ),
        ],
    )


# ---------------------------------------------------------------------
# Pill filter groups
#
# Built from real buttons plus a dcc.Store rather than dcc.RadioItems,
# so the selected state is set from Python and never depends on a CSS
# :has() selector being supported by the browser.
#
# Usage inside a page module:
#
#     T.pill_group("year", "YEAR", ["All", "2015", "2016"])
#     T.register_pill_group("year", ["All", "2015", "2016"])
#
# Then read the value with Input(T.store_id("year"), "data").
# ---------------------------------------------------------------------
from dash import ALL, Input, Output, State, callback, ctx, dcc  # noqa: E402


def store_id(gid: str) -> str:
    return f"pillstore-{gid}"


def pill_group(gid: str, label: str, options: list[str], value: str | None = None):
    value = value if value is not None else options[0]
    return html.Div(
        className="filter",
        children=[
            dcc.Store(id=store_id(gid), data=value),
            html.Div(label, className="filter-label"),
            html.Div(
                className="pills",
                children=[
                    html.Button(
                        opt,
                        id={"type": f"pill-{gid}", "index": opt},
                        n_clicks=0,
                        className="pill pill-on" if opt == value else "pill",
                    )
                    for opt in options
                ],
            ),
        ],
    )


def register_pill_group(gid: str, options: list[str], default: str | None = None):
    default = default if default is not None else options[0]

    @callback(
        Output(store_id(gid), "data"),
        Input({"type": f"pill-{gid}", "index": ALL}, "n_clicks"),
        State(store_id(gid), "data"),
        prevent_initial_call=True,
    )
    def _pick(_clicks, current):
        trig = ctx.triggered_id
        if not isinstance(trig, dict):
            return current
        return trig.get("index", current)

    @callback(
        Output({"type": f"pill-{gid}", "index": ALL}, "className"),
        Input(store_id(gid), "data"),
    )
    def _mark(value):
        value = value if value is not None else default
        return ["pill pill-on" if o == value else "pill" for o in options]

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

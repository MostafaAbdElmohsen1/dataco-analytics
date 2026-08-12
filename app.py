"""
app.py - application shell and navigation.

Run with:
    .venv\\Scripts\\python.exe app.py

Pages live in ./pages and register themselves automatically.
"""

import os

import dash
from dash import Dash, html, dcc

import theme as T
import db

app = Dash(
    __name__,
    use_pages=True,
    pages_folder="pages",
    title="DataCo | Supply Chain Analytics",
    suppress_callback_exceptions=True,
)

# gunicorn looks for this object: `gunicorn app:server`
server = app.server

NAV = [
    ("/", "Home", "\u25c6"),
    ("/executive", "Executive", "\u25a6"),
    ("/network", "Network", "\u25cb"),
    ("/map", "World map", "\u2295"),
    ("/trends", "Trends", "\u25b8"),
    ("/risk", "Orders & risk", "\u26a0"),
    ("/quality", "Data Quality", "\u25c9"),
    ("/chat", "Ask the data", "\u25c7"),
]


def sidebar():
    links = []
    for path, label, glyph in NAV:
        links.append(
            dcc.Link(
                href=path,
                className="nav-link",
                children=[
                    html.Span(glyph, className="nav-glyph"),
                    html.Span(label, className="nav-label"),
                ],
            )
        )

    t = db.totals()
    return html.Div(
        className="sidebar",
        children=[
            html.Div(
                className="side-brand",
                children=[
                    html.Div("DataCo", className="side-brand-name"),
                    html.Div("ANALYTICS", className="side-brand-sub"),
                ],
            ),
            html.Nav(links, className="nav"),
            html.Div(
                className="side-foot",
                children=[
                    html.Div(f"{t['lines']:,}", className="side-foot-value"),
                    html.Div("ORDER LINES", className="side-foot-label"),
                    html.Div(
                        className="credit",
                        children=[
                            "Data: Constante, Silva & Pereira (2019), ",
                            html.I("DataCo Smart Supply Chain"),
                            ", Mendeley Data V5 \u2014 ",
                            html.A(
                                "CC BY 4.0",
                                href="https://creativecommons.org/licenses/by/4.0/",
                                target="_blank",
                                rel="noopener noreferrer",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


app.layout = html.Div(
    className="shell",
    children=[
        html.Div(className="grid-overlay"),
        sidebar(),
        html.Main(dash.page_container, className="content"),
    ],
)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    debug = os.environ.get("DASH_DEBUG", "1") == "1"
    print(f"\n  DataCo -> http://127.0.0.1:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)

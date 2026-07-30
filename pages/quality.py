"""
pages/quality.py - live data quality audit.

Every table on this page is computed from the database each time the
page loads. Nothing is hard-coded, so the numbers cannot drift away
from the data.
"""

import dash
from dash import html

import db
import theme as T

dash.register_page(__name__, path="/quality", name="Data Quality")

DIMS = db.audit_dimensions()
RELS = db.audit_relationships()
DUPES = db.duplicate_labels()

n_dims = len(DIMS)
n_clean_dims = int((DIMS["status"] == "clean").sum())
n_rels = len(RELS)
n_clean_rels = int((RELS["status"] == "clean").sum())
n_orphans = int(RELS["orphan rows"].sum()) if n_rels else 0

layout = html.Div(
    className="page",
    children=[
        T.page_head(
            "Data quality audit",
            "Key integrity, referential integrity and label collisions - "
            "recomputed live from the database.",
        ),
        html.Div(
            className="kpi-row kpi-row-tight",
            children=[
                T.kpi(
                    f"{n_clean_dims}/{n_dims}",
                    "DIMENSIONS WITH CLEAN KEYS",
                    T.MINT if n_clean_dims == n_dims else T.AMBER,
                    T.MINT if n_clean_dims == n_dims else T.AMBER,
                ),
                T.kpi(
                    f"{n_clean_rels}/{n_rels}",
                    "RELATIONSHIPS INTACT",
                    T.MINT if n_clean_rels == n_rels else T.AMBER,
                    T.MINT if n_clean_rels == n_rels else T.AMBER,
                ),
                T.kpi(
                    f"{n_orphans:,}",
                    "ORPHAN ROWS",
                    T.MINT if n_orphans == 0 else T.M1,
                    T.MINT if n_orphans == 0 else T.M1,
                ),
                T.kpi(
                    f"{len(DUPES)}",
                    "DUPLICATE LABELS",
                    T.M1 if len(DUPES) else T.MINT,
                    T.M1 if len(DUPES) else T.MINT,
                ),
            ],
        ),
        T.panel(
            "Dimension key integrity",
            "One row per dimension. A clean dimension has as many unique keys as rows, "
            "no nulls, and one label per key.",
            T.table(DIMS, max_rows=30, status_col="status"),
            wide=True,
        ),
        T.panel(
            "Referential integrity",
            "Orphan rows are child records whose foreign key has no matching parent.",
            T.table(RELS, max_rows=30, status_col="status"),
            wide=True,
        ),
        T.panel(
            "Label collisions",
            "Labels that map to more than one key. Grouping a chart by these labels "
            "would silently merge distinct members.",
            T.table(DUPES, max_rows=30)
            if len(DUPES)
            else html.Div("No label collisions found.", className="empty"),
            wide=True,
        ),
        html.Div(
            className="note",
            children=[
                html.Strong("Why this page exists. "),
                "Dimension views that expose only labels force every visual to group by "
                "text. Where a label is reused, two distinct members collapse into one "
                "number and the error is invisible. Every query in this application "
                "groups by the primary key and uses the label for display only.",
            ],
        ),
    ],
)

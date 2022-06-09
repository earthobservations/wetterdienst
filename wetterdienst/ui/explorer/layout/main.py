# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
Wetterdienst Explorer UI layout.
"""
import dash_bootstrap_components as dbc
from dash import dcc, html

from wetterdienst.ui.explorer.layout.observations_germany import dashboard_layout


def get_about_modal():
    return dbc.Modal(
        [
            dbc.ModalHeader(html.P("About Wetterdienst Explorer")),
            dbc.ModalBody(
                dcc.Markdown(
                    """
                    Wetterdienst Explorer is a Dash user interface on top of Wetterdienst.

                    **Resources**:
                    - https://wetterdienst.readthedocs.io/en/latest/overview.html
                    - https://github.com/earthobservations/wetterdienst
                    """
                )
            ),
            dbc.ModalFooter(dbc.Button("Close", id="close-about", className="ml-auto")),
        ],
        id="modal-about",
        is_open=False,
        centered=True,
        autoFocus=True,
        size="lg",
        keyboard=True,
        fade=True,
        backdrop=True,
    )


def get_app_layout():
    return html.Div(
        [
            dcc.Location(id="url", refresh=False),
            html.Div(
                [
                    html.H1("Wetterdienst Explorer"),
                    dbc.Navbar(
                        [dbc.NavLink("About", id="open-about")],
                        id="navbar",
                    ),
                    get_about_modal(),
                ],
                className="d-flex flex-row",
                style={"justify-content": "space-between"},
            ),
            dashboard_layout(),
        ],
        id="mainContainer",
        style={"display": "flex", "flex-direction": "column"},
    )

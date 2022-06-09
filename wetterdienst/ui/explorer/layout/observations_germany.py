# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from dash import dcc, html

from wetterdienst.api import ApiEndpoints


def get_providers():
    return [{"label": provider.__name__, "value": provider.__name__} for provider in ApiEndpoints]


def dashboard_layout() -> html:
    """
    Dashboard layout for observations in Germany.
    """
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Provider:"),
                            dcc.Dropdown(
                                id="select-provider",
                                options=get_providers(),
                                value=None,
                                multi=False,
                                className="dcc_control",
                            ),
                            html.Div("Network:"),
                            dcc.Dropdown(
                                id="select-network",
                                value=None,
                                multi=False,
                                className="dcc_control",
                            ),
                            html.Div("Resolution:"),
                            dcc.Dropdown(
                                id="select-resolution",
                                value=None,
                                multi=False,
                                className="dcc_control",
                            ),
                            html.Div("Dataset:"),
                            dcc.Dropdown(
                                id="select-dataset",
                                value=None,
                                multi=False,
                                className="dcc_control",
                            ),
                            html.Div("Parameter:"),
                            dcc.Dropdown(
                                id="select-parameter",
                                value=None,
                                multi=False,
                                className="dcc_control",
                            ),
                            html.Div("Period:"),
                            dcc.Dropdown(
                                id="select-period",
                                value=None,
                                multi=False,
                                className="dcc_control",
                            ),
                            html.Div("Station:"),
                            dcc.Loading(
                                id="loading-1",
                                children=[
                                    dcc.Dropdown(
                                        id="select-station",
                                        multi=False,
                                        className="dcc_control",
                                    ),
                                    html.Div(
                                        [],
                                        id="dataframe-values",
                                        style={"display": "None"},
                                    ),
                                ],
                            ),
                        ],
                        id="navigation",
                        className="col wd-panel d-flex flex-column",
                    ),
                    html.Div(
                        [
                            html.Div(
                                id="status-response-stations_result",
                            ),
                            html.Hr(),
                            html.Div(
                                id="status-response-values",
                            ),
                        ],
                        id="status-response",
                        className="col wd-panel flex-column",
                    ),
                    html.Div(
                        [dcc.Graph(id="map-stations_result")],
                        id="map",
                        className="col wd-panel",
                    ),
                ],
                id="header",
                className="d-flex flex-row",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            dcc.Graph(id="graph-values"),
                        ],
                        id="graph",
                        className="col wd-panel",
                    ),
                ],
                className="d-flex flex-row",
            ),
            html.Div([], id="dataframe-stations_result", style={"display": "None"}),
        ],
    )

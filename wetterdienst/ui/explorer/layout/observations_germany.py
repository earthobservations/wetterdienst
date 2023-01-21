# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import dash_leaflet as dl
from dash import dcc, html

from wetterdienst.api import RequestRegistry


def get_providers():
    return [{"label": provider, "value": provider} for provider in RequestRegistry.get_provider_names()]


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
                            dcc.Dropdown(
                                id="select-provider",
                                options=get_providers(),
                                value=None,
                                multi=False,
                                className="dcc_control",
                                placeholder="Select provider...",
                            ),
                            dcc.Dropdown(
                                id="select-network",
                                value=None,
                                multi=False,
                                className="dcc_control",
                                placeholder="Select network...",
                            ),
                            dcc.Dropdown(
                                id="select-resolution",
                                value=None,
                                multi=False,
                                className="dcc_control",
                                placeholder="Select resolution...",
                            ),
                            dcc.Dropdown(
                                id="select-dataset",
                                value=None,
                                multi=False,
                                className="dcc_control",
                                placeholder="Select dataset...",
                            ),
                            dcc.Dropdown(
                                id="select-parameter",
                                value=None,
                                multi=False,
                                className="dcc_control",
                                placeholder="Select parameter...",
                            ),
                            dcc.Dropdown(
                                id="select-period",
                                value=None,
                                multi=False,
                                className="dcc_control",
                                placeholder="Select period...",
                            ),
                            dcc.Loading(
                                id="loading-1",
                                children=[
                                    dcc.Dropdown(
                                        id="select-station",
                                        multi=False,
                                        className="dcc_control",
                                        placeholder="Select station...",
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
                        className="col map-panel d-flex flex-column",
                    ),
                    html.Div(
                        [
                            dl.Map(
                                [
                                    dl.LayersControl(
                                        [
                                            dl.BaseLayer(
                                                dl.TileLayer(),
                                                name="OpenStreetMaps",
                                                checked=True,
                                            ),
                                            dl.LayerGroup(id="map-stations_result"),
                                        ],
                                    ),
                                ],
                                id="map",
                            ),
                        ],
                        id="map-div",
                        className="col map-panel",
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
                        className="col map-panel flex-column",
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

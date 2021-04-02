# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import operator

import dash_core_components as dcc
import dash_html_components as html

from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationResolution,
)


def get_parameters():
    return sorted(
        [
            {"label": param.value, "value": param.value}
            for param in DwdObservationDataset
        ],
        key=operator.itemgetter("label"),
    )


def get_resolutions():
    return [
        {"label": param.value, "value": param.value}
        for param in DwdObservationResolution
    ]


def get_periods():
    return [
        {"label": param.value, "value": param.value} for param in DwdObservationPeriod
    ]


def dashboard_layout() -> html:
    """
    Dashboard layout for observations in Germany.
    """
    return html.Div(
        [
            dcc.Location(id="url", refresh=False),
            html.H1("Wetterdienst UI"),
            # html.P("Hello world"),
            html.Div(
                [
                    html.Div(
                        [
                            html.P("Parameter:"),
                            dcc.Dropdown(
                                id="select-parameter",
                                options=get_parameters(),
                                value=DwdObservationDataset.TEMPERATURE_AIR.value,
                                multi=False,
                                className="dcc_control",
                            ),
                            html.P("Resolution:"),
                            dcc.Dropdown(
                                id="select-resolution",
                                options=get_resolutions(),
                                value=DwdObservationResolution.HOURLY.value,
                                multi=False,
                                className="dcc_control",
                            ),
                            html.P("Period:"),
                            dcc.Dropdown(
                                id="select-period",
                                options=get_periods(),
                                value=DwdObservationPeriod.RECENT.value,
                                multi=False,
                                className="dcc_control",
                            ),
                            html.P("Weather station:"),
                            dcc.Dropdown(
                                id="select-station",
                                multi=False,
                                className="dcc_control",
                            ),
                            html.P("Variable:"),
                            dcc.Loading(
                                id="loading-1",
                                children=[
                                    dcc.Dropdown(
                                        id="select-variable",
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
                        className="pretty_container four columns",
                    ),
                    html.Div(
                        [
                            html.Div(
                                id="status-response-stations",
                            ),
                            html.Div(
                                id="status-response-values",
                            ),
                        ],
                        id="status-response",
                        className="pretty_container four columns",
                    ),
                    html.Div(
                        [dcc.Graph(id="map-stations")],
                        id="map",
                        className="pretty_container four columns",
                        style={"align-self": "flex-end"},
                    ),
                ],
                id="header",
                className="row flex-display",
                style={"justify-content": "space-between", "margin-bottom": "25px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            # html.P("Time-series graph", style={"text-align": "center"}),
                            dcc.Graph(id="graph-values"),
                        ],
                        id="graph",
                        className="pretty_container twelve columns",
                    ),
                ],
                className="row flex-display",
            ),
            html.Div([], id="dataframe-stations", style={"display": "None"}),
        ],
        id="mainContainer",
        style={"display": "flex", "flex-direction": "column"},
    )

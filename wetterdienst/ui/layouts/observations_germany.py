""" holds html layout for observation dashboard """
import dash_core_components as dcc
import dash_html_components as html
from wetterdienst.dwd.observations import (
    DWDObservationPeriod,
    DWDObservationResolution,
    DWDObservationParameterSet,
)


def dashboard_layout() -> html:
    """ main dashboard layout """
    return html.Div(
        [
            dcc.Location(id="url", refresh=False),
            html.Div(
                [
                    html.Div(
                        [
                            html.P("Select Parameter:"),
                            dcc.Dropdown(
                                id="select-parameter",
                                options=[
                                    {"label": param.value, "value": param.value}
                                    for param in DWDObservationParameterSet
                                ],
                                value=DWDObservationParameterSet.PRECIPITATION.value,
                                multi=False,
                                className="dcc_control",
                            ),
                            html.P("Select time resolution:"),
                            dcc.Dropdown(
                                id="select-time-resolution",
                                options=[
                                    {"label": param.value, "value": param.value}
                                    for param in DWDObservationResolution
                                ],
                                value=DWDObservationResolution.MINUTE_10.value,
                                multi=False,
                                className="dcc_control",
                            ),
                            html.P("Select period type: [NOW, RECENT, HISTORIC]"),
                            dcc.Dropdown(
                                id="select-period-type",
                                options=[
                                    {"label": param.value, "value": param.value}
                                    for param in DWDObservationPeriod
                                ],
                                value=DWDObservationPeriod.RECENT.value,
                                multi=False,
                                className="dcc_control",
                            ),
                            html.P("Select weather station:"),
                            dcc.Dropdown(
                                id="select-weather-stations",
                                multi=False,
                                className="dcc_control",
                            ),
                            html.P("Select variable:"),
                            dcc.Loading(
                                id="loading-1",
                                children=[
                                    dcc.Dropdown(
                                        id="select-variable",
                                        multi=False,
                                        className="dcc_control",
                                    ),
                                    html.Div(
                                        [], id="hidden-div", style={"display": "None"}
                                    ),
                                ],
                            ),
                        ],
                        className="pretty_container four columns",
                    ),
                    html.Div(
                        [dcc.Graph(id="sites-map")],
                        className="pretty_container eight columns",
                    ),
                ],
                id="header",
                className="row flex-display",
                style={"margin-bottom": "25px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.P(
                                "Visualisation of Data", style={"text-align": "center"}
                            ),
                            dcc.Graph(id="graph1"),
                        ],
                        className="pretty_container twelve columns",
                    ),
                ],
                className="row flex-display",
            ),
            html.Div([], id="hidden-div-metadata", style={"display": "None"}),
        ],
        id="mainContainer",
        style={"display": "flex", "flex-direction": "column"},
    )

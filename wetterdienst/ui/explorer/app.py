# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
Wetterdienst Explorer UI Dash application.
"""
import logging
from typing import Optional

import dash
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import plotly.graph_objects as go
import requests
from dash.dependencies import Input, Output, State

from wetterdienst.exceptions import InvalidParameterCombination
from wetterdienst.metadata.columns import Columns
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)
from wetterdienst.ui.explorer.layout.main import get_app_layout
from wetterdienst.ui.explorer.library import add_annotation_no_data, default_figure
from wetterdienst.ui.explorer.util import frame_summary
from wetterdienst.util.cli import setup_logging

log = logging.getLogger(__name__)

# Create and configure Dash application object.
app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width"}],
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.themes.SANDSTONE],
)
app.title = "Wetterdienst Explorer"
app.layout = get_app_layout()

empty_frame = pd.DataFrame().to_json(date_format="iso", orient="split")


@app.callback(
    Output("modal-about", "is_open"),
    [Input("open-about", "n_clicks"), Input("close-about", "n_clicks")],
    [State("modal-about", "is_open")],
)
def toggle_about(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open


@app.callback(
    Output("dataframe-stations", "children"),
    [
        Input("select-parameter", "value"),
        Input("select-resolution", "value"),
        Input("select-period", "value"),
    ],
)
def fetch_stations(parameter: str, resolution: str, period: str):
    """
    Fetch "stations" data.

    This will be used to populate the navigation chooser and to render the map.

    The data will be stored on a hidden within the browser DOM.
    """
    log.info(
        f"Requesting stations for "
        f"parameter={parameter}, "
        f"resolution={resolution}, "
        f"period={period}"
    )
    try:
        stations = DwdObservationRequest(
            parameter=DwdObservationDataset(parameter),
            resolution=DwdObservationResolution(resolution),
            period=DwdObservationPeriod(period),
        ).all()
    except (requests.exceptions.ConnectionError, InvalidParameterCombination) as ex:
        log.warning(ex)
        # raise PreventUpdate
        log.error("Unable to connect to data source")
        return empty_frame

    df = stations.df

    log.info(f"Propagating stations data frame with {frame_summary(df)}")

    return df.to_json(date_format="iso", orient="split")


@app.callback(
    Output("dataframe-values", "children"),
    [
        Input("select-parameter", "value"),
        Input("select-resolution", "value"),
        Input("select-period", "value"),
        Input("select-station", "value"),
    ],
)
def fetch_values(parameter: str, resolution: str, period: str, station_id: int):
    """
    Fetch "values" data.

    This will be used to populate the navigation chooser and to render the graph.

    The data will be stored on a hidden within the browser DOM.
    """

    # Sanity checks.
    if station_id is None:
        log.warning("Querying without station_id is rejected")
        return empty_frame

    log.info(
        f"Requesting values for "
        f"station_id={station_id}, "
        f"parameter={parameter}, "
        f"resolution={resolution}, "
        f"period={period}"
    )
    stations = DwdObservationRequest(
        parameter=DwdObservationDataset(parameter),
        resolution=DwdObservationResolution(resolution),
        period=DwdObservationPeriod(period),
        tidy=False,
        humanize=True,
    ).filter_by_station_id(station_id=(str(station_id),))

    try:
        df = stations.values.all().df
    except ValueError:
        log.exception("No data received")
        return empty_frame

    df = df.dropna(axis=0)

    log.info(f"Propagating values data frame with {frame_summary(df)}")

    return df.to_json(date_format="iso", orient="split")


@app.callback(
    Output("select-station", "options"),
    [Input("dataframe-stations", "children")],
)
def render_navigation_stations(payload):
    """
    Compute list of items from "stations" data for populating the "stations"
    chooser element.
    """
    stations_data = pd.read_json(payload, orient="split")
    if stations_data.empty:
        return []
    log.info(f"Rendering stations dropdown from {frame_summary(stations_data)}")
    return [
        {"label": name, "value": station_id}
        for name, station_id in sorted(
            zip(
                stations_data[Columns.NAME.value],
                stations_data[Columns.STATION_ID.value],
            )
        )
    ]


@app.callback(
    Output("select-variable", "options"),
    [Input("dataframe-values", "children")],
)
def render_navigation_variables(payload):
    """
    Compute list of items from "values" data for populating the "variables"
    chooser element.
    """
    climate_data = pd.read_json(payload, orient="split")
    log.info(f"Rendering variable dropdown from {frame_summary(climate_data)}")

    # Build list of columns to be selectable.
    columns = []
    for column in climate_data.columns:

        # Skip some columns.
        if column in ["station_id", "date"]:
            continue

        columns.append({"label": column, "value": column})

    return columns


@app.callback(
    Output("status-response-stations", "children"),
    [
        Input("select-parameter", "value"),
        Input("select-resolution", "value"),
        Input("select-period", "value"),
        Input("dataframe-stations", "children"),
    ],
)
def render_status_response_stations(
    parameter: str, resolution: str, period: str, payload: str
):
    """
    Report about the status of the query.
    """

    title = [dcc.Markdown("#### Stations")]

    empty_message = [
        dcc.Markdown(
            f"""
No data.
Maybe the combination of "{parameter}", "{resolution}" and "{period}" is invalid.
    """
        )
    ]

    try:
        stations_data = pd.read_json(payload, orient="split")
    except ValueError:
        return title + empty_message

    if stations_data.empty:
        return title + empty_message

    return title + [
        html.Div(
            [
                html.Div(f"Columns: {len(stations_data.columns)}"),
                html.Div(f"Records: {len(stations_data)}"),
            ]
        )
    ]


@app.callback(
    Output("status-response-values", "children"),
    [
        Input("dataframe-values", "children"),
        State("select-parameter", "value"),
        State("select-resolution", "value"),
        State("select-period", "value"),
        State("select-station", "value"),
        State("select-variable", "value"),
    ],
)
def render_status_response_values(
    payload: str,
    parameter: str,
    resolution: str,
    period: str,
    station: str,
    variable: str,
):
    """
    Report about the status of the query.
    """
    values_data = pd.read_json(payload, orient="split")

    messages = [dcc.Markdown("#### Values")]

    if values_data.empty:

        # Main message.
        empty_message = [html.Span("No data. ")]

        candidates = ["parameter", "resolution", "period", "station", "variable"]
        missing = []
        for candidate in candidates:
            if locals().get(candidate) is None:
                missing.append(candidate)

        if missing:
            empty_message.append(
                html.Span(f"Please select all of the missing options {missing}.")
            )

        messages += [html.Div(empty_message), html.Br()]

    messages += [
        html.Div(f"Columns: {len(values_data.columns)}"),
        html.Div(f"Records: {len(values_data)}"),
        html.Br(),
    ]

    if "date" in values_data:
        messages += [
            html.Div(f"Station: {station}"),
            html.Div(f"Begin date: {values_data.date.iloc[0]}"),
            html.Div(f"End date: {values_data.date.iloc[-1]}"),
        ]

    return html.Div(messages)


@app.callback(
    Output("map-stations", "figure"),
    [Input("dataframe-stations", "children")],
)
def render_map(payload):
    """
    Create a "map" Figure element from "stations" data.
    """
    stations_data = pd.read_json(payload, orient="split")

    layout_germany = dict(
        hovermode="closest",
        mapbox=dict(
            bearing=0,
            center=go.layout.mapbox.Center(lat=51.5, lon=10),
            style="open-street-map",
            pitch=0,
            zoom=4.5,
        ),
        margin=go.layout.Margin(
            l=0,
            r=0,
            b=0,
            t=0,
        ),
    )

    if stations_data.empty:
        fig = go.Figure(
            data=go.Scattermapbox(
                mode="markers",
            ),
            layout=layout_germany,
        )
        add_annotation_no_data(fig)
        return fig

    log.info(f"Rendering stations map from {frame_summary(stations_data)}")
    fig = go.Figure(
        data=go.Scattermapbox(
            lat=stations_data[Columns.LATITUDE.value],
            lon=stations_data[Columns.LONGITUDE.value],
            mode="markers",
            marker=go.scattermapbox.Marker(size=5),
            text=[
                f"Name: {name}<br>Id: {station_id}<br>Height: {altitude}m "
                for name, altitude, station_id in zip(
                    stations_data[Columns.NAME.value],
                    stations_data[Columns.HEIGHT.value],
                    stations_data[Columns.STATION_ID.value],
                )
            ],
        ),
        layout=layout_germany,
    )

    return fig


@app.callback(
    Output("graph-values", "figure"),
    [Input("select-variable", "value")],
    [Input("dataframe-values", "children")],
)
def render_graph(variable, payload):
    """
    Create a "graph" Figure element from "values" data.
    """

    try:
        climate_data = pd.read_json(payload, orient="split")
    except ValueError:
        climate_data = pd.DataFrame()

    log.info(
        f"Rendering graph for variable={variable} from {frame_summary(climate_data)}"
    )

    fig = default_figure(climate_data, variable)

    fig.update_layout(
        margin=go.layout.Margin(
            l=0,  # left margin
            r=0,  # right margin
            b=0,  # bottom margin
            t=0,  # top margin
        )
    )

    return fig


def start_service(
    listen_address: Optional[str] = None, reload: Optional[bool] = False
):  # pragma: no cover
    """
    This entrypoint will be used by `wetterdienst.cli`.
    """

    setup_logging()

    if listen_address is None:
        listen_address = "127.0.0.1:7891"

    host, port = listen_address.split(":")
    port = int(port)
    app.server.run(host=host, port=port, debug=reload)


if __name__ == "__main__":
    """
    This entrypoint will be used by `dash.testing`.
    """
    app.run_server(debug=True)

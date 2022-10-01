# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
Wetterdienst Explorer UI Dash application.
"""
import logging
from typing import Optional

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
import requests
from dash import Input, Output, State, dcc, html

from wetterdienst.api import ApiEndpoints
from wetterdienst.exceptions import InvalidParameterCombination
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import PeriodType
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType
from wetterdienst.ui.core import get_stations, get_values
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
    Output("dataframe-stations_result", "children"),
    [
        Input("select-provider", "value"),
        Input("select-network", "value"),
        Input("select-resolution", "value"),
        Input("select-dataset", "value"),
        Input("select-parameter", "value"),
        Input("select-period", "value"),
    ],
)
def fetch_stations(provider: str, network: str, resolution: str, dataset: str, parameter: str, period: str):
    """
    Fetch "stations_result" data.

    This will be used to populate the navigation chooser and to render the map.

    The data will be stored on a hidden within the browser DOM.
    """
    if not (provider and network and resolution and dataset and parameter and period):
        return empty_frame

    api = ApiEndpoints[provider][network].value

    if period == "ALL":
        period = [*api._period_base]

    log.info(f"Requesting stations for parameter={parameter}, resolution={resolution}, period={period}")

    try:
        stations = get_stations(
            api=api,
            parameter=parameter,
            resolution=resolution,
            period=period,
            date=None,
            issue="latest",
            all_=True,
            station_id=None,
            name=None,
            coordinates=None,
            rank=None,
            distance=None,
            bbox=None,
            sql=None,
            si_units=True,
            tidy=True,
            humanize=True,
            skip_empty=False,
            skip_threshold=0.95,
            dropna=False,
        )
    except (requests.exceptions.ConnectionError, InvalidParameterCombination) as ex:
        log.warning(ex)
        log.error("Unable to connect to data source")
        return empty_frame

    df = stations.df

    log.info(f"Propagating stations data frame with {frame_summary(df)}")

    return df.to_json(date_format="iso", orient="split")


@app.callback(
    Output("dataframe-values", "children"),
    [
        Input("select-provider", "value"),
        Input("select-network", "value"),
        Input("select-resolution", "value"),
        Input("select-dataset", "value"),
        Input("select-parameter", "value"),
        Input("select-period", "value"),
        Input("select-station", "value"),
    ],
)
def fetch_values(
    provider: str, network: str, resolution: str, dataset: str, parameter: str, period: str, station_id: int
):
    """
    Fetch "values" data.

    This will be used to populate the navigation chooser and to render the graph.

    The data will be stored on a hidden within the browser DOM.
    """
    if not (provider and network and resolution and dataset and parameter and period):
        return empty_frame

    # Sanity checks.
    if station_id is None:
        log.warning("Querying without station_id is rejected")
        return empty_frame

    api = ApiEndpoints[provider][network].value

    if period == "ALL":
        period = [*api._period_base]

    log.info(
        f"Requesting values for station_id={station_id}, parameter={parameter}, resolution={resolution}, "
        f"period={period}"
    )

    try:
        values = get_values(
            api=api,
            parameter=parameter,
            resolution=resolution,
            period=period,
            date=None,
            issue="latest",
            all_=None,
            station_id=station_id,
            name=None,
            coordinates=None,
            rank=None,
            distance=None,
            bbox=None,
            sql=None,
            sql_values=None,
            si_units=True,
            skip_empty=False,
            skip_threshold=0.95,
            dropna=False,
            tidy=True,
            humanize=True,
        )
        df = values.df
    except ValueError:
        log.exception("No data received")
        return empty_frame

    df = df.drop(columns="quality").dropna(axis=0)

    log.info(f"Propagating values data frame with {frame_summary(df)}")

    return df.to_json(date_format="iso", orient="split")


@app.callback(
    Output("select-station", "options"),
    [Input("dataframe-stations_result", "children")],
)
def render_navigation_stations(payload):
    """
    Compute list of items from "stations_result" data for populating the "stations_result"
    chooser element.
    """
    stations_data = pd.read_json(payload, orient="split")
    if stations_data.empty:
        return []
    log.info(f"Rendering stations_result dropdown from {frame_summary(stations_data)}")
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
    Output("status-response-stations_result", "children"),
    [
        Input("select-provider", "value"),
        Input("select-network", "value"),
        Input("select-resolution", "value"),
        Input("select-dataset", "value"),
        Input("select-parameter", "value"),
        Input("select-period", "value"),
        Input("dataframe-stations_result", "children"),
    ],
)
def render_status_response_stations(
    provider: str, network: str, resolution: str, dataset: str, parameter: str, period: str, payload: str
):
    """
    Report about the status of the query.
    """

    title = [dcc.Markdown("#### Stations")]

    if not (provider and network and resolution and dataset and parameter and period):
        empty_message = [dcc.Markdown("Choose from provider, network, resolution, dataset,  parameter and period.")]

        return title + empty_message

    empty_message = [
        dcc.Markdown(
            f"""
            No data. Maybe the combination of "{resolution}", "{dataset}", "{parameter}" and "{period}"
            is invalid for provider "{provider}" and network "{network}".
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
        State("select-provider", "value"),
        State("select-network", "value"),
        State("select-resolution", "value"),
        State("select-dataset", "value"),
        State("select-parameter", "value"),
        State("select-period", "value"),
        State("select-station", "value"),
    ],
)
def render_status_response_values(
    payload: str,
    provider: str,
    network: str,
    resolution: str,
    dataset: str,
    parameter: str,
    period: str,
    station: str,
):
    """
    Report about the status of the query.
    """
    values_data = pd.read_json(payload, orient="split")

    messages = [dcc.Markdown("#### Values")]

    if values_data.empty:

        # Main message.
        empty_message = [html.Span("No data. ")]

        candidates = ["provider", "network", "resolution", "dataset", "parameter", "period", "station"]
        missing = []
        for candidate in candidates:
            if locals().get(candidate) is None:
                missing.append(candidate)

        if missing:
            empty_message.append(html.Span(f"Please select all of the missing options {missing}."))

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
    Output("map-stations_result", "figure"),
    [Input("dataframe-stations_result", "children")],
)
def render_map(payload):
    """
    Create a "map" Figure element from "stations_result" data.
    """
    stations_data = pd.read_json(payload, orient="split")

    layout_germany = {
        "hovermode": "closest",
        "mapbox": {
            "bearing": 0,
            "center": go.layout.mapbox.Center(lat=51.5, lon=10),
            "style": "open-street-map",
            "pitch": 0,
            "zoom": 4.5,
        },
        "margin": go.layout.Margin(
            l=0,
            r=0,
            b=0,
            t=0,
        ),
    }

    if stations_data.empty:
        fig = go.Figure(
            data=go.Scattermapbox(
                mode="markers",
            ),
            layout=layout_germany,
        )
        add_annotation_no_data(fig)
        return fig

    log.info(f"Rendering stations_result map from {frame_summary(stations_data)}")
    return go.Figure(
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


@app.callback(
    Output("graph-values", "figure"),
    [Input("select-parameter", "value"), Input("dataframe-values", "children")],
)
def render_graph(parameter, payload):
    """
    Create a "graph" Figure element from "values" data.
    """

    try:
        climate_data = pd.read_json(payload, orient="split")
    except ValueError:
        climate_data = pd.DataFrame()

    log.info(f"Rendering graph for parameter={parameter} from {frame_summary(climate_data)}")

    fig = default_figure(climate_data, parameter)

    fig.update_layout(
        margin=go.layout.Margin(
            l=0,  # left margin
            r=0,  # right margin
            b=0,  # bottom margin
            t=0,  # top margin
        )
    )

    return fig


@app.callback(Output("select-network", "options"), Input("select-provider", "value"))
def set_network_options(provider):
    """Set network options based on provider"""
    if not provider:
        return []

    return [{"label": network.name, "value": network.name} for network in ApiEndpoints[provider]]


@app.callback(
    Output("select-resolution", "options"),
    [
        Input("select-provider", "value"),
        Input("select-network", "value"),
    ],
)
def set_resolution_options(provider, network):
    """Set resolution options based on provider and network"""
    if not (provider and network):
        return []

    api = ApiEndpoints[provider][network].value

    if api == DwdMosmixRequest:
        return [{"label": resolution.name, "value": resolution.name} for resolution in DwdMosmixType]
    else:
        return [{"label": resolution.name, "value": resolution.name} for resolution in api._resolution_base]


@app.callback(
    Output("select-dataset", "options"),
    [
        Input("select-provider", "value"),
        Input("select-network", "value"),
        Input("select-resolution", "value"),
    ],
)
def set_dataset_options(provider, network, resolution):
    """Set dataset options based on provider network and resolution"""
    if not (provider and network and resolution):
        return []

    api = ApiEndpoints[provider][network].value

    if api._has_datasets and not api._unique_dataset:
        # first dataset is placeholder for unique dataset with parameters combined from all datasets
        datasets = [{"label": resolution, "value": resolution}]
        for dataset in api._parameter_base[resolution]:
            if not hasattr(dataset, "name"):
                ds_dict = {"label": dataset.__name__, "value": dataset.__name__}
                if ds_dict not in datasets:
                    datasets.append(ds_dict)
        return datasets
    else:
        return [{"label": resolution, "value": resolution}]


@app.callback(
    [
        Output("select-parameter", "options"),
        Output("select-period", "options"),
    ],
    [
        Input("select-provider", "value"),
        Input("select-network", "value"),
        Input("select-resolution", "value"),
        Input("select-dataset", "value"),
    ],
)
def set_parameter_options(provider, network, resolution, dataset):
    """Set parameter options based on provider, network, resolution and dataset"""
    if not (provider and network and resolution and dataset):
        return [], []

    api = ApiEndpoints[provider][network].value

    if api._has_datasets and not api._unique_dataset:
        if dataset == resolution:
            # Return tidy parameters e.g. parameters grouped under one resolution
            parameters = [
                {"label": parameter.name, "value": parameter.name}
                for parameter in api._parameter_base[resolution]
                if hasattr(parameter, "name")
            ]
        else:
            # return individual parameters of one dataset e.g. climate_summary
            parameters = [
                {"label": parameter.name, "value": parameter.name}
                for parameter in api._parameter_base[resolution][dataset]
            ]
    else:
        # If network only provides parameters but not datasets, just return them all as option
        parameters = [
            {"label": parameter.name, "value": parameter.name} for parameter in api._parameter_base[resolution]
        ]

    if api._period_type == PeriodType.FIXED:
        period = list(api._period_base)[0]
        periods = [{"label": period.name, "value": period.name}]
    else:
        # Periods ALL placeholder, may use click options for multiple periods
        periods = [{"label": "ALL", "value": "ALL"}]
        for period in api._period_base:
            periods.append({"label": period.name, "value": period.name})

    return parameters, periods


@app.callback(
    [
        Output("select-network", "value"),
        Output("select-resolution", "value"),
        Output("select-dataset", "value"),
        Output("select-parameter", "value"),
        Output("select-period", "value"),
    ],
    [
        Input("select-provider", "value"),
        Input("select-network", "value"),
        Input("select-resolution", "value"),
        Input("select-dataset", "value"),
        Input("select-parameter", "value"),
        Input("select-period", "value"),
    ],
)
def reset_values(provider, network, resolution, dataset, parameter, period):
    """Reset settings values if any previous parameter has been changed e.g.
    when a new provider is selected, reset network, resolution, etc"""
    last_triggered = dash.callback_context.triggered[0]["prop_id"].split(".")[0]

    previous = ("select-provider", "select-network", "select-resolution", "select-dataset")

    if last_triggered in previous[:1]:
        network = None

    if last_triggered in previous[:2]:
        resolution = None

    if last_triggered in previous[:3]:
        dataset = None

    if last_triggered in previous:
        parameter = None
        period = None

    return network, resolution, dataset, parameter, period


def start_service(listen_address: Optional[str] = None, reload: Optional[bool] = False):  # pragma: no cover
    """
    This entrypoint will be used by `wetterdienst.cli`.
    """

    setup_logging()

    if listen_address is None:
        listen_address = "127.0.0.1:7891"

    host, port = listen_address.split(":")
    port = int(port)

    app.run_server(host=host, port=port, debug=reload)


if __name__ == "__main__":
    """
    This entrypoint will be used by `dash.testing`.
    """
    app.run_server(debug=True)

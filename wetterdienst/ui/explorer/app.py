# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
Wetterdienst Explorer UI Dash application.
"""
import json
import logging
from typing import Optional

import dash
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import plotly.graph_objects as go
import polars as pl
from dash import Input, Output, State, dcc, html
from geojson import Feature, FeatureCollection, Point

from wetterdienst.api import RequestRegistry
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import PeriodType
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType
from wetterdienst.ui.core import get_stations, get_values
from wetterdienst.ui.explorer.layout.main import get_app_layout
from wetterdienst.ui.explorer.library import default_figure
from wetterdienst.ui.explorer.util import frame_summary
from wetterdienst.util.cli import setup_logging

log = logging.getLogger(__name__)

# Create and configure Dash application object.
app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width"}],
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.themes.SANDSTONE],
    suppress_callback_exceptions=True,
)
app.title = "Wetterdienst Explorer"
app.layout = get_app_layout()

empty_frame = pl.DataFrame().write_json(row_oriented=True)


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

    api = RequestRegistry.resolve(provider, network)

    if period == "ALL":
        period = [*api._period_base]

    log.info(f"Requesting stations for parameter={parameter}, resolution={resolution}, period={period}")

    try:
        stations = get_stations(
            api=api,
            parameter=parameter,
            resolution=resolution,
            period=period,
            lead_time="short",
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
            shape="long",
            humanize=True,
            skip_empty=False,
            skip_threshold=0.95,
            skip_criteria="min",
            dropna=False,
        )
    except Exception as e:
        log.warning(e)
        log.error("Unable to connect to data source")
        return empty_frame

    df = stations.df

    df = df.with_columns(
        pl.col(Columns.START_DATE.value).map_elements(
            lambda date: date and date.isoformat() or None, return_dtype=pl.Utf8
        ),
        pl.col(Columns.END_DATE.value).map_elements(
            lambda date: date and date.isoformat() or None, return_dtype=pl.Utf8
        ),
    )

    log.info(f"Propagating stations data frame with {frame_summary(df)}")

    return df.write_json(row_oriented=True)


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

    api = RequestRegistry.resolve(provider, network)

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
            shape="long",
            skip_empty=False,
            skip_threshold=0.95,
            skip_criteria="min",
            dropna=False,
            humanize=True,
        )
    except ValueError:
        log.exception("No data received")
        return empty_frame

    df = values.df
    df = df.drop("quality").drop_nulls()
    df = df.with_columns(pl.col("date").map_elements(lambda date: date.isoformat()))

    log.info(f"Propagating values data frame with {frame_summary(df)}")

    return json.dumps({"values": df.to_dicts(), "unit_dict": values.stations.stations.discover()})


@app.callback(
    Output("select-station", "options"),
    [Input("dataframe-stations_result", "children")],
)
def render_navigation_stations(payload):
    """
    Compute list of items from "stations_result" data for populating the "stations_result"
    chooser element.
    """
    data = json.loads(payload)

    if not data:
        return []

    try:
        stations_data = pl.from_dicts(data, infer_schema_length=0)
    except ValueError:
        stations_data = pl.DataFrame()

    log.info(f"Rendering stations_result dropdown from {frame_summary(stations_data)}")
    return [
        {"label": name, "value": station_id}
        for name, station_id in stations_data.select("name", "station_id").iter_rows()
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

    data = json.loads(payload)

    if not data:
        return title + empty_message

    stations_data = pl.from_dicts(data)

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
    try:
        climate_data = pl.from_dicts(payload["values"])
    except (KeyError, ValueError, TypeError):
        climate_data = pl.DataFrame()

    messages = [dcc.Markdown("#### Values")]

    if climate_data.is_empty():
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
        html.Div(f"Columns: {len(climate_data.columns)}"),
        html.Div(f"Records: {len(climate_data)}"),
        html.Br(),
    ]
    if "date" in climate_data:
        messages += [
            html.Div(f"Station: {station}"),
            html.Div(f"Begin date: {climate_data.get_column('date').min()}"),
            html.Div(f"End date: {climate_data.get_column('date').max()}"),
        ]

    return html.Div(messages)


@app.callback(
    Output("map-stations_result", "children"),
    [Input("dataframe-stations_result", "children")],
)
def render_map(payload):
    """
    Create a "map" Figure element from "stations_result" data.
    """
    data = json.loads(payload)
    if not data:
        return []
    stations_data = pl.from_dicts(data, infer_schema_length=0)
    stations_data = stations_data.with_columns(
        pl.col("station_id").cast(pl.Utf8), pl.col("latitude").cast(pl.Float64), pl.col("longitude").cast(pl.Float64)
    )
    log.info(f"Rendering stations_result map from {frame_summary(stations_data)}")
    # columns used for constructing geojson object
    features = [
        Feature(
            geometry=Point((longitude, latitude)),
            properties={"station_id": station_id},
        )
        for station_id, latitude, longitude in stations_data.select("station_id", "latitude", "longitude").iter_rows()
    ]
    # all the other columns used as properties
    properties = stations_data.drop("latitude", "longitude").to_dicts()
    # whole geojson object
    feature_collection = FeatureCollection(features=features, properties=properties)
    return dl.GeoJSON(id="markers", data=feature_collection, cluster=True, zoomToBounds=True, zoomToBoundsOnClick=True)


@app.callback(
    Output("select-station", "value"),
    [
        Input("markers", "click_feature"),
    ],
)
def map_click(click_feature):
    if click_feature is not None:
        return click_feature.get("properties", {}).get("station_id")
    return None


def _get_station_text(row):
    return f"Name: {row['name']}\nId: {row['station_id']}\nHeight: {row['height']}m"


@app.callback(
    Output("graph-values", "figure"),
    [Input("select-parameter", "value"), Input("select-resolution", "value"), Input("dataframe-values", "children")],
)
def render_graph(parameter, resolution, payload: str):
    """
    Create a "graph" Figure element from "values" data.
    """
    data = json.loads(payload)

    try:
        climate_data = pl.from_dicts(data["values"])
        unit_dict = data["unit_dict"]
    except (KeyError, ValueError, TypeError):
        climate_data = pl.DataFrame()
        unit_dict = {}

    log.info(f"Rendering graph for parameter={parameter} from {frame_summary(climate_data)}")

    fig = default_figure(climate_data, parameter, resolution, unit_dict)

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

    return [{"label": network, "value": network} for network in RequestRegistry.get_network_names(provider)]


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

    api = RequestRegistry.resolve(provider, network)

    if issubclass(api, DwdMosmixRequest):
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

    api = RequestRegistry.resolve(provider, network)

    datasets = [{"label": resolution, "value": resolution}]
    for dataset in api._parameter_base[resolution]:
        if not hasattr(dataset, "name"):
            ds_dict = {"label": dataset.__name__, "value": dataset.__name__}
            if ds_dict not in datasets:
                datasets.append(ds_dict)
    return datasets


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

    api = RequestRegistry.resolve(provider, network)

    if dataset == resolution:
        # Return long shape parameters e.g. parameters grouped under one resolution
        parameters = [
            {"label": parameter.name, "value": parameter.name}
            for parameter in api._parameter_base[resolution]
            if hasattr(parameter, "name")
        ]
    else:
        # return individual parameters of one dataset e.g. climate_summary
        parameters = [
            {"label": parameter.name, "value": parameter.name} for parameter in api._parameter_base[resolution][dataset]
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

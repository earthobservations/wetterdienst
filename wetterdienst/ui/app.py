""" main app for wetterdienst-ui """
import logging

import dash
import dash_html_components as html
import pandas as pd
import plotly.graph_objects as go
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from wetterdienst.exceptions import InvalidParameterCombination
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)
from wetterdienst.ui.layouts.observations_germany import dashboard_layout
from wetterdienst.ui.plotting.figure import default_figure

log = logging.getLogger(__name__)


app = dash.Dash(
    __name__, meta_tags=[{"name": "viewport", "content": "width=device-width"}]
)

app.title = "Wetterdienst UI"
app.layout = dashboard_layout()

OBSERVATION_VALUES_PARAMETER_COLUMN = "parameter"
OBSERVATION_VALUES_VALUE_COLUMN = "value"
OBSERVATION_VALUES_DATE_COLUMN = "date"


@app.callback(
    Output("hidden-div-metadata", "children"),
    [
        Input("select-parameter", "value"),
        Input("select-time-resolution", "value"),
        Input("select-period-type", "value"),
    ],
)
def update_meta_data(parameter, time_resolution, period_type):
    """
    Function to update the metadata according to
    the selection of the dropdowns
    It stores MetaData behind a hidden div on the front-end
    """
    log.info(
        f"Requesting stations for "
        f"parameter={parameter}, "
        f"resolution={time_resolution}, "
        f"period={period_type}"
    )
    try:
        stations = DwdObservationRequest(
            parameter=DwdObservationDataset(parameter),
            resolution=DwdObservationResolution(time_resolution),
            period=DwdObservationPeriod(period_type),
        ).all()
    except InvalidParameterCombination:
        raise PreventUpdate

    df = stations.df

    log.info(f"Forwarding stations data frame {frame_summary(df)}")

    return df.to_json(date_format="iso", orient="split")


@app.callback(
    Output("graph1", "figure"),
    [Input("select-variable", "value")],
    [State("hidden-div", "children")],
)
def make_graph(variable, jsonified_data):
    """  takes hidden data to show up the central plot  """

    # FIXME: This does not work yet.
    if not jsonified_data:
        return html.Div(html.P("No data available"))

    climate_data = pd.read_json(jsonified_data, orient="split")
    log.info(
        f"Building graph for variable={variable} from {frame_summary(climate_data)}"
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


@app.callback(
    Output("hidden-div", "children"),
    [Input("select-weather-stations", "value")],
    [
        State("select-parameter", "value"),
        State("select-time-resolution", "value"),
        State("select-period-type", "value"),
    ],
)
def update_data(
    station_id: int, parameter: str, time_resolution: str, period_type: str
):
    """ stores selected data behind a hidden div box to share with other callbacks """
    log.info(
        f"Requesting values for "
        f"station_id={station_id}, "
        f"parameter={parameter}, "
        f"resolution={time_resolution}, "
        f"period={period_type}"
    )
    stations = DwdObservationRequest(
        parameter=DwdObservationDataset(parameter),
        resolution=DwdObservationResolution(time_resolution),
        period=DwdObservationPeriod(period_type),
        tidy=False,
        humanize=True,
    ).filter(station_id=tuple(str(station_id)))

    try:
        df = stations.values.all().df
    except ValueError:
        log.exception("No data received")
        return pd.DataFrame().to_json(date_format="iso", orient="split")

    df = df.dropna(axis=0)

    # 2021-03-30 [amo]: I amended this from the original version by Daniel.
    #                   However, I am a bit clueless what I am doing here.

    # df.value = df.value.astype(float)
    # df = df.pivot_table(
    #    values=OBSERVATION_VALUES_VALUE_COLUMN,
    #    columns=OBSERVATION_VALUES_PARAMETER_COLUMN,
    #    index=OBSERVATION_VALUES_DATE_COLUMN,
    # )

    log.info(f"Forwarding values data frame {frame_summary(df)}")

    return df.to_json(date_format="iso", orient="split")


@app.callback(Output("select-variable", "options"), [Input("hidden-div", "children")])
def update_variable_drop_down(jsonified_data):
    """ Depending on the selection the variable drop_down is adapted """
    climate_data = pd.read_json(jsonified_data, orient="split")
    log.info(f"Building variable dropdown from {frame_summary(climate_data)}")
    return [{"label": column, "value": column} for column in climate_data.columns]


@app.callback(
    Output("select-weather-stations", "options"),
    [Input("hidden-div-metadata", "children")],
)
def update_weather_stations_dropdown(jsonified_data):
    """ Depending on the selection the variable drop_down is adapted """
    meta_data = pd.read_json(jsonified_data, orient="split")
    log.info(f"Building stations dropdown from {frame_summary(meta_data)}")
    return [
        {"label": name, "value": station_id}
        for name, station_id in zip(meta_data.station_name, meta_data.station_id)
    ]


def frame_summary(frame: pd.DataFrame):
    return f"columns={list(frame.columns)}, length={len(frame)}"


@app.callback(Output("sites-map", "figure"), [Input("hidden-div-metadata", "children")])
def update_systems_map(jsonified_data):
    meta_data = pd.read_json(jsonified_data, orient="split")
    log.info(f"Building stations map from {frame_summary(meta_data)}")
    fig = go.Figure(
        go.Scattermapbox(
            lat=meta_data.latitude,
            lon=meta_data.longitude,
            mode="markers",
            marker=go.scattermapbox.Marker(size=5),
            text=[
                f"{name} <br>Station Height: {altitude}m <br>Id: {station_id}"
                for name, altitude, station_id in zip(
                    meta_data.station_name,
                    meta_data.height,
                    meta_data.station_id,
                )
            ],
        )
    )

    fig.update_layout(
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
    return fig


def start_service(listen_address, reload: bool = False):  # pragma: no cover
    host, port = listen_address.split(":")
    port = int(port)
    app.server.run(host=host, port=port, debug=reload)


if __name__ == "__main__":
    app.run_server(debug=True)

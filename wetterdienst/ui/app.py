""" main app for wetterdienst-ui """
import os

import dash
import pandas as pd
import plotly.graph_objects as go
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from wetterdienst.dwd.observations import (
    DWDObservationStations,
    DWDObservationValues,
    DWDObservationPeriod,
    DWDObservationResolution,
    DWDObservationParameterSet,
)
from wetterdienst.exceptions import InvalidParameterCombination

from ui.layouts.observations_germany import dashboard_layout
from ui.plotting.figure import default_figure

app = dash.Dash(
    __name__, meta_tags=[{"name": "viewport", "content": "width=device-width"}]
)
server = app.server

app.layout = dashboard_layout()

OBSERVATION_VALUES_PARAMETER_COLUMN = "PARAMETER"
OBSERVATION_VALUES_VALUE_COLUMN = "VALUE"
OBSERVATION_VALUES_DATE_COLUMN = "DATE"


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
    try:
        meta_data = DWDObservationStations(
            parameter=DWDObservationParameterSet(parameter),
            resolution=DWDObservationResolution(time_resolution),
            period=DWDObservationPeriod(period_type),
        ).all()
    except InvalidParameterCombination:
        raise PreventUpdate

    return meta_data.to_json(date_format="iso", orient="split")


@app.callback(
    Output("graph1", "figure"),
    [Input("select-variable", "value")],
    [State("hidden-div", "children")],
)
def make_graph(variable, jsonified_data):
    """  takes hidden data to show up the central plot  """
    climate_data = pd.read_json(jsonified_data, orient="split")
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
    climate_data = DWDObservationValues(
        station_id=station_id,
        parameter=DWDObservationParameterSet(parameter),
        resolution=DWDObservationResolution(time_resolution),
        period=DWDObservationPeriod(period_type),
        humanize_parameters=True,
    ).all()
    climate_data = climate_data.dropna(axis=0)
    climate_data.VALUE = climate_data.VALUE.astype(float)
    climate_data = climate_data.pivot_table(
        values=OBSERVATION_VALUES_VALUE_COLUMN,
        columns=OBSERVATION_VALUES_PARAMETER_COLUMN,
        index=OBSERVATION_VALUES_DATE_COLUMN,
    )
    return climate_data.to_json(date_format="iso", orient="split")


@app.callback(Output("select-variable", "options"), [Input("hidden-div", "children")])
def update_variable_drop_down(jsonified_data):
    """ Depending on the selection the variable drop_down is adapted """
    climate_data = pd.read_json(jsonified_data, orient="split")
    return [{"label": column, "value": column} for column in climate_data.columns]


@app.callback(
    Output("select-weather-stations", "options"),
    [Input("hidden-div-metadata", "children")],
)
def update_weather_stations_dropdown(jsonified_data):
    """ Depending on the selection the variable drop_down is adapted """
    meta_data = pd.read_json(jsonified_data, orient="split")
    return [
        {"label": name, "value": station_id}
        for name, station_id in zip(meta_data.STATION_NAME, meta_data.STATION_ID)
    ]


@app.callback(Output("sites-map", "figure"), [Input("hidden-div-metadata", "children")])
def update_systems_map(jsonified_data):
    meta_data = pd.read_json(jsonified_data, orient="split")
    fig = go.Figure(
        go.Scattermapbox(
            lat=meta_data.LATITUDE,
            lon=meta_data.LONGITUDE,
            mode="markers",
            marker=go.scattermapbox.Marker(size=10),
            text=[
                f"{name} <br>Station Height: {altitude}m <br>Id: {station_id}"
                for name, altitude, station_id in zip(
                    meta_data.STATION_NAME,
                    meta_data.HEIGHT,
                    meta_data.STATION_ID,
                )
            ],
        )
    )

    fig.update_layout(
        hovermode="closest",
        mapbox=dict(
            bearing=0,
            center=go.layout.mapbox.Center(lat=50, lon=10),
            style="open-street-map",
            pitch=0,
            zoom=5,
        ),
        margin=go.layout.Margin(
            l=0,
            r=0,
            b=0,
            t=0,
        ),
    )
    return fig


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    server.run(host="0.0.0.0", port=port, processes=4)

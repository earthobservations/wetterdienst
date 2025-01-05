# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import duckdb
import plotly.express as px
import polars as pl
import streamlit as st

from wetterdienst import Resolution, Settings, Wetterdienst, __version__
from wetterdienst.core.timeseries.unit import UnitConverter

if TYPE_CHECKING:
    from wetterdienst.core.timeseries.metadata import DatasetModel, MetadataModel, ParameterModel, ResolutionModel
    from wetterdienst.core.timeseries.request import TimeseriesRequest

# this env is set manually on streamlit.com
LIVE = os.getenv("LIVE", "false").lower() == "true"

SUBDAILY_AT_MOST = [
    Resolution.MINUTE_1.value,
    Resolution.MINUTE_5.value,
    Resolution.MINUTE_10.value,
    Resolution.MINUTE_15.value,
    Resolution.HOURLY.value,
    Resolution.HOUR_6.value,
    Resolution.SUBDAILY.value,
]

SQL_DEFAULT = """
SELECT *
FROM df
WHERE value IS NOT NULL
""".strip()


@st.cache_resource
def get_api(provider: str, network: str):
    return Wetterdienst(provider, network)


@st.cache_resource
def get_metadata(api: TimeseriesRequest):
    return api.metadata


def get_stations(provider: str, network: str, request_kwargs: dict):
    request_kwargs = request_kwargs.copy()
    request_kwargs["settings"] = Settings(**request_kwargs["settings"])
    return get_api(provider, network)(**request_kwargs).all()


def get_station(provider: str, network: str, request_kwargs: dict, station_id: str):
    request_kwargs = request_kwargs.copy()
    request_kwargs["settings"] = Settings(**request_kwargs["settings"])
    return get_api(provider, network)(**request_kwargs).filter_by_station_id(station_id)


def create_plotly_fig(
    df: pl.DataFrame,
    variable_column: str,
    variable_filter: list[str],
    x: str,
    y: str,
    facet: bool,
    lm: str | None,
    settings: dict,
):
    if "unit" in df.columns:
        df = df.with_columns(
            pl.struct(["parameter", "unit"])
            .map_elements(lambda s: f"{s['parameter']} ({s['unit']})", return_dtype=pl.String)
            .alias("parameter"),
        )
    fig = px.scatter(
        x=df.get_column(x).to_list(),
        y=df.get_column(y).to_list(),
        color=df.get_column(variable_column).to_list(),
        facet_row=df.get_column(variable_column).to_list() if facet else None,
        trendline=lm,
    )
    fig.update_traces(
        marker={"opacity": settings["opacity"], "symbol": settings["symbol"], "size": settings["size"]},
    )
    fig.update_layout(
        legend={"x": 0, "y": 1.08},
        height=400 * len(variable_filter),  # plot height times parameters
        xaxis_title="date",
        yaxis_title="value",
    )
    fig.update_yaxes(matches=None)
    # Update y-axis titles to use facet labels and remove subplot titles
    for i, annotation in enumerate(fig.layout.annotations):
        axis_name = f"yaxis{i + 1}"
        if axis_name in fig.layout:
            fig.layout[axis_name].title.text = annotation.text
        annotation.text = ""
    return fig


title = f"Wetterdienst Explorer v{__version__}"
st.set_page_config(page_title=title)
st.title(title)

with st.sidebar:
    st.header("Settings")

    st.subheader("General")
    ts_humanize = st.checkbox("humanize", value=True)
    ts_convert_units = st.checkbox("convert_units", value=True)
    if ts_convert_units:
        unit_converter = UnitConverter()
        unit_targets = {k: v.name for k, v in unit_converter.targets.items()}
        with st.expander("set unit targets"):
            ts_unit_targets = {k: st.text_input(k, value=v) for k, v in unit_targets.items()}
    settings = {"ts_humanize": ts_humanize, "ts_convert_units": ts_convert_units, "ts_unit_targets": ts_unit_targets}

    st.subheader("Plotting")

    marker_size = st.slider("marker size", min_value=1, max_value=8, value=2)
    opacity = st.slider("opacity", min_value=0.0, max_value=1.0, value=1.0)
    marker_symbol = st.selectbox("marker symbol", options=["circle", "square", "diamond", "cross", "x"])
    plotting_settings = {"opacity": opacity, "symbol": marker_symbol, "size": marker_size}

st.subheader("Introduction")
st.markdown(
    """
    This is a streamlit app based on the [wetterdienst](https://github.com/earthobservations/wetterdienst)
    library that enables the user to analyze meteorological and hydrological data by the
    [Deutscher Wetterdienst](https://www.dwd.de/) and others. You can select any of the stations (by station id or
    name), download its data (as CSV or JSON) and get visualizations of it. Enjoy!
    """,
)

st.subheader("Request")
provider_options = Wetterdienst.get_provider_names()
provider = st.selectbox("Select provider", options=provider_options, index=provider_options.index("dwd"))
network_options = Wetterdienst.get_network_names(provider)
network = st.selectbox(
    "Select network",
    options=network_options,
    index=network_options.index("observation") if "observation" in network_options else 0,
)


api = get_api(provider, network)
metadata: MetadataModel = api.metadata

resolution_options = list(metadata)
resolution_names = [r.name for r in resolution_options]
resolution: ResolutionModel = st.selectbox(
    "Select resolution",
    options=resolution_options,
    index=resolution_names.index("daily") if "daily" in resolution_names else 0,
    disabled=len(resolution_options) == 1,
    format_func=lambda r: r.name,
)

# for hosted app, we disallow higher resolutions as the machine might not be able to handle it
if LIVE:
    if resolution.value in SUBDAILY_AT_MOST:
        st.warning("Higher resolutions are disabled for hosted app. Choose at least daily resolution.")
        st.stop()

dataset_options = list(resolution)
dataset_names = [d.name for d in dataset_options]
dataset: DatasetModel = st.selectbox(
    "Select dataset",
    options=dataset_options,
    index=dataset_names.index("climate_summary") if "climate_summary" in dataset_names else 0,
    disabled=len(dataset_options) == 1,
    format_func=lambda d: d.name,
)

parameter_options = list(dataset)
parameter_options = [dataset] + parameter_options
parameter: DatasetModel | ParameterModel = st.selectbox(
    "Select parameter", options=parameter_options, index=0, format_func=lambda p: p.name
)

parameter = dataset if parameter == dataset else parameter

# TODO: replace this with a general request kwargs resolver
request_kwargs = {
    "parameters": parameter,
    "settings": settings,
}

df_stations = get_stations(provider, network, request_kwargs).df
if df_stations.is_empty():
    st.warning("No stations found. Please adjust your request.")
    st.stop()
with st.expander("Map of all stations", expanded=False):
    st.map(df_stations, latitude="latitude", longitude="longitude")

st.subheader("Station")
station = st.selectbox(
    "Select climate station",
    options=df_stations.sort("name").rows(named=True),
    format_func=lambda s: f"{s['name']} [{s['station_id']}]",
)
df = pl.DataFrame()
if station:
    request_station = get_station(provider, network, request_kwargs, station["station_id"])
    df = request_station.values.all().df
    station["start_date"] = station["start_date"].isoformat() if station["start_date"] else None
    station["end_date"] = station["end_date"].isoformat() if station["end_date"] else None
    with st.expander("Station JSON", expanded=False):
        st.json(station)
    with st.expander("Map of selected station", expanded=False):
        st.map(request_station.df, latitude="latitude", longitude="longitude")

st.subheader("Values")
df_stats = (
    df.drop_nulls(["value"])
    .group_by(["parameter"])
    .agg(pl.len().alias("count"), pl.min("date").alias("min_date"), pl.max("date").alias("max_date"))
)
df_stats = df_stats.sort("parameter")
df_stats = df_stats.with_columns(
    pl.col("min_date").map_elements(lambda d: d.isoformat(), return_dtype=pl.String).alias("min_date"),
    pl.col("max_date").map_elements(lambda d: d.isoformat(), return_dtype=pl.String).alias("max_date"),
)
values_summary = df_stats.to_dicts()
with st.expander("Stats JSON", expanded=False):
    st.json(values_summary)

st.info(
    """
    Use [duckdb](https://duckdb.org/docs/sql/introduction.html) sql queries to transform the data.
    Important:
      - use **FROM df**
      - use single quotes for strings e.g. 'a_string'
    """,
)
sql_query = st.text_area(
    "sql query",
    value=SQL_DEFAULT,
)
if station:
    if sql_query:
        df = duckdb.query(sql_query).pl()
    st.dataframe(df, hide_index=True, use_container_width=True)
    data_csv = df.write_csv()
    st.download_button("Download CSV", data_csv, "data.csv", "text/csv")
    data_json = df.with_columns(
        pl.col("date").map_elements(lambda d: d.isoformat(), return_dtype=pl.String)
    ).write_json()
    st.download_button(
        "Download JSON",
        data_json,
        "data.json",
        "text/json",
    )

st.subheader("Plot")
plot_enable = not df.is_empty()

with st.expander("settings", expanded=True):
    columns = sorted(df.columns)
    column_x = st.selectbox("Column X", options=columns, index="date" in columns and columns.index("date"))
    columns = columns.copy()
    columns.remove(column_x)
    column_y = st.selectbox("Column Y", options=columns, index="value" in columns and columns.index("value"))
    columns = columns.copy()
    columns.remove(column_y)
    variable_column = st.selectbox(
        "Column Variable",
        options=columns,
        index="parameter" in columns and columns.index("parameter"),
    )
    variable_options = df.get_column(variable_column).unique().sort().to_list()
    variable_filter = st.multiselect("Variable Filter", options=variable_options)
    df = df.filter(pl.col(variable_column).is_in(variable_filter))
    facet = st.toggle("facet")
    lm = st.selectbox("linear model", options=["none", "lowess", "ols", "expanding"])
    lm = lm if lm != "none" else None

if not plot_enable:
    st.warning("No plot. Reason: empty DataFrame")
elif not variable_filter:
    st.warning("No plot. Reason: empty variable filter")
else:
    fig = create_plotly_fig(df, variable_column, variable_filter, column_x, column_y, facet, lm, plotting_settings)
    st.plotly_chart(fig)

st.subheader("Credits")
st.markdown(
    """
    This app is powered by [wetterdienst](https://github.com/earthobservations/wetterdienst) from
    [earthobservations](https://github.com/earthobservations) developers.

    Credits for the data go to
    [Deutscher Wetterdienst](https://www.dwd.de) - Germany's national meteorological service - and
    [others](https://wetterdienst.readthedocs.io/en/latest/data/coverage.html) for publishing their data as
    **open data**.

    Credits also go to [streamlit](https://streamlit.io/) for hosting this
    app.

    Special credits go to [Daniel Lassahn](https://github.com/meteoDaniel) who had originally started the idea of
    creating an interactive dashboard on top of the wetterdienst library.

    If you have any issues or ideas regarding this app, please let us know in the
    [issues](https://github.com/earthobservations/wetterdienst/issues) on Github.
    """,
)

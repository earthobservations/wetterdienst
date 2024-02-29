# -*- coding: utf-8 -*-
# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
from typing import Optional

import duckdb
import plotly.express as px
import polars as pl
import streamlit
import streamlit as st

from wetterdienst import Settings, __version__
from wetterdienst.provider.dwd.observation import DwdObservationRequest

SQL_DEFAULT = """
SELECT *
FROM df
WHERE value IS NOT NULL
""".strip()


def get_dwd_observation_request(settings=None):
    if settings:
        settings = Settings(**settings)
    return DwdObservationRequest("climate_summary", "daily", settings=settings)


@streamlit.cache_data
def get_dwd_observation_stations(settings):
    return get_dwd_observation_request(settings=settings).all().df


@streamlit.cache_data
def get_dwd_observation_station(station_id, settings):
    return get_dwd_observation_request(settings=settings).filter_by_station_id(station_id)


@streamlit.cache_data
def get_dwd_observation_station_values_df(station_id, settings):
    request = get_dwd_observation_request()
    units = request.discover("daily", "climate_summary")["daily"]
    units = {
        parameter: (unit["si"] if settings["ts_si_units"] else unit["origin"]) for parameter, unit in units.items()
    }
    values = get_dwd_observation_station(station_id, settings).values.all().df
    return values.with_columns(pl.col("parameter").replace(units).alias("unit"))


def create_plotly_fig(
    df: pl.DataFrame,
    variable_column: str,
    variable_filter: list[str],
    x: str,
    y: str,
    facet: bool,
    lm: Optional[str],
    settings: dict,
):
    if "unit" in df.columns:
        df = df.with_columns(
            pl.struct(["parameter", "unit"])
            .map_elements(lambda s: f"{s['parameter']} ({s['unit']})")
            .alias("parameter")
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


def main():
    """Small streamlit app for accessing German climate stations by DWD"""
    title = f"Wetterdienst Data Tool v{__version__}"
    st.set_page_config(page_title=title)
    st.title(title)

    with st.sidebar:
        st.header("Settings")

        st.subheader("General")
        ts_humanize = st.checkbox("humanize", value=True)
        ts_si_units = st.checkbox("si_units", value=True)
        settings = {"ts_humanize": ts_humanize, "ts_si_units": ts_si_units}

        st.subheader("Plotting")

        marker_size = st.slider("marker size", min_value=1, max_value=8, value=2)
        opacity = st.slider("opacity", min_value=0.0, max_value=1.0, value=1.0)
        marker_symbol = st.selectbox("marker symbol", options=["circle", "square", "diamond", "cross", "x"])
        plotting_settings = {"opacity": opacity, "symbol": marker_symbol, "size": marker_size}

    st.subheader("Introduction")
    st.markdown(
        """
        This is a streamlit app based on the [wetterdienst](https://github.com/earthobservations/wetterdienst)
        library that allows analysis of German climate stations (internally phrased "climate summary") by
        the [Deutscher Wetterdienst](https://www.dwd.de/). There are over 1_500 climate stations in Germany and
        all of the data can be accessed freely thanks to the open data initiative. The app enables you to select any
        of the stations (by station id or name), download its data (as CSV) and get visualizations of it.
        """
    )
    st.markdown("Here's a map of all stations:")
    stations = get_dwd_observation_stations(settings)
    st.map(stations, latitude="latitude", longitude="longitude")

    st.subheader("Select")
    station = st.selectbox(
        "Select climate station",
        options=stations.sort("name").rows(named=True),
        format_func=lambda s: f"{s['name']} [{s['station_id']}]",
    )
    if station:
        station["start_date"] = station["start_date"].isoformat()
        station["end_date"] = station["end_date"].isoformat()
        st.code(json.dumps(station, indent=4), language="json")
        st.map(get_dwd_observation_station(station["station_id"], settings).df)

    st.subheader("DataFrame")
    st.info(
        """
        Use [duckdb](https://duckdb.org/docs/sql/introduction.html) sql queries to transform the data.
        Important:
          - use **FROM df**
          - use single quotes for strings e.g. 'a_string'
        """
    )
    sql_query = st.text_area(
        "sql query",
        value=SQL_DEFAULT,
    )
    df = pl.DataFrame()
    if station:
        df = get_dwd_observation_station_values_df(station["station_id"], settings)
        if sql_query:
            df = duckdb.query(sql_query).pl()
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.download_button("Download CSV", df.write_csv(), "data.csv", "text/csv")
        st.download_button(
            "Download JSON",
            df.with_columns(pl.col("date").map_elements(lambda d: d.isoformat())).write_json(
                pretty=True, row_oriented=True
            ),
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
            "Column Variable", options=columns, index="parameter" in columns and columns.index("parameter")
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
        [earthobservations](https://github.com/earthobservations). Credits for the data go to
        [Deutscher Wetterdienst](https://www.dwd.de) - Germany's national meteorological service - for
        publishing their data as **open data**. Credits also go to [streamlit](https://streamlit.io/) for hosting this
        app. If you have any issues or ideas regarding this app, please let us know in the
        [issues](https://github.com/earthobservations/wetterdienst/issues).
        """
    )


if __name__ == "__main__":
    main()

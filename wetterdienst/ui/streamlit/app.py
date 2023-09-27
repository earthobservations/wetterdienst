# -*- coding: utf-8 -*-
# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import plotly.express as px
import polars as pl
import streamlit
import streamlit as st

from wetterdienst.provider.dwd.observation import DwdObservationRequest

SQL_DEFAULT = """
SELECT * 
FROM data
WHERE value IS NOT NULL
""".strip()

request = DwdObservationRequest("climate_summary", "daily")


@streamlit.cache_data
def get_dwd_observation_stations():
    return request.all().df


@streamlit.cache_data
def get_dwd_observation_station(station_id):
    return request.filter_by_station_id(station_id)


@streamlit.cache_data
def get_dwd_observation_station_values(station_id):
    return get_dwd_observation_station(station_id).values.all()


def main():
    """Small streamlit app for accessing German climate stations by DWD"""
    st.title("Wetterdienst - Data Tool")

    st.subheader("Introduction")
    st.markdown(
        """
        This is a streamlit app based on the [wetterdienst](https://github.com/earthobservations/wetterdienst) 
        library that allows analysis of German climate stations (internally phrased "climate summary") by
        the [German Weather Service (DWD)](https://www.dwd.de/). There are over 1_500 climate stations in Germany and
        all of the data can be accessed freely thanks to the open data initiative. The app enables you to select any 
        of the stations (by station id or name), download its data (as CSV) and get visualizations of it. 
        """
    )
    st.markdown("Here's a map of all stations:")
    st.map(get_dwd_observation_stations(), latitude="latitude", longitude="longitude")

    st.subheader("Select")
    station = st.selectbox(
        "Select climate station",
        options=get_dwd_observation_stations().sort("name").rows(named=True),
        format_func=lambda s: f"{s['name']} [{s['station_id']}]",
    )
    if station:
        st.map(get_dwd_observation_station(station["station_id"]).df)

    st.subheader("DataFrame")
    sql_query = st.text_area(
        "sql query",
        value=SQL_DEFAULT,
    )
    df = pl.DataFrame()
    if station:
        df = get_dwd_observation_station_values(station["station_id"]).df
        if sql_query:
            sql_context = pl.SQLContext()
            sql_context.register("data", lf=df.lazy())
            df = sql_context.execute(sql_query).collect()
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.download_button("Download CSV", df.write_csv(), "data.csv", "text/csv")

    st.subheader("Plot")
    parameters = st.multiselect("Select parameters", options=df.get_column("parameter").unique().sort().to_list())
    if parameters:
        fig = px.scatter(
            df.filter(pl.col("parameter").is_in(parameters)),
            x="date",
            y="value",
            color="parameter",
            facet_row="parameter",
        )
        fig.update_layout(
            showlegend=False,  # Hide the legend
            height=400 * len(parameters),  # plot height times parameters
        )
        fig.update_yaxes(matches=None)
        # Update y-axis titles to use facet labels and remove subplot titles
        for i, annotation in enumerate(fig.layout.annotations):
            axis_name = f"yaxis{i + 1}"
            if axis_name in fig.layout:
                fig.layout[axis_name].title.text = annotation.text
            annotation.text = ""
        st.plotly_chart(fig)


if __name__ == "__main__":
    main()

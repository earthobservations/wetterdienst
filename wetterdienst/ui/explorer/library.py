# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
Library of generic components.

Examples:
- Different figures for different data types.
"""
import plotly.graph_objs as go
import polars as pl


def default_figure(climate_data: pl.DataFrame, parameter, resolution, unit_dict) -> go.Figure:
    """
    Default figure generation
    Args:
        climate_data: DataFrame with
        column: Which column of the data should be displayed
    Returns:
        plotly Figure object
    """
    if climate_data.is_empty():
        fig = go.Figure()
        add_annotation_no_data(fig)
        return fig

    ytitle = f"{parameter.lower()} [{unit_dict[resolution.lower()][parameter.lower()]['si']}]"

    fig = go.Figure(
        data=[
            go.Scatter(
                x=climate_data.get_column("date").to_list(),
                y=climate_data.get_column("value").to_list(),
                hoverinfo="x+y",
            )
        ]
    )
    fig.update_layout(yaxis={"title": ytitle}, xaxis={"title": "Date"}, showlegend=False)
    return fig


def add_annotation_no_data(fig: go.Figure):
    fig.add_annotation(
        text="No data to display",
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 28},
    )

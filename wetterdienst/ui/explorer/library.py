# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
Library of generic components.

Examples:
- Different figures for different data types.
"""
import pandas as pd
import plotly.graph_objs as go


def default_figure(climate_data: pd.DataFrame, column: str) -> go.Figure:
    """
    Default figure generation
    Args:
        climate_data: DataFrame with
        column: Which column of the data should be displayed
    Returns:
        plotly Figure object
    """

    # Create a placeholder figure for empty data.
    # https://community.plotly.com/t/replacing-an-empty-graph-with-a-message/31497/2
    if column is None:
        fig = go.Figure()
        fig.add_annotation(
            text="No variable selected",
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"size": 28},
        )
        return fig

    if climate_data.empty:
        fig = go.Figure()
        add_annotation_no_data(fig)
        return fig

    fig = go.Figure(data=[go.Scatter(x=climate_data.date, y=climate_data.loc[:, column], hoverinfo="x+y")])
    fig.update_layout(yaxis={"title": f"{column}"}, showlegend=False)
    return fig


def add_annotation_no_data(fig: go.Figure):
    fig.add_annotation(
        text="No data to display",
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 28},
    )

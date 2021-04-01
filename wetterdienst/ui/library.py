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
    fig = go.Figure(
        data=[
            go.Scatter(
                x=climate_data.index, y=climate_data.loc[:, column], hoverinfo="x+y"
            )
        ]
    )
    fig.update_layout(yaxis=dict(title=f"{column}"))
    return fig

# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Summarize data over time."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.io.charts import FONT, altair
from wetterdienst.io.export import render_image
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)

if TYPE_CHECKING:
    import altair as alt

#: where the picture is written: the folder of the benchmarks that is not tracked
CACHE_DIR = Path(__file__).parent / ".cache"
#: the stations the summary takes values from, with their colours
STATION_COLORS = {"01050": "gold", "01051": "blue", "01048": "green", "05282": "pink"}
#: the panels from top to bottom: the summary, then each station
PANELS = ["Summarized", *STATION_COLORS]
#: the size in pixels of the plot area of a panel: the picture is as large as the five panels, their titles, axes and
#: the legend need, around 640 x 480 (a chart made of panels has no size of its own to ask for)
PANEL_WIDTH, PANEL_HEIGHT = 602, 51


def get_summarized_df(start_date: dt.datetime, end_date: dt.datetime, lat: float, lon: float) -> pl.DataFrame:
    """Get summarized data for a location."""
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start=start_date,
        end=end_date,
    )
    return stations.summarize(latlon=(lat, lon)).df


def get_regular_df(start_date: dt.datetime, end_date: dt.datetime, station_id: str) -> pl.DataFrame:
    """Get regular data for a station."""
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start=start_date,
        end=end_date,
    )
    request = stations.filter_by_station_id(station_id)
    return request.values().all().df


def inline_data(df: pl.DataFrame) -> alt.InlineData:
    """Give the rows of a frame as the text of a CSV file: Altair takes no more than 5000 rows of a frame itself."""
    alt = altair()
    frame = df.with_columns(pl.col("timestamp").dt.convert_time_zone("UTC").dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
    parse = {"panel": "string", "station": "string", "timestamp": "date", "value": "number", "segment": "number"}
    return alt.InlineData(values=frame.write_csv(), format=alt.CsvDataFormat(type="csv", parse=parse))


def draw(summarized_df: pl.DataFrame, regular_dfs: dict[str, pl.DataFrame]) -> alt.VConcatChart:
    """Draw the summarized values and the values of each station, a panel each, one below the other in the same time."""
    alt = altair()
    summarized = summarized_df.select(
        pl.lit("Summarized").alias("panel"),
        pl.col("taken_station_id").alias("station"),
        "timestamp",
        "value",
    )
    stations = [
        df.select(pl.lit(station).alias("panel"), pl.lit(station).alias("station"), "timestamp", "value")
        for station, df in regular_dfs.items()
    ]
    # a line breaks where a station has no value for more than a day, instead of running straight across the gap
    df = pl.concat([summarized, *stations]).with_columns(
        (pl.col("timestamp").diff().over("panel") > pl.duration(days=1))
        .fill_null(value=False)
        .cum_sum()
        .over("panel")
        .alias("segment"),
    )
    # the time in milliseconds, which is what the scale of a time takes as its domain
    domain = [int(df["timestamp"].min().timestamp() * 1000), int(df["timestamp"].max().timestamp() * 1000)]
    color = alt.Color(
        "station:N",
        title="Stations",
        scale=alt.Scale(domain=list(STATION_COLORS), range=list(STATION_COLORS.values())),
        legend=alt.Legend(orient="top", direction="horizontal", symbolType="stroke"),
    )
    panels = []
    for name in PANELS:
        last = name == PANELS[-1]
        base = alt.Chart(inline_data(df.filter(pl.col("panel") == name))).encode(
            x=alt.X(
                "timestamp:T",
                scale=alt.Scale(type="utc", domain=domain, nice=False),
                axis=alt.Axis(title="date") if last else alt.Axis(labels=False, ticks=False, title=None),
            ),
            y=alt.Y("value:Q", title=None, scale=alt.Scale(zero=False), axis=alt.Axis(tickCount=3)),
            color=color,
            detail="segment:N",
        )
        mark = base.mark_circle(size=6, opacity=1) if name == "Summarized" else base.mark_line(strokeWidth=1)
        title = alt.TitleParams(name, anchor="start", fontSize=11, offset=2)
        panels.append(mark.properties(width=PANEL_WIDTH, height=PANEL_HEIGHT, title=title))
    return (
        alt.vconcat(*panels, spacing=9)
        .properties(title="Comparison of summarized values and single stations for temperature_air_mean_2m")
        .configure(font=FONT, background="white")
        .configure_view(stroke="#ddd")
    )


def main() -> None:
    """Run example."""
    start_date = dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(1980, 12, 31, tzinfo=ZoneInfo("UTC"))
    lat = 51.0221
    lon = 13.8470

    summarized_df = get_summarized_df(start_date, end_date, lat, lon)
    print(summarized_df)
    regular_dfs = {station: get_regular_df(start_date, end_date, station) for station in STATION_COLORS}

    chart = draw(summarized_df, regular_dfs)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / "summary.png"
    path.write_bytes(render_image(chart, "png"))
    print(f"picture: {path}")


if __name__ == "__main__":
    main()

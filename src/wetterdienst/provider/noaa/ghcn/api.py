# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""NOAA GHCN api."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import polars as pl
import polars.selectors as cs

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import group_parameters_by_dataset
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.noaa.ghcn.metadata import (
    DAILY_PARAMETER_MULTIPLICATION_FACTORS,
    NoaaGhcnMetadata,
)
from wetterdienst.util.geo import EARTH_RADIUS_IN_KM
from wetterdienst.util.network import download_file
from wetterdienst.util.polars_util import read_fwf_from_df

if TYPE_CHECKING:
    from collections.abc import Iterable

    from wetterdienst.model.metadata import DatasetModel, ParameterModel
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

# how far apart the hourly and the daily list may put a station and still be taken to mean one place
MAX_DISTANCE_KM_SAME_STATION = 5.0


class NoaaGhcnValues(TimeseriesValues):
    """Values class for NOAA GHCN data provider."""

    def _collect_station_parameter_or_dataset(  # ty: ignore[invalid-method-override]
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        if parameter_or_dataset.resolution.value == Resolution.HOURLY:
            return self._collect_station_parameter_for_hourly(station_id=station_id, dataset=parameter_or_dataset)
        return self._collect_station_parameter_for_daily(station_id=station_id, dataset=parameter_or_dataset)

    def _collect_station_parameter_for_hourly(self, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.sr.stations.settings)
        url = f"https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/by-station/GHCNh_{station_id}_por.psv"
        file = url.format(station_id=station_id)
        file = download_file(
            url=file,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.DataFrame()
        df = pl.read_csv(file.content, separator="|", has_header=True, infer_schema_length=0)
        # drop last line if it is a repeated header line
        if df.get_column("STATION").last() == "STATION":
            df = df[:-1, :]
        df = df.rename(
            {
                "STATION": "station_id",
                "DATE": "timestamp",
            },
        )
        parameters = [parameter.name_original for parameter in dataset]
        df = df.select(
            "station_id",
            "timestamp",
            *parameters,
        )
        df = df.unpivot(
            index=["station_id", "timestamp"],
            on=parameters,
            variable_name="parameter",
            value_name="value",
        )
        return df.with_columns(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter").str.to_lowercase(),
            # GHCNh provides a ready-made ISO-8601 timestamp column; parse it directly rather than
            # reconstructing from the separate year/month/day/hour/minute fields
            pl.col("timestamp").str.to_datetime("%Y-%m-%dT%H:%M:%S", time_zone="UTC"),
            pl.col("value").replace("-None", None).cast(pl.Float64),
            pl.lit(value=None, dtype=pl.Float64).alias("quality"),
        )

    def _collect_station_parameter_for_daily(
        self,
        station_id: str,
        dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect station parameter for daily resolution."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.sr.stations.settings)
        url = "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/{station_id}.csv"
        file = url.format(station_id=station_id)
        file = download_file(
            url=file,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.DataFrame()
        df = pl.read_csv(
            source=file.content,
            separator=",",
            has_header=True,
        )
        df = df.rename(str.lower).rename({"date": "timestamp"})
        df = df.select(
            cs.exclude(
                [
                    pl.col("latitude"),
                    pl.col("longitude"),
                    pl.col("elevation"),
                    pl.col("name"),
                    cs.ends_with("_attributes"),
                ],
            ),
        )
        df = df.unpivot(
            index=["station", "timestamp"],
            on=cs.exclude(["station", "timestamp"]),
            variable_name="parameter",
            value_name="value",
        )
        df = df.select(
            pl.col("station").alias("station_id"),
            pl.col("timestamp").str.to_date("%Y-%m-%d"),
            pl.col("parameter").str.to_lowercase(),
            pl.col("value").str.strip_chars().cast(float),
            pl.lit(value=None, dtype=pl.Float64).alias("quality"),
        )
        # Here comes a bit of magic ;)
        # Because we deal with stations (and timezones, sigh...) around the world, all kinds of problems await us
        # with the local timezones if we try to parse midnight (00:00) as a local time.
        # What do we do instead?
        # - We parse the date as 1.) UTC and 2.) as the local timezone of the station.
        # - We calculate the UTC offset of the local timezone.
        # - We subtract the UTC offset from the date.
        # The result will be a datetime in UTC with the correct offset to local midnight time.
        time_zone = self._get_timezone_from_station(station_id)
        df = df.with_columns(
            pl.col("timestamp").cast(pl.Datetime(time_zone="UTC")).alias("timestamp"),
            pl.col("timestamp").cast(pl.Datetime(time_zone=time_zone)).dt.base_utc_offset().alias("utc_offset"),
        )
        df = df.with_columns(pl.col("timestamp").sub(pl.col("utc_offset")).cast(pl.Datetime(time_zone="UTC")))
        df = self._apply_daily_factors(df)
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            "parameter",
            "station_id",
            "timestamp",
            "value",
            "quality",
        )

    @staticmethod
    def _apply_daily_factors(df: pl.DataFrame) -> pl.DataFrame:
        """Apply given factors on parameters that have been converted to integers.

        Make their unit one tenth e.g. 2.0 [°C] becomes 20 [1/10 °C]
        """
        data = []
        for (parameter,), df_group in df.group_by(["parameter"]):
            factor = DAILY_PARAMETER_MULTIPLICATION_FACTORS.get(parameter)
            if factor:
                df_group = df_group.with_columns(pl.col("value").cast(float).mul(factor))
            data.append(df_group)
        return pl.concat(data)


@dataclass
class NoaaGhcnRequest(TimeseriesRequest):
    """Request class for NOAA GHCN data provider."""

    metadata = NoaaGhcnMetadata
    _values = NoaaGhcnValues

    def _all(self) -> pl.LazyFrame:
        from typing import cast  # noqa: PLC0415

        data = []
        for dataset, _ in group_parameters_by_dataset(cast("Iterable[ParameterModel]", self.parameters)):
            if dataset.resolution.value == Resolution.HOURLY:
                data.append(self._create_metaindex_for_ghcn_hourly())
            elif dataset.resolution.value == Resolution.DAILY:
                data.append(self._create_metaindex_for_ghcn_daily())
            else:
                msg = f"Resolution {dataset.resolution.value} is not supported."
                raise ValueError(msg)
        data = [d for d in data if d.collect_schema().names()]
        if not data:
            return pl.LazyFrame()
        # only the daily frame has start_date and end_date, from its inventory, and wmo_id, which the
        # hourly reader does not select; the hourly stations get nulls
        df = pl.concat(data, how="diagonal")
        return self._take_daily_elevation(df)

    @staticmethod
    def _take_daily_elevation(df: pl.LazyFrame) -> pl.LazyFrame:
        """Give a station's hourly row the daily list's elevation, where both lists mean one place.

        So every reader of a station in both lists gets one elevation, whichever row it takes
        (GH-2336). Only where the two lists put the station within 5 km of each other: for some ids
        they name different stations (MXM00076840 is ARRIAGA on the Chiapas coast in the hourly
        list and its data, TEMOSACHI 2000 km away and 1900 m higher in the daily one), and there
        each row keeps its own list's height. Nor does a daily 0.0 replace a height the hourly list
        gives (GH-2362), and a daily list giving none leaves the hourly one. A request for one
        resolution has no pairs to settle.
        """
        is_daily = pl.col("resolution").eq("daily")

        def daily(column: str) -> pl.Expr:
            return pl.col(column).filter(is_daily).first().over("station_id")

        lat, lon = pl.col("latitude").cast(pl.Float64).radians(), pl.col("longitude").cast(pl.Float64).radians()
        lat_daily = daily("latitude").cast(pl.Float64).radians()
        lon_daily = daily("longitude").cast(pl.Float64).radians()
        haversine = ((lat_daily - lat) / 2).sin().pow(2) + lat.cos() * lat_daily.cos() * (
            (lon_daily - lon) / 2
        ).sin().pow(2)
        distance_km = 2 * EARTH_RADIUS_IN_KM * haversine.sqrt().arcsin()
        elevation_daily = daily("elevation")
        return df.with_columns(
            pl.when(
                ~is_daily
                & distance_km.le(MAX_DISTANCE_KM_SAME_STATION)
                & elevation_daily.is_not_null()
                & (elevation_daily.cast(pl.Float64).ne(0.0) | pl.col("elevation").is_null())
            )
            .then(elevation_daily)
            .otherwise(pl.col("elevation"))
            .alias("elevation"),
        )

    def _create_metaindex_for_ghcn_hourly(self) -> pl.LazyFrame:
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        file = "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh-station-list.csv"
        file = download_file(
            url=file,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        df = pl.read_csv(
            file.content,
            has_header=True,
            infer_schema_length=0,
        )
        df = df.select(
            [
                "GHCN_ID",
                "LATITUDE",
                "LONGITUDE",
                "ELEVATION",
                "STATE",
                "NAME",
            ]
        )
        df = df.rename(
            {
                "GHCN_ID": "station_id",
                "LATITUDE": "latitude",
                "LONGITUDE": "longitude",
                "ELEVATION": "elevation",
                "STATE": "region",
                "NAME": "name",
            }
        )
        df = df.with_columns(
            pl.lit("hourly", dtype=pl.String).alias("resolution"),
            pl.lit("data", dtype=pl.String).alias("dataset"),
            cs.string().str.strip_chars().replace("", None),
        )
        # the documentation marks a missing elevation as -999.9. The list also carries 9999.0 and
        # 8191.0, undocumented, on rows such as the North Sea lightship GMMU0010434 ELBE NO. 1 and
        # DNEPRODZERJINSK, which the daily list puts at 148.0 m: placeholders, not heights. -999.0
        # is still read as a height (GH-2352)
        df = df.with_columns(pl.col("elevation").replace(["-999.9", "9999.0", "8191.0"], None))
        return df.lazy()

    def _create_metaindex_for_ghcn_daily(self) -> pl.LazyFrame:
        """Acquire station listing for ghcn daily.

        station listing
        | Variable     | Columns | Type      | Example     |
        |--------------|---------|-----------|-------------|
        | ID           | 1-11    | Character | EI000003980 |
        | LATITUDE     | 13-20   | Real      | 55.3717     |
        | LONGITUDE    | 22-30   | Real      | -7.3400     |
        | ELEVATION    | 32-37   | Real      | 21.0        |
        | STATE        | 39-40   | Character |             |
        | NAME         | 42-71   | Character | MALIN HEAD  |
        | GSN FLAG     | 73-75   | Character | GSN         |
        | HCN/CRN FLAG | 77-79   | Character |             |
        | WMO ID       | 81-85   | Character | 03980       |

        inventory listing
        | Variable  | Columns | Type      |
        |-----------|---------|-----------|
        | ID        | 1-11    | CHARACTER |
        | LATITUDE  | 13-20   | REAL      |
        | LONGITUDE | 22-30   | REAL      |
        | ELEMENT   | 32-35   | CHARACTER |
        | FIRSTYEAR | 37-40   | INTEGER   |
        | LASTYEAR  | 42-45   | INTEGER   |
        """
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        listings_url = "http://noaa-ghcn-pds.s3.amazonaws.com/ghcnd-stations.txt"
        listings_file = download_file(
            url=listings_url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.TWELVE_HOURS,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        listings_file.raise_if_exception()
        if isinstance(listings_file.content, Exception):
            return pl.LazyFrame()
        lines = listings_file.content.read().decode("utf8").splitlines()
        df = pl.DataFrame(lines)
        column_specs = ((0, 10), (12, 19), (21, 29), (31, 36), (38, 39), (41, 70), (80, 84))
        df = read_fwf_from_df(df, column_specs)
        df.columns = [
            "station_id",
            "latitude",
            "longitude",
            "elevation",
            "region",
            "name",
            "wmo_id",
        ]
        # the readme marks a missing elevation as -999.9. The Brazilian network (BR0...) also lists 912
        # stations at 0.0, inland ones on the plateau among them, such as ALFENAS at about 880 m: a
        # placeholder there, while a 0.0 elsewhere, on a coast or in the Netherlands, is a height,
        # see GH-2362
        df = df.with_columns(
            pl.when(pl.col("station_id").str.starts_with("BR0") & pl.col("elevation").eq("0.0"))
            .then(None)
            .otherwise(pl.col("elevation").replace("-999.9", None))
            .alias("elevation"),
        )

        inventory_url = "http://noaa-ghcn-pds.s3.amazonaws.com/ghcnd-inventory.txt"
        inventory_file = download_file(
            url=inventory_url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.TWELVE_HOURS,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        inventory_file.raise_if_exception()
        if isinstance(inventory_file.content, Exception):
            return pl.LazyFrame()
        inventory_df = pl.read_csv(inventory_file.content, has_header=False, truncate_ragged_lines=True)
        column_specs = ((0, 10), (36, 39), (41, 44))
        inventory_df = read_fwf_from_df(inventory_df, column_specs)
        inventory_df.columns = ["station_id", "start_date", "end_date"]
        inventory_df = inventory_df.with_columns(
            pl.col("start_date").cast(pl.Int64),
            pl.col("end_date").cast(pl.Int64),
        )
        inventory_df = inventory_df.group_by(["station_id"]).agg(
            pl.col("start_date").min(),
            pl.col("end_date").max(),
        )
        inventory_df = inventory_df.with_columns(
            pl.col("start_date").cast(pl.String).str.to_datetime("%Y"),
            pl.col("end_date").add(1).cast(pl.String).str.to_datetime("%Y").dt.offset_by("-1d"),
            # .map_batches(lambda s: s - dt.timedelta(days=1)),
        )
        df = df.join(other=inventory_df, how="left", on=["station_id"]).lazy()
        df = df.with_columns(
            pl.lit("daily").alias("resolution"),
            pl.lit("data").alias("dataset"),
        )
        return df.lazy()

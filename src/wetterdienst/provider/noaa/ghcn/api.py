# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""NOAA GHCN api."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import polars as pl
import polars.selectors as cs

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, group_parameters_by_dataset
from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels
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

    from wetterdienst.model.metadata import ParameterModel
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

# how far apart the hourly and the daily list may put a station and still be taken to mean one place
MAX_DISTANCE_KM_SAME_STATION = 5.0

# what the hourly files write for a reading they do not have, as text: the reading keeps it as `raw:` (GH-2759)
GHCNH_WIND_DIRECTION_MISSING = "999"
# the documentation: "wind_direction = Wind Direction from true north using compass directions (e.g. 360 = true north,
# ...). Note: A direction of "000" is given for calm winds", which the files write as `0` (GH-2794). Of the 898,935 and
# 221,947 hours with a direction of USW00023174 and ASN00086282 (read 2026-10-12) 565 and 11,347 are 0, of which all but
# one (1.5 m/s, 1985) have a wind speed of 0, and 12,384 and 28,366 are 360
GHCNH_WIND_DIRECTION_CALM = "0"
GHCNH_PRECIPITATION_MISSING = "-9999"
GHCNH_NONE = "-None"
# the reports of Table 4 that are specials, filed between the routine ones: FM16 is a SPECI, SAOSP an airways special
GHCNH_SPECIAL_REPORT_TYPES = ("FM16", "SAOSP")
# the text some sources write in a code column for "no code": 245 at CAMU0019904 (6,191 hours of temperature), 367 at
# UKI0000EGLL (20,623 hours of sea level pressure)
GHCNH_NO_CODE = "Null"

# stations that `ghcnd-stations.txt` (and `ghcnd-inventory.txt`) put east of Greenwich where they lie west of it, 6 to
# 756 km off: the list has lost the sign of the longitude (GH-2645, GH-2886). Each was checked against two or more
# other sources (ECA&D, GHCN hourly list, DWD MOSMIX, OpenStreetMap, Wikipedia, AEMET) that put the same place west
# of the meridian and within 4 km of the mirrored position; the values per station are in the pull requests of those
# issues.
# The longitude of these is taken as west whatever sign the list gives, so a list corrected by NOAA is read as it is.
GHCND_WEST_LONGITUDE_STATIONS = (
    "AGE00135039",  # ORAN-HOPITAL MILITAIRE
    "AGE00147714",  # ORAN-CAP FALCON
    "AGE00147717",  # SIDI-BEL-ABBES
    "FR000007510",  # BORDEAUX-MERIGNAC
    "FRE00104044",  # CAEN-CARPIQUET
    "FRE00104957",  # ESPOEY
    "FRE00106203",  # MONT-DE-MARSAN
    "SP000008416",  # VALENCIA
    "SPE00101035",  # ALICANTE EL ALTET
    "SPE00101043",  # ALICANTE
    "SPE00119999",  # CASTELLON
    "SPE00120008",  # CASTELLON DE LA PLANA
    "SPE00120161",  # HUESCA
    "SPE00120341",  # MURCIA/SAN JAVIER
    "SPE00120584",  # VALENCIA/AEROPUERTO
    "UK000003377",  # WADDINGTON
    "UKE00100808",  # HULL
    "UKE00105894",  # HIGH MOWTHORPE
    "UKE00105900",  # ROTHAMSTED
    "UKE00105915",  # HAMPSTEAD
    "UKE00105919",  # BOGNOR REGIS
    "UKE00105926",  # HAYLING ISLAND
    "UKE00107650",  # HEATHROW
    "UKE00156848",  # CRANWELL
    "UKE00156864",  # MONKS WOOD
    "UKE00156884",  # WISLEY
    "UKE00156888",  # WOBURN
    "UKW00015034",  # WYTON
    "UKW00015035",  # WADDINGTON
    "UKW00015041",  # STURGATE
    "UV000005503",  # OUAGADOUGOU
    "UVM00065505",  # DEDOUGOU
)


def _closes_its_hour(df: pl.DataFrame) -> pl.Series:
    """Say for each row of a GHCNh file whether its `precipitation` is the one that closes its hour (GH-2841).

    A METAR's precipitation group is the amount since the last routine report, so the reports of an hour repeat a
    growing total, and the file's documentation (section IX) says "to extract the total precipitation for a
    particular hour, the last report should be used", the standard reporting time being "the most common minute
    closest to the end of the hour". The hour is the UTC clock hour of the report, and a report counts if it holds a
    precipitation (a missing value of -9999 is one: the report closing the hour has no amount, and the amount of an
    earlier report is not the hour's). The report kept is, in this order:

    1. the last one at the routine minute of its month, the most common minute of the reports that are not specials
       (`:53` at LAX; a station changes its minute, LAX in 1996 from :00 of the SAO to :50 to :54 of the METAR in
       July; of two equally common minutes the later one is taken, the one closer to the end of the hour). Whatever
       is filed after it in the hour is the amount since that report, which the next hour's routine report holds
       again: a SPECI (`FM16`, `SAOSP`) and, from source 413, `FM15` reports at other minutes that carry no sea level
       pressure either. LAX 2022 has 4 of its 98 hours with several reports end in a SPECI (2022-03-28 17:53 reads
       12.4 mm, 17:57 0.2 mm), and Denver 2026-09-18 23:53 reads 21.6 mm, the `FM15` of 23:59 0.0 mm;
    2. else the last report that is not a special, for an hour whose routine report is missing or late;
    3. else the last report.
    """
    # in steps, each a column of its own: a window over a predicate that is a window itself answered the wrong rows
    reports = df.select(
        pl.col("timestamp").str.to_datetime("%Y-%m-%dT%H:%M:%S", time_zone="UTC").alias("stamp"),
        pl.col("precipitation").is_not_null().alias("reported"),
        ~pl.col("precipitation_Report_Type").is_in(GHCNH_SPECIAL_REPORT_TYPES).fill_null(value=False).alias("plain"),
    ).with_columns(
        pl.col("stamp").dt.truncate("1h").alias("hour"),
        pl.col("stamp").dt.minute().alias("minute"),
        (pl.col("reported") & pl.col("plain")).alias("not_special"),
    )
    reports = reports.with_columns(
        pl.col("minute")
        .filter(pl.col("not_special"))
        .mode()
        .max()
        .over(pl.col("stamp").dt.truncate("1mo"))
        .alias("routine"),
    ).with_columns(
        (pl.col("not_special") & pl.col("minute").eq(pl.col("routine"))).alias("at_routine_minute"),
    )
    closing_stamp = pl.coalesce(
        *(
            pl.when(kept).then(pl.col("stamp")).max().over("hour")
            for kept in ("at_routine_minute", "not_special", "reported")
        )
    )
    return reports.select((pl.col("reported") & pl.col("stamp").eq(closing_stamp)).alias("closing")).to_series()


class NoaaGhcnValues(TimeseriesValues[DatasetModel]):
    """Values class for NOAA GHCN data provider."""

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        if parameter_or_dataset.resolution.value == Resolution.HOURLY:
            return self._collect_station_parameter_for_hourly(station_id=station_id, dataset=parameter_or_dataset)
        return self._collect_station_parameter_for_daily(station_id=station_id, dataset=parameter_or_dataset)

    def _collect_station_parameter_for_hourly(self, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.sr.request.settings)
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
        # `<element>_Quality_Code` is what the source's own quality control made of the value, a code that Table 3 of
        # the documentation lists per source, and `<element>_Source_Code` is that source (ghcnh-source-list.pdf), which
        # says which list the code is read in. In the legacy sources 313, 314, 315, 322, 335, 343, 344, 346 `2` is
        # "Suspect", `3` "Erroneous" and `1` "Passed all quality control checks"; in 220, 221, 222, 223, 347, 348 `2`
        # and `3` are the same and `1` is "Good"; source 345 has its own (`1` "Issue", `3` "Error"). A letter is a check
        # of the integration on six elements (`c` climatological outlier, `s` spike, `f` frequent value) or a legacy
        # flag (`f` and `o` of a derived humidity, `A`, `P`, `U`, `q`). Sources Table 3 does not list occur too (`0` of
        # source 401). The value stays as the file gives it, suspect or erroneous too, and the code travels with it
        # through the unpivot as the field of a struct, written as the source writes it, case included (`q` and `Q`
        # differ) (GH-2754).
        # `<element>_Measurement_Code` says how the value was made (Table 2, by element and by source): `N` a normal
        # and `C` a calm wind, `D` a derived humidity, `0` to `8` the tendency of the 3-hour pressure change, `T` or `2`
        # a trace of precipitation (`T` is Table 1's wording, Table 2 gives `2` for most sources). Both
        # follow the quality code as the tokens `measurement:` and `source:`, as in daily
        # (`QFLAG,measurement:MFLAG,source:SFLAG`), as the file writes them (GH-2925). Elements this reader does not
        # return write several codes in one cell (`06:4`, `M;N`), none of those returned does (8 stations read on
        # 2026-10-15). `<element>_Report_Type` (`SAO`, `FM15`, ...) and `<element>_Source_Station_ID` are not returned.
        # A code of `Null` is no code (sources 245 and 367 write it): left out.
        # `precipitation` is a METAR's running total, which the reports of an hour repeat with growing amounts; only
        # the report that closes the hour keeps it (`_closes_its_hour`, GH-2841). The other elements keep every report
        closing = _closes_its_hour(df)

        def element(parameter: str) -> pl.Expr:
            fields = pl.struct(
                pl.col(parameter).alias("value"),
                pl.col(f"{parameter}_Quality_Code").replace(GHCNH_NO_CODE, None).alias("quality"),
                pl.col(f"{parameter}_Measurement_Code").replace(GHCNH_NO_CODE, None).alias("measurement"),
                pl.col(f"{parameter}_Source_Code").replace(GHCNH_NO_CODE, None).alias("source"),
            )
            return pl.when(closing).then(fields) if parameter == "precipitation" else fields

        df = df.select("station_id", "timestamp", *(element(parameter).alias(parameter) for parameter in parameters))
        df = df.unpivot(
            index=["station_id", "timestamp"],
            on=parameters,
            variable_name="parameter",
            value_name="value",
        )
        df = df.with_columns(
            pl.col("value").struct.field("quality"),
            pl.col("value").struct.field("measurement"),
            pl.col("value").struct.field("source"),
            pl.col("value").struct.field("value"),
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter").str.to_lowercase(),
            # GHCNh provides a ready-made ISO-8601 timestamp column; parse it directly rather than
            # reconstructing from the separate year/month/day/hour/minute fields
            pl.col("timestamp").str.to_datetime("%Y-%m-%dT%H:%M:%S", time_zone="UTC"),
        )
        # a wind direction is 1 to 360 degrees and 0 for a calm wind ("000" is calm, per the documentation), which
        # is no bearing (GH-2794), yet the older reports write 999, mostly with the measurement code C (calm) but
        # also on an hour with a wind speed of 4.1 m/s: no direction was given (GH-2672). The documentation names
        # -9999 as the missing value of the precipitation value, which is the column "precipitation" (none seen so
        # far)
        value, raw = null_sentinels(
            pl.col("value"),
            Sentinel(GHCNH_NONE),
            Sentinel(
                GHCNH_WIND_DIRECTION_MISSING,
                GHCNH_WIND_DIRECTION_CALM,
                where=pl.col("parameter").eq("wind_direction"),
            ),
            Sentinel(GHCNH_PRECIPITATION_MISSING, where=pl.col("parameter").eq("precipitation")),
        )
        return df.with_columns(
            value.cast(pl.Float64).alias("value"),
            join_quality_flags(pl.col("quality"), measurement=pl.col("measurement"), source=pl.col("source"), raw=raw),
        ).drop("quality", "measurement", "source")

    def _collect_station_parameter_for_daily(
        self,
        station_id: str,
        dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect station parameter for daily resolution."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.sr.request.settings)
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
                ],
            ),
        )
        index = ["station", "timestamp"]
        elements = [column for column in df.columns if column not in index and not column.endswith("_attributes")]
        # `<element>_attributes` holds "MFLAG,QFLAG,SFLAG", e.g. ",,E" or "H,,S" (readme.txt): the quality flag is a
        # letter naming the check the value failed, blank where it failed none; the measurement and source flags say
        # how the value was made and where it came from. They travel with their value through the unpivot as the
        # field of a struct, and are written `QFLAG,measurement:MFLAG,source:SFLAG` (GH-2018, GH-2758)
        df = df.select(
            *index,
            *(
                pl.struct(
                    pl.col(element).cast(pl.String).alias("value"),
                    (
                        pl.col(f"{element}_attributes").cast(pl.String)
                        if f"{element}_attributes" in df.columns
                        else pl.lit(None, dtype=pl.String)
                    ).alias("attributes"),
                ).alias(element)
                for element in elements
            ),
        ).unpivot(index=index, on=elements, variable_name="parameter", value_name="value")
        attributes = pl.col("value").struct.field("attributes").str.split(",")
        df = df.with_columns(
            join_quality_flags(
                attributes.list.get(1, null_on_oob=True),
                measurement=attributes.list.get(0, null_on_oob=True),
                source=attributes.list.get(2, null_on_oob=True),
            ),
            pl.col("value").struct.field("value"),
        )
        df = df.select(
            pl.col("station").alias("station_id"),
            pl.col("timestamp").str.to_date("%Y-%m-%d"),
            pl.col("parameter").str.to_lowercase(),
            pl.col("value").str.strip_chars().cast(float),
            "quality_flags",
        )
        # A daily value is stamped at 00:00 UTC of the date the file gives it, whichever time zone the station is in.
        # The date is the station's own observing day, which the readme gives no zone for, and a stamp shifted by the
        # station's offset (Tokyo 15:00 UTC the day before) was dropped by a request for that one day, whose bounds
        # are 00:00 UTC (GH-2683).
        df = df.with_columns(pl.col("timestamp").cast(pl.Datetime(time_zone="UTC")))
        df = self._apply_daily_factors(df)
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            "parameter",
            "station_id",
            "timestamp",
            "value",
            "quality_flags",
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

    # extend base columns of core class with the station's WMO number, which cross-references it with
    # the WMO lists and with the other providers' stations
    _base_columns: ClassVar = (
        *TimeseriesRequest._base_columns,  # noqa: SLF001
        "wmo_id",
    )

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
        # only the daily frame has start_timestamp and end_timestamp, from its inventory; the hourly stations
        # get nulls
        df = pl.concat(data, how="diagonal")
        # a request for one resolution has no pairs to settle
        return self._take_daily_elevation(df) if len(data) > 1 else df

    @staticmethod
    def _take_daily_elevation(df: pl.LazyFrame) -> pl.LazyFrame:
        """Give a station's hourly row the daily list's elevation, where both lists mean one place.

        Then every reader of the station gets one elevation, whichever row it takes (GH-2336). Only
        where the two lists put the station within 5 km of each other: for some ids they name
        different stations (MXM00076840 is ARRIAGA on the Chiapas coast in the hourly list and its
        data, TEMOSACHI 2000 km away and 1900 m higher in the daily one), and there each row keeps
        its own list's height. Nor does a daily 0.0 replace a height the hourly list gives
        (GH-2362); both rows then keep their own as well. A daily list giving none leaves the
        hourly one.
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
                # with no daily elevation the row keeps its own: this is null, or the hourly one was too
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
                "WMO_ID",
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
                "WMO_ID": "wmo_id",
            }
        )
        df = df.with_columns(
            pl.lit("hourly", dtype=pl.String).alias("resolution"),
            pl.lit("data", dtype=pl.String).alias("dataset"),
            cs.string().str.strip_chars().replace("", None),
        )
        # a WMO number is five digits, as the daily list writes it. The hourly list also has `400` on 445 Spanish
        # stations such as SPN00000293 BEGUR (CAP), and `of`, `unkno`, `resol`, `260` and `open` on a dozen more:
        # not numbers of a station
        df = df.with_columns(
            pl.when(pl.col("wmo_id").str.contains(r"^\d{5}$")).then(pl.col("wmo_id")).alias("wmo_id"),
        )
        # the documentation marks a missing elevation as -999.9. The list also carries 9999.0 and
        # 8191.0, undocumented, on rows such as the North Sea lightship GMMU0010434 ELBE NO. 1 and
        # DNEPRODZERJINSK, which the daily list puts at 148.0 m: placeholders, not heights. So is
        # -999.0, on rows such as BOGUS ALGERIAN, about 570 m below the lowest dry land (GH-2352), and
        # -99.0, on GJBAKKI near Thingvellir in southwestern Iceland (GH-2377). Real stations also lie
        # below sea level, such as SALTON SEA NAAF at -68.9, so only these exact values are nulled
        df = df.with_columns(
            pl.col("elevation").replace(["-999.9", "-999.0", "-99.0", "9999.0", "8191.0"], None),
        )
        # 0.0, 0.0 is no position either: BOGUS ARGENTINEAN and NAME AND LOC UNKN are listed there,
        # and their data rows repeat it. A station named BOGUS, such as BOGUS AUSTRIAN or the ten
        # BOGUS CHINESE, is a placeholder whose identity, so whose position, was not established. Both
        # stay in the list and can be fetched by id, but without a position no distance search,
        # interpolation or summary picks them (GH-2380). Only this list: every name in it starting
        # BOGUS is such a placeholder, while the daily list's BOGUS CREEK is a real place in Idaho.
        # Nor is a position off the globe one: the historic Russian CHABAROWKA and IRKUTSK (RUU71-) are
        # listed at latitude 135.117 and 104.367, with their latitude and longitude swapped. They are
        # given no position rather than a guessed one
        latitude, longitude = pl.col("latitude").cast(pl.Float64), pl.col("longitude").cast(pl.Float64)
        no_position = (
            (latitude.eq(0.0) & longitude.eq(0.0))
            | pl.col("name").str.starts_with("BOGUS ")
            | (latitude.abs() > 90)
            | (longitude.abs() > 180)
        )
        df = df.with_columns(
            pl.when(no_position).then(None).otherwise(pl.col(column)).alias(column)
            for column in ("latitude", "longitude")
        )
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
        listings_url = "https://noaa-ghcn-pds.s3.amazonaws.com/ghcnd-stations.txt"
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
        # see GH-2362. -100.0 is a placeholder too, on QOORNOQ and ARSUK on the coast of Greenland and on
        # SORFJORD_KRV and SKJOMEN_SLETTJORD by the fjords near Narvik, where no land lies 100 m below
        # sea level (GH-2418). Real stations also lie below sea level, such as SALTON SEA NAAF at -68.9,
        # so -100.0 is matched exactly rather than every height below sea level being nulled
        df = df.with_columns(
            pl.when(pl.col("station_id").str.starts_with("BR0") & pl.col("elevation").eq("0.0"))
            .then(None)
            .otherwise(pl.col("elevation").replace(["-999.9", "-100.0"], None))
            .alias("elevation"),
        )

        df = df.with_columns(
            pl.when(pl.col("station_id").is_in(GHCND_WEST_LONGITUDE_STATIONS))
            .then(pl.lit("-") + pl.col("longitude").str.strip_chars_start("-"))
            .otherwise(pl.col("longitude"))
            .alias("longitude"),
        )

        inventory_url = "https://noaa-ghcn-pds.s3.amazonaws.com/ghcnd-inventory.txt"
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
        inventory_df.columns = ["station_id", "start_timestamp", "end_timestamp"]
        inventory_df = inventory_df.with_columns(
            pl.col("start_timestamp").cast(pl.Int64),
            pl.col("end_timestamp").cast(pl.Int64),
        )
        inventory_df = inventory_df.group_by(["station_id"]).agg(
            pl.col("start_timestamp").min(),
            pl.col("end_timestamp").max(),
        )
        # the inventory gives the year of the last observation, so a station whose last year is this one is
        # still reporting as far as the list can tell: its end is not 31 December, which has not come yet,
        # but empty, as for a station the provider has not closed (GH-2643)
        this_year = dt.datetime.now(dt.UTC).year
        inventory_df = inventory_df.with_columns(
            pl.col("start_timestamp").cast(pl.String).str.to_datetime("%Y"),
            pl.when(pl.col("end_timestamp") < this_year)
            .then(pl.col("end_timestamp").add(1).cast(pl.String).str.to_datetime("%Y").dt.offset_by("-1d"))
            .alias("end_timestamp"),
        )
        df = df.join(other=inventory_df, how="left", on=["station_id"]).lazy()
        df = df.with_columns(
            pl.lit("daily").alias("resolution"),
            pl.lit("data").alias("dataset"),
        )
        return df.lazy()

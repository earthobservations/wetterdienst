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
from wetterdienst.model.quality_flags import (
    SPEED_BESIDE,
    Sentinel,
    calm,
    join_quality_flags,
    null_sentinels,
    with_speed_beside,
)
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import UPDATED, TimeseriesValues
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
# one (1.5 m/s, 1985) have a wind speed of 0, and 12,384 and 28,366 are 360. The 0 beside a speed of 0 is null; the
# one beside a wind that blows stays, as in every provider (`calm`, GH-3222), where it was null too
GHCNH_WIND_SPEED_OF_DIRECTION = {"wind_direction": "wind_speed"}
# the speed of the direction of each daily wind direction (the element names of the daily files, lower case): AWDR,
# the average direction, beside AWND, and the readme's "Direction of ..." the fastest or peak wind (WDF1, WDF2, WDF5,
# WDFG, WDFI and WDFM) beside WSF1, WSF2, WSF5, WSFG, WSFI and WSFM, the speed of that wind, in tenths of m/s
GHCND_WIND_SPEED_OF_DIRECTION = {
    "awdr": "awnd",
    "wdf1": "wsf1",
    "wdf2": "wsf2",
    "wdf5": "wsf5",
    "wdfg": "wsfg",
    "wdfi": "wsfi",
    "wdfm": "wsfm",
}
GHCNH_PRECIPITATION_MISSING = "-9999"
GHCNH_NONE = "-None"
# the reports of Table 4 that are specials, filed between the routine ones: FM16 is a SPECI, SAOSP an airways special
GHCNH_SPECIAL_REPORT_TYPES = ("FM16", "SAOSP")
# the text some sources write in a code column for "no code": 245 at CAMU0019904 (6,191 hours of temperature), 367 at
# UKI0000EGLL (20,623 hours of sea level pressure)
GHCNH_NO_CODE = "Null"

# stations whose longitude `ghcnd-stations.txt` (and `ghcnd-inventory.txt`) and `ghcnh-station-list.csv` list with the
# wrong sign, all 38 listed east of Greenwich where they lie west of it, 6 to 756 km off: the list has lost the sign
# (GH-2645, GH-2886, GH-3384). Each was checked against two or more other sources (ECA&D, GHCN hourly list, ISD
# history, DWD MOSMIX, OpenStreetMap, Wikipedia, AEMET) that put the same place on the other side of the meridian and
# within 4 km of the mirrored position; the values per station are in the pull requests of those issues.
# The value is the (latitude, longitude) the lists gave when the station was checked: the longitude of a row is turned
# only while the row still lists exactly this position (`_restore_lost_longitude_sign`), so a list that NOAA has
# corrected, or moved, is read as it is, and an id that the lists use for another station is not touched. One table
# serves both lists; UKW00015015 and UKW00015033 are in both with the same position.
LOST_LONGITUDE_SIGN_STATIONS: dict[str, tuple[float, float]] = {
    "AGE00135039": (35.7297, 0.65),  # ORAN-HOPITAL MILITAIRE
    "AGE00147714": (35.77, 0.8),  # ORAN-CAP FALCON
    "AGE00147717": (35.2, 0.63),  # SIDI-BEL-ABBES
    "FR000007510": (44.8306, 0.6914),  # BORDEAUX-MERIGNAC
    "FRE00104044": (49.18, 0.4558),  # CAEN-CARPIQUET
    "FRE00104957": (43.2481, 0.155),  # ESPOEY
    "FRE00106203": (43.9094, 0.5003),  # MONT-DE-MARSAN
    "SP000007038": (37.9769, 0.7106),  # TORREVIEJA
    "SP000008416": (39.4806, 0.3664),  # VALENCIA
    "SPE00101035": (38.2828, 0.5706),  # ALICANTE EL ALTET
    "SPE00101043": (38.3725, 0.4942),  # ALICANTE
    "SPE00119999": (39.95, 0.0714),  # CASTELLON
    "SPE00120008": (39.9892, 0.0406),  # CASTELLON DE LA PLANA
    "SPE00120161": (42.0831, 0.3264),  # HUESCA
    "SPE00120341": (37.7889, 0.8031),  # MURCIA/SAN JAVIER
    "SPE00120584": (39.4867, 0.4731),  # VALENCIA/AEROPUERTO
    "UK000003377": (53.1658, 0.5239),  # WADDINGTON
    "UKE00100808": (53.7667, 0.3667),  # HULL
    "UKE00105894": (54.105, 0.6417),  # HIGH MOWTHORPE
    "UKE00105900": (51.8067, 0.3581),  # ROTHAMSTED
    "UKE00105915": (51.5608, 0.1789),  # HAMPSTEAD
    "UKE00105919": (50.7808, 0.6758),  # BOGNOR REGIS
    "UKE00105926": (50.7839, 0.9839),  # HAYLING ISLAND
    "UKE00105927": (51.1767, 0.8481),  # ALICE HOLT LODGE
    "UKE00107650": (51.4789, 0.4489),  # HEATHROW
    "UKE00156848": (53.0306, 0.5017),  # CRANWELL
    "UKE00156864": (52.4008, 0.2353),  # MONKS WOOD
    "UKE00156884": (51.3103, 0.4744),  # WISLEY
    "UKE00156888": (52.0142, 0.5942),  # WOBURN
    "UKW00015014": (52.3833, 0.4167),  # MOLESWORTH
    "UKW00015015": (52.3, 0.5333),  # CHELVESTON
    "UKW00015018": (52.1, 0.05),  # BASSINGBOURN
    "UKW00015033": (52.3667, 0.2167),  # HUNTINGTON (RAF Alconbury)
    "UKW00015034": (52.35, 0.1167),  # WYTON
    "UKW00015035": (53.1667, 0.5167),  # WADDINGTON
    "UKW00015041": (53.3667, 0.6833),  # STURGATE
    "UV000005503": (12.35, 1.52),  # OUAGADOUGOU
    "UVM00065505": (12.467, 3.483),  # DEDOUGOU
}


def _restore_lost_longitude_sign(df: pl.DataFrame) -> pl.DataFrame:
    """Turn the sign of the longitude of the stations of `LOST_LONGITUDE_SIGN_STATIONS`, for either list (GH-3384).

    A row is changed only if its id is in the table and its latitude and longitude are what the table recorded, so
    a list in which NOAA has put the sign right, or has moved the station, is read as it is.
    """
    latitude = pl.col("latitude").str.strip_chars().cast(pl.Float64, strict=False)
    longitude = pl.col("longitude").str.strip_chars().cast(pl.Float64, strict=False)
    listed_latitude = pl.col("station_id").replace_strict(
        {station_id: position[0] for station_id, position in LOST_LONGITUDE_SIGN_STATIONS.items()},
        default=None,
        return_dtype=pl.Float64,
    )
    listed_longitude = pl.col("station_id").replace_strict(
        {station_id: position[1] for station_id, position in LOST_LONGITUDE_SIGN_STATIONS.items()},
        default=None,
        return_dtype=pl.Float64,
    )
    return df.with_columns(
        pl.when(latitude.eq(listed_latitude) & longitude.eq(listed_longitude))
        .then((-longitude).cast(pl.String))
        .otherwise(pl.col("longitude"))
        .alias("longitude"),
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


# a report belongs to the full hour it is nearest to, so an hour reaches half an hour to either side of its full hour
_HALF_HOUR = dt.timedelta(minutes=30)


def _one_report_per_hour(df: pl.DataFrame) -> pl.DataFrame:
    """Keep, for each parameter and full hour, the one reading nearest to the hour, stamped with it (GH-3000).

    The hourly file holds every report of a station: the temperature of Denver 2026 (read 2026-10-17) has 9,146 rows in
    its 6,854 hours, one to seven in an hour. They are the routine METAR at :53 (source 413), the SPECI and the further
    `FM15` reports filed between (:21, :47, :59), and at the synoptic hours a SYNOP at :00 (source 412). The 5-minute
    rows of the file hold the 5-minute precipitation only (`precipitation_5_minute`, source 343), which is not read.
    A reading belongs to the full hour it is nearest to (14:53 to 15:00, 14:20 to 14:00; 14:30 to 15:00). Of the
    readings of a parameter in an hour the one kept is, in this order:

    1. one the file gives a value for, so that a parameter a SPECI does not carry (no sea level pressure) is read
       from the report that has it, rather than the hour reading null;
    2. the one nearest to the full hour, the routine METAR at :51 to :54 unless a report was filed closer;
    3. the earlier of two at the same distance, 14:57 over 15:03.

    The kept reading is stamped with the full hour (15:00 for the METAR of 14:53), as DWD and ECCC stamp their hourly
    readings, the instant ones among them (DWD's are those of about ten minutes before the stamp). On the full-hour
    grid that `interpolate` and `summarize` join on, a reading at :53 would count for nothing, and `skip_empty` counts
    the rows of an hour by its truncated hour. The parameters of an hour come from the reports nearest to it each, so
    they may come from different reports. An hour in which a parameter has no value at all keeps one null for it,
    which only `drop_nulls=False` shows. The precipitation holds one reading an hour already (`_closes_its_hour`), and
    is stamped with the hour that report is nearest to: 15:00 for the report of 14:53, which closes the clock hour 14.
    """
    timestamp = pl.col("timestamp")
    hour = (timestamp + _HALF_HOUR).dt.truncate("1h")
    return (
        df.with_columns(
            hour.alias("_hour"),
            pl.col("value").struct.field("value").is_not_null().alias("_has_value"),
            (timestamp - hour).dt.total_microseconds().abs().alias("_distance"),
        )
        .sort(["_has_value", "_distance", "timestamp"], descending=[True, False, False], maintain_order=True)
        .unique(subset=["station_id", "parameter", "_hour"], keep="first", maintain_order=True)
        .with_columns(pl.col("_hour").alias("timestamp"))
        .drop("_hour", "_has_value", "_distance")
    )


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
        # the report that closes the hour keeps it (`_closes_its_hour`, GH-2841). Every element is then thinned to one
        # reading for each full hour (`_one_report_per_hour`, GH-3000)
        closing = _closes_its_hour(df)

        def element(parameter: str) -> pl.Expr:
            # the speed of the report travels with its direction, as the thinning below may take the two of an hour
            # from different reports
            speed = GHCNH_WIND_SPEED_OF_DIRECTION.get(parameter)
            fields = pl.struct(
                pl.col(parameter).alias("value"),
                pl.col(f"{parameter}_Quality_Code").replace(GHCNH_NO_CODE, None).alias("quality"),
                pl.col(f"{parameter}_Measurement_Code").replace(GHCNH_NO_CODE, None).alias("measurement"),
                pl.col(f"{parameter}_Source_Code").replace(GHCNH_NO_CODE, None).alias("source"),
                (pl.col(speed) if speed in df.columns else pl.lit(None, dtype=pl.String)).alias(SPEED_BESIDE),
            )
            return pl.when(closing).then(fields) if parameter == "precipitation" else fields

        df = df.select("station_id", "timestamp", *(element(parameter).alias(parameter) for parameter in parameters))
        df = df.unpivot(
            index=["station_id", "timestamp"],
            on=parameters,
            variable_name="parameter",
            value_name="value",
        )
        # GHCNh provides a ready-made ISO-8601 timestamp column; parse it directly rather than
        # reconstructing from the separate year/month/day/hour/minute fields
        df = df.with_columns(pl.col("timestamp").str.to_datetime("%Y-%m-%dT%H:%M:%S", time_zone="UTC"))
        # the file holds every report of the station, which `hourly` is not: one reading for each parameter and full
        # hour, stamped with the hour (GH-3000)
        df = _one_report_per_hour(df)
        df = df.with_columns(
            pl.col("value").struct.field("quality"),
            pl.col("value").struct.field("measurement"),
            pl.col("value").struct.field("source"),
            pl.col("value").struct.field(SPEED_BESIDE),
            pl.col("value").struct.field("value"),
            pl.col("parameter").str.to_lowercase(),
        )
        # a wind direction is 1 to 360 degrees and 0 for a calm wind ("000" is calm, per the documentation), which
        # is no bearing beside a speed of 0 (GH-2794, GH-3222), yet the older reports write 999, mostly with the
        # measurement code C (calm) but also on an hour with a wind speed of 4.1 m/s: no direction was given
        # (GH-2672). The documentation names -9999 as the missing value of the precipitation value, which is the
        # column "precipitation" (none seen so far)
        value, raw = null_sentinels(
            pl.col("value"),
            Sentinel(GHCNH_NONE),
            Sentinel(GHCNH_WIND_DIRECTION_MISSING, where=pl.col("parameter").eq("wind_direction")),
            calm(pl.col(SPEED_BESIDE), where=pl.col("parameter").eq("wind_direction")),
            Sentinel(GHCNH_PRECIPITATION_MISSING, where=pl.col("parameter").eq("precipitation")),
        )
        df = df.with_columns(
            value.alias("value"),
            join_quality_flags(pl.col("quality"), measurement=pl.col("measurement"), source=pl.col("source"), raw=raw),
        ).drop("quality", "measurement", "source", SPEED_BESIDE)
        # when NCEI last wrote the file of the station travels with its rows (`_note_files_with_rows`, GH-2567)
        return self._note_files_with_rows(
            df.with_columns(pl.lit(file.last_modified, dtype=pl.Datetime("us", "UTC")).alias(UPDATED)), dataset
        )

    def _collect_station_parameter_for_daily(self, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
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
            pl.col("value").str.strip_chars(),
            "quality_flags",
        )
        # AWDR, the average daily wind direction, is 0 beside an AWND of 0 (a calm day) as much as it is a bearing
        # beside a wind that blows: at USS0054K01S (read 2026-10-30) 2 of its 11 directions of 0 have a speed of 0 and 5
        # have one above, besides the 360 of 2025-06-30. So are the directions of the fastest and peak winds (9 station
        # files read 2026-10-30): of the 1,799 zeros of WDFG 1,798 have a WSFG of 0 (1,789 at CAN03031640, source flag
        # C), and 123 zeros of WDF5 at USW00014755 (1998 to 2002) are beside a WSF5 of 4.0 to 59.0 m/s, besides its 360
        # for north. WDF1, WDF2 and WDF5 have 2 of 3, 8 of 23 and 11 of 134 zeros beside a speed of 0, WDFI and WDFM
        # none in 8,410 and 28,815 directions. The readme gives no code for a day without a direction. The 0 beside a
        # speed of exactly 0 is a calm and null, and stays as `raw:0` in `quality_flags` (GH-3222); the 0 beside a
        # wind that blows stays (GH-3648)
        df = with_speed_beside(df, GHCND_WIND_SPEED_OF_DIRECTION, on=["station_id", "timestamp"])
        value, raw = null_sentinels(
            pl.col("value"),
            calm(pl.col(SPEED_BESIDE), where=pl.col("parameter").is_in(list(GHCND_WIND_SPEED_OF_DIRECTION))),
        )
        df = df.with_columns(value.alias("value"), join_quality_flags(pl.col("quality_flags"), raw=raw)).drop(
            SPEED_BESIDE
        )
        # A daily value is stamped at 00:00 UTC of the date the file gives it, whichever time zone the station is in:
        # the date is handed over as it is, which the core reads as midnight UTC. The date is the station's own
        # observing day, which the readme gives no zone for, and a stamp shifted by the station's offset (Tokyo 15:00
        # UTC the day before) was dropped by a request for that one day, whose bounds are 00:00 UTC (GH-2683).
        # when NCEI last wrote the file of the station travels with its rows (`_note_files_with_rows`, GH-2567)
        df = self._note_files_with_rows(
            df.with_columns(pl.lit(file.last_modified, dtype=pl.Datetime("us", "UTC")).alias(UPDATED)), dataset
        )
        return self._apply_daily_factors(df)

    @staticmethod
    def _apply_daily_factors(df: pl.DataFrame) -> pl.DataFrame:
        """Apply given factors on parameters that have been converted to integers.

        Make their unit one tenth e.g. 2.0 [°C] becomes 20 [1/10 °C]

        The value is the text the file wrote and is read as a number here only because it is multiplied: a cell that
        is no number is null, as the core makes of it, so no value of the file raises.
        """
        factor = pl.col("parameter").replace_strict(
            DAILY_PARAMETER_MULTIPLICATION_FACTORS, default=1.0, return_dtype=pl.Float64
        )
        return df.with_columns((pl.col("value").cast(pl.Float64, strict=False) * factor).alias("value"))


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
        if len(data) > 1:
            df = self._take_daily_elevation(df)
        # the list holds 147 stations (of 133,039) that the inventory has no line for, because they have no data in
        # any element: 146 have no data file either, and one has a file whose rows are all quality flagged
        # (USC00144840). Their daily rows are left out, as dwd/observation leaves out a station without a file, but
        # only now: their hourly rows are still given the daily list's elevation above (GH-3260)
        if "start_timestamp" not in df.collect_schema().names():
            return df
        return df.filter(~(pl.col("resolution").eq("daily") & pl.col("start_timestamp").is_null()))

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
        df = _restore_lost_longitude_sign(df)
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

        df = _restore_lost_longitude_sign(df)

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
        df = df.join(other=inventory_df, how="left", on=["station_id"], maintain_order="left").lazy()
        df = df.with_columns(
            pl.lit("daily").alias("resolution"),
            pl.lit("data").alias("dataset"),
        )
        return df.lazy()

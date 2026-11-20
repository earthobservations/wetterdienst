# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""API for DWD's KOSTRA-DWD-2020 heavy-rainfall statistics: the table of the grid cell that holds a point.

KOSTRA has no time axis, and its "stations" would be 90,000 grid cells, so -- like `DwdStormCellsRequest` -- this is a
point lookup of its own and no `TimeseriesRequest`. DWD publishes one zipped table per duration (22, from 5 minutes to
7 days), each with a row for every cell of the 300 x 300 grid and the columns `HN_<T>A` (depth, mm), `RN_<T>A`
(intensity, l/(s ha)) and `UC_<T>A` (uncertainty, plus-minus percent) for the nine return periods `T`. A lookup for one
duration downloads that table alone; one without a duration downloads the 22 at once. The files are static (DWD wrote
them in December 2022), so the cache keeps them for a week.

The values come through `null_sentinels` like the readings of any provider: DWD's missing-value codes are `-99,9` (and
`-99` for the uncertainty) and are null. A cell is either all of its values or none of them in every table (checked for
all 22 when this was written), so a cell without values is refused as `LocationOutOfRangeError`, never answered as a
table of nulls, and no value of an answer carries a `raw:` token. A cell with some of its values missing is not what
DWD publishes: a `MetaFileFormatError`, and not nulls with no text of the source beside them.
"""

from __future__ import annotations

import io
import logging
import time
import zipfile
import zlib
from typing import TYPE_CHECKING, Any, ClassVar

import polars as pl

from wetterdienst.exceptions import LocationOutOfRangeError, MetaFileFormatError, RequestError
from wetterdienst.io.export import render_data_format
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import Extent, ProviderTerms
from wetterdienst.model.quality_flags import Sentinel, null_sentinels
from wetterdienst.model.result import describe_provider
from wetterdienst.provider.dwd.kostra.grid import Cell, locate
from wetterdienst.provider.dwd.kostra.metadata import (
    DURATIONS,
    DWD_KOSTRA_BASE_URL,
    EDITION,
    KOSTRA_NOTE,
    RETURN_PERIODS,
    VALUES_BBOX,
    table_url,
)
from wetterdienst.provider.dwd.metadata import _METADATA
from wetterdienst.settings import Settings
from wetterdienst.util.json_util import dumps_json, json_indent
from wetterdienst.util.network import File, download_file, download_files, drop_cached_file

if TYPE_CHECKING:
    import datetime as dt

    from wetterdienst.model.result import ResultMetadata

log = logging.getLogger(__name__)

#: how long the files are kept in the cache: they are static (December 2022), so as long as the cache keeps a file
#: without asking again
_EXPIRY = CacheExpiry.ONE_WEEK

#: the most a table may hold once it is unzipped (the real ones are about 13 MB), against a file that is no table
_MAX_TABLE_BYTES = 64 * 1024 * 1024

_KINDS = {"HN": "depth_mm", "RN": "intensity_l_s_ha", "UC": "uncertainty_percent"}
_HEADER = ["INDEX_RC", *(f"{kind}_{period:03d}A" for kind in _KINDS for period in RETURN_PERIODS)]

#: the columns of the table of an answer, one row for each duration and return period
_SCHEMA: dict[str, Any] = {
    "duration_minutes": pl.Int64,
    "return_period_years": pl.Int64,
    "depth_mm": pl.Float64,
    "intensity_l_s_ha": pl.Float64,
    "uncertainty_percent": pl.Float64,
}

#: the missing-value codes of DWD: `-99.9` of the depth and the intensity, `-99` of the uncertainty (the decimal comma
#: is turned to a point before, as a comma is the separator of the tokens of `raw`)
_NO_DEPTH = Sentinel("-99.9", where=pl.col("kind") != "UC")
_NO_UNCERTAINTY = Sentinel("-99", where=pl.col("kind") == "UC")


class DwdKostraResult:
    """Result of a :class:`DwdKostraRequest`: the table of one grid cell, a row for each duration and return period."""

    def __init__(self, df: pl.DataFrame, cell: Cell, data_updated_at: dt.datetime | None = None) -> None:
        """Initialize the result.

        Args:
            df: the table, with the columns of the answer (``duration_minutes``, ``return_period_years``,
                ``depth_mm``, ``intensity_l_s_ha`` and ``uncertainty_percent``).
            cell: the grid cell the table is of.
            data_updated_at: when DWD wrote the newest of the files the table was read from (their ``Last-Modified``).

        """
        self.df = df
        self.cell = cell
        self.data_updated_at = data_updated_at

    @property
    def edition(self) -> str:
        """Name the edition of the statistics, as DWD does."""
        return EDITION

    def _cell(self) -> dict[str, Any]:
        """Describe the cell: DWD's `INDEX_RC`, its row and column and the position of its centre (degrees)."""
        latitude, longitude = self.cell.centre
        return {
            "index_rc": self.cell.index_rc,
            "row": self.cell.row,
            "column": self.cell.column,
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
        }

    def _metadata(self) -> ResultMetadata:
        """Give the `metadata` block that `with_metadata` adds: the provider, this library and the date of the data."""
        return describe_provider(DwdKostraRequest.terms, self.data_updated_at, calculated=KOSTRA_NOTE)

    def to_dict(self, *, with_metadata: bool = False) -> dict[str, Any]:
        """Return the answer as ``{"edition": ..., "cell": {...}, "values": [...]}``.

        Args:
            with_metadata: whether to put the ``metadata`` block (provider, producer and the date of the data) first

        """
        data: dict[str, Any] = {"edition": self.edition, "cell": self._cell(), "values": self.df.to_dicts()}
        return {"metadata": self._metadata(), **data} if with_metadata else data

    def to_json(self, indent: int | bool | None = False, *, with_metadata: bool = False) -> str:  # noqa: FBT001, FBT002
        """Return the answer as a JSON string.

        Args:
            indent: a number of spaces, ``True`` for 4, ``False`` or ``None`` (the default) for one line
            with_metadata: whether to put the ``metadata`` block first

        """
        return dumps_json(self.to_dict(with_metadata=with_metadata), indent=json_indent(indent), ensure_ascii=False)

    def to_csv(self) -> str:
        """Return the table as CSV, a row each; it holds neither the cell nor the metadata, which JSON does."""
        return self.df.write_csv()

    def to_format(self, fmt: str, **kwargs: Any) -> str:  # noqa: ANN401
        """Render the result in the requested format (``json`` or ``csv``), in any case.

        Raises:
            UnknownFormatError: ``fmt`` is neither. It is a ``ValueError`` and a ``KeyError``.
            TypeError: an argument that no format takes.

        """
        return render_data_format(self, fmt, kwargs, only=("json", "csv"))


class DwdKostraRequest:
    """API for DWD's KOSTRA-DWD-2020 heavy-rainfall statistics at a point.

    Finds the cell of DWD's 5 km grid that holds the point and reads its table: for each of 22 durations (5 minutes to
    7 days) and 9 return periods (1 to 100 years) the rainfall depth in mm (``HN``), the intensity in l/(s ha) (``RN``)
    and DWD's uncertainty in plus-minus percent (``UC``). A ``duration`` reads that one table (0.7 MB); without it the
    22 are downloaded, which the cache keeps for a week.

    A point outside the grid, or in a cell DWD gives no values (the sea, a country around Germany), is refused with a
    :class:`~wetterdienst.exceptions.LocationOutOfRangeError`, not answered with an empty table.
    """

    # who published the files and under which terms, which an answer about them names as a network with a metadata
    # model does through its `MetadataModel`. The licence and the credit line are DWD's, as for every dataset of its CDC
    terms: ClassVar = ProviderTerms(
        name_local=_METADATA["name_local"],
        name_english=_METADATA["name_english"],
        country=_METADATA["country"],
        country_code=_METADATA["country_code"],
        copyright="© Deutscher Wetterdienst (DWD), KOSTRA-DWD-2020",
        license=_METADATA["license"],
        attribution=_METADATA["attribution"],
        url=DWD_KOSTRA_BASE_URL,
        extent=Extent(scope="national", continents=["europe"], country_codes=["DE"], bbox=list(VALUES_BBOX)),
    )

    def __init__(
        self,
        *,
        latitude: float,
        longitude: float,
        duration: int | None = None,
        return_period: int | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the request. Every argument is a keyword: a latitude and a longitude are easily swapped.

        Args:
            latitude: the latitude of the point (WGS84 degrees).
            longitude: the longitude of the point (WGS84 degrees).
            duration: only this duration, in minutes: one of 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 360, 540,
                720, 1080, 1440, 2880, 4320, 5760, 7200, 8640 and 10080. ``None`` (default) gives all 22, which reads
                22 files.
            return_period: only this return period, in years: 1, 2, 3, 5, 10, 20, 30, 50 or 100. ``None`` (default)
                gives all nine.
            settings: settings for the request.

        Raises:
            RequestError: a ``duration`` or ``return_period`` DWD publishes none of.
            LocationOutOfRangeError: a latitude or longitude that is no point on the globe, or a point outside the
                grid, which reaches from about 43.4 N to 57.3 N and 1.8 W to 22.8 E.

        """
        if duration is not None and duration not in DURATIONS:
            msg = (
                f"duration {duration!r} is not one DWD publishes, use one of {', '.join(map(str, DURATIONS))} (minutes)"
            )
            raise RequestError(msg)
        if return_period is not None and return_period not in RETURN_PERIODS:
            msg = (
                f"return_period {return_period!r} is not one DWD publishes, "
                f"use one of {', '.join(map(str, RETURN_PERIODS))} (years)"
            )
            raise RequestError(msg)
        self.latitude = latitude
        self.longitude = longitude
        # a duration of 60.0 is the one of 60 minutes, which names the file
        self.duration = None if duration is None else int(duration)
        self.return_period = None if return_period is None else int(return_period)
        self.settings = settings or Settings()
        # refuses a point that is no point on the globe or is outside the grid, before anything is downloaded
        self.cell = locate(latitude, longitude)

    def __repr__(self) -> str:
        """Return a string representation of the request."""
        return (
            f"DwdKostraRequest(latitude={self.latitude}, longitude={self.longitude}, duration={self.duration}, "
            f"return_period={self.return_period})"
        )

    def query(self) -> DwdKostraResult:
        """Read the table of the cell that holds the point.

        Raises:
            LocationOutOfRangeError: the point is outside the grid, or its cell has no values.
            DownloadError: a table could not be downloaded (a 404, a timeout).
            ProviderRateLimitError: DWD answered a 429 for one of the tables, which is raised before any other failure.
            MetaFileFormatError: what came is no table laid out as DWD describes it: a page of a CDN's outage answered
                with a 200, a file that is no zip or is corrupt, or a cell with some of its values missing.

        """
        cell = self.cell
        durations = (self.duration,) if self.duration is not None else DURATIONS
        files = self._download(durations)
        frames = []
        for duration, file in zip(durations, files, strict=True):
            fields = self._row_of(duration, file, cell)
            frames.append(self._frame_of(duration, fields))
        df = self._table_of(pl.concat(frames))
        missing = sum(df.select(list(_SCHEMA)[2:]).null_count().row(0))
        if missing and missing < df.height * len(_KINDS):
            msg = (
                f"the cell {cell.index_rc} has {missing} of its {df.height * len(_KINDS)} values missing in the tables "
                "of KOSTRA-DWD-2020: DWD gives a cell all its values or none"
            )
            raise MetaFileFormatError(msg)
        if missing:
            msg = (
                f"DWD gives no KOSTRA-DWD-2020 values for the point {self.latitude}, {self.longitude}: its cell "
                f"({cell.index_rc}) is outside Germany and the border of about 10 km DWD covers."
            )
            raise LocationOutOfRangeError(msg)
        if self.return_period is not None:
            df = df.filter(pl.col("return_period_years") == self.return_period)
        updated = [file.last_modified for file in files if file.last_modified is not None]
        return DwdKostraResult(df=df, cell=cell, data_updated_at=max(updated) if updated else None)

    def _download(self, durations: tuple[int, ...]) -> list[File]:
        """Download the tables of the durations, which one call does at once; a failure is raised as the error it is."""
        urls = [table_url(duration) for duration in durations]
        files = (
            [self._download_one(urls[0])]
            if len(urls) == 1
            else download_files(
                urls,
                cache_dir=self.settings.cache_dir,
                ttl=_EXPIRY,
                client_kwargs=self.settings.fsspec_client_kwargs,
                cache_disable=self.settings.cache_disable,
                use_certifi=self.settings.use_certifi,
            )
        )
        # a 429 is raised before any other failure: it is a limit the next request meets too, and must not be hidden
        # behind a 404 of another of the tables
        for file in files:
            if file.is_rate_limited:
                file.raise_if_exception()
        for file in files:
            file.raise_if_exception()
        return files

    def _download_one(self, url: str, *, refetch: bool = False) -> File:
        return download_file(
            url=url,
            cache_dir=self.settings.cache_dir,
            ttl=_EXPIRY,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
            use_certifi=self.settings.use_certifi,
            refetch_before=time.time() if refetch else None,
        )

    def _row_of(self, duration: int, file: File, cell: Cell) -> list[str]:
        """Read the fields of the row of the cell from a downloaded table.

        A file that does not read as a table is a `MetaFileFormatError`: DWD's, not the request's, and the copy of it
        the cache made is dropped, so that the next request asks DWD again and not the cache for a week. A copy that was
        kept by a request before (a page of an outage answered with a 200) is fetched once more before it is refused.
        """
        try:
            return _read_row(file, cell)
        except MetaFileFormatError:
            self._drop(file.url)
            if not file.from_cache:
                raise
        refetched = self._download_one(table_url(duration), refetch=True)
        refetched.raise_if_exception()
        try:
            return _read_row(refetched, cell)
        except MetaFileFormatError:
            self._drop(refetched.url)
            raise

    def _drop(self, url: str) -> None:
        """Delete the copy of a file the cache made, which is no table and would be served for a week."""
        drop_cached_file(
            url,
            cache_dir=self.settings.cache_dir,
            ttl=_EXPIRY,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
            use_certifi=self.settings.use_certifi,
        )

    @staticmethod
    def _frame_of(duration: int, fields: list[str]) -> pl.DataFrame:
        """Give the long frame of one table's row: a line for each column, with its duration."""
        return pl.DataFrame(
            {
                "duration_minutes": [duration] * (len(_HEADER) - 1),
                "column": _HEADER[1:],
                "text": fields[1:],
            },
            schema={"duration_minutes": pl.Int64, "column": pl.String, "text": pl.String},
        )

    @staticmethod
    def _table_of(long: pl.DataFrame) -> pl.DataFrame:
        """Turn the lines of the columns into the table of an answer: the codes of DWD's missing values are null.

        The decimal comma is a point first, which `null_sentinels` matches by number; the text DWD wrote in place of
        a value (`raw`) has no place in an answer, since a cell with a missing value is no answer (see the module).
        """
        long = long.with_columns(
            pl.col("column").str.slice(0, 2).alias("kind"),
            pl.col("column").str.slice(3, 3).cast(pl.Int64).alias("return_period_years"),
            pl.col("text").str.replace(",", ".", literal=True),
        )
        value, _raw = null_sentinels(pl.col("text"), _NO_DEPTH, _NO_UNCERTAINTY)
        try:
            long = long.with_columns(value.cast(pl.Float64).alias("value"))
        except pl.exceptions.PolarsError as e:
            msg = f"a table of KOSTRA-DWD-2020 holds a value that is no number: {e}"
            raise MetaFileFormatError(msg) from e
        table = (
            long.with_columns(pl.col("kind").replace_strict(_KINDS, return_dtype=pl.String).alias("name"))
            .pivot(on="name", index=["duration_minutes", "return_period_years"], values="value")
            .sort("duration_minutes", "return_period_years")
        )
        return table.select(list(_SCHEMA)).cast(pl.Schema(_SCHEMA))


def _read_row(file: File, cell: Cell) -> list[str]:
    """Read the fields of the row of a cell from the zipped table of a duration, in the order of the header.

    Raises:
        MetaFileFormatError: the body is no zip (a page of an outage), is corrupt or compressed in a way the reader does
            not know, holds no single table, the table's header is not the one DWD describes, or it has no row for the
            cell.

    """
    content = file.content
    if isinstance(content, Exception):  # raised by the caller
        raise content
    try:
        with zipfile.ZipFile(io.BytesIO(content.getvalue())) as archive:
            members = [info for info in archive.infolist() if info.filename.lower().endswith(".csv")]
            if len(members) != 1 or members[0].file_size > _MAX_TABLE_BYTES:
                msg = f"{file.url} holds no single KOSTRA table"
                raise MetaFileFormatError(msg)
            with archive.open(members[0]) as member:
                text = member.read(_MAX_TABLE_BYTES + 1)
            if len(text) > _MAX_TABLE_BYTES:
                msg = f"{file.url} holds a table larger than any of KOSTRA-DWD-2020"
                raise MetaFileFormatError(msg)
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError) as e:
        # a page of a CDN's outage, a body cut short or flipped, a compression the reader does not know, or an
        # encrypted member: DWD's to answer for, whichever of the readers of the archive says so
        msg = f"{file.url} is no readable zip archive of a table"
        raise MetaFileFormatError(msg) from e
    text = text.removeprefix(b"\xef\xbb\xbf")
    head, _, _ = text.partition(b"\n")
    header = head.decode("utf-8", errors="replace").strip().split(";")
    if header != _HEADER:
        msg = f"the table {file.url} has the columns {header[:3]}..., not those DWD describes"
        raise MetaFileFormatError(msg)
    # the rows are sorted by `INDEX_RC`, which a line of the table starts with: find it without parsing 90,000 rows
    start = text.find(b"\n" + cell.index_rc.encode() + b";")
    if start < 0:
        msg = f"the table {file.url} has no row for the cell {cell.index_rc}"
        raise MetaFileFormatError(msg)
    end = text.find(b"\n", start + 1)
    line = text[start + 1 : end if end >= 0 else len(text)]
    fields = line.decode("utf-8", errors="replace").strip().split(";")
    if len(fields) != len(_HEADER):
        msg = f"the row of the cell {cell.index_rc} in {file.url} has {len(fields)} fields, not {len(_HEADER)}"
        raise MetaFileFormatError(msg)
    return fields

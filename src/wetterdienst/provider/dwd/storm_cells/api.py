# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""API for DWD's KONRAD3D thunderstorm cells.

KONRAD3D finds the convective cells in DWD's radar volume scans, tracks them and nowcasts the position of their centre
for the next hour. DWD publishes one XML file every five minutes at https://opendata.dwd.de/weather/radar/konrad3d/ ,
named for the reference time of the run, and keeps about 48 hours of them. This module reads the newest, or the newest
at or before a time, into one row per cell with its severity, its warning flags, its outline and its forecast track.

Cells do not fit the station/timeseries model (a cell has no stable id: DWD reuses the identifiers), so -- like
`DwdWeatherAlertRequest` -- this is a standalone request class returning its own result object. The raw files stay
available through `DwdRadarValues` (`RadarParameter.KONRAD3D_CONVECTIVE_CELLS`).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.exceptions import InvalidTimeIntervalError, MetaFileFormatError, MetaFileNotFoundError, RequestError
from wetterdienst.io.export import render_data_format
from wetterdienst.io.sinks import write_storm_cells_to_target
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import Extent, ProviderTerms
from wetterdienst.model.result import describe_provider
from wetterdienst.provider.dwd.metadata import _METADATA
from wetterdienst.provider.dwd.storm_cells.metadata import (
    DWD_STORM_CELLS_BASE_URL,
    SCAN_STALE_AFTER,
    SEVERITY_LABELS,
    STORM_CELLS_NOTE,
)
from wetterdienst.provider.dwd.storm_cells.parser import Scan, parse_scan
from wetterdienst.provider.dwd.storm_cells.place import check_place, is_for_box, is_for_point
from wetterdienst.settings import Settings
from wetterdienst.util.datetime import format_timestamp
from wetterdienst.util.json_util import dumps_json, json_indent
from wetterdienst.util.network import download_file, list_remote_directory_fsspec
from wetterdienst.util.response_warnings import RESPONSE_WARNING_RECORD, record_response_warning, warn_response
from wetterdienst.util.url import ConnectionString, redact_password

if TYPE_CHECKING:
    from wetterdienst.model.result import ResultMetadata

log = logging.getLogger(__name__)

UTC = ZoneInfo("UTC")

#: the code of the warning that tells that a filter left no cell of a scan that has some: an answer, not a failure,
#: which a caller who reads `cells: []` alone would take for a quiet sky
NO_STORM_CELLS_FOR_PLACE = "no-storm-cells-for-place"
#: what the log says of it, with nothing of the place (the point is a location of the requester)
_NO_STORM_CELLS_FOR_PLACE_LOG = "no cell of the scan is for the requested place"

#: the code of the warning that tells that the newest scan is much older than the time asked for: DWD's run stopped, or
#: its files did, and an empty answer is then no all-clear
SCAN_STALE = "scan-stale"

#: how long DWD keeps the files, for the message of a time before them
_WINDOW = "about 48 hours"

_FILE_PATTERN = re.compile(r"KONRAD3D_(\d{8}T\d{6})\.xml$")

#: the severity of a cell is 0 to 3
_MAX_SEVERITY = len(SEVERITY_LABELS) - 1

_TRACK_FIELD = pl.Struct(
    {
        "time": pl.Datetime(time_unit="us", time_zone="UTC"),
        "latitude": pl.Float64,
        "longitude": pl.Float64,
        "uncertainty_major_km": pl.Float64,
        "uncertainty_minor_km": pl.Float64,
        "uncertainty_angle_degrees": pl.Float64,
    }
)

# Column order / schema of the cells' DataFrame (``.df``). `geometry` is GeoJSON text and `track` a list of structs.
_SCHEMA: dict[str, Any] = {
    "reference_time": pl.Datetime(time_unit="us", time_zone="UTC"),
    "cell_id": pl.String,
    "code": pl.String,
    "predecessor_code": pl.String,
    "split_event": pl.Boolean,
    "merge_event": pl.Boolean,
    "first_detection": pl.Datetime(time_unit="us", time_zone="UTC"),
    "number_detections": pl.Int64,
    "severity": pl.Int64,
    "severity_label": pl.String,
    "severity_decimal": pl.Float64,
    "hail_flag": pl.Int64,
    "heavy_rain_flag": pl.Int64,
    "gust_flag": pl.Int64,
    "centroid_latitude": pl.Float64,
    "centroid_longitude": pl.Float64,
    "cell_speed_kmh": pl.Float64,
    "direction_degrees": pl.Float64,
    "covered_area_km2": pl.Float64,
    "echo_top_msl_m": pl.Float64,
    "max_reflectivity_dbz": pl.Float64,
    "vil_kg_m2": pl.Float64,
    "max_estimated_gust_kmh": pl.Float64,
    "heavy_rain_potential_mm": pl.Float64,
    "geometry": pl.String,
    "track": pl.List(_TRACK_FIELD),
}

#: the columns of a cell that are times: written as text wherever the format has no times
_TIME_COLUMNS = ("reference_time", "first_detection")

GeometryKind = Literal["outline", "centroid"]


def _now() -> dt.datetime:
    """Give the time now (UTC); the one place the age of a scan is measured against, so that a test can set it."""
    return dt.datetime.now(UTC)


def _geometry_of(cell: dict[str, Any], kind: GeometryKind) -> dict[str, Any] | None:
    """Give the GeoJSON geometry of a cell: its outline (a `MultiPolygon` if in parts) or the point of its centre."""
    if kind == "centroid":
        latitude, longitude = cell["centroid_latitude"], cell["centroid_longitude"]
        return (
            None if latitude is None or longitude is None else {"type": "Point", "coordinates": [longitude, latitude]}
        )
    rings = cell["rings"]
    if not rings:
        return None
    if len(rings) == 1:
        return {"type": "Polygon", "coordinates": [rings[0]]}
    return {"type": "MultiPolygon", "coordinates": [[ring] for ring in rings]}


class DwdStormCellsResult:
    """Result of a :class:`DwdStormCellsRequest`: the cells of a scan as a polars DataFrame, one row per cell."""

    def __init__(
        self,
        df: pl.DataFrame,
        reference_time: dt.datetime | None,
        data_updated_at: dt.datetime | None = None,
    ) -> None:
        """Initialize the result.

        Args:
            df: the cells, one row each, following the columns of the answer (``track`` is left out for a request
                without it).
            reference_time: the reference time of the scan the cells are of, the start of its radar scan cycle (UTC):
                an empty scan has it too, so that "no cell" says when it was true.
            data_updated_at: when DWD wrote the file (`creation-date`), the date of the data in the metadata.

        """
        self.df = df
        self.reference_time = reference_time
        self.data_updated_at = data_updated_at

    def _cells(self) -> list[dict[str, Any]]:
        """Return the cells with the geometry decoded and every time written as text."""
        cells = []
        for row in self.df.iter_rows(named=True):
            cell = dict(row)
            if cell.get("geometry") is not None:
                cell["geometry"] = json.loads(row["geometry"])
            for column in _TIME_COLUMNS:
                value: dt.datetime | None = row[column]
                cell[column] = format_timestamp(value) if value is not None else None
            if row.get("track") is not None:
                cell["track"] = [
                    {**point, "time": format_timestamp(point["time"]) if point["time"] is not None else None}
                    for point in row["track"]
                ]
            cells.append(cell)
        return cells

    def _metadata(self) -> ResultMetadata:
        """Give the `metadata` block that `with_metadata` adds: the provider, this library and the date of the data."""
        return describe_provider(DwdStormCellsRequest.terms, self.data_updated_at, calculated=STORM_CELLS_NOTE)

    @property
    def _reference_time_text(self) -> str | None:
        return format_timestamp(self.reference_time) if self.reference_time is not None else None

    def to_dict(self, *, with_metadata: bool = False) -> dict[str, Any]:
        """Return the cells as ``{"reference_time": ..., "cells": [...]}``, with the outline and the track nested.

        ``reference_time`` is the UTC reference time (ISO string) of the scan, also for a scan without a cell.

        Args:
            with_metadata: whether to put the ``metadata`` block (provider, producer and the date of the data) first

        """
        data: dict[str, Any] = {"reference_time": self._reference_time_text, "cells": self._cells()}
        return {"metadata": self._metadata(), **data} if with_metadata else data

    def to_json(self, indent: int | bool | None = False, *, with_metadata: bool = False) -> str:  # noqa: FBT001, FBT002
        """Return the cells as a JSON string.

        Args:
            indent: a number of spaces, ``True`` for 4, ``False`` or ``None`` (the default) for one line
            with_metadata: whether to put the ``metadata`` block first

        """
        return dumps_json(self.to_dict(with_metadata=with_metadata), indent=json_indent(indent), ensure_ascii=False)

    def to_ogc_feature_collection(self, *, with_metadata: bool = False) -> dict[str, Any]:
        """Return the cells as a GeoJSON ``FeatureCollection``.

        Each cell becomes a ``Feature`` whose geometry is its outline (``null`` where DWD gave none) and whose
        properties are the other columns, the track nested.

        Args:
            with_metadata: whether to carry the ``metadata`` block as a foreign member after ``type``, as the REST API
                does (RFC 7946, 6.1)

        """
        features = []
        for cell in self._cells():
            geometry = cell.pop("geometry", None)
            features.append({"type": "Feature", "geometry": geometry, "properties": cell})
        return {
            "type": "FeatureCollection",
            **({"metadata": self._metadata()} if with_metadata else {}),
            "reference_time": self._reference_time_text,
            "features": features,
        }

    def to_geojson(self, indent: int | bool | None = False, *, with_metadata: bool = False) -> str:  # noqa: FBT001, FBT002
        """Return the cells as a GeoJSON ``FeatureCollection`` string.

        Args:
            indent: a number of spaces, ``True`` for 4, ``False`` or ``None`` (the default) for one line
            with_metadata: whether to carry the ``metadata`` block as a foreign member

        """
        return dumps_json(
            self.to_ogc_feature_collection(with_metadata=with_metadata),
            indent=json_indent(indent),
            ensure_ascii=False,
        )

    def to_csv(self) -> str:
        """Return the cells as CSV, a row each; the times are ISO strings, the ``geometry`` and ``track`` JSON text."""
        from wetterdienst.util.datetime import timestamps_to_string  # noqa: PLC0415

        df = timestamps_to_string(self.df.drop("track", strict=False), _TIME_COLUMNS)
        if "track" in self.df.columns:
            tracks = [json.dumps(cell["track"], ensure_ascii=False) for cell in self._cells()]
            df = df.with_columns(pl.Series("track", tracks, dtype=pl.String))
        return df.write_csv()

    def to_format(self, fmt: str, **kwargs: Any) -> str:  # noqa: ANN401
        """Render the result in the requested format (``json``, ``geojson`` or ``csv``), in any case.

        Like ``to_format`` of the other results, it takes the one set of arguments a caller builds for every format and
        gives each format those it takes: ``with_metadata`` and ``indent`` to JSON and GeoJSON, none to CSV (it has no
        place for the ``metadata`` block).

        Raises:
            UnknownFormatError: ``fmt`` is none of the three. It is a ``ValueError`` and a ``KeyError``.
            TypeError: an argument that no format takes.

        """
        return render_data_format(self, fmt, kwargs, only=("json", "geojson", "csv"))

    def to_target(
        self,
        target: str,
        if_exists: Literal["replace", "append", "fail", "skip"] = "replace",
        *,
        with_metadata: bool = False,
        pretty: bool = False,
    ) -> None:
        """Write the cells to a file: JSON, GeoJSON or CSV, by the extension of the target.

        A file holds what the REST API answers for the format (``render_storm_cells``), on one line unless ``pretty``:

        - ``file://cells.json``: ``{"metadata": ..., "reference_time": ..., "cells": [...]}``
        - ``file://cells.geojson``: the ``FeatureCollection`` of ``to_geojson``, with ``metadata`` as a foreign member
        - ``file://cells.csv``: the text of ``to_csv``, bare, a row for each cell

        A scan without a cell is written as it is (an empty ``cells`` list and the block in a JSON file, a CSV of the
        header alone), so a file that a schedule rewrites does not keep the cells of the run before. ``with_metadata``
        writes the block beside any file as ``<file>.metadata.json``, which is how a CSV file gets it. A database
        target is refused: a cell is nested, and there is no table for it yet.

        Args:
            target: ``file://`` and a path, ending in ``.json``, ``.geojson`` or ``.csv``
            if_exists: ``replace`` (default), ``fail`` or ``skip``; ``append`` is refused for a file
            with_metadata: write ``<file>.metadata.json`` beside the file
            pretty: indent a JSON or GeoJSON file with 4 spaces

        Raises:
            ExportRefusedError: a target that is no file of those three types, ``append``, a file that exists under
                ``fail``, or ``with_metadata`` for a database target.

        """
        connspec = ConnectionString(target)
        log.info(f"Exporting {self.df.height} storm cells to {redact_password(target)}")
        write_storm_cells_to_target(self, target, connspec, if_exists, with_metadata=with_metadata, pretty=pretty)


class DwdStormCellsRequest:
    """API for DWD's KONRAD3D thunderstorm cells.

    Reads one scan of the cells -- the newest, or the newest at or before a ``timestamp`` within the ~48 hours DWD
    keeps -- and parses it into a :class:`DwdStormCellsResult`. A scan is the cells of the whole of Germany and its
    surroundings; ``latitude``, ``longitude`` and ``distance``, or a box (``left``, ``bottom``, ``right``, ``top``),
    keep the cells for a place, and ``min_severity`` those of at least that severity.

    Most scans hold no cell, and the newest file is 5 to 10 minutes old when it appears: the answer says which scan it
    is of (``reference_time``), and warns (``scan-stale``) where that scan is more than 20 minutes older than the time
    asked for, so that an empty answer from a stopped feed is not read as a quiet sky.
    """

    # how `Wetterdienst.discover()` lists the network, which is no timeseries network and has no metadata model: the
    # name and the country are the provider's, the url is where the scans are published
    listing: ClassVar = {
        "name_short": _METADATA["name_short"],
        "country": _METADATA["country"],
        "kind": "storm_cells",
        "url": DWD_STORM_CELLS_BASE_URL,
    }

    # who published the files and under which terms, which an answer about them names as a network with a metadata
    # model does through its `MetadataModel`
    terms: ClassVar = ProviderTerms(
        name_local=_METADATA["name_local"],
        name_english=_METADATA["name_english"],
        country=_METADATA["country"],
        country_code=_METADATA["country_code"],
        copyright="© Deutscher Wetterdienst (DWD), KONRAD3D convective cells",
        license=_METADATA["license"],
        attribution=_METADATA["attribution"],
        url=DWD_STORM_CELLS_BASE_URL,
        # the grid of the radar composite DWD runs KONRAD3D on (45.7 to 55.9 N, 1.4 to 18.8 E): cells outside Germany
        # are possible (declared from the documentation of DWD, no station list to hold it to)
        extent=Extent(scope="national", continents=["europe"], country_codes=["DE"], bbox=[1.4, 45.7, 18.8, 55.9]),
    )

    def __init__(
        self,
        timestamp: str | dt.datetime | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        distance: float | None = None,
        left: float | None = None,
        bottom: float | None = None,
        right: float | None = None,
        top: float | None = None,
        min_severity: int | None = None,
        *,
        track: bool = True,
        geometry: GeometryKind = "outline",
        settings: Settings | None = None,
    ) -> None:
        """Initialize the request.

        Args:
            timestamp: point in time to select the scan for. ``None`` (default) uses the newest scan. Otherwise the
                newest scan at or before it is used; it must fall within DWD's rolling ~48-hour window. A naive
                datetime or ISO string is interpreted as UTC.
            latitude: with ``longitude``, keep the cells whose outline contains this point (WGS84 degrees; an edge
                counts as inside) or comes within ``distance`` of it.
            longitude: the longitude of the point; it is given with ``latitude``, or not at all.
            distance: with a point, the km from the point within which the outline of a cell counts as near, 0
                (default) for the cells that are over the point. Not given without a point.
            left: with ``bottom``, ``right`` and ``top``, keep the cells whose outline reaches into this box (WGS84
                degrees, the western edge). The point and the box are not given together.
            bottom: the southern edge of the box.
            right: the eastern edge of the box.
            top: the northern edge of the box.
            min_severity: keep the cells of this severity (0 weak, 1 moderate, 2 severe, 3 extreme) and above.
            track: whether the cells carry their forecast ``track`` (12 positions, 1.6 KB of JSON each); without it
                the column is left out. ``direction_degrees`` is calculated from it either way.
            geometry: ``outline`` (default) gives the ``geometry`` of a cell as the polygon of its outline;
                ``centroid`` as the point of its centre, which is a few dozen characters and not a few hundred to two
                thousand. The filters of a place read the outline either way.
            settings: settings for the request.

        Raises:
            RequestError: a place that is half a point, a distance without a point, half a box, a point and a box
                together, a ``min_severity`` that is no severity, a ``geometry`` of neither kind, or a ``timestamp``
                that does not parse.

        """
        self.timestamp = self._parse_timestamp(timestamp)
        check_place(latitude, longitude, distance, left, bottom, right, top)
        if min_severity is not None and not (0 <= min_severity <= _MAX_SEVERITY):
            msg = f"min_severity is a severity from 0 ({SEVERITY_LABELS[0]}) to {_MAX_SEVERITY} ({SEVERITY_LABELS[-1]})"
            raise RequestError(msg)
        if geometry not in ("outline", "centroid"):
            msg = f"geometry {geometry!r} not supported, use 'outline' or 'centroid'"
            raise RequestError(msg)
        self.latitude = latitude
        self.longitude = longitude
        self.distance = distance
        self.left, self.bottom, self.right, self.top = left, bottom, right, top
        self.min_severity = min_severity
        self.track = track
        self.geometry: GeometryKind = geometry
        self.settings = settings or Settings()

    def __repr__(self) -> str:
        """Return a string representation of the request."""
        return (
            f"DwdStormCellsRequest(timestamp={self.timestamp.isoformat() if self.timestamp else None}, "
            f"latitude={self.latitude}, longitude={self.longitude}, distance={self.distance}, "
            f"left={self.left}, bottom={self.bottom}, right={self.right}, top={self.top}, "
            f"min_severity={self.min_severity}, track={self.track}, geometry={self.geometry!r})"
        )

    @staticmethod
    def _parse_timestamp(timestamp: str | dt.datetime | None) -> dt.datetime | None:
        if timestamp is None:
            return None
        if isinstance(timestamp, str):
            # An empty/whitespace timestamp (e.g. from an omitted-but-present ``?timestamp=`` query param) means
            # "newest", not an invalid timestamp.
            timestamp = timestamp.strip()
            if not timestamp:
                return None
            try:
                parsed = dt.datetime.fromisoformat(timestamp)
            except ValueError as e:
                msg = f"timestamp {timestamp!r} is not an ISO 8601 time: {e}"
                raise RequestError(msg) from e
        else:
            parsed = timestamp
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        try:
            return parsed.astimezone(UTC)
        except OverflowError as e:
            # an offset that carries the time out of what a datetime holds
            msg = f"timestamp {timestamp!r} is out of range"
            raise RequestError(msg) from e

    @property
    def _has_place(self) -> bool:
        """Tell whether the request names a point or a box."""
        return self.latitude is not None or self.left is not None

    @property
    def _has_filter(self) -> bool:
        """Tell whether the request keeps some of the cells of a scan: a place or a severity."""
        return self._has_place or self.min_severity is not None

    @property
    def _directory_url(self) -> str:
        return f"{DWD_STORM_CELLS_BASE_URL}/"

    def _resolve_scan(self) -> tuple[str, dt.datetime]:
        """Resolve the request to the file of a scan: ``(url, reference time)``, from the listing of the directory.

        The newest file, or the newest at or before ``timestamp``; the times of the file names are UTC. The listing is
        kept for a minute (the files come every five). There is no ``latest`` file to ask for instead.

        Raises:
            InvalidTimeIntervalError: ``timestamp`` falls before DWD's rolling window (no file at or before it).
            MetaFileNotFoundError: the listing holds no scan at all, which is no time's doing.

        """
        scans: list[tuple[dt.datetime, str]] = []
        for entry in list_remote_directory_fsspec(
            self._directory_url, settings=self.settings, cache_expiry=CacheExpiry.ONE_MINUTE
        ):
            name = entry["name"].rsplit("/", 1)[-1]
            match = _FILE_PATTERN.search(name)
            if match:
                reference_time = dt.datetime.strptime(match.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
                scans.append((reference_time, name))

        if not scans:
            msg = f"no KONRAD3D scan listed at {self._directory_url}"
            raise MetaFileNotFoundError(msg)

        if self.timestamp is None:
            reference_time, name = max(scans)
        else:
            candidates = [(reference_time, name) for reference_time, name in scans if reference_time <= self.timestamp]
            if not candidates:
                earliest = min(reference_time for reference_time, _ in scans)
                msg = (
                    f"no KONRAD3D scan available at or before {self.timestamp.isoformat()} "
                    f"(DWD only keeps a rolling {_WINDOW} window). earliest available is {earliest.isoformat()}."
                )
                raise InvalidTimeIntervalError(msg)
            reference_time, name = max(candidates)
        return f"{self._directory_url}{name}", reference_time

    def _warn_if_stale(self, reference_time: dt.datetime) -> None:
        """Warn where the scan is more than `SCAN_STALE_AFTER` older than the time asked for (now, or the timestamp)."""
        asked = self.timestamp or _now()
        age = asked - reference_time
        if age <= SCAN_STALE_AFTER:
            return
        minutes = round(age.total_seconds() / 60)
        what = "the timestamp asked for" if self.timestamp else "now"
        warn_response(
            log,
            SCAN_STALE,
            f"The newest scan at or before {what} is from {format_timestamp(reference_time)}, {minutes} minutes "
            f"earlier: DWD publishes one every 5 minutes, so scans are missing (DWD's run or its files stopped, or "
            f"the time asked for is past the last scan). Cells that were there since are not in the answer, and "
            f"an empty one is no all-clear.",
        )

    def query(self) -> DwdStormCellsResult:
        """Download and parse the selected KONRAD3D scan (the newest by default) and keep the cells asked for."""
        url, file_time = self._resolve_scan()
        self._warn_if_stale(file_time)
        log.info(f"acquiring storm cells from {url}")
        scan = self._read(url)
        cells = self._keep(scan.cells)
        return DwdStormCellsResult(
            df=self._build_dataframe(cells),
            reference_time=scan.reference_time or file_time,
            data_updated_at=scan.created_at,
        )

    def _download(self, url: str, *, refetch: bool = False) -> tuple[bytes, bool]:
        """Download a scan file, a copy held in the cache as it is, or fetched again if `refetch`.

        A file named for a time never changes once it is written, so it is kept for 12 hours.
        """
        file = download_file(
            url=url,
            cache_dir=self.settings.cache_dir,
            ttl=CacheExpiry.TWELVE_HOURS,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
            use_certifi=self.settings.use_certifi,
            refetch_before=time.time() if refetch else None,
        )
        # A download failure (a 404 from a file that rolled off the window between the listing and this download, a
        # timeout, a 429) is raised as the error it is: a `DownloadError` naming the file, a `ProviderRateLimitError`,
        # a `NoInternetError` naming the URL
        file.raise_if_exception()
        content = file.content
        if isinstance(content, Exception):  # raised above
            raise content
        return content.read(), file.from_cache

    def _read(self, url: str) -> Scan:
        """Download and parse a scan file.

        A file that does not parse is a `MetaFileFormatError`: DWD's, not the request's. A copy from the cache that
        does not parse (one read while DWD was still writing it) is fetched once more before it is: the cache would
        keep it for 12 hours.
        """
        body, from_cache = self._download(url)
        try:
            return self._parse(body, url)
        except MetaFileFormatError:
            if not from_cache:
                raise
        body, _ = self._download(url, refetch=True)
        return self._parse(body, url)

    @staticmethod
    def _parse(body: bytes, url: str) -> Scan:
        try:
            return parse_scan(body)
        except (ValueError, OverflowError, SyntaxError) as e:
            # lxml's `XMLSyntaxError` is a `SyntaxError`: a file that does not parse, one read while it was written; or
            # a document of another kind, a time or a number the parser does not read
            msg = f"KONRAD3D scan from {url} holds what the parser does not expect: {e}"
            raise MetaFileFormatError(msg) from e

    def _keep(self, cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep the cells for the place and the severity asked for; all of them for a request that gives none.

        A filter that leaves no cell of a scan that has some is an answer: the `no-storm-cells-for-place` warning
        says so with how many cells the scan holds, so that it is not taken for a failure or for a quiet sky.
        """
        if not self._has_filter:
            return cells
        kept = [cell for cell in cells if self._is_wanted(cell)]
        if cells and not kept:
            record_response_warning(NO_STORM_CELLS_FOR_PLACE, self._none_wanted(len(cells)))
            # the log line is a fixed text: the message holds the point, which is the requester's own
            log.info(_NO_STORM_CELLS_FOR_PLACE_LOG, extra={RESPONSE_WARNING_RECORD: NO_STORM_CELLS_FOR_PLACE})
        return kept

    def _is_wanted(self, cell: dict[str, Any]) -> bool:
        if self.min_severity is not None and (cell["severity"] is None or cell["severity"] < self.min_severity):
            return False
        if self.latitude is not None and self.longitude is not None:
            return is_for_point(_geometry_of(cell, "outline"), self.latitude, self.longitude, self.distance or 0.0)
        if self.left is not None and self.bottom is not None and self.right is not None and self.top is not None:
            return is_for_box(_geometry_of(cell, "outline"), self.left, self.bottom, self.right, self.top)
        return True

    def _none_wanted(self, count: int) -> str:
        """Say that no cell of a scan of `count` cells is wanted, in the words of what was asked."""
        asked = []
        if self.latitude is not None:
            near = f"within {self.distance:g} km of" if self.distance else "over"
            asked.append(f"{near} the point {self.latitude}, {self.longitude}")
        elif self.left is not None:
            asked.append(f"in the box {self.left}, {self.bottom}, {self.right}, {self.top}")
        if self.min_severity is not None:
            asked.append(f"of severity {self.min_severity} ({SEVERITY_LABELS[self.min_severity]}) or more")
        cells = "1 cell is" if count == 1 else f"{count} cells are"
        return (
            f"No storm cell of the scan is {' and '.join(asked)}. That is the answer, not an error: {cells} "
            "elsewhere in the scan, which the request leaves out."
        )

    def _build_dataframe(self, cells: list[dict[str, Any]]) -> pl.DataFrame:
        """Build the DataFrame of the cells: the columns of `_SCHEMA`, the geometry as GeoJSON text."""
        schema = {name: dtype for name, dtype in _SCHEMA.items() if self.track or name != "track"}
        rows = []
        for cell in cells:
            row = {column: cell.get(column) for column in schema}
            severity = cell["severity"]
            row["severity_label"] = SEVERITY_LABELS[severity] if severity is not None and 0 <= severity <= 3 else None
            geometry = _geometry_of(cell, self.geometry)
            row["geometry"] = None if geometry is None else json.dumps(geometry)
            rows.append(row)
        return pl.DataFrame(rows, schema=cast("Any", schema))

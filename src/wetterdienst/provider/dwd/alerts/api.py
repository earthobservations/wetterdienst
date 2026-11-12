# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""API for DWD CAP weather alerts (warnings).

DWD publishes its public warnings as zipped Common Alerting Protocol (CAP) v1.2 documents at
https://opendata.dwd.de/weather/alerts/cap/ . This module exposes the DWD full-snapshot products
(one CAP file per active warning) on community (Gemeinde) or district (Landkreis) basis and
flattens each alert into a single row, including a GeoJSON ``MultiPolygon`` geometry.

Alerts do not fit the station/timeseries model, so -- like ``DwdRadarValues`` -- this is a
standalone request class returning its own result object rather than a ``TimeseriesRequest``.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import zipfile
import zlib
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Never, cast
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.exceptions import (
    DownloadError,
    InvalidTimeIntervalError,
    MetaFileFormatError,
    MetaFileNotFoundError,
    RequestError,
)
from wetterdienst.io.export import render_data_format
from wetterdienst.io.sinks import write_alerts_to_target
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import Extent, ProviderTerms
from wetterdienst.model.result import describe_provider
from wetterdienst.provider.dwd.alerts.metadata import (
    DWD_ALERTS_BASE_URL,
    DwdWeatherAlertGranularity,
    DwdWeatherAlertLanguage,
)
from wetterdienst.provider.dwd.alerts.parser import parse_cap_alert
from wetterdienst.provider.dwd.alerts.place import check_point, is_for_place
from wetterdienst.provider.dwd.metadata import _METADATA
from wetterdienst.settings import Settings
from wetterdienst.util.archive import check_zip, read_unpacked
from wetterdienst.util.datetime import format_timestamp, timestamps_to_string
from wetterdienst.util.json_util import dumps_json, json_indent
from wetterdienst.util.network import download_file, list_remote_directory_fsspec
from wetterdienst.util.response_warnings import warn_response
from wetterdienst.util.url import ConnectionString, redact_password

if TYPE_CHECKING:
    from io import BytesIO

    from wetterdienst.model.result import ResultMetadata

log = logging.getLogger(__name__)

#: the code of the warning that tells a request for a place that no warning of the snapshot is for it: an answer, not
#: a failure, which a caller who reads `alerts: []` alone would take for the one or the other
NO_ALERTS_FOR_PLACE = "no-alerts-for-place"

# The most a snapshot may unpack to. The largest unpacks to 35 MB (the multilingual district file, on a quiet day);
# 256 MiB is seven times that.
_MAX_UNPACKED_BYTES = 256 * 1024**2

# The alert row columns whose values are nested structures; stored as JSON strings in the DataFrame
# but returned as native objects by ``to_dict``/``to_ogc_feature_collection``.
_JSON_COLUMNS = ("parameters", "geometry", "translations")

# List-valued alert row columns.
_LIST_COLUMNS = ("groups", "warncell_ids", "area_names")

# Column order / schema of the flat alert DataFrame (``.df``).
_SCHEMA = {
    "alert_id": pl.String,
    "status": pl.String,
    "msg_type": pl.String,
    "category": pl.String,
    "event": pl.String,
    "event_code": pl.String,
    "groups": pl.List(pl.String),
    "response_type": pl.String,
    "urgency": pl.String,
    "severity": pl.String,
    "certainty": pl.String,
    "effective": pl.Datetime(time_unit="us", time_zone="UTC"),
    "onset": pl.Datetime(time_unit="us", time_zone="UTC"),
    "expires": pl.Datetime(time_unit="us", time_zone="UTC"),
    "sent": pl.Datetime(time_unit="us", time_zone="UTC"),
    "headline": pl.String,
    "description": pl.String,
    "instruction": pl.String,
    "sender_name": pl.String,
    "web": pl.String,
    "contact": pl.String,
    "area_color": pl.String,
    "parameters": pl.String,
    "warncell_ids": pl.List(pl.String),
    "area_names": pl.List(pl.String),
    "geometry": pl.String,
    "references": pl.String,
    "language": pl.String,
    # the further `<info>` blocks of the message (the other languages of `mul`), JSON text: [{"language": ..., + the
    # fields that differ from the first block's}, ...], `[]` for a message of one block (GH-3801)
    "translations": pl.String,
}


class DwdWeatherAlertResult:
    """Result of a :class:`DwdWeatherAlertRequest`, wrapping the parsed alerts as a polars DataFrame."""

    def __init__(
        self,
        df: pl.DataFrame,
        granularity: DwdWeatherAlertGranularity,
        language: DwdWeatherAlertLanguage,
        snapshot: dt.datetime | None = None,
        snapshot_updated_at: dt.datetime | None = None,
    ) -> None:
        """Initialize the result.

        Args:
            df: the flat alert DataFrame following ``_SCHEMA`` (nested fields JSON-encoded).
            granularity: the requested granularity.
            language: the requested language.
            snapshot: production time (UTC) of the selected snapshot, or ``None`` for the latest one.
            snapshot_updated_at: the newest ``sent`` of every warning of the snapshot, which a request for a place
                gives because ``df`` holds only the warnings for it; ``None`` (the default) for ``df`` being the
                whole snapshot, whose own newest ``sent`` it is.

        """
        self.snapshot_updated_at = snapshot_updated_at
        self.df = df
        self.granularity = granularity
        self.language = language
        self.snapshot = snapshot

    @property
    def data_updated_at(self) -> dt.datetime | None:
        """When DWD last said anything of the warnings it published: the newest `sent` of the snapshot (GH-2567).

        The `sent` of a CAP message is the time DWD issued it, an update of a warning being a new message, so the
        newest of them is the "date of the most recent update" of the data read. It is stated in the body of each
        warning, not read off the file the snapshot came in. It is that of the **whole snapshot**, also for a request
        for a place (`DwdWeatherAlertRequest` with a point or a name) whose answer holds a few warnings, or none: it
        says how current the data is that was checked, and a `timestamp` taken from it reads the same snapshot.
        `None` for a snapshot without a warning.
        """
        if self.snapshot_updated_at is not None:
            return self.snapshot_updated_at
        sent = self.df.get_column("sent").drop_nulls()
        return None if sent.is_empty() else cast("dt.datetime", sent.max())

    def _alerts(self) -> list[dict[str, Any]]:
        """Return the alert rows with nested fields (parameters, geometry, translations) decoded to native objects."""
        alerts = []
        for row in self.df.iter_rows(named=True):
            alert = dict(row)
            for column in _JSON_COLUMNS:
                alert[column] = json.loads(row[column]) if row[column] is not None else None
            for column in ("effective", "onset", "expires", "sent"):
                value: dt.datetime | None = row[column]
                alert[column] = format_timestamp(value) if value is not None else None
            alerts.append(alert)
        return alerts

    def _metadata(self) -> ResultMetadata:
        """Give the `metadata` block that `with_metadata` adds: the provider, this library and the date of the data.

        The block of the other results, from the terms of the network; the REST API answers with a fuller one.
        """
        return describe_provider(DwdWeatherAlertRequest.terms, self.data_updated_at)

    def to_dict(self, *, with_metadata: bool = False) -> dict[str, Any]:
        """Return the alerts as ``{"snapshot": ..., "alerts": [...]}`` with nested geometry/parameters/translations.

        ``snapshot`` is the UTC production time (ISO string) of the selected snapshot, or ``None``
        for the latest one, so callers can tell which point-in-time snapshot they received.

        Args:
            with_metadata: whether to put the ``metadata`` block (provider, producer and the date of the data) first

        """
        data: dict[str, Any] = {
            "snapshot": format_timestamp(self.snapshot) if self.snapshot is not None else None,
            "alerts": self._alerts(),
        }
        return {"metadata": self._metadata(), **data} if with_metadata else data

    def to_json(self, indent: int | bool | None = False, *, with_metadata: bool = False) -> str:  # noqa: FBT001, FBT002
        """Return the alerts as a JSON string.

        Args:
            indent: a number of spaces, ``True`` for 4, ``False`` or ``None`` (the default) for one line, as the
                ``indent`` of the other results' ``to_json``
            with_metadata: whether to put the ``metadata`` block first

        """
        return dumps_json(self.to_dict(with_metadata=with_metadata), indent=json_indent(indent), ensure_ascii=False)

    def to_ogc_feature_collection(self, *, with_metadata: bool = False) -> dict[str, Any]:
        """Return the alerts as a GeoJSON ``FeatureCollection``.

        Each alert becomes a ``Feature`` whose geometry is its ``MultiPolygon`` (``null`` when the
        alert only carries entity/``WARNCELLID`` areas without polygons) and whose properties are the
        remaining alert fields.

        Args:
            with_metadata: whether to carry the ``metadata`` block as a foreign member after ``type``, as the REST API
                does (RFC 7946, 6.1)

        """
        features = []
        for alert in self._alerts():
            geometry = alert.pop("geometry")
            features.append({"type": "Feature", "geometry": geometry, "properties": alert})
        # "snapshot" is a GeoJSON foreign member carrying the selected snapshot's UTC production time.
        return {
            "type": "FeatureCollection",
            **({"metadata": self._metadata()} if with_metadata else {}),
            "snapshot": format_timestamp(self.snapshot) if self.snapshot is not None else None,
            "features": features,
        }

    def to_geojson(self, indent: int | bool | None = False, *, with_metadata: bool = False) -> str:  # noqa: FBT001, FBT002
        """Return the alerts as a GeoJSON ``FeatureCollection`` string.

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
        """Return the flat alert DataFrame as CSV.

        List columns are comma-joined and the ``parameters``/``geometry``/``translations`` structures stay
        JSON-encoded, since CSV cannot represent nested data.
        """
        df = timestamps_to_string(self.df.with_columns(pl.col(column).list.join(",") for column in _LIST_COLUMNS))
        return df.write_csv()

    def to_format(self, fmt: str, **kwargs: Any) -> str:  # noqa: ANN401
        """Render the result in the requested format (``json``, ``geojson`` or ``csv``), in any case.

        Like ``to_format`` of the other results, it takes the one set of arguments a caller builds for every format and
        gives each format those it takes: ``with_metadata`` and ``indent`` to JSON and GeoJSON, none to CSV (it has no
        place for the ``metadata`` block).

        Args:
            fmt: the format, in any case
            **kwargs: ``with_metadata`` and ``indent``, as ``to_json`` takes them

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
        """Write the alerts to a file: JSON, GeoJSON or CSV, by the extension of the target.

        A file holds what the REST API answers for the format (``render_alerts``), on one line unless ``pretty``:

        - ``file://alerts.json``: ``{"metadata": ..., "snapshot": ..., "alerts": [...]}``, an alert with its areas,
          parameters, translations and geometry nested as they are in ``to_dict``
        - ``file://alerts.geojson``: the ``FeatureCollection`` of ``to_geojson``, with ``metadata`` as a foreign member
        - ``file://alerts.csv``: the text of ``to_csv``, bare, a row for each alert: its areas are the comma-joined
          ``warncell_ids`` and ``area_names``, its ``parameters``, ``translations`` and ``geometry`` JSON text, its
          times ISO strings

        A snapshot without a warning is written as it is (an empty ``alerts`` list and the block in a JSON file, a CSV
        of the header alone), so a file that a schedule rewrites does not keep the warnings of the run before. The
        ``metadata`` block (provider, licence, credit line and the date of the data) is in a JSON and a GeoJSON file,
        and ``with_metadata`` writes it beside any file as ``<file>.metadata.json``, which is how a CSV file gets it.
        A database target is refused: an alert is nested, and there is no table for it yet.

        Args:
            target: ``file://`` and a path, ending in ``.json``, ``.geojson`` or ``.csv``
            if_exists: ``replace`` (default), ``fail`` or ``skip``; ``append`` is refused for a file
            with_metadata: write ``<file>.metadata.json`` beside the file
            pretty: indent a JSON or GeoJSON file with 4 spaces (a district snapshot is 614 KB on one line, 3.7 MB so)

        Raises:
            ExportRefusedError: a target that is no file of those three types, ``append``, a file that exists under
                ``fail``, or ``with_metadata`` for a database target.

        """
        connspec = ConnectionString(target)
        log.info(f"Exporting {self.df.height} alerts to {redact_password(target)}")
        write_alerts_to_target(self, target, connspec, if_exists, with_metadata=with_metadata, pretty=pretty)


class DwdWeatherAlertRequest:
    """API for DWD CAP weather alerts (warnings).

    Fetches a DWD warning snapshot (all warnings active at a point in time) for a given granularity
    and language and parses it into a :class:`DwdWeatherAlertResult`. By default the latest snapshot
    is used; a ``timestamp`` selects a historical snapshot from DWD's rolling ~48-hour archive instead.

    A snapshot is every warning of Germany (a few hundred KB). ``latitude`` and ``longitude``, and ``name``, keep the
    warnings for one place (:mod:`wetterdienst.provider.dwd.alerts.place`): without them the result is unchanged.
    """

    # how `Wetterdienst.discover()` lists the network, which is no timeseries network and has no metadata model: the
    # name and the country are the provider's, the url is where the warnings are published
    listing: ClassVar = {
        "name_short": _METADATA["name_short"],
        "country": _METADATA["country"],
        "kind": "alerts",
        "url": DWD_ALERTS_BASE_URL,
    }

    # who published the products and under which terms, which an answer about them names as a network with a
    # metadata model does through its `MetadataModel` (GH-3059)
    terms: ClassVar = ProviderTerms(
        name_local=_METADATA["name_local"],
        name_english=_METADATA["name_english"],
        country=_METADATA["country"],
        country_code=_METADATA["country_code"],
        copyright="© Deutscher Wetterdienst (DWD), weather warnings (CAP)",
        license=_METADATA["license"],
        attribution=_METADATA["attribution"],
        url=DWD_ALERTS_BASE_URL,
        # the warnings are issued for the communes and districts of Germany, and for the sea around its coast
        # (declared from the documentation of DWD, no station list to hold it to)
        extent=Extent(scope="national", continents=["europe"], country_codes=["DE"], bbox=[3.0, 47.0, 16.0, 56.0]),
    )

    def __init__(
        self,
        granularity: str | DwdWeatherAlertGranularity = DwdWeatherAlertGranularity.COMMUNITY,
        language: str | DwdWeatherAlertLanguage = DwdWeatherAlertLanguage.ENGLISH,
        timestamp: str | dt.datetime | None = None,
        settings: Settings | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        name: str | None = None,
        **kwargs: Never,
    ) -> None:
        """Initialize the request.

        Args:
            granularity: ``community`` (per Gemeinde, default) or ``district`` (per Landkreis).
            language: one of ``de``, ``en`` (default), ``es``, ``fr``, ``mul``. A ``mul`` alert has the fields of its
                first (German) language and the other seven as ``translations``.
            timestamp: point in time to select the active-warnings snapshot for. ``None`` (default)
                uses the latest snapshot. Otherwise the newest snapshot produced at or before it is
                used; it must fall within DWD's rolling ~48-hour window. A naive datetime or ISO
                string is interpreted as UTC.
            settings: settings for the request.
            latitude: with ``longitude``, keep the warnings whose area polygons contain this point (WGS84 degrees); a
                point on the edge of a polygon is inside. A warning that has no polygon (one for the sea, given by
                its areas alone) is never for a point: ask for it by ``name``.
            longitude: the longitude of the point; it is given with ``latitude``, or not at all.
            name: keep the warnings with an area of this name (the words of it, in any case: ``Kiel`` is ``Stadt
                Kiel``, not ``Kielstau``) or of this warn cell id (``101002000``, or its 8-digit key ``01002000``). With
                a point, a warning must be for both.
            kwargs: none is taken; ``date``, the old name of ``timestamp`` (GH-2438), is refused
                with an error naming it.

        """
        if "date" in kwargs:
            msg = "date was renamed to timestamp"
            raise TypeError(msg)
        if kwargs:
            # in Python's own words
            msg = (
                f"{DwdWeatherAlertRequest.__init__.__qualname__}() got an unexpected keyword argument "
                f"{next(iter(kwargs))!r}"
            )
            raise TypeError(msg)
        self.granularity = self._parse_granularity(granularity)
        self.language = self._parse_language(language)
        self.timestamp = self._parse_timestamp(timestamp)
        self.settings = settings or Settings()
        check_point(latitude, longitude)
        self.latitude = latitude
        self.longitude = longitude
        # an empty name (a query parameter that is present and empty) is no filter, as an empty timestamp is none
        self.name = name.strip() or None if isinstance(name, str) else name

    def __repr__(self) -> str:
        """Return a string representation of the request."""
        return (
            f"DwdWeatherAlertRequest(granularity={self.granularity.value}, "
            f"language={self.language.value}, "
            f"timestamp={self.timestamp.isoformat() if self.timestamp else None}, "
            f"latitude={self.latitude}, longitude={self.longitude}, name={self.name!r})"
        )

    @property
    def _has_place(self) -> bool:
        """Tell whether the request names a place (a point, a name, or both), `False` for the whole snapshot."""
        return self.latitude is not None or self.name is not None

    def _none_for_place(self, others: int) -> str:
        """Say that no warning is for the place, in the words of what was asked: a point, a name, or both.

        A point that no polygon contains is that nothing in force covers it. A name that matches no area is not: the
        names are DWD's German ones, so `Munich` matches none while `München` does, and a place without a warning is not
        listed, so the message does not say that nothing is in force. `others` is the number of warnings of the
        snapshot, none of them for the place.
        """
        held = f"{others} are for other places" if others else "it holds none"
        point = f"the point {self.latitude}, {self.longitude}"
        names = (
            "the names are DWD's German ones ('München', not 'Munich') and a place without a warning is in none, "
            "so check the spelling, or ask by point"
        )
        if self.name is None:
            return (
                f"No warning of the snapshot has an area that contains {point} ({held}). That is the answer, not an "
                "error: nothing in force covers it."
            )
        if self.latitude is None:
            return f"No warning in force lists an area named {self.name!r} ({held}): {names}."
        return (
            f"No warning of the snapshot has an area that contains {point} and is named {self.name!r} ({held}). "
            f"Either nothing in force covers the point, or the name matches no area: {names}."
        )

    @staticmethod
    def _parse_granularity(granularity: str | DwdWeatherAlertGranularity) -> DwdWeatherAlertGranularity:
        if isinstance(granularity, DwdWeatherAlertGranularity):
            return granularity
        value = str(granularity).strip().lower()
        mapping = {
            "community": DwdWeatherAlertGranularity.COMMUNITY,
            "communeunion": DwdWeatherAlertGranularity.COMMUNITY,
            "commune": DwdWeatherAlertGranularity.COMMUNITY,
            "gemeinde": DwdWeatherAlertGranularity.COMMUNITY,
            "district": DwdWeatherAlertGranularity.DISTRICT,
            "landkreis": DwdWeatherAlertGranularity.DISTRICT,
        }
        try:
            return mapping[value]
        except KeyError as e:
            msg = f"granularity {granularity!r} not supported, use 'community' or 'district'"
            raise RequestError(msg) from e

    @staticmethod
    def _parse_language(language: str | DwdWeatherAlertLanguage) -> DwdWeatherAlertLanguage:
        if isinstance(language, DwdWeatherAlertLanguage):
            return language
        value = str(language).strip().lower()
        try:
            return DwdWeatherAlertLanguage(value)
        except ValueError as e:
            supported = ", ".join(item.value for item in DwdWeatherAlertLanguage)
            msg = f"language {language!r} not supported, use one of {supported}"
            raise RequestError(msg) from e

    @staticmethod
    def _parse_timestamp(timestamp: str | dt.datetime | None) -> dt.datetime | None:
        if timestamp is None:
            return None
        if isinstance(timestamp, str):
            # An empty/whitespace timestamp (e.g. from an omitted-but-present ``?timestamp=`` query
            # param) means "latest", not an invalid timestamp.
            timestamp = timestamp.strip()
            if not timestamp:
                return None
            try:
                parsed = dt.datetime.fromisoformat(timestamp)
            except ValueError as e:
                raise RequestError(str(e)) from e
        else:
            parsed = timestamp
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
        return parsed.astimezone(ZoneInfo("UTC"))

    @property
    def _directory_url(self) -> str:
        """Return the URL of the snapshot directory for this granularity."""
        return f"{DWD_ALERTS_BASE_URL}/{self.granularity.product}/"

    @property
    def _filename_pattern(self) -> re.Pattern[str]:
        """Return a regex matching this granularity/language's timestamped snapshot filenames."""
        return re.compile(
            rf"Z_CAP_C_EDZW_(\d{{14}})_PVW_STATUS_PREMIUMDWD_{self.granularity.token}_{self.language.suffix}\.zip$",
        )

    @property
    def url(self) -> str:
        """Return the URL of the ``LATEST`` CAP snapshot zip for this granularity and language."""
        filename = f"Z_CAP_C_EDZW_LATEST_PVW_STATUS_PREMIUMDWD_{self.granularity.token}_{self.language.suffix}.zip"
        return f"{self._directory_url}{filename}"

    def _resolve_snapshot(self) -> tuple[str, dt.datetime | None]:
        """Resolve the request to a concrete snapshot ``(url, production_time)``.

        For a dateless request this is the ``LATEST`` alias (production time unknown -> ``None``).
        For a dated request the newest snapshot produced at or before ``timestamp`` is selected from
        the directory listing; the filename timestamps are UTC. Raises ``InvalidTimeIntervalError``
        (a ``ValueError``) if ``timestamp`` falls before DWD's rolling window (no snapshot at or
        before it is available), and ``MetaFileNotFoundError`` (a ``FileNotFoundError`` too) if the
        listing holds no snapshot at all, which is no date's doing.
        """
        if self.timestamp is None:
            return self.url, None

        pattern = self._filename_pattern
        snapshots: list[tuple[dt.datetime, str]] = []
        for entry in list_remote_directory_fsspec(self._directory_url, settings=self.settings):
            match = pattern.search(entry["name"].rsplit("/", 1)[-1])
            if match:
                timestamp = dt.datetime.strptime(match.group(1), "%Y%m%d%H%M%S").replace(tzinfo=ZoneInfo("UTC"))
                snapshots.append((timestamp, entry["name"]))

        if not snapshots:
            msg = f"no weather-alerts snapshot listed at {self._directory_url}"
            raise MetaFileNotFoundError(msg)

        candidates = [(timestamp, name) for timestamp, name in snapshots if timestamp <= self.timestamp]
        if not candidates:
            earliest = min(timestamp for timestamp, _ in snapshots)
            msg = (
                f"no weather-alerts snapshot available at or before {self.timestamp.isoformat()} "
                f"(DWD only keeps a rolling ~48-hour window). earliest available is {earliest.isoformat()}."
            )
            raise InvalidTimeIntervalError(msg)

        timestamp, name = max(candidates)
        url = name if name.startswith("http") else f"{self._directory_url}{name.rsplit('/', 1)[-1]}"
        return url, timestamp

    def query(self) -> DwdWeatherAlertResult:
        """Download and parse the selected DWD warning snapshot (latest by default)."""
        url, snapshot = self._resolve_snapshot()
        # LATEST is a moving alias -> short TTL; a timestamped snapshot is immutable -> cache longer.
        ttl = CacheExpiry.FIVE_MINUTES if snapshot is None else CacheExpiry.TWELVE_HOURS
        log.info(f"acquiring weather alerts from {url}")
        file = download_file(
            url=url,
            cache_dir=self.settings.cache_dir,
            ttl=ttl,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
            use_certifi=self.settings.use_certifi,
        )
        # A download failure (e.g. HTTP 404 from a snapshot that rolled off the window between the
        # directory listing and this download, a timeout) is surfaced as content being an
        # Exception, raised as the `DownloadError` naming the file, its cause underneath. No
        # internet is raised as it is, naming the URL (GH-2640).
        file.raise_if_exception()
        content = file.content
        if isinstance(content, Exception):  # raised above
            raise content
        try:
            alerts = self._parse_archive(content, url)
            sent = [alert["sent"] for alert in alerts if alert.get("sent") is not None]
            snapshot_updated_at = max(sent) if sent else None
            alerts = self._keep_place(alerts)
            df = self._build_dataframe(alerts)
        except zipfile.BadZipFile as e:
            raise DownloadError(url, "the snapshot is not a valid zip archive") from e
        except (ValueError, OverflowError, SyntaxError, EOFError, zlib.error) as e:
            # an alert whose time DWD wrote in a form the parser does not read, or one a datetime
            # cannot hold, an XML that does not parse (lxml's `XMLSyntaxError` is a `SyntaxError`) or
            # an archive member that does not inflate: the feed's, not the request's, whose own date
            # was converted already
            msg = f"weather alerts snapshot from {url} holds what the parser does not expect: {e}"
            raise MetaFileFormatError(msg) from e
        return DwdWeatherAlertResult(
            df=df,
            granularity=self.granularity,
            language=self.language,
            snapshot=snapshot,
            snapshot_updated_at=snapshot_updated_at,
        )

    def _keep_place(self, alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep the warnings for the place asked for; all of them for a request that names none.

        No warning for a place is an answer: it is told by the `no-alerts-for-place` warning of the response, with how
        many warnings the snapshot holds for other places, so that it is not taken for a failure or a filter that
        matched nothing by mistake.
        """
        if not self._has_place:
            return alerts
        kept = [
            alert
            for alert in alerts
            if is_for_place(alert, latitude=self.latitude, longitude=self.longitude, name=self.name)
        ]
        if not kept:
            message = self._none_for_place(len(alerts))
            warn_response(log, NO_ALERTS_FOR_PLACE, message, level=logging.INFO)
        return kept

    @staticmethod
    def _parse_archive(content: BytesIO, url: str) -> list[dict[str, Any]]:
        """Parse every CAP XML file inside the snapshot zip into an alert row.

        An empty archive (~22 bytes) means there are currently no active warnings. An archive that unpacks
        to more than `_MAX_UNPACKED_BYTES` is refused as a `DownloadError` naming ``url``.
        """
        alerts = []
        with zipfile.ZipFile(content) as archive:
            check_zip(archive, url=url, limit=_MAX_UNPACKED_BYTES)
            for name in archive.namelist():
                if not name.lower().endswith(".xml"):
                    continue
                with archive.open(name) as member:
                    alert = parse_cap_alert(read_unpacked(member, url=url, limit=_MAX_UNPACKED_BYTES))
                if alert is not None:
                    alerts.append(alert)
        return alerts

    @staticmethod
    def _build_dataframe(alerts: list[dict[str, Any]]) -> pl.DataFrame:
        """Build the flat alert DataFrame, JSON-encoding the nested (parameters, geometry, translations) fields."""
        if not alerts:
            return pl.DataFrame(schema=_SCHEMA)
        rows = []
        for alert in alerts:
            row = {column: alert.get(column) for column in _SCHEMA}
            for column in _JSON_COLUMNS:
                row[column] = (
                    json.dumps(alert.get(column), ensure_ascii=False) if alert.get(column) is not None else None
                )
            for column in _LIST_COLUMNS:
                row[column] = alert.get(column) or []
            # a message without an `<info>` has no translations either: `[]` on every row, never null
            row["translations"] = json.dumps(alert.get("translations") or [], ensure_ascii=False)
            rows.append(row)
        return pl.DataFrame(rows, schema=_SCHEMA)

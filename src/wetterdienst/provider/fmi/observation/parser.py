# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parsers for FMI's WFS XML responses (station catalogue and simple observations)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl
from lxml.etree import XMLParser, fromstring

if TYPE_CHECKING:
    from lxml.etree import _Element

_EMPTY_STATIONS_SCHEMA = {
    "station_id": pl.String,
    "name": pl.String,
    "state": pl.String,
    "latitude": pl.Float64,
    "longitude": pl.Float64,
    "start_date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "end_date": pl.Datetime(time_unit="us", time_zone="UTC"),
}

_EMPTY_OBSERVATIONS_SCHEMA = {
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "parameter": pl.String,
    "value": pl.Float64,
}

# FMI encodes "no precipitation" / "no snow cover" as the sentinel -1 (rather than 0) for these
# parameter codes; normalise it to 0.0 so aggregations are not corrupted by negative amounts
# (mirroring the KNMI trace-precipitation handling).
_NO_VALUE_SENTINEL_PARAMETERS = ("r_1h", "rrday", "snow_aws", "snow")

# Disable entity resolution and network access -- FMI is first-party, but there is no reason to
# fetch external entities/DTDs and it guards against XXE (matching the DWD mosmix KML reader).
_XML_PARSER = XMLParser(resolve_entities=False, no_network=True)


def _local_name(tag: object) -> str:
    """Return an element's local name, stripping lxml's ``{namespace}`` prefix.

    lxml yields non-element nodes (comments, processing instructions) with a callable ``tag``
    during iteration; those are reported as an empty local name so callers skip them.
    """
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _parse_operational_period(facility: _Element) -> tuple[str | None, str | None]:
    """Return the ``(begin, end)`` of a facility's operational-activity period.

    Only the first begin/endPosition pair is honoured so a stray later time period cannot
    overwrite it. An ``endPosition`` carrying an ``indeterminatePosition`` attribute (``"now"``)
    marks a still-active station and leaves ``end`` null.
    """
    start = end = None
    start_seen = end_seen = False
    for el in facility.iter():
        tag = _local_name(el.tag)
        if tag == "beginPosition" and not start_seen:
            start_seen = True
            start = (el.text or "").strip() or None
        elif tag == "endPosition" and not end_seen:
            end_seen = True
            if el.get("indeterminatePosition") is None:
                end = (el.text or "").strip() or None
    return start, end


def _parse_facility(facility: _Element) -> dict[str, str | None] | None:
    """Extract one station row from a single ``EnvironmentalMonitoringFacility`` element.

    Returns ``None`` for a facility without a resolvable fmisid.
    """
    station_id = name = region = latitude = longitude = None
    for el in facility.iter():
        tag = _local_name(el.tag)
        code_space = el.get("codeSpace", "")
        text = (el.text or "").strip()
        if tag == "identifier" and code_space.endswith("/fmisid"):
            station_id = text or None
        elif tag == "name" and code_space.endswith("/locationcode/name") and name is None:
            name = text or None
        elif tag == "name" and code_space.endswith("/location/region") and region is None:
            region = text or None
        elif tag == "pos" and latitude is None:
            parts = text.split()
            if len(parts) >= 2:
                latitude, longitude = parts[0], parts[1]
    if not station_id:
        return None
    start, end = _parse_operational_period(facility)
    return {
        "station_id": station_id,
        "name": name,
        "state": region,
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start,
        "end_date": end,
    }


def parse_fmi_stations(content: bytes) -> pl.DataFrame:
    """Parse FMI's ``fmi::ef::stations`` INSPIRE EF catalogue into a station DataFrame.

    Each ``EnvironmentalMonitoringFacility`` carries its FMI station id (fmisid) as a
    ``gml:identifier`` in the ``.../stationcode/fmisid`` code space, human-readable name and
    region as ``gml:name`` entries in the ``.../locationcode/name`` and ``.../location/region``
    code spaces, its position as a ``gml:pos`` (``lat lon``), and its operational period as a
    ``gml:beginPosition``/``gml:endPosition`` pair. Elevation is not exposed by this catalogue,
    so ``height`` is left for the request layer to fill with null.
    """
    root = fromstring(content, parser=_XML_PARSER)
    rows = [
        row
        for facility in root.iter()
        if _local_name(facility.tag) == "EnvironmentalMonitoringFacility"
        and (row := _parse_facility(facility)) is not None
    ]
    if not rows:
        return pl.DataFrame(schema=_EMPTY_STATIONS_SCHEMA)
    return pl.DataFrame(rows, infer_schema_length=None).select(
        pl.col("station_id").cast(pl.String),
        pl.col("name").cast(pl.String),
        pl.col("state").cast(pl.String),
        pl.col("latitude").cast(pl.Float64, strict=False),
        pl.col("longitude").cast(pl.Float64, strict=False),
        # cast to String first: when every station is still active (or the field is absent) the
        # column is inferred as Null dtype, which str.to_datetime rejects.
        pl.col("start_date")
        .cast(pl.String)
        .str.to_datetime("%Y-%m-%dT%H:%M:%SZ", time_unit="us")
        .dt.replace_time_zone("UTC"),
        pl.col("end_date")
        .cast(pl.String)
        .str.to_datetime("%Y-%m-%dT%H:%M:%SZ", time_unit="us")
        .dt.replace_time_zone("UTC"),
    )


def extract_exception_text(content: bytes) -> str | None:
    """Return the text of an OWS ``ExceptionReport`` in ``content``, else ``None``.

    FMI returns an ``ows:ExceptionReport`` (with HTTP 200) for server-side errors such as an
    invalid stored query or rate limiting; those otherwise parse as an empty observation frame
    and would be indistinguishable from a station legitimately reporting no data.
    """
    root = fromstring(content, parser=_XML_PARSER)
    if _local_name(root.tag) != "ExceptionReport":
        return None
    texts = [text for el in root.iter() if _local_name(el.tag) == "ExceptionText" and (text := (el.text or "").strip())]
    return "; ".join(texts) or "unknown FMI exception"


def parse_fmi_observations(content: bytes) -> pl.DataFrame:
    """Parse an FMI ``...::simple`` WFS response into a (date, parameter, value) DataFrame.

    The simple stored queries return a flat list of ``BsWfsElement`` features, each holding a
    single ``Time`` / ``ParameterName`` / ``ParameterValue`` triple. Missing readings are
    emitted as ``NaN`` and normalised to null here.
    """
    root = fromstring(content, parser=_XML_PARSER)
    times: list[str] = []
    names: list[str] = []
    values: list[str | None] = []
    for el in root.iter():
        if _local_name(el.tag) != "BsWfsElement":
            continue
        time = name = value = None
        for child in el:
            tag = _local_name(child.tag)
            if tag == "Time":
                time = child.text
            elif tag == "ParameterName":
                name = child.text
            elif tag == "ParameterValue":
                value = child.text
        if time and name:
            times.append(time)
            names.append(name)
            values.append(value)
    if not times:
        return pl.DataFrame(schema=_EMPTY_OBSERVATIONS_SCHEMA)
    value = pl.col("value").cast(pl.Float64, strict=False).fill_nan(None)
    return pl.DataFrame({"date": times, "parameter": names, "value": values}).select(
        pl.col("date").str.to_datetime("%Y-%m-%dT%H:%M:%SZ", time_unit="us").dt.replace_time_zone("UTC"),
        pl.col("parameter").cast(pl.String),
        pl.when(pl.col("parameter").is_in(_NO_VALUE_SENTINEL_PARAMETERS) & (value == -1.0))
        .then(pl.lit(0.0, dtype=pl.Float64))
        .otherwise(value)
        .alias("value"),
    )

# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A stand-in for KNMI's EDR API and for the Open Data files, which hold the same data (GH-3928).

A `World` is the data: the value of each station, parameter and stamp, stamped as the EDR API stamps it (with the end of
the interval, as the time coordinate of a file is). The EDR API is served from it by a local HTTP server, answering as
the real one does (CoverageJSON, a parameter that a station has no sensor for left out, a null for a NaN, a 404 for a
range without data, a 413 beyond 300,000 points, gzip if it is asked for), and the files from it as NetCDF, so that
the two routes can be compared on data that is the same by construction.

`edr_*.json` in `files/` are real answers of the API, read on 2026-11-11 for De Bilt (06260) and Schiphol (06240) at the
10-minute, hourly and daily resolutions and on 2026-11-12 for De Bilt at the monthly and the annual one, cut down to the
variables the provider maps (the `parameters` and `referencing` blocks, which are not read, are left out).
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.knmi.observation import api, edr
from wetterdienst.provider.knmi.observation.grid import advance
from wetterdienst.provider.knmi.observation.metadata import KnmiObservationMetadata

h5netcdf = pytest.importorskip("h5netcdf", reason="h5netcdf not installed")
h5py = pytest.importorskip("h5py", reason="h5py not installed")

UTC = ZoneInfo("UTC")
FILES = Path(__file__).parent / "files"
RESOLUTION_OF_NAME = {
    "10_minutes": Resolution.MINUTE_10,
    "hourly": Resolution.HOURLY,
    "daily": Resolution.DAILY,
    "monthly": Resolution.MONTHLY,
    "annual": Resolution.ANNUAL,
}
#: the parameters the provider maps for each resolution, as KNMI names them
PARAMETERS = {
    resolution: [p.name_original for dataset in KnmiObservationMetadata[name] for p in dataset.parameters]
    for name, resolution in RESOLUTION_OF_NAME.items()
}
EDR_STAMP = "%Y-%m-%dT%H:%M:%SZ"


def wsi(station_id: str) -> str:
    """Give the WIGOS identifier of a station of the Netherlands (the file of the catalogue writes the same)."""
    return f"0-20000-0-{station_id}"


class World:
    """The data of some stations: `cells[station][parameter][edr_stamp]`, a number or None (a NaN of the file)."""

    def __init__(self, resolution: Resolution, cells: dict[str, dict[str, dict[dt.datetime, float | None]]]) -> None:
        """Hold the data of a resolution."""
        self.resolution = resolution
        self.cells = cells

    @classmethod
    def real(cls, name: str) -> World:
        """Read the real answer saved for a resolution (`edr_<name>.json`) as the data of its stations."""
        document = json.loads((FILES / f"edr_{name}.json").read_text())
        cells: dict[str, dict[str, dict[dt.datetime, float | None]]] = {}
        for coverage in document["coverages"]:
            station = coverage["eumetnet:locationId"].rsplit("-", 1)[-1]
            stamps = [
                dt.datetime.strptime(t, EDR_STAMP).replace(tzinfo=UTC)
                for t in coverage["domain"]["axes"]["t"]["values"]
            ]
            cells[station] = {
                parameter: dict(zip(stamps, values["values"], strict=True))
                for parameter, values in coverage["ranges"].items()
            }
        return cls(RESOLUTION_OF_NAME[name], cells)

    @classmethod
    def generated(
        cls,
        resolution: Resolution,
        stations: list[str],
        first: dt.datetime,
        count: int,
        parameters: list[str] | None = None,
    ) -> World:
        """Make up `count` stamps from `first` (an EDR stamp) for stations, with a number for every parameter."""
        names = parameters or PARAMETERS[resolution]
        stamps = [advance(first, resolution, step) for step in range(count)]
        cells = {
            station: {
                name: {
                    stamp: round(((index * 7 + number * 3 + position) % 200) / 4 - 10, 2)
                    for index, stamp in enumerate(stamps)
                }
                for number, name in enumerate(names)
            }
            for position, station in enumerate(stations)
        }
        return cls(resolution, cells)

    def set(self, station: str, parameter: str, stamp: dt.datetime, value: float | None) -> None:
        """Change a value, to a code of the source or to a NaN (None)."""
        self.cells[station][parameter][stamp] = value

    def stamps(self, station: str) -> list[dt.datetime]:
        """Give the stamps a station has, in order."""
        return sorted({stamp for series in self.cells[station].values() for stamp in series})


class EdrStub(ThreadingHTTPServer):
    """The EDR API: what it was asked, and what it answers, from the worlds it is given (by collection)."""

    def __init__(self, worlds: list[World]) -> None:
        """Serve the worlds, one for each resolution, on a local port."""
        super().__init__(("127.0.0.1", 0), _EdrHandler)
        self.worlds = {edr.COLLECTION_BY_RESOLUTION[world.resolution]: world for world in worlds}
        self.requests: list[dict] = []
        #: the statuses to answer the next requests with (None: as the data says), taken in turn
        self.statuses: deque[int | None] = deque()
        self.max_points = edr.MAX_POINTS
        #: a body to answer every request with (200), instead of the data
        self.raw: bytes | None = None
        self.known = {station for world in worlds for station in world.cells}

    def asked(self) -> list[str]:
        """Give the paths of the requests, with their query."""
        return [request["path"] for request in self.requests]


class _EdrHandler(BaseHTTPRequestHandler):
    server: EdrStub

    def do_GET(self) -> None:
        server = self.server
        server.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}})
        forced = server.statuses.popleft() if server.statuses else None
        if server.raw is not None:
            self._send(200, server.raw, "text/html")
            return
        if forced not in (None, 200):
            self._send(forced, json.dumps({"detail": "stub"}).encode(), "application/json")
            return
        parts = urlsplit(self.path)
        pieces = parts.path.split("/")
        query = parse_qs(parts.query)
        world = server.worlds.get(pieces[4]) if len(pieces) > 6 else None
        if world is None:
            self._send(404, b'{"detail":"no collection"}', "application/json")
            return
        wanted = pieces[6].split(",")
        stations = [identifier.rsplit("-", 1)[-1] for identifier in wanted]
        unknown = [identifier for identifier in stations if identifier not in server.known]
        if unknown:
            self._send(400, json.dumps({"detail": f"the stations {unknown} do not exist"}).encode(), "application/json")
            return
        start, end = (
            dt.datetime.strptime(text, EDR_STAMP).replace(tzinfo=UTC) for text in query["datetime"][0].split("/")
        )
        names = query["parameter-name"][0].split(",")
        in_range = {
            station: [stamp for stamp in world.stamps(station) if start <= stamp <= end]
            for station in stations
            if station in world.cells
        }
        times = {stamp for stamps in in_range.values() for stamp in stamps}
        if len(times) * len(names) * len(stations) > server.max_points:
            self._send(413, b'{"detail":"Maximum number of requested data points exceeded"}', "application/json")
            return
        coverages = []
        for station, stamps in in_range.items():
            if not stamps:
                continue
            ranges = {
                name: {
                    "type": "NdArray",
                    "dataType": "float",
                    "axisNames": ["t", "y", "x"],
                    "shape": [len(stamps), 1, 1],
                    "values": [world.cells[station][name].get(stamp) for stamp in stamps],
                }
                for name in names
                if name in world.cells[station]
            }
            axes = {
                "x": {"values": [5.0]},
                "y": {"values": [52.0]},
                "t": {"values": [s.strftime(EDR_STAMP) for s in stamps]},
            }
            coverages.append(
                {
                    "type": "Coverage",
                    "domain": {"type": "Domain", "domainType": "PointSeries", "axes": axes},
                    "ranges": ranges,
                    "eumetnet:locationId": wsi(station),
                }
            )
        if not coverages:
            self._send(404, b'{"detail":"no data"}', "application/json")
            return
        body = json.dumps({"type": "CoverageCollection", "domainType": "PointSeries", "coverages": coverages}).encode()
        self._send(200, body, "application/prs.coverage+json")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.server.requests[-1]["status"] = status
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if "gzip" in self.headers.get("Accept-Encoding", ""):
            body = gzip.compress(body)
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        """Keep the test output free of the access log."""


def netcdf_of(worlds: dict[Resolution, World], resolution: Resolution, stamp: dt.datetime, path: Path) -> bytes:
    """Write the file of the Open Data API for the interval that ends at `stamp`, with every station that has it.

    As the real files: every variable the provider maps is there, a NaN for the station that has no value of it.
    """
    world = worlds[resolution]
    stations = [station for station in world.cells if stamp in world.stamps(station)]
    string = h5py.string_dtype()
    with h5netcdf.File(path, "w") as file:
        file.dimensions = {"station": len(stations), "time": 1}
        keys = file.create_variable("station", ("station",), dtype=string)
        keys[:] = [wsi(station) for station in stations]
        for name in PARAMETERS[resolution]:
            variable = file.create_variable(name, ("station", "time"), dtype="f8")
            variable[:] = [[_cell(world, station, name, stamp)] for station in stations]
    return path.read_bytes()


def _cell(world: World, station: str, name: str, stamp: dt.datetime) -> float:
    value = world.cells[station].get(name, {}).get(stamp)
    return float("nan") if value is None else value


_PREFIXES = {
    "KMDS": Resolution.MINUTE_10,
    "hourly": Resolution.HOURLY,
    "daily": Resolution.DAILY,
    "monthly": Resolution.MONTHLY,
    "annual": Resolution.ANNUAL,
}


def serve_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, worlds: list[World]) -> list[str]:
    """Have the provider read the files of the worlds, and give the names of the files it is asked for."""
    by_resolution = {world.resolution: world for world in worlds}
    asked: list[str] = []

    def fetch(
        _dataset: str, _version: str, filename: str, _settings: object, _expiry: object = None
    ) -> bytes | Exception:
        asked.append(filename)
        resolution = _PREFIXES[filename.split("-", 1)[0].split("_", 1)[0]]
        stamp = api._end_of(filename)  # noqa: SLF001
        world = by_resolution[resolution]
        if not any(stamp in world.stamps(station) for station in world.cells):
            return FileNotFoundError(filename)
        return netcdf_of(by_resolution, resolution, stamp, tmp_path / "file.nc")

    monkeypatch.setattr(api, "_fetch_netcdf", fetch)
    return asked

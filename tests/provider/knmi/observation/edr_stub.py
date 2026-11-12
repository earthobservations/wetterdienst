# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A stand-in for KNMI's EDR API (GH-3928).

A `World` is the data: the value of each station, parameter and stamp, stamped as the EDR API stamps it (with the end of
the interval). The EDR API is served from it by a local HTTP server, answering as the real one does (CoverageJSON, a
parameter that a station has no sensor for left out, a null for a NaN, a 404 for a range without data, a 413 beyond
300,000 points, a 400 for a station it does not know, gzip if it is asked for, a 401 or a 403 for a key it does not
take), with the list of the stations (`catalogue`) and the list of those that were open at a time.

`files/edr_*.json` are real answers of the API, read on 2026-11-11 for De Bilt (06260) and Schiphol (06240) at the
10-minute, hourly and daily resolutions and on 2026-11-12 for De Bilt at the monthly and the annual one, cut down to the
variables the provider maps (the `parameters` and `referencing` blocks, which are not read, are left out).
`files/frozen_*.csv` are the rows that the Open Data files route returned for the same data (with the codes of the files
laid in, `real_world`) before GH-3928 removed it: what an answer of the EDR API must still be made into.
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

from tests.provider.knmi.observation import catalogue
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.knmi.observation import edr
from wetterdienst.provider.knmi.observation.grid import advance
from wetterdienst.provider.knmi.observation.metadata import KnmiObservationMetadata

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
DE_BILT = "06260"
SCHIPHOL = "06240"


def wsi(station_id: str) -> str:
    """Give the WIGOS identifier of a station (of the list where it is there, else of the Netherlands)."""
    return catalogue.LOCATIONS[station_id][0] if station_id in catalogue.LOCATIONS else f"0-20000-0-{station_id}"


def _at(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=UTC)


class World:
    """The data of some stations: `cells[station][parameter][edr_stamp]`, a number or None (a NaN)."""

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


# the real answers, over the stamps (of the provider) that they hold: a day, a month and a year are stamped with their
# first moment, so one earlier than the stamps of the API in the answers
REAL = {
    "10_minutes": (_at(2026, 11, 9, 6, 10), _at(2026, 11, 9, 9, 0)),
    "hourly": (_at(2026, 11, 5, 1), _at(2026, 11, 6, 0)),
    "daily": (_at(2019, 12, 29), _at(2020, 1, 4)),
    "monthly": (_at(2019, 12, 1), _at(2020, 3, 1)),
    "annual": (_at(2017, 1, 1), _at(2020, 1, 1)),
}


def real_world(name: str) -> World:
    """Give the real answer saved for a resolution, with codes of the files laid in that no cell of it holds.

    The codes are those the Open Data files held and the API passes through: a trace of rain and of sunshine, a calm and
    a variable wind, an invisible sky, a NaN. `files/frozen_*.csv` are what the file route made of these.
    """
    world = World.real(name)
    first = world.stamps(next(iter(world.cells)))
    last = first[-1]
    if name == "daily":
        world.set(DE_BILT, "RH", first[1], -1.0)  # a trace of precipitation
        world.set(DE_BILT, "SQ", first[2], -1.0)  # and of sunshine
        world.set(DE_BILT, "NG", first[3], 9.0)  # a sky that is invisible
        world.set(DE_BILT, "TG", last, None)  # a NaN
    if name == "hourly":
        world.set(DE_BILT, "DD", first[1], 0.0)  # a calm
        world.set(DE_BILT, "DD", first[2], 990.0)  # a variable wind
        world.set(DE_BILT, "N", first[3], 9.0)
        world.set(DE_BILT, "RH", first[4], -1.0)
        world.set(DE_BILT, "T", last, None)
    if name == "10_minutes":
        world.set(DE_BILT, "n", first[3], 9.0)
        world.set(DE_BILT, "rh", last, None)
    if name == "monthly":
        world.set(DE_BILT, "DDVEC", first[1], 0.0)
        world.set(DE_BILT, "RH", first[2], -1.0)  # no trace in a sum of days: left as it is
    return world


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
        #: a body to answer every request of data with (200), instead of the data
        self.raw: bytes | None = None
        #: the stations the API knows, and so does not answer 400 for
        self.known = set(catalogue.LOCATIONS) | {station for world in worlds for station in world.cells}
        #: the stations of the list, and those that have closed with the time they closed (none, unless a test says so:
        #: `catalogue.ENDS` are the real ones), which `/locations?datetime=` leaves out of a window after it
        self.listed = list(catalogue.LOCATIONS)
        self.closed: dict[str, dt.datetime] = {}
        #: a status to answer every request for data with, whatever it asks (a 400 for a parameter that is not one)
        self.always: int | None = None
        #: bodies to answer the next requests for a list of stations with (200), instead of the list
        self.locations_bodies: deque[bytes] = deque()
        #: the key it takes, any if None: a missing one is a 401, another a 403
        self.key: str | None = None

    def asked(self) -> list[str]:
        """Give the paths of the requests, with their query."""
        return [request["path"] for request in self.requests]

    def data_requests(self) -> list[str]:
        """Give the paths of the requests for data, which name stations (`/locations/<ids>`)."""
        return [path for path in self.asked() if "/locations/" in urlsplit(path).path]


class _EdrHandler(BaseHTTPRequestHandler):
    server: EdrStub

    def do_GET(self) -> None:
        server = self.server
        headers = {k.lower(): v for k, v in self.headers.items()}
        server.requests.append({"path": self.path, "headers": headers})
        if server.key is not None and headers.get("authorization") != server.key:
            status = 401 if "authorization" not in headers else 403
            self._send(status, json.dumps({"error": "refused"}).encode(), "application/json")
            return
        forced = server.statuses.popleft() if server.statuses else None
        if forced not in (None, 200):
            self._send(forced, json.dumps({"detail": "stub"}).encode(), "application/json")
            return
        parts = urlsplit(self.path)
        pieces = parts.path.split("/")
        query = parse_qs(parts.query)
        if parts.path.rstrip("/") == "/edr/v1":
            self._send(200, b'{"title":"KNMI Data Platform - EDR API"}', "application/json")
        elif len(pieces) == 6 and pieces[3] == "collections" and pieces[5] == "locations":
            self._locations(query)
        elif len(pieces) > 6 and pieces[5] == "locations":
            self._data(pieces, query)
        else:
            self._send(404, b'{"detail":"no such route"}', "application/json")

    def _locations(self, query: dict) -> None:
        """Answer the list of the stations, those that were open in a window where one is asked for."""
        server = self.server
        ids = server.listed
        if server.locations_bodies:
            self._send(200, server.locations_bodies.popleft(), "text/html")
            return
        if "datetime" in query:
            start, end = (
                dt.datetime.strptime(text, EDR_STAMP).replace(tzinfo=UTC) for text in query["datetime"][0].split("/")
            )
            ids = [station for station in ids if station not in server.closed or server.closed[station] >= start]
            del end
        self._send(200, catalogue.locations_json(ids), "application/geo+json")

    def _data(self, pieces: list[str], query: dict) -> None:
        server = self.server
        if server.always:
            self._send(server.always, json.dumps({"detail": "unknown parameter-name"}).encode(), "application/json")
            return
        world = server.worlds.get(pieces[4])
        if world is None:
            self._send(404, b'{"detail":"no collection"}', "application/json")
            return
        stations = [identifier.rsplit("-", 1)[-1] for identifier in pieces[6].split(",")]
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
        if server.raw is not None:
            self._send(200, server.raw, "text/html")
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

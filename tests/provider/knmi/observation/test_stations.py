# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The stations of KNMI, read from its EDR API (GH-3928, GH-4008).

`GET /collections/{collection}/locations` lists the 77 stations with their name, position, height, type and WIGOS
identifier, and no dates. What keeps a station that has closed out of a listing for a window (GH-4008: Soesterberg,
closed
in 2008, was the second nearest station to De Bilt in a listing for 2026) is read from the API too: the stations that
are
not in the list of those open now, and the last monthly value of each, three requests of the quota in all.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import polars as pl
import pytest

from tests.provider.knmi.observation import catalogue
from tests.provider.knmi.observation.edr_stub import EdrStub, World
from wetterdienst.exceptions import CredentialRejectedError, DownloadError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.knmi.observation import api, edr
from wetterdienst.provider.knmi.observation.api import KnmiObservationRequest
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from pathlib import Path

UTC = dt.UTC
NOW = dt.datetime(2026, 11, 12, 12, 30, tzinfo=UTC)
KEY = "knmi-edr-key-for-test-9f3a"
ALL = list(catalogue.LOCATIONS)
FOG = {"06233"}
#: the stations a resolution cannot have: the fog stations are only in the 10-minute data, block 78 not in the
#: annual, and
#: Soesterberg (closed in 2008) not in the 10-minute data that begins in 2012
NOT_IN = {
    "10_minutes": {"06265"},
    "hourly": FOG,
    "daily": FOG,
    "monthly": FOG,
    "annual": FOG | {"78871", "78990"},
}


@pytest.fixture(autouse=True)
def _pinned_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_now", lambda: NOW)


@pytest.fixture
def closed(edr_server: EdrStub) -> EdrStub:
    """Serve the stations that have closed, as KNMI's list has them: the list of those open now leaves them out."""
    edr_server.closed = dict(catalogue.ENDS)
    monthly = World.generated(Resolution.MONTHLY, ["06265"], dt.datetime(2007, 8, 1, tzinfo=UTC), 12)
    valkenburg = World.generated(Resolution.MONTHLY, ["06210"], dt.datetime(2015, 7, 1, tzinfo=UTC), 11)
    monthly.cells.update(valkenburg.cells)
    edr_server.worlds[edr.COLLECTION_BY_RESOLUTION[Resolution.MONTHLY]] = monthly
    return edr_server


def _request(tmp_path: Path, *resolutions: str, key: str | None = KEY, **kwargs: object) -> KnmiObservationRequest:
    return KnmiObservationRequest(
        parameters=[(resolution, "data") for resolution in resolutions],
        settings=Settings(auth={"knmi_edr": key} if key else {}, cache_dir=tmp_path / "cache"),
        **kwargs,
    )


def _stations(tmp_path: Path, *resolutions: str) -> pl.DataFrame:
    return _request(tmp_path, *resolutions).all().df


def _paths(server: EdrStub) -> list[str]:
    return [
        urlsplit(path).path.rsplit("/", 1)[-1] + ("?" + urlsplit(path).query[:9] if "?" in path else "")
        for path in server.asked()
    ]


@pytest.mark.parametrize("resolution", NOT_IN)
@pytest.mark.usefixtures("closed")
def test_the_stations_of_a_resolution_are_those_of_the_list_that_have_data(tmp_path: Path, resolution: str) -> None:
    """A station is listed for a resolution unless its dataset cannot hold it: fog stations, closed before it began."""
    listed = _stations(tmp_path, resolution).get_column("station_id").to_list()
    assert listed == [station for station in ALL if station not in NOT_IN[resolution]]


@pytest.mark.parametrize("resolution", ["hourly", "daily", "monthly", "annual"])
@pytest.mark.usefixtures("closed")
def test_a_station_that_has_only_history_is_listed(tmp_path: Path, resolution: str) -> None:
    """Valkenburg (closed 2016) and Soesterberg (2008) have history, and no latest data lists them (GH-4008)."""
    assert {"06210", "06265"} <= set(_stations(tmp_path, resolution).get_column("station_id"))


@pytest.mark.usefixtures("closed")
def test_a_station_closed_before_the_10_minute_data_began_is_not_one_of_them(tmp_path: Path) -> None:
    """The 10-minute data starts in 2012: Valkenburg (closed 2016) is in it, Soesterberg (2008) cannot be."""
    listed = set(_stations(tmp_path, "10_minutes").get_column("station_id"))
    assert "06210" in listed
    assert "06265" not in listed


@pytest.mark.usefixtures("closed")
def test_every_station_has_its_wigos_identifier_a_position_and_a_height_with_its_sign(tmp_path: Path) -> None:
    """`wigos_id` is the `id` of the list, `station_id` the WMO number (`wmoId`), the height keeps its sign."""
    df = _stations(tmp_path, "10_minutes")
    rows = {row["station_id"]: row for row in df.iter_rows(named=True)}
    assert rows["06260"]["wigos_id"] == "0-20000-0-06260"
    assert rows["06233"]["wigos_id"] == "0-528-0-06233"
    assert (rows["06260"]["name"], rows["06260"]["latitude"], rows["06260"]["longitude"]) == (
        "De Bilt",
        52.0989,
        5.1797,
    )
    assert rows["06240"]["elevation"] == -3.87
    assert rows["06344"]["elevation"] == -5.14
    assert rows["78990"]["longitude"] == -68.2758
    assert {row["resolution"] for row in rows.values()} == {"10_minutes"}


@pytest.mark.usefixtures("closed")
def test_a_closed_station_ends_with_its_last_monthly_value_and_no_station_has_a_start(tmp_path: Path) -> None:
    """`end_timestamp` is the stamp of the last month with a value of a closed station, null for an open one.

    `start_timestamp` is null: the start of a station in KNMI's catalogue is not the first day of its data (Schiphol's
    station starts in 1990 and its daily values in 1951), and `/locations?datetime=` leaves it out of a window in 1960.
    A closed station without a value (F16-A here) has no end.
    """
    df = _stations(tmp_path, "hourly")
    assert df.get_column("start_timestamp").null_count() == df.height
    ends = dict(df.select("station_id", "end_timestamp").iter_rows())
    assert ends["06265"] == dt.datetime(2008, 7, 1, tzinfo=UTC)
    assert ends["06210"] == dt.datetime(2016, 5, 1, tzinfo=UTC)
    assert ends["06206"] is None
    assert [station for station, end in ends.items() if end is not None] == ["06210", "06265"]
    assert df.schema["end_timestamp"] == pl.Datetime("us", "UTC")


@pytest.mark.usefixtures("closed")
def test_a_listing_for_a_window_in_2026_leaves_out_the_stations_closed_long_before(tmp_path: Path) -> None:
    """The nearest three to De Bilt for January 2026 do not include Soesterberg (closed 2008) or Valkenburg (2016).

    The rank listing is cut to the window as the stations route is (`limit_stations_to_window`, GH-3026): without an
    end a closed station was kept, and was the nearest after De Bilt.
    """
    from wetterdienst.ui.core import limit_stations_to_rank, limit_stations_to_window  # noqa: PLC0415

    request = _request(
        tmp_path, "hourly", start=dt.datetime(2026, 1, 1, tzinfo=UTC), end=dt.datetime(2026, 1, 31, tzinfo=UTC)
    )
    ranked = request.filter_by_rank(latlon=(52.0989, 5.1797), rank=3)
    assert ranked.df.get_column("station_id").to_list()[:2] == ["06260", "06265"]  # nearest, with no window
    cut = limit_stations_to_rank(limit_stations_to_window(ranked)).df.get_column("station_id").to_list()
    assert len(cut) == 3
    assert not {"06265", "06210", "06206"} & set(cut)
    assert cut[0] == "06260"


@pytest.mark.usefixtures("closed")
def test_a_window_a_closed_station_has_data_in_keeps_it_and_one_after_it_leaves_it_out(tmp_path: Path) -> None:
    """Soesterberg's last monthly value is June 2008 (stamped 2008-07-01): it is listed for July 2008, not for 2009."""
    from wetterdienst.ui.core import limit_stations_to_window  # noqa: PLC0415

    def kept(start: dt.datetime, end: dt.datetime) -> list[str]:
        request = _request(tmp_path, "daily", start=start, end=end)
        return limit_stations_to_window(request.all()).df.get_column("station_id").to_list()

    assert "06265" in kept(dt.datetime(2008, 6, 15, tzinfo=UTC), dt.datetime(2008, 7, 10, tzinfo=UTC))
    assert "06265" not in kept(dt.datetime(2009, 1, 1, tzinfo=UTC), dt.datetime(2009, 1, 31, tzinfo=UTC))


@pytest.mark.usefixtures("closed")
def test_a_station_that_starts_after_its_catalogue_does_not_vanish_from_an_old_window(tmp_path: Path) -> None:
    """Schiphol (catalogue 1990, data 1951) is listed for a window in 1960, which `/locations?datetime=` would not."""
    from wetterdienst.ui.core import limit_stations_to_window  # noqa: PLC0415

    request = _request(
        tmp_path, "daily", start=dt.datetime(1960, 1, 1, tzinfo=UTC), end=dt.datetime(1960, 1, 31, tzinfo=UTC)
    )
    assert "06240" in limit_stations_to_window(request.all()).df.get_column("station_id").to_list()


@pytest.mark.usefixtures("closed")
def test_the_fog_type_is_compared_stripped_and_in_lower_case(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A change of the label's case or padding does not bring the fog stations into the validated datasets."""
    frame = catalogue.locations_frame("06233", "06260").with_columns(
        pl.when(pl.col("station_id") == "06233").then(pl.lit(" FOG Station ")).otherwise(pl.col("type")).alias("type")
    )
    monkeypatch.setattr(api, "read_stations", lambda *_args: frame)
    assert _stations(tmp_path, "hourly").get_column("station_id").to_list() == ["06260"]
    assert _stations(tmp_path, "10_minutes").get_column("station_id").to_list() == ["06233", "06260"]


@pytest.mark.usefixtures("closed")
def test_the_caribbean_stations_are_no_stations_of_the_annual_dataset(tmp_path: Path) -> None:
    """The annual collection answers 404 for block 78 (read 2026-11-12), the daily and monthly ones have data."""
    annual = set(_stations(tmp_path, "annual").get_column("station_id"))
    monthly = set(_stations(tmp_path, "monthly").get_column("station_id"))
    assert not {"78871", "78990"} & annual
    assert {"78871", "78990"} <= monthly


def test_the_stations_cost_three_requests_for_every_resolution_and_are_then_kept(
    closed: EdrStub, tmp_path: Path
) -> None:
    """Five resolutions are the list, the list of those open now and the last values of the closed: three requests.

    A second listing is served from the cache (12 hours for the two lists, a week for the dates).
    """
    _stations(tmp_path, "10_minutes", "hourly", "daily", "monthly", "annual")
    assert _paths(closed) == [
        "locations",
        "locations?datetime=",
        "0-20000-0-06206,0-20000-0-06210,0-20000-0-06265?datetime=",
    ]
    assert len(closed.asked()) == 3

    _stations(tmp_path, "hourly")

    assert len(closed.asked()) == 3


def test_with_no_station_closed_the_dates_are_not_asked_for(edr_server: EdrStub, tmp_path: Path) -> None:
    """Two requests where no station has closed (the list, and the list of those open now): no monthly request."""
    df = _stations(tmp_path, "daily")
    assert df.get_column("end_timestamp").null_count() == df.height
    assert _paths(edr_server) == ["locations", "locations?datetime="]


def test_a_list_that_cannot_be_read_is_the_empty_frame_and_is_not_kept(
    caplog: pytest.LogCaptureFixture, edr_server: EdrStub, tmp_path: Path
) -> None:
    """A 200 that is no list of stations is warned about, dropped from the cache and asked for again."""
    edr_server.locations_bodies.append(b"<html>maintenance</html>")
    with caplog.at_level(logging.WARNING):
        first = _stations(tmp_path, "daily")
        second = _stations(tmp_path, "daily")

    assert first.is_empty()
    assert "no list of stations" in caplog.text
    assert second.get_column("station_id").to_list() == [s for s in ALL if s not in FOG]


def test_a_refused_key_is_the_error_that_names_the_edr_key(edr_server: EdrStub, tmp_path: Path) -> None:
    """The list of the stations is the first request of a query: a key the gateway refuses is met there."""
    edr_server.key = "another-key"
    with pytest.raises(CredentialRejectedError, match="WD_AUTH__KNMI_EDR"):
        _stations(tmp_path, "daily")


def test_a_list_that_does_not_answer_is_a_download_error_and_no_empty_list(edr_server: EdrStub, tmp_path: Path) -> None:
    """A 5xx that the retries do not clear is not an answer: an empty list would read as a network with no stations."""
    edr_server.statuses.extend([500, 500, 500])
    with pytest.raises(DownloadError):
        _stations(tmp_path, "daily")

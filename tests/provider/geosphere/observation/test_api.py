# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for geosphere observation API."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from dirty_equals import IsNumeric

from wetterdienst.provider.geosphere.observation import GeosphereObservationRequest


@pytest.mark.remote
def test_geosphere_observation_api() -> None:
    """Test the correct parsing of data, especially the dates.

    Thanks, @mhuber89, for the discovery and fix!
    """
    stations_at = GeosphereObservationRequest(
        parameters=[("hourly", "data", "wind_speed")],
        start_date=datetime(2022, 6, 1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime(2022, 6, 2, tzinfo=ZoneInfo("UTC")),
    )
    station_at = stations_at.filter_by_station_id("4821")
    df = station_at.values.all().df
    assert df.get_column("value").is_not_null().sum() == 25


@pytest.mark.remote
@pytest.mark.parametrize(
    ("resolution", "parameter", "expected_rows", "expected_sum"),
    [
        # cglo, served as irradiance in W / m² and passed through unconverted
        ("minute_10", "radiation_global_intensity", 288, IsNumeric(ge=82770.0, le=82870.0)),
        ("hourly", "radiation_global_intensity", 48, IsNumeric(ge=13790.0, le=13815.0)),
        # cglo_j, a distinct upstream parameter already accumulated over the day in J / cm²
        ("daily", "radiation_global", 2, IsNumeric(ge=4966.2000, le=4972.0000)),
    ],
)
def test_geosphere_observation_api_radiation(
    resolution: str,
    parameter: str,
    expected_rows: int,
    expected_sum: IsNumeric,
) -> None:
    """Test that radiation is reported in the unit the source publishes it in.

    Geosphere serves ``cglo`` as irradiance (W / m²) at 10 minutes and hourly, and ``cglo_j`` as
    irradiation accumulated over the interval (J / cm²) at daily and monthly. The sub-daily values used
    to be multiplied by the interval length in the parser to make them look like the daily ones; they
    now keep their own unit and canonical name instead. The expected sums are equivalent to the former
    J / cm² ones scaled by that interval: 82851 * 0.06 and 13795 * 0.36 both land in the daily range.

    The row count is asserted alongside the sum because the window is a fixed and complete stretch of
    archive, so a sum that drifts because rows went missing should say so rather than read as the unit
    having changed.
    """
    stations_at = GeosphereObservationRequest(
        parameters=[(resolution, "data", parameter)],
        start_date=datetime(2022, 6, 1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime(2022, 6, 2, hour=23, minute=50, tzinfo=ZoneInfo("UTC")),
    )
    station_at = stations_at.filter_by_station_id("4821")
    df = station_at.values.all().df
    assert df.get_column("value").is_not_null().sum() == expected_rows
    # the result is slightly different for each resolution
    assert df.get_column("value").sum() == expected_sum


def test_geosphere_observation_request_window_carries_the_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the start and end sent upstream keep the request's minutes.

    The window was formatted with ``%H:%m``, so the minute position carried the month: a request
    starting 13:37 in December sent ``13:12`` (GH-2436). The values are cut to the requested span
    locally, so this showed only in the URL, and with it the cache key.
    """
    from io import BytesIO  # noqa: PLC0415
    from urllib.parse import parse_qs, urlparse  # noqa: PLC0415

    from wetterdienst.provider.geosphere.observation import api  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    stations = (
        "id,Stationsname,Länge [°E],Breite [°N],Höhe [m],Startdatum,Enddatum,Bundesland,Sonnenschein,Globalstrahlung\n"
        "4821,Test,16.0,48.0,200,1992-05-20 00:00:00+00:00,2100-01-01 00:00:00+00:00,Wien,True,True\n"
    ).encode()
    data_urls = []

    def _download(**kwargs: object) -> File:
        url = str(kwargs["url"])
        if url.endswith("/metadata/stations"):
            return File(url=url, content=BytesIO(stations), status=200)
        data_urls.append(url)
        return File(url=url, content=BytesIO(b'{"timestamps": [], "features": []}'), status=200)

    monkeypatch.setattr(api, "download_file", _download)

    request = GeosphereObservationRequest(
        parameters=[("10_minutes", "data", "humidity_relative")],
        start_date=datetime(2020, 12, 2, 13, 37, tzinfo=ZoneInfo("UTC")),
        end_date=datetime(2020, 12, 3, 8, 45, tzinfo=ZoneInfo("UTC")),
    )
    request.filter_by_station_id("4821").values.all()

    assert len(data_urls) == 1
    query = parse_qs(urlparse(data_urls[0]).query)
    # one day of buffer on either side of the requested window
    assert query["start"] == ["2020-12-01T13:37"]
    assert query["end"] == ["2020-12-04T08:45"]

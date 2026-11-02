# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""CHMI's `QUALITY` is the verdict of the check `source` where it words one (GH-3677).

`metadata/meta4.csv` of the open-data portal (https://opendata.chmi.cz/meteorology/climate/historical_csv/metadata/meta4.csv,
read 2026-11-02) explains the code of the daily, hourly and 10 minute files:

    FLAG2,DESCRIPTION,
    0,Good/Kvalitní hodnota,
    1,Suspect/Podezřelá hodnota,
    2,Poor/Hodnota s nízkou kvalitou, podezřelá, zatím nepoužívat,
    3,Estimated/Odhadnutá hodnota,
    4,Missing/Chybějící hodnota,
    5,Unknown/Kvalita neznámá,

`1` and `2` are the verdicts. The files read the same day (the first three of three directories of each of the daily,
hourly and 10 minute resolutions) hold `0`, `3` and `4` only, so the rows below are written as `meta4.csv` words them,
served through the provider's own reader.
"""

from __future__ import annotations

import datetime as dt

import pytest

from tests.provider.chmi.observation.test_values_frames import CHEB, _serve
from tests.provider.value_stubs import _settings, stations_result
from wetterdienst import Options
from wetterdienst.provider.chmi.observation import ChmiObservationRequest

UTC = dt.UTC

_DAILY = (
    "STATION,ELEMENT,TIMEFUNC,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},T,AVG,2020-01-01T00:00Z,-3.0,,0.0,\n"
    f"{CHEB},T,AVG,2020-01-02T00:00Z,-2.0,,1.0,\n"
    f"{CHEB},T,AVG,2020-01-03T00:00Z,-1.5,,2.0,\n"
    f"{CHEB},T,AVG,2020-01-04T00:00Z,-1.0,,3.0,\n"
    f"{CHEB},T,AVG,2020-01-05T00:00Z,0.5,,5.0,\n"
)
_HOURLY = (
    "STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},Td,2020-01-01T00:00Z,-3.9,,0.0,\n"
    f"{CHEB},Td,2020-01-01T01:00Z,-3.7,,1.0,\n"
    f"{CHEB},Td,2020-01-01T02:00Z,-3.5,,2.0,\n"
    f"{CHEB},Td,2020-01-01T03:00Z,-3.4,,3.0,\n"
)
_TEN_MINUTES = (
    "STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},T,2020-01-01T00:00Z,-2.7,,0.0,\n"
    f"{CHEB},T,2020-01-01T00:10Z,-2.6,,1.0,\n"
    f"{CHEB},T,2020-01-01T00:20Z,-2.5,,2.0,\n"
    f"{CHEB},T,2020-01-01T00:30Z,-2.4,,3.0,\n"
)


@pytest.mark.parametrize(
    ("resolution", "file", "body", "end", "verdicts"),
    [
        ("daily", f"dly-{CHEB}-T.csv", _DAILY, dt.datetime(2020, 1, 5, tzinfo=UTC), {1, 2}),
        ("hourly", f"1h-{CHEB}-Td-202001.csv", _HOURLY, dt.datetime(2020, 1, 1, 3, tzinfo=UTC), {1, 2}),
        ("10_minutes", f"10m-{CHEB}-T-202001.csv", _TEN_MINUTES, dt.datetime(2020, 1, 1, 0, 30, tzinfo=UTC), {1, 2}),
    ],
    ids=["daily", "hourly", "10_minutes"],
)
@pytest.mark.parametrize("mode", ["soft", "hard"])
def test_chmi_suspect_and_poor_are_the_verdict_of_the_check_source(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    file: str,
    body: str,
    end: dt.datetime,
    verdicts: set[int],
    mode: str,
) -> None:
    """Test that `QUALITY` 1 (Suspect) and 2 (Poor) are judged, and 0, 3 (Estimated) and 5 (Unknown) are not.

    Soft flags both. Hard nulls the worse level, 2 (Poor), and still only flags 1 (Suspect), the milder one.
    """
    _serve(monkeypatch, {file: body})
    request = ChmiObservationRequest(
        parameters=[(resolution, "data")],
        start=dt.datetime(2020, 1, 1, tzinfo=UTC),
        end=end,
        settings=_settings(),
        options=Options(drop_nulls=False, plausibility={"source": mode}),
    )
    df = stations_result(request, resolution, "data", CHEB).values().all().df.sort("timestamp")
    flags = df.get_column("quality_flags").to_list()
    values = df.get_column("value").to_list()
    codes = [flag.split(",")[0] for flag in flags]
    assert len(flags) >= 4
    for index, code in enumerate(codes):
        if index in verdicts:
            assert int(code) in {1, 2}
            if mode == "soft" or int(code) == 1:
                assert flags[index] == f"{code},suspect:source"
                assert values[index] is not None
            else:
                assert flags[index].startswith(f"{code},rejected:source,raw:")
                assert values[index] is None
        else:
            assert not any(token in flags[index] for token in ("suspect:source", "rejected:source"))
            assert values[index] is not None

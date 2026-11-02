# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The status digit of MIDAS's `MESQL` is the verdict of the check `source` where it words one (GH-3745).

The CEDA documentation (https://dap.ceda.ac.uk/badc/ukmo-midas/metadata/doc/QC_J_flags.html, read 2026-11-02):
"This _q attribute is a five digit number (of the form MESQL), where each digit describes one aspect of the quality of a
meteorological element", and of the status (S, `qc_status`): "0 Observed and not suspect", "1 Observed and suspect (i.e.
has failed the latest QC check), or there are strong grounds for suspecting the accuracy of the observation", "5 A
correction (a reported value is assumed to be in error)". The files write the integer, so `02176` is `2176`.

The archive needs a CEDA login, which these tests do not use: the rows are written as the documentation words the flag,
served through the provider's own reader, as the stub of `value_stubs.py` does.
"""

from __future__ import annotations

import datetime as dt

import pytest

from tests.provider.value_stubs import _settings, stations_result
from wetterdienst import Options
from wetterdienst.provider.metoffice.observation import MetOfficeObservationRequest
from wetterdienst.provider.metoffice.observation import api as metoffice_api

UTC = dt.UTC

#: the flags of the days of the file below, and whether the status of each is `1`: "100" and "2176" and "20101" have a
#: status of 1; "2576" is a correction (5), "20001" and "1" have no status above 0, and "0" has a level of 0 only
_FLAGS = [("100", True), ("2176", True), ("20101", True), ("2576", False), ("20001", False), ("1", False), ("0", False)]


def _badc(columns: str, rows: str) -> bytes:
    return f"Conventions,G,BADC-CSV,1\ndata\n{columns}\n{rows}end data\n".encode()


@pytest.mark.parametrize("mode", ["soft", "hard"])
def test_metoffice_status_one_is_the_verdict_of_the_check_source_and_no_other_digit_is(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Test that a status (the third digit from the right) of 1 is judged, whatever the other digits are (GH-3745).

    `MESQL` is a compound: the query digit (Q, "Failed climate QC range check", ...) "gives information about the
    original (as reported) value" and the estimate digit (E) tells a correction, so only the status is read. Soft keeps
    the value and flags it; hard nulls it and keeps the number the file wrote.
    """
    stations = _badc(
        "src_id,station_name,station_file_name,historic_county,authority,"
        "station_latitude,station_longitude,station_elevation,first_year,last_year",
        "00001,FOULA,foula,shetland,Met Office,60.154,-2.074,22,1989,2003\n",
    )
    rows = "".join(f"2000-01-0{day} 00:00:00,1,{day}.5,{flag}\n" for day, (flag, _) in enumerate(_FLAGS, start=1))
    values = _badc("ob_date,ob_day_cnt,prcp_amt,prcp_amt_q", rows)

    def download(_self: object, url: str, *_args: object, **_kwargs: object) -> bytes | None:
        if "station-metadata" in url:
            return stations
        return values if "qcv-1" in url else None

    monkeypatch.setattr(metoffice_api.MetOfficeObservationValues, "_token", lambda _self, _settings: "token")
    monkeypatch.setattr(metoffice_api.MetOfficeObservationValues, "_download", download)
    monkeypatch.setattr(metoffice_api, "latest_release_version", lambda *_args, **_kwargs: "202507")
    request = MetOfficeObservationRequest(
        parameters=[("daily", "rain")],
        start=dt.datetime(2000, 1, 1, tzinfo=UTC),
        end=dt.datetime(2000, 1, 7, tzinfo=UTC),
        settings=_settings(),
        options=Options(drop_nulls=False, plausibility={"source": mode}),
    )
    df = stations_result(request, "daily", "rain", "00001").values().all().df.sort("timestamp")
    flags = df.get_column("quality_flags").to_list()
    values_ = df.get_column("value").to_list()
    assert len(flags) == len(_FLAGS)
    for index, (code, judged) in enumerate(_FLAGS):
        if not judged:
            assert flags[index] == code
            assert values_[index] == index + 1.5
        elif mode == "soft":
            assert flags[index] == f"{code},suspect:source"
            assert values_[index] == index + 1.5
        else:
            assert flags[index] == f"{code},rejected:source,raw:{index + 1}.5"
            assert values_[index] is None

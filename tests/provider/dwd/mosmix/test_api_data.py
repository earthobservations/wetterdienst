# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest


@pytest.mark.remote
def test_dwd_mosmix_l(settings_humanize_false_drop_nulls_false):
    """
    Test some details of a typical MOSMIX-L response.
    """
    request = DwdMosmixRequest(
        parameters=[("hourly", "large")],
        settings=settings_humanize_false_drop_nulls_false,
    ).filter_by_station_id(
        station_id=["01001"],
    )
    response = next(request.values.query())

    # Verify list of stations_result.
    station_names = response.stations.df.get_column("name").unique().to_list()
    assert station_names == ["JAN MAYEN"]

    # Verify mosmix data.
    station_ids = response.df.get_column("station_id").unique().to_list()
    assert station_ids == ["01001"]
    assert len(response.df) > 200

    assert response.df_stations.get_column("station_id").to_list() == ["01001"]

    assert len(response.df.columns) == 6
    assert list(response.df.columns) == [
        "station_id",
        "dataset",
        "parameter",
        "date",
        "value",
        "quality",
    ]

    assert set(response.df["parameter"]).issuperset(
        [
            "pppp",
            "e_ppp",
            "tx",
            "ttt",
            "e_ttt",
            "td",
            "e_td",
            "tn",
            "tg",
            "tm",
            "t5cm",
            "dd",
            "e_dd",
            "ff",
            "e_ff",
            "fx1",
            "fx3",
            "fx625",
            "fx640",
            "fx655",
            "fxh",
            "fxh25",
            "fxh40",
            "fxh55",
            "n",
            "neff",
            "nlm",
            "nh",
            "nm",
            "nl",
            "n05",
            "vv",
            "vv10",
            "wwm",
            "wwm6",
            "wwmh",
            "wwmd",
            "ww",
            "ww3",
            "w1w2",
            "wwp",
            "wwp6",
            "wwph",
            "wwpd",
            "wwz",
            "wwz6",
            "wwzh",
            "wwd",
            "wwd6",
            "wwdh",
            "wwc",
            "wwc6",
            "wwch",
            "wwt",
            "wwt6",
            "wwth",
            "wwtd",
            "wws",
            "wws6",
            "wwsh",
            "wwl",
            "wwl6",
            "wwlh",
            "wwf",
            "wwf6",
            "wwfh",
            "drr1",
            "rr6c",
            "rrhc",
            "rrdc",
            "rr1c",
            "rrs1c",
            "rrl1c",
            "rr3c",
            "rrs3c",
            "r101",
            "r102",
            "r103",
            "r105",
            "r107",
            "r110",
            "r120",
            "r130",
            "r150",
            "rr1o1",
            "rr1w1",
            "rr1u1",
            "r600",
            "r602",
            "r610",
            "r650",
            "rh00",
            "rh02",
            "rh10",
            "rh50",
            "rd00",
            "rd02",
            "rd10",
            "rd50",
            "sund",
            "rsund",
            "psd00",
            "psd30",
            "psd60",
            "rrad1",
            "rad1h",
            "sund1",
            "sund3",
            "pevap",
            "wpc11",
            "wpc31",
            "wpc61",
            "wpch1",
            "wpcd1",
        ],
    )


@pytest.mark.remote
@pytest.mark.slow
def test_dwd_mosmix_s(settings_humanize_false_drop_nulls_false):
    """Test some details of a typical MOSMIX-S response."""
    request = DwdMosmixRequest(
        parameters=[("hourly", "small")],
        settings=settings_humanize_false_drop_nulls_false,
    ).filter_by_station_id(
        station_id=["01028"],
    )
    response = next(request.values.query())
    # Verify list of stations_result.
    station_names = response.stations.df.get_column("name").unique().to_list()
    assert station_names == ["BJORNOYA"]
    # Verify mosmix data.
    station_ids = response.df.get_column("station_id").unique().to_list()
    assert station_ids == ["01028"]
    assert len(response.df) > 200
    assert len(response.df.columns) == 6
    assert list(response.df.columns) == [
        "station_id",
        "dataset",
        "parameter",
        "date",
        "value",
        "quality",
    ]
    assert set(response.df["parameter"]).issuperset(
        [
            "pppp",
            "tx",
            "ttt",
            "td",
            "tn",
            "t5cm",
            "dd",
            "ff",
            "fx1",
            "fx3",
            "fxh",
            "fxh25",
            "fxh40",
            "fxh55",
            "n",
            "neff",
            "nh",
            "nm",
            "nl",
            "n05",
            "vv",
            "wwm",
            "wwm6",
            "wwmh",
            "ww",
            "w1w2",
            "rr1c",
            "rrs1c",
            "rr3c",
            "rrs3c",
            "r602",
            "r650",
            "rh00",
            "rh02",
            "rh10",
            "rh50",
            "rd02",
            "rd50",
            "rad1h",
            "sund1",
        ],
    )


@pytest.mark.remote
def test_mosmix_date_filter(settings_drop_nulls_false):
    now = dt.datetime.now(tz=ZoneInfo("UTC"))
    request = DwdMosmixRequest(
        parameters=[("hourly", "small")],
        start_date=now - dt.timedelta(hours=1),
        end_date=now,
        issue=now - dt.timedelta(hours=5),
        settings=settings_drop_nulls_false,
    ).filter_by_rank(latlon=(52.122050, 11.619845), rank=1)
    given_df = request.values.all().df
    assert len(given_df) == 40


@pytest.mark.remote
def test_mosmix_l_parameters(settings_humanize_false_drop_nulls_false):
    """
    Test some details of a MOSMIX-L response when queried for specific parameters.
    """
    request = DwdMosmixRequest(
        parameters=[
            ("hourly", "large", "dd"),
            ("hourly", "large", "ww"),
        ],
        settings=settings_humanize_false_drop_nulls_false,
    ).filter_by_station_id(
        station_id=("01001", "123"),
    )
    response = next(request.values.query())
    # Verify mosmix data.
    station_ids = response.stations.df.get_column("station_id").unique().to_list()
    assert station_ids == ["01001"]
    assert len(response.df) > 200
    assert len(response.df.columns) == 6
    assert list(response.df.columns) == [
        "station_id",
        "dataset",
        "parameter",
        "date",
        "value",
        "quality",
    ]
    assert set(response.df["parameter"]).issuperset(["dd", "ww"])

# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType
from wetterdienst.settings import Settings


@pytest.mark.remote
def test_dwd_mosmix_l():
    """
    Test some details of a typical MOSMIX-L response.
    """
    Settings.tidy = True
    Settings.humanize = False
    Settings.si_units = True

    request = DwdMosmixRequest(parameter="large", mosmix_type=DwdMosmixType.LARGE).filter_by_station_id(
        station_id=["01001"],
    )
    response = next(request.values.query())

    # Verify list of stations_result.
    station_names = response.stations.df["name"].unique().tolist()
    assert station_names == ["JAN MAYEN"]

    # Verify mosmix data.
    station_ids = response.df["station_id"].unique().tolist()
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
        ]
    )


@pytest.mark.remote
@pytest.mark.slow
def test_dwd_mosmix_s():
    """Test some details of a typical MOSMIX-S response."""
    Settings.tidy = True
    Settings.humanize = False
    Settings.si_units = True

    request = DwdMosmixRequest(parameter="small", mosmix_type=DwdMosmixType.SMALL,).filter_by_station_id(
        station_id=["01028"],
    )
    response = next(request.values.query())

    # Verify list of stations_result.
    station_names = list(response.stations.df["name"].unique())
    assert station_names == ["BJORNOYA"]

    # Verify mosmix data.
    station_ids = response.df["station_id"].unique().tolist()
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
        ]
    )


@pytest.mark.remote
def test_mosmix_l_parameters():
    """
    Test some details of a MOSMIX-L response when queried for specific parameters.
    """
    Settings.tidy = True
    Settings.humanize = False
    Settings.si_units = True

    request = DwdMosmixRequest(mosmix_type=DwdMosmixType.LARGE, parameter=["DD", "ww"],).filter_by_station_id(
        station_id=("01001", "123"),
    )
    response = next(request.values.query())

    # Verify mosmix data.
    station_ids = response.stations.df["station_id"].unique().tolist()
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

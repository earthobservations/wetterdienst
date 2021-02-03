# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst.dwd.forecasts import DWDMosmixData, DWDMosmixType


@pytest.mark.remote
def test_dwd_mosmix_l():
    """
    Test some details of a typical MOSMIX-L response.
    """

    mosmix = DWDMosmixData(
        station_ids=["01001"],
        mosmix_type=DWDMosmixType.LARGE,
    )
    response = next(mosmix.query())

    # Verify metadata.
    assert response.metadata.loc[0, "ISSUER"] == "Deutscher Wetterdienst"
    assert response.metadata.loc[0, "PRODUCT_ID"] == "MOSMIX"

    # Verify list of stations.
    station_names = response.metadata["STATION_NAME"].unique().tolist()
    assert station_names == ["JAN MAYEN"]

    # Verify forecast data.
    station_ids = response.data["STATION_ID"].unique().tolist()
    assert station_ids == ["01001"]
    assert len(response.data) > 200

    assert len(response.data.columns) == 4
    assert list(response.data.columns) == ["STATION_ID", "DATE", "PARAMETER", "VALUE"]

    assert set(response.data["PARAMETER"]).issuperset(
        [
            "PPPP",
            "E_PPP",
            "TX",
            "TTT",
            "E_TTT",
            "Td",
            "E_Td",
            "TN",
            "TG",
            "TM",
            "T5cm",
            "DD",
            "E_DD",
            "FF",
            "E_FF",
            "FX1",
            "FX3",
            "FX625",
            "FX640",
            "FX655",
            "FXh",
            "FXh25",
            "FXh40",
            "FXh55",
            "N",
            "Neff",
            "Nlm",
            "Nh",
            "Nm",
            "Nl",
            "N05",
            "VV",
            "VV10",
            "wwM",
            "wwM6",
            "wwMh",
            "wwMd",
            "ww",
            "ww3",
            "W1W2",
            "wwP",
            "wwP6",
            "wwPh",
            "wwPd",
            "wwZ",
            "wwZ6",
            "wwZh",
            "wwD",
            "wwD6",
            "wwDh",
            "wwC",
            "wwC6",
            "wwCh",
            "wwT",
            "wwT6",
            "wwTh",
            "wwTd",
            "wwS",
            "wwS6",
            "wwSh",
            "wwL",
            "wwL6",
            "wwLh",
            "wwF",
            "wwF6",
            "wwFh",
            "DRR1",
            "RR6c",
            "RRhc",
            "RRdc",
            "RR1c",
            "RRS1c",
            "RRL1c",
            "RR3c",
            "RRS3c",
            "R101",
            "R102",
            "R103",
            "R105",
            "R107",
            "R110",
            "R120",
            "R130",
            "R150",
            "RR1o1",
            "RR1w1",
            "RR1u1",
            "R600",
            "R602",
            "R610",
            "R650",
            "Rh00",
            "Rh02",
            "Rh10",
            "Rh50",
            "Rd00",
            "Rd02",
            "Rd10",
            "Rd50",
            "SunD",
            "RSunD",
            "PSd00",
            "PSd30",
            "PSd60",
            "RRad1",
            "Rad1h",
            "SunD1",
            "SunD3",
            "PEvap",
            "WPc11",
            "WPc31",
            "WPc61",
            "WPch1",
            "WPcd1",
        ]
    )


@pytest.mark.remote
@pytest.mark.slow
def test_dwd_mosmix_s():
    """
    Test some details of a typical MOSMIX-S response.
    """

    mosmix = DWDMosmixData(
        station_ids=["01028"],
        mosmix_type=DWDMosmixType.SMALL,
    )
    response = next(mosmix.query())

    # Verify metadata.
    assert response.metadata.loc[0, "ISSUER"] == "Deutscher Wetterdienst"
    assert response.metadata.loc[0, "PRODUCT_ID"] == "MOSMIX"

    # Verify list of stations.
    station_names = list(response.metadata["STATION_NAME"].unique())
    assert station_names == ["BJORNOYA"]

    # Verify forecast data.
    station_ids = response.data["STATION_ID"].unique().tolist()
    assert station_ids == ["01028"]
    assert len(response.data) > 200

    assert len(response.data.columns) == 4
    assert list(response.data.columns) == ["STATION_ID", "DATE", "PARAMETER", "VALUE"]

    assert set(response.data["PARAMETER"]).issuperset(
        [
            "PPPP",
            "TX",
            "TTT",
            "Td",
            "TN",
            "T5cm",
            "DD",
            "FF",
            "FX1",
            "FX3",
            "FXh",
            "FXh25",
            "FXh40",
            "FXh55",
            "N",
            "Neff",
            "Nh",
            "Nm",
            "Nl",
            "N05",
            "VV",
            "wwM",
            "wwM6",
            "wwMh",
            "ww",
            "W1W2",
            "RR1c",
            "RRS1c",
            "RR3c",
            "RRS3c",
            "R602",
            "R650",
            "Rh00",
            "Rh02",
            "Rh10",
            "Rh50",
            "Rd02",
            "Rd50",
            "Rad1h",
            "SunD1",
        ]
    )


@pytest.mark.remote
def test_mosmix_l_parameters():
    """
    Test some details of a MOSMIX-L response when queried for specific parameters.
    """

    mosmix = DWDMosmixData(
        station_ids=["01001"],
        mosmix_type=DWDMosmixType.LARGE,
        parameters=["DD", "ww"],
    )
    response = next(mosmix.query())

    # Verify forecast data.
    station_ids = response.metadata["STATION_ID"].unique().tolist()
    assert station_ids == ["01001"]
    assert len(response.data) > 200

    assert len(response.data.columns) == 4
    assert list(response.data.columns) == [
        "STATION_ID",
        "DATE",
        "PARAMETER",
        "VALUE",
    ]
    assert set(response.data["PARAMETER"]).issuperset(["DD", "ww"])

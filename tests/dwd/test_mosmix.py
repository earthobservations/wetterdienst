import pytest
from wetterdienst.dwd.mosmix.api import MOSMIXRequest


@pytest.mark.remote
def test_mosmix_l():
    """
    Test some details of a typical MOSMIX-L response.
    """

    mosmix = MOSMIXRequest(station_ids=["01001", "01008"])
    response = mosmix.read_mosmix_l_latest()

    # Verify metadata.
    assert response.metadata.loc[0].issuer == "Deutscher Wetterdienst"
    assert response.metadata.loc[0].product_id == "MOSMIX"

    # Verify list of stations.
    station_names = list(response.stations["station_name"].unique())
    assert station_names == ["JAN MAYEN", "SVALBARD"]

    # Verify forecast data.
    station_ids = list(response.forecasts["station_id"].unique())
    assert station_ids == ["01001", "01008"]
    assert len(response.forecasts) > 200

    assert len(response.forecasts.columns) == 116
    assert list(response.forecasts.columns) == [
        "station_id",
        "datetime",
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


@pytest.mark.remote
@pytest.mark.slow
def test_mosmix_s():
    """
    Test some details of a typical MOSMIX-S response.
    """

    mosmix = MOSMIXRequest(station_ids=["01028", "01092"])
    response = mosmix.read_mosmix_s_latest()

    # Verify metadata.
    assert response.metadata.loc[0].issuer == "Deutscher Wetterdienst"
    assert response.metadata.loc[0].product_id == "MOSMIX"

    # Verify list of stations.
    station_names = list(response.stations["station_name"].unique())
    assert station_names == ["BJORNOYA", "MAKKAUR FYR"]

    # Verify forecast data.
    station_ids = list(response.forecasts["station_id"].unique())
    assert station_ids == ["01028", "01092"]
    assert len(response.forecasts) > 200

    assert len(response.forecasts.columns) == 42
    assert list(response.forecasts.columns) == [
        "station_id",
        "datetime",
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


@pytest.mark.remote
def test_mosmix_l_parameters():
    """
    Test some details of a MOSMIX-L response when queried for specific parameters.
    """

    mosmix = MOSMIXRequest(station_ids=["01001", "01008"], parameters=["DD", "ww"])
    response = mosmix.read_mosmix_l_latest()

    # Verify forecast data.
    station_ids = list(response.forecasts["station_id"].unique())
    assert station_ids == ["01001", "01008"]
    assert len(response.forecasts) > 200

    assert len(response.forecasts.columns) == 4
    assert list(response.forecasts.columns) == ["station_id", "datetime", "DD", "ww"]


def test_mosmix_get_url_latest_fails():
    mosmix = MOSMIXRequest()
    with pytest.raises(KeyError) as ex:
        mosmix.get_url_latest("http://example.net")

    assert "Unable to find LATEST file within http://example.net" in str(ex.value)

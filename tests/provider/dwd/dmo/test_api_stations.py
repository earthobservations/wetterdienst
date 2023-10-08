import polars as pl
import pytest

from wetterdienst.provider.dwd.dmo import DwdDmoRequest


@pytest.mark.remote
def test_dwd_dmo_stations(default_settings):
    # Acquire data.
    stations = DwdDmoRequest(parameter="icon", dmo_type="icon", settings=default_settings)
    given_df = stations.all().df
    assert not given_df.is_empty()
    assert given_df.select(pl.all().max()).to_dicts()[0] == {
        "from_date": None,
        "height": 4670.0,
        "icao_id": "ZYTX",
        "latitude": 79.59,
        "longitude": 179.2,
        "name": "ZWOENITZ",
        "state": None,
        "station_id": "Z949",
        "to_date": None,
    }
    assert given_df.select(pl.all().min()).to_dicts()[0] == {
        "from_date": None,
        "height": -350.0,
        "icao_id": "AFDU",
        "latitude": -78.27,
        "longitude": -176.1,
        "name": "16N55W",
        "state": None,
        "station_id": "01001",
        "to_date": None,
    }
    station_names_sorted = given_df.sort(pl.col("name").str.n_chars()).get_column("name").to_list()
    assert station_names_sorted[:5] == ["ELM", "PAU", "SAL", "AUE", "HOF"]
    assert station_names_sorted[-5:] == [
        "MÜNSINGEN-APFELSTETT",
        "VILLINGEN-SCHWENNING",
        "WEINGARTEN BEI RAVEN",
        "LONDON WEATHER CENT.",
        "QUITO/MARISCAL SUCRE",
    ]

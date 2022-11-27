import datetime as dt

from wetterdienst.provider.noaa.ghcn import NoaaGhcnParameter, NoaaGhcnRequest


def test_api_amsterdam():
    request = NoaaGhcnRequest(
        parameter=[NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_MEAN_200],
        start_date=dt.datetime(2015, 1, 1),
        end_date=dt.datetime(2022, 1, 1),
    ).filter_by_name("DE BILT")
    values = request.values.all()
    assert not values.df.value.dropna().empty

import pytest

from wetterdienst import Settings
from wetterdienst.exceptions import NoParametersFound
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationRequest,
    DwdObservationResolution,
)


def test_api_skip_empty_stations():
    start_date = "2021-01-01"
    end_date = "2021-12-31"

    with Settings:
        Settings.skip_empty = True

        stations = DwdObservationRequest(
            parameter=[
                DwdObservationDataset.TEMPERATURE_AIR,
                DwdObservationDataset.PRECIPITATION,
            ],
            resolution=DwdObservationResolution.MINUTE_10,
            start_date=start_date,
            end_date=end_date,
        ).filter_by_rank(49.19780976647141, 8.135207205143768, 20)

    values = next(stations.values.query())

    assert (
        values.df.station_id.iloc[0] != stations.df.station_id.iloc[0]
    )  # not supposed to be the first station of the list
    assert values.df.station_id.iloc[0] == "05426"


def test_api_dropna():
    start_date = "2021-01-01"
    end_date = "2021-12-31"

    with Settings:
        Settings.dropna = True

        stations = DwdObservationRequest(
            parameter=[
                DwdObservationDataset.TEMPERATURE_AIR,
                DwdObservationDataset.PRECIPITATION,
            ],
            resolution=DwdObservationResolution.MINUTE_10,
            start_date=start_date,
            end_date=end_date,
        ).filter_by_rank(49.19780976647141, 8.135207205143768, 20)

    values = next(stations.values.query())

    assert values.df.shape[0] == 51971


def test_api_no_valid_parameters():
    with pytest.raises(NoParametersFound):
        DwdObservationRequest(
            parameter=[
                DwdObservationDataset.TEMPERATURE_AIR,
            ],
            resolution=DwdObservationResolution.DAILY,
        )


def test_api_partly_valid_parameters(caplog):
    request = DwdObservationRequest(
        parameter=[
            DwdObservationDataset.TEMPERATURE_AIR,
            DwdObservationDataset.WIND,
            DwdObservationDataset.PRECIPITATION,
            DwdObservationDataset.SOLAR,
        ],
        resolution=DwdObservationResolution.DAILY,
    )

    assert "dataset WIND is not a valid dataset for resolution DAILY" in caplog.text
    assert "dataset PRECIPITATION is not a valid dataset for resolution DAILY" in caplog.text

    assert request.parameter == [
        (
            DwdObservationDataset.SOLAR,
            DwdObservationDataset.SOLAR,
        )
    ]

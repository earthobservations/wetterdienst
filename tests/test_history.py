"""Test history access for different services in wetterdienst."""

import pytest

from wetterdienst.model.metadata import DatasetModel
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata
from wetterdienst.provider.wsv.pegel.api import WsvPegelRequest


def test_history_not_implemented_for_other_services() -> None:
    """History is provided for DWD observation only; other services should raise NotImplementedError.

    This test ensures that attempting to access history for non-DWD observation services raises
    the appropriate error.
    """
    # use a valid parameter spec for WSV to avoid parameter parsing errors
    req = WsvPegelRequest(parameters=[("dynamic", "data", "stage")])
    with pytest.raises(NotImplementedError):
        _ = req.filter_by_station_id("01234").history


def test_history_dwd_observation_single_station() -> None:
    """Basic smoke test that DwdObservationRequest.history can be created for a single station.

    This test does not attempt to download remote files; we only ensure the API path works and
    that a NotImplementedError is not raised for DWD observation.
    """
    req = DwdObservationRequest(parameters=[("daily", "climate_summary")])
    # filter by a single station that likely exists in metaindex reading tests use '01048'
    stations = req.filter_by_station_id("01048")
    # Accessing history should return a TimeseriesHistory instance
    history = stations.history
    assert history is not None


@pytest.mark.parametrize("dataset", [dataset for resolution in DwdObservationMetadata for dataset in resolution])
def test_history_dwd_observation_all_datasets(dataset: DatasetModel) -> None:
    """Test that DwdObservationRequest.history can be created for all datasets.

    This test iterates over all datasets defined in DwdObservationMetadata and ensures that
    accessing the history attribute does not raise a NotImplementedError.
    """
    request = DwdObservationRequest(parameters=[dataset]).all()
    history = next(request.history.query())
    assert history.history is not None

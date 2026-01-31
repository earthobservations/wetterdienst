"""Tests for HistoryRequest model validation in wetterdienst UI."""

import pytest
from pydantic import ValidationError

from wetterdienst.ui.core import HistoryRequest


def test_history_request_accepts_multiple_stations_string() -> None:
    """Test that HistoryRequest accepts multiple stations as a comma-separated string."""
    m = HistoryRequest.model_validate(
        {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "station": "01048,00011"}
    )
    assert isinstance(m.station, list)
    assert m.station == ["01048", "00011"]


def test_history_request_accepts_station_list() -> None:
    """Test that HistoryRequest accepts multiple stations as a list."""
    m = HistoryRequest.model_validate(
        {"provider": "dwd", "network": "observation", "parameters": ["daily/kl"], "station": ["01048", "00011"]}
    )
    assert m.station == ["01048", "00011"]


def test_history_request_all_true_allowed() -> None:
    """Test that HistoryRequest accepts 'all' parameter set to True."""
    m = HistoryRequest.model_validate(
        {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "all": True}
    )
    assert m.all is True
    assert m.station is None


def test_history_request_all_and_station_rejected() -> None:
    """Test that HistoryRequest rejects when both 'all' and 'station' are provided."""
    with pytest.raises(ValidationError):
        HistoryRequest.model_validate(
            {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "all": True, "station": "01048"}
        )


def test_history_request_forbids_selection_params_with_all() -> None:
    """Test that HistoryRequest rejects when 'all' is True and selection parameters are provided."""
    with pytest.raises(ValidationError):
        HistoryRequest.model_validate(
            {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "all": True, "name": "foo"}
        )

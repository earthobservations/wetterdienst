# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A provider that needs a credential and has none says so with a type of its own (GH-2638)."""

import datetime as dt

import pytest

from wetterdienst.exceptions import CredentialMissingError
from wetterdienst.provider.aemet.observation.api import AemetObservationRequest
from wetterdienst.provider.knmi.observation.api import KnmiObservationRequest
from wetterdienst.provider.metno.frost.api import MetnoFrostRequest
from wetterdienst.settings import Settings

UTC = dt.UTC


@pytest.mark.parametrize(
    ("request_class", "parameters", "auth", "setting"),
    [
        (KnmiObservationRequest, [("daily", "data", "temperature_air_mean_2m")], "knmi", "WD_AUTH__KNMI"),
        (AemetObservationRequest, [("daily", "data", "temperature_air_mean_2m")], "aemet", "WD_AUTH__AEMET"),
        (MetnoFrostRequest, [("hourly", "data", "temperature_air_2m")], "metno_frost", "WD_AUTH__METNO_FROST"),
    ],
)
def test_a_request_without_its_credential_raises_credential_missing_error(
    request_class: type,
    parameters: list[tuple[str, ...]],
    auth: str,
    setting: str,
) -> None:
    """Python callers get the type, still a `ValueError`, and the message that names the setting."""
    with pytest.raises(CredentialMissingError, match=setting) as excinfo:
        request_class(
            parameters=parameters,
            start=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end=dt.datetime(2020, 1, 2, tzinfo=UTC),
            settings=Settings(auth={auth: None}),
        )
    assert isinstance(excinfo.value, ValueError)

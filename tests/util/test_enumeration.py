import pytest

from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.provider.dwd.observation import DwdObservationDataset
from wetterdienst.util.enumeration import parse_enumeration_from_template


def test_parse_enumeration_from_template():
    assert (
        parse_enumeration_from_template("climate_summary", DwdObservationDataset)
        == DwdObservationDataset.CLIMATE_SUMMARY
    )
    assert (
        parse_enumeration_from_template("CLIMATE_SUMMARY", DwdObservationDataset)
        == DwdObservationDataset.CLIMATE_SUMMARY
    )
    assert parse_enumeration_from_template("kl", DwdObservationDataset) == DwdObservationDataset.CLIMATE_SUMMARY

    with pytest.raises(InvalidEnumerationError):
        parse_enumeration_from_template("climate", DwdObservationDataset)

"""Tests for the names renamed on the way to 1.0."""

from wetterdienst.metadata.parameter_table import PARAMETER_TABLE
from wetterdienst.metadata.renamed import RENAMED_PARAMETERS


def test_renamed_parameters_point_from_a_retired_name_to_a_canonical_one() -> None:
    """Every rename leads from a name the table no longer has to one it does.

    An old name back in the table would be answered by the table rather than by the rename, and a
    new name missing from it would send the caller to a parameter that does not exist.
    """
    names = {parameter.name for parameter in PARAMETER_TABLE}
    assert sorted(old for old in RENAMED_PARAMETERS if old in names) == []
    assert sorted(new for new in RENAMED_PARAMETERS.values() if new not in names) == []

# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for what is said when an optional dependency is missing."""

import builtins

import pytest
from click.testing import CliRunner

from wetterdienst.util.extras import extras_installing, missing_dependency_message


@pytest.mark.parametrize(
    ("module_name", "expected"),
    [
        ("utm", ["interpolation"]),
        ("plotly", ["plotting"]),
        ("fastapi", ["restapi"]),
        ("h5py", ["knmi", "radar"]),
        # a core dependency belongs to no extra, and neither does something that is not ours at all
        ("polars", []),
        ("not-a-package-of-ours", []),
    ],
)
def test_extras_are_read_out_of_the_installed_metadata(module_name: str, expected: list[str]) -> None:
    """Which extra installs what is read from the metadata, not from a list kept in the code."""
    assert extras_installing(module_name) == expected


def test_the_message_names_the_extra_the_caller_belongs_to() -> None:
    """Where several extras install a package, the caller's own is the one worth naming.

    `h5py` comes with both `knmi` and `radar`, and telling someone reading radar files to install
    the KNMI extra is true and no help.
    """
    message = missing_dependency_message("Reading radar HDF5", "h5py", extra="radar")

    assert message == (
        "Reading radar HDF5 requires h5py, which is not installed. Install it with: pip install wetterdienst[radar]"
    )


def test_an_extra_the_metadata_does_not_know_is_not_repeated_back() -> None:
    """A hint that no longer matches the metadata falls back to what is there, not to a wrong name."""
    message = missing_dependency_message("Something", "h5py", extra="renamed-since")

    assert "wetterdienst[renamed-since]" not in message
    assert "wetterdienst[knmi] or pip install wetterdienst[radar]" in message


def test_a_package_of_no_extra_gets_no_install_line() -> None:
    """Nothing is suggested for a package that no extra installs."""
    assert missing_dependency_message("Module wetterdienst.provider.x", "polars") == (
        "Module wetterdienst.provider.x requires polars, which is not installed."
    )


def test_a_dependency_with_no_name_still_says_something() -> None:
    """An ImportError that carries no module name still gets a sentence rather than a blank."""
    assert missing_dependency_message("Interpolation", None) == (
        "Interpolation is missing a dependency that is not installed."
    )


@pytest.fixture
def without(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    """Make an import of the named module fail the way a missing package does."""

    def _without(module_name: str, missing: str) -> None:
        real_import = builtins.__import__

        def _fake(name: str, *args: object, **kwargs: object) -> object:
            if name == module_name:
                msg = f"No module named {missing!r}"
                raise ModuleNotFoundError(msg, name=missing)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _fake)

    return _without


def test_the_restapi_command_names_its_extra(without) -> None:  # noqa: ANN001
    """`wetterdienst restapi` without the extra says which extra, not just which module."""
    from wetterdienst.ui.cli import cli  # noqa: PLC0415

    without("wetterdienst.ui.restapi", "fastapi")

    result = CliRunner().invoke(cli, ["restapi"])

    assert isinstance(result.exception, ImportError)
    assert str(result.exception) == (
        "The REST API requires fastapi, which is not installed. Install it with: pip install wetterdienst[restapi]"
    )


def test_interpolation_names_its_extra(without) -> None:  # noqa: ANN001
    """`.interpolate()` without the extra says which extra, not just which module."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    without("wetterdienst.core.interpolate", "utm")
    request = DwdObservationRequest(parameters=[("daily", "kl")], periods="recent")

    with pytest.raises(ImportError, match=r"pip install wetterdienst\[interpolation\]"):
        request.interpolate(latlon=(50.0, 8.0))


def test_reading_radar_hdf5_names_its_extra(without) -> None:  # noqa: ANN001
    """The HDF5 dump without the extra says which extra, not just which module."""
    from wetterdienst.provider.dwd.radar.cli import hdf5dump  # noqa: PLC0415

    without("h5py", "h5py")

    with pytest.raises(ImportError, match=r"pip install wetterdienst\[radar\]"):
        hdf5dump("some-file.h5")

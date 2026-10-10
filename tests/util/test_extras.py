# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for what is said when an optional dependency is missing."""

import builtins
import importlib
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from wetterdienst.exceptions import BufrReaderMissingError, MissingDependencyError
from wetterdienst.util.extras import extras_installing, import_optional, missing_dependency_message


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
        real_import_module = importlib.import_module

        def _fake(name: str, *args: object, **kwargs: object) -> object:
            if name == module_name:
                msg = f"No module named {missing!r}"
                raise ModuleNotFoundError(msg, name=missing)
            return real_import(name, *args, **kwargs)

        def _fake_import_module(name: str, *args: object, **kwargs: object) -> object:
            # `import_optional` imports through `importlib`, which does not go through `__import__`
            if name == module_name:
                msg = f"No module named {missing!r}"
                raise ModuleNotFoundError(msg, name=missing)
            return real_import_module(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _fake)
        monkeypatch.setattr(importlib, "import_module", _fake_import_module)

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


def test_an_optional_import_that_succeeds_returns_the_module() -> None:
    """`import_optional` is the import, when the package is there (GH-2637)."""
    import json  # noqa: PLC0415

    assert import_optional("json", "Anything") is json


def test_an_optional_package_that_is_not_installed_raises_one_class_naming_the_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The absence of a package is a `MissingDependencyError` that names the extra, whichever package (GH-2637).

    Masked in `sys.modules`, which is how a package that is not installed looks to the import system:
    a `ModuleNotFoundError` naming it. It is an `ImportError` still, so callers that caught that
    keep working.
    """
    monkeypatch.setitem(sys.modules, "duckdb", None)

    with pytest.raises(MissingDependencyError) as excinfo:
        import_optional("duckdb", "Filtering with SQL", extra="sql")

    assert str(excinfo.value) == (
        "Filtering with SQL requires duckdb, which is not installed. Install it with: pip install wetterdienst[sql]"
    )
    assert isinstance(excinfo.value, ImportError)
    assert isinstance(excinfo.value.__cause__, ModuleNotFoundError)


def test_a_dependency_of_the_package_that_is_missing_is_named_not_the_package(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A package that is installed and needs one that is not is told by the one that is missing (GH-2637)."""
    (tmp_path / "optional_needing_another.py").write_text("import a_dependency_nobody_installed\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(MissingDependencyError, match="requires a_dependency_nobody_installed, which is not installed"):
        import_optional("optional_needing_another", "Something")


def test_an_import_error_that_is_not_an_absence_keeps_its_traceback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A cycle or a name the installed version lacks is a defect, not an instruction to install (GH-2637)."""
    (tmp_path / "optional_missing_a_name.py").write_text("from json import not_a_name_of_json\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(ImportError, match="cannot import name") as excinfo:
        import_optional("optional_missing_a_name", "Something")

    assert not isinstance(excinfo.value, MissingDependencyError)


def test_a_module_of_wetterdienst_that_is_missing_is_not_a_missing_dependency() -> None:
    """A module of our own that does not exist is a defect, and keeps its `ModuleNotFoundError` (GH-2637)."""
    with pytest.raises(ModuleNotFoundError) as excinfo:
        import_optional("wetterdienst.provider.no_such_provider", "Something")

    assert not isinstance(excinfo.value, MissingDependencyError)


def test_the_bufr_reader_is_one_of_the_missing_dependencies() -> None:
    """The BUFR reader's error is a `MissingDependencyError`, so the UIs handle it with the rest (GH-2637)."""
    assert issubclass(BufrReaderMissingError, MissingDependencyError)
    assert issubclass(MissingDependencyError, ImportError)


def test_a_provider_module_with_an_uninstalled_dependency_is_a_missing_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Wetterdienst.resolve` names the package a provider module cannot import (GH-2637)."""
    from wetterdienst import Wetterdienst  # noqa: PLC0415

    def import_module(_name: str) -> None:
        msg = "No module named 'some_package'"
        raise ModuleNotFoundError(msg, name="some_package")

    monkeypatch.setattr(importlib, "import_module", import_module)

    with pytest.raises(MissingDependencyError, match="requires some_package, which is not installed"):
        Wetterdienst.resolve("dwd", "observation")


def test_a_provider_module_of_ours_that_is_missing_stays_an_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo in a provider's own import is a defect, not an instruction to install anything (GH-2637)."""
    from wetterdienst import Wetterdienst  # noqa: PLC0415

    def import_module(_name: str) -> None:
        msg = "No module named 'wetterdienst.provider.dwd.nowhere'"
        raise ModuleNotFoundError(msg, name="wetterdienst.provider.dwd.nowhere")

    monkeypatch.setattr(importlib, "import_module", import_module)

    with pytest.raises(ImportError, match="nowhere not found") as excinfo:
        Wetterdienst.resolve("dwd", "observation")

    assert not isinstance(excinfo.value, MissingDependencyError)


def test_a_module_missing_inside_an_installed_package_keeps_its_traceback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A broken install is not an instruction to install an extra (GH-2637)."""
    (tmp_path / "optional_broken_inside.py").write_text("import json.no_such_submodule\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(ModuleNotFoundError) as excinfo:
        import_optional("optional_broken_inside", "Something")

    assert not isinstance(excinfo.value, MissingDependencyError)

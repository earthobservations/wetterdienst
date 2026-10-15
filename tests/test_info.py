# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the package information."""

import tomllib
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

import wetterdienst
from wetterdienst import Author, Info

PYPROJECT_FILE = Path(__file__).parent.parent / "pyproject.toml"


def test_info_authors_are_those_of_pyproject() -> None:
    """Test that `Info` names the authors, and the addresses, `[project] authors` names (GH-2954).

    `Info` once held its own copy of them, which named another address for the first author. It
    reads the installed package's metadata now, which an editable install takes from pyproject.toml
    when it was last installed (`uv sync`), so a stale environment fails this rather than the code.
    """
    declared = tomllib.loads(PYPROJECT_FILE.read_text(encoding="utf8"))["project"]["authors"]
    expected = [f"{author['name']} <{author['email']}>" for author in declared]
    assert expected
    info = Info()
    assert [f"{author.name} <{author.email}>" for author in info.authors] == expected
    assert ", ".join(expected) in str(info)


def test_info_authors_keep_the_github_handles() -> None:
    """Test that the handle the REST index links to comes with the author."""
    assert {author.name: author.github_handle for author in Info().authors} == {
        "Benjamin Gutzmann": "gutzbenj",
        "Andreas Motl": "amotl",
    }


def test_info_authors_unknown_without_installed_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a checkout that was never installed has no authors, rather than failing."""

    def not_installed(_: str) -> None:
        raise PackageNotFoundError

    monkeypatch.setattr(wetterdienst, "package_metadata", not_installed)
    info = Info()
    assert info.authors == []
    assert info.to_dict()["authors"] == []
    assert "unknown" in str(info)


def test_info_author_named_only_by_address_or_unknown_to_github(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an author the package names only by address is listed by it, without a handle."""

    class Metadata:
        def get_all(self, name: str) -> list[str]:
            assert name == "Author-email"
            return ["somebody@example.org, Jane Doe <jane@example.org>"]

    monkeypatch.setattr(wetterdienst, "package_metadata", lambda _: Metadata())
    assert Info().authors == [
        Author("somebody@example.org", "somebody@example.org", ""),
        Author("Jane Doe", "jane@example.org", ""),
    ]

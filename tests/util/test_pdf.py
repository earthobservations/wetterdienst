# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the PDF helper."""

import sys

import pytest
from fsspec.exceptions import FSTimeoutError

from wetterdienst.exceptions import DownloadError, MissingDependencyError, NoInternetError
from wetterdienst.util import pdf
from wetterdienst.util.network import File


def test_read_pdf_a_failed_download_names_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a PDF download that timed out raises an error naming the file (GH-2507)."""
    pytest.importorskip("pypdf")
    monkeypatch.setattr(
        pdf,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=FSTimeoutError(), status=408),
    )

    with pytest.raises(
        DownloadError, match=r"Failed to download https://example\.org/a\.pdf: FSTimeoutError"
    ) as caught:
        pdf.read_pdf("https://example.org/a.pdf")
    assert isinstance(caught.value.__cause__, FSTimeoutError)


def test_read_pdf_without_internet_returns_no_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that being offline gives empty text rather than an error."""
    pytest.importorskip("pypdf")
    monkeypatch.setattr(
        pdf,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=NoInternetError("offline"), status=503),
    )

    assert pdf.read_pdf("https://example.org/a.pdf") == ""


def test_read_pdf_without_pypdf_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reading a PDF without pypdf says what to install, before anything is downloaded (GH-2667)."""
    monkeypatch.setitem(sys.modules, "pypdf", None)

    def download_file(**_kwargs: object) -> None:
        pytest.fail("downloaded although the reader is missing")

    monkeypatch.setattr(pdf, "download_file", download_file)

    with pytest.raises(MissingDependencyError) as excinfo:
        pdf.read_pdf("https://example.org/a.pdf")

    assert str(excinfo.value) == (
        "Reading a PDF requires pypdf, which is not installed. Install it with: pip install wetterdienst[pdf]"
    )

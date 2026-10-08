# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the PDF helper."""

import pytest
from fsspec.exceptions import FSTimeoutError

from wetterdienst.exceptions import DownloadError
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

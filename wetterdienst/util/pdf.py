# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Helper functions for PDF files."""

from io import StringIO

import pypdf

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.settings import Settings
from wetterdienst.util.network import download_file


def read_pdf(url: str) -> str:
    """Read text from a PDF file."""
    text = StringIO()
    response = download_file(url, settings=Settings(), ttl=CacheExpiry.NO_CACHE)
    pdf = pypdf.PdfReader(response)
    for page_number in range(len(pdf.pages)):
        page = pdf.pages[page_number]
        result = page.extract_text()
        text.write(result)
    return text.getvalue()

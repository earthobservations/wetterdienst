# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from io import StringIO

import pypdf

from wetterdienst.settings import Settings
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file


def read_pdf(url):
    text = StringIO()
    response = download_file(url, settings=Settings.default(), ttl=CacheExpiry.NO_CACHE)
    pdf = pypdf.PdfReader(response)
    for page_number in range(len(pdf.pages)):
        page = pdf.pages[page_number]
        result = page.extract_text()
        text.write(result)
    return text.getvalue()

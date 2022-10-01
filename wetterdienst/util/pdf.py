# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from io import StringIO

import PyPDF2

from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file


def read_pdf(url):
    text = StringIO()
    response = download_file(url, CacheExpiry.NO_CACHE)
    pdf = PyPDF2.PdfFileReader(response)
    for page_number in range(pdf.numPages):
        page = pdf.getPage(page_number)
        result = page.extractText()
        text.write(result)
    return text.getvalue()

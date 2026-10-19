# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""IMG metadata."""

from wetterdienst.model.metadata import LicenseModel

_METADATA = {
    "name_short": "IMGW",
    "name_english": "Institute of Meteorology and Water Management",
    "name_local": "Instytut Meteorologii i Gospodarki Wodnej",
    "country": "Poland",
    "country_code": "PL",
    "copyright": "© IMGW, Observations",
    # no SPDX licence: the terms are IMGW-PIB's own ("Regulamin udostępniania danych", dane.imgw.pl is catalogued on
    # dane.gov.pl as CC BY-NC-ND 4.0). They make the data free for private use (§ 5 ust. 1) and, for any purpose, only
    # where it is "dane o wysokiej wartości" (high-value data, § 3 ust. 1); use for business needs an agreement with
    # IMGW-PIB (§ 3 ust. 2). IMGW-PIB declares no dataset high-value, so a commercial use is not cleared
    "license": LicenseModel(
        spdx_id=None,
        name="IMGW-PIB terms of data provision (Regulamin udostępniania danych)",
        url="https://danepubliczne.imgw.pl/docs/regulamin_udostepniania_danych.pdf",
    ),
    # the two statements the terms prescribe, as one sentence each: § 5 ust. 3, the source of the data on every work
    # made with it, and § 5 ust. 4, that the data were processed, beside it. The latter is always the case here: the
    # files come back as tidy rows with their own timestamps, quality flags and, where the source leaves a day out of
    # the daily precipitation, a filled one, and the values are converted where the caller asks for other units
    "attribution": (
        "Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy. "  # noqa: RUF001 -- the dash the terms write
        "Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu Badawczego zostały przetworzone."  # noqa: RUF001
    ),
    "url": "https://imgw.pl/",
}

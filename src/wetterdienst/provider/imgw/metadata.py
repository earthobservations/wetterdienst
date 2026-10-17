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
    # no SPDX licence: the terms are IMGW-PIB's own ("Regulamin udostępniania danych"), printed on the portal. They
    # make the data free for private use and, by § 3 and § 5, for any purpose only where they are "dane o wysokiej
    # wartości" (high-value data); other use for business needs an agreement with IMGW-PIB
    "license": LicenseModel(
        spdx_id=None,
        name="IMGW-PIB terms of data provision (Regulamin udostępniania danych)",
        url="https://danepubliczne.imgw.pl/",
    ),
    # § 5 ust. 1 of the terms, which asks for these words on every work made with the data
    "attribution": (
        "Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy"  # noqa: RUF001 -- the dash the terms write
    ),
    "url": "https://imgw.pl/",
}

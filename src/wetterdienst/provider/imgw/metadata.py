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
    # one licence for all of it (maintainer, GH-2567): IMGW-PIB says CC BY-NC-ND 4.0 for all it does not class as
    # high-value (that is CC BY 4.0) but not which the directories read here are, and dane.gov.pl catalogues them as
    # CC BY-NC-ND 4.0 and not high-value. Its own terms ("Regulamin udostępniania danych") apply beside the licence
    "license": LicenseModel(
        spdx_id="CC-BY-NC-ND-4.0",
        name="Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International",
        url="https://creativecommons.org/licenses/by-nc-nd/4.0/",
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

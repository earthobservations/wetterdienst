# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The note every answer carries about what wetterdienst did to the data (GH-2567).

Licences such as CC BY ask that changes to the data be indicated, and the library changes it: it reshapes what a
provider publishes into one table, renames parameters and converts units. This is the one sentence that says so, in
one place, for every provider and every licence. An answer whose values are selected or calculated from readings
(interpolation, summary) says so as well, and so does an image drawn from the provider's values (climate stripes).

The note is plain information and no claim about what a licence asks for: it is not legal advice, and it does not
replace the credit line (`attribution`) of the provider.
"""

from __future__ import annotations

#: what wetterdienst did to the data of every answer that holds provider data. The app holds translated copies of this
#: and of `DERIVED_NOTE` in `app/i18n/locales/*.json` (`processingNote.*`), which change with them;
#: `app/tests/unit/processing-note.test.ts` holds its English text equal to these.
PROCESSING_NOTE = (
    "Processed by wetterdienst: the provider's data was reshaped into a uniform table, and its units converted where "
    "they differ."
)

#: what an answer whose values are selected or calculated from readings says besides (interpolation, summary)
DERIVED_NOTE = "The values were selected or calculated from the provider's readings."

#: what the image of climate stripes says besides: it is drawn, and holds no table
IMAGE_NOTE = "The image is drawn from the provider's annual values."

#: the same for years that were calculated from daily values, which the note has said before it (GH-4222)
IMAGE_OF_CALCULATED_NOTE = "The image is drawn from the annual values calculated above."


#: what the answer of the search for a WMO, WIGOS or ICAO id says besides: the stations are the providers' own, chosen
#: by the id (GH-4075)
STATION_IDS_NOTE = (
    "The stations were selected from the station list each provider publishes, by the id searched for and by the "
    "ids equivalent to it; no station's data was changed."
)


def processing_note(
    *, derived: bool = False, image: bool = False, calculated: str | None = None, image_note: str = IMAGE_NOTE
) -> str:
    """Give the note of an answer: `PROCESSING_NOTE`, then `DERIVED_NOTE` and `IMAGE_NOTE` where they apply.

    `calculated` is the sentence of an answer that holds numbers calculated from the values besides them, which says
    what they are relative to: the climate stripes' anomalies and classes (`StripesReference.note`). `image_note` is
    what the note says of an `image`.
    """
    parts = [PROCESSING_NOTE]
    if derived:
        parts.append(DERIVED_NOTE)
    if calculated:
        parts.append(calculated)
    if image:
        parts.append(image_note)
    return " ".join(parts)

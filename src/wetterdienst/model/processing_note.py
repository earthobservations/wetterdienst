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

#: what wetterdienst did to the data of every answer that holds provider data
PROCESSING_NOTE = (
    "Processed by wetterdienst: the provider's data was reshaped into a uniform table, and its units converted where "
    "they differ."
)

#: what an answer whose values are selected or calculated from readings says besides (interpolation, summary)
DERIVED_NOTE = "The values were selected or calculated from the provider's readings."

#: what the image of climate stripes says besides: it is drawn, and holds no table
IMAGE_NOTE = "The image is drawn from the provider's annual values."


def processing_note(*, derived: bool = False, image: bool = False) -> str:
    """Give the note of an answer: `PROCESSING_NOTE`, then `DERIVED_NOTE` and `IMAGE_NOTE` where they apply."""
    parts = [PROCESSING_NOTE]
    if derived:
        parts.append(DERIVED_NOTE)
    if image:
        parts.append(IMAGE_NOTE)
    return " ".join(parts)

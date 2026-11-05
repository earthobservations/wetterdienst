# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The note every answer carries about what wetterdienst did to the data (GH-2567).

Licences such as CC BY ask that changes to the data be indicated, and the library changes it: it reshapes what a
provider publishes into one table, renames parameters and converts units. This is the one sentence that says so, in
one place, for every provider and every licence. An answer that is calculated rather than read (interpolation,
summary, climate stripes) says so as well.

The note is plain information and no claim about what a licence asks for: it is not legal advice, and it does not
replace the credit line (`attribution`) of the provider.
"""

from __future__ import annotations

#: what wetterdienst did to the data of every answer
PROCESSING_NOTE = (
    "Processed by wetterdienst: the provider's data was reshaped into a uniform table and its units were converted "
    "(unless turned off)."
)

#: what an answer that is calculated from readings says besides
DERIVED_NOTE = (
    "The values are derived: wetterdienst calculated them from the provider's readings, they are not the provider's "
    "own values."
)


def processing_note(*, derived: bool = False) -> str:
    """Give the note of an answer: `PROCESSING_NOTE`, and `DERIVED_NOTE` after it where the values are derived."""
    return f"{PROCESSING_NOTE} {DERIVED_NOTE}" if derived else PROCESSING_NOTE

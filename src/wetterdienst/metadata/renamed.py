"""Names renamed on the way to 1.0, kept so that the old spelling fails by naming the new one.

None of these is accepted in place of its replacement. A caller still writing the old name gets an
error that says what it is called now, instead of the not-found a name that never existed gets.
"""

#: station and values columns, old name to new
RENAMED_COLUMNS: dict[str, str] = {
    "height": "elevation",  # GH-2024
}

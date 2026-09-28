"""Names renamed on the way to 1.0, kept so that the old spelling fails by naming the new one.

None of these is accepted in place of its replacement. A caller still writing the old name gets an
error that says what it is called now, instead of the not-found a name that never existed gets.
"""

from collections.abc import Collection

#: station and values columns, old name to new
RENAMED_COLUMNS: dict[str, str] = {
    "height": "elevation",  # GH-2024
}


def renamed_column(old: str, columns: Collection[str]) -> str | None:
    """Name the column `old` is called now, where the frame holds it under that name.

    Looked up regardless of case, as DuckDB matches identifiers. And only where the frame has the
    new name: a values frame never had `height`, and pointing its caller at an `elevation` it lacks
    as well would send them the wrong way.
    """
    new = RENAMED_COLUMNS.get(old.lower())
    return new if new in columns else None

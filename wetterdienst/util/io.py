# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Input/output utilities for the wetterdienst package."""

from collections.abc import Iterator
from io import BytesIO


def read_in_chunks(file_object: BytesIO, chunk_size: int = 1024) -> Iterator[bytes]:
    """Lazy function (generator) to read a file piece by piece.

    Default chunk size: 1k.

    -- https://stackoverflow.com/questions/519633/lazy-method-for-reading-big-file-in-python/519653#519653
    """
    while True:
        data = file_object.read(chunk_size)
        if not data:
            break
        yield data

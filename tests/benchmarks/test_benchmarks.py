# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest


@pytest.mark.xfail(reason="zlib.error: Error -3 while decompressing data: invalid literal/length/distance code")
def test_benchmarks():
    from benchmarks import (
        interpolation,
        interpolation_over_time,
        interpolation_precipitation_difference,
        summary_over_time,
    )

    assert interpolation.main() is None
    assert interpolation_over_time.main() is None
    assert interpolation_precipitation_difference.main() is None
    assert summary_over_time.main() is None

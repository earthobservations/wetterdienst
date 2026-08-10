# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Unit types, the quantities the unit converter knows how to convert within.

A unit type names a physical quantity -- ``temperature``, ``pressure``, ``speed`` -- and selects
which unit values are returned in, via ``UnitConverter.targets``. Every canonical parameter has
exactly one, so this is the closed vocabulary that ``CanonicalParameter.unit_type`` draws from.

``UnitType`` restates the keys of ``UnitConverter.units``, which are built as a dict literal at
runtime and so cannot be turned into a static type. That makes this a second place the same
vocabulary is written down, which is worth it only because it is pinned:
``tests/test_api.py::test_unit_type_matches_unit_converter`` asserts the two agree exactly, in
both directions. Adding a unit type to one and not the other fails that test rather than drifting.

Being a ``Literal`` it is checked by ``ty``, not at runtime, so a typo in a parameter table entry
is caught by the type checker rather than only by a test.
"""

from __future__ import annotations

from typing import Literal

UnitType = Literal[
    "angle",
    "concentration",
    "conductivity",
    "degree_day",
    "degree_hour",
    "dimensionless",
    "energy_per_area",
    "fraction",
    "length_long",
    "length_medium",
    "length_short",
    "mass_per_volume",
    "power_per_area",
    "precipitation",
    "precipitation_intensity",
    "pressure",
    "significant_weather",
    "speed",
    "temperature",
    "time",
    "turbidity",
    "volume_per_time",
    "wind_scale",
]

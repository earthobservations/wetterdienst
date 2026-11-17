# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The window and the steps of every element of MOSMIX-L and MOSMIX-S (GH-4176).

DWD's element table (``mosmix_elemente_xls.xlsx``, as of 2020-05-25) gives each element's unit, its window ("during the
last 3 hours") and the product that carries it. It says nothing of the steps at which a window ends or of how far into
the run an element goes. The only statement about range is the product's, "MOSMIX_S (24x taeglich, 40 Parameter, bis
+240h), MOSMIX_L (4x taeglich, ca. 115 Parameter, bis +240h)", on
https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html.

What the files give is measured here, on 2026-11-17: MOSMIX_L of the stations 10382 (Berlin-Tegel), 10147 (Hamburg),
P0489 and 10961 (Zugspitze), runs of 09 and 15 UTC of the 16th and 03 UTC of the 17th, and MOSMIX_S of all 5,648
stations, run of 03 UTC of the 17th (``l_range`` and ``s_range`` are those of the run of 03 UTC).

This module is the table of those measurements, free of Sphinx so that ``tests/provider/dwd/mosmix`` can hold it to the
two runs it keeps as stubs (``test_element_cadence.py``) and to the metadata; ``mosmix_elements.py`` renders it as the
table of ``docs/data/provider/dwd/mosmix/elements/index.md``, joined at build time to the provider's metadata, so that the
parameter and the product are read from the model. Nothing generated is committed.
"""

from __future__ import annotations

from typing import NamedTuple

ALL = tuple(range(24))
EVERY_3 = (0, 3, 6, 9, 12, 15, 18, 21)
EVERY_6 = (0, 6, 12, 18)

#: the lead time, in hours, of the last step a run can give: the steps start one hour after the issue
HORIZON = {"L": 247, "S": 240}

#: the hour of the run (UTC) of which the first and the last step of every element are given
RUN_HOUR_UTC = 3


class Cadence(NamedTuple):
    """When the steps of one element fall.

    ``hours`` are the UTC clock hours at which a step ends a window of ``window`` hours (None: the element is the
    state at the step), ``extra`` further hours that some stations give it at. ``l_range`` and ``s_range`` are the first
    and the last step of the run of 03 UTC, in hours after the issue, of MOSMIX-L and of most stations of MOSMIX-S;
    ``s_range`` is None where MOSMIX-S does not carry the element. ``subset`` is an element given at some of its
    ``hours`` only (daylight, some days), so that its ranges are those of the stations measured.
    """

    window: int | None
    hours: tuple[int, ...]
    l_range: tuple[int, int]
    s_range: tuple[int, int] | None
    extra: tuple[int, ...] = ()
    subset: bool = False
    note: str = ""


_ZERO_TAIL = (
    "0.0 from about +100 to +125 h at most German lowland stations (`RR3c`: often, median last non-zero +132 h), "
    "a real zero and no gap: the totals of 12 and 24 h (`RRhc`, `RRdc`) still carry rain, `RR6c` falls to zero early "
    "at some stations"
)
_TX_TN = (
    "06 and 18 UTC at about 70 % of the stations; at the others at one of them, at all four of 00/06/12/18, "
    "or at 00 or 12 UTC (Tokyo)"
)
_RD = "06 UTC; 07 UTC as well at 3 of the 4 MOSMIX-L stations and at 1,976 of 5,648 MOSMIX-S stations"

#: every element of MOSMIX-L (114), under the name DWD writes it; ordered by window, then by name
ELEMENTS: dict[str, Cadence] = {
    "DD": Cadence(None, ALL, (1, 247), (1, 240)),
    "E_DD": Cadence(None, ALL, (1, 247), None),
    "E_FF": Cadence(None, ALL, (1, 247), None),
    "E_PPP": Cadence(None, ALL, (1, 247), None),
    "E_Td": Cadence(None, ALL, (1, 247), None),
    "E_TTT": Cadence(None, ALL, (1, 247), None),
    "FF": Cadence(None, ALL, (1, 247), (1, 240)),
    "N": Cadence(None, ALL, (1, 247), (1, 240)),
    "N05": Cadence(None, ALL, (1, 247), (1, 240)),
    "Neff": Cadence(None, ALL, (1, 247), (1, 240)),
    "Nh": Cadence(None, ALL, (1, 247), (1, 240)),
    "Nl": Cadence(None, ALL, (1, 247), (1, 240)),
    "Nlm": Cadence(None, ALL, (1, 247), None),
    "Nm": Cadence(None, ALL, (1, 247), (1, 240)),
    "PPPP": Cadence(None, ALL, (1, 247), (1, 240)),
    "T5cm": Cadence(None, ALL, (1, 247), (1, 240)),
    "Td": Cadence(None, ALL, (1, 247), (1, 240)),
    "TTT": Cadence(None, ALL, (1, 247), (1, 240)),
    "VV": Cadence(None, ALL, (1, 247), (1, 240)),
    "VV10": Cadence(None, ALL, (1, 247), None),
    "ww": Cadence(None, ALL, (1, 246), (1, 240)),
    "DRR1": Cadence(
        1,
        ALL,
        (1, 247),
        None,
        note="0 for most rainy hours at 10382, not given at 10961 (Zugspitze): `skip_empty` drops that station",
    ),
    "FX1": Cadence(1, ALL, (1, 247), (1, 240)),
    "R101": Cadence(1, ALL, (1, 247), None),
    "R102": Cadence(1, ALL, (1, 247), None),
    "R103": Cadence(1, ALL, (1, 247), None),
    "R105": Cadence(1, ALL, (1, 247), None),
    "R107": Cadence(1, ALL, (1, 247), None),
    "R110": Cadence(1, ALL, (1, 247), None),
    "R120": Cadence(1, ALL, (1, 247), None),
    "R130": Cadence(1, ALL, (1, 247), None),
    "R150": Cadence(1, ALL, (1, 247), None),
    "Rad1h": Cadence(1, ALL, (1, 247), (1, 240)),
    "RR1c": Cadence(1, ALL, (1, 247), (1, 240), note=_ZERO_TAIL),
    "RR1o1": Cadence(1, ALL, (1, 247), None),
    "RR1u1": Cadence(1, ALL, (1, 247), None),
    "RR1w1": Cadence(1, ALL, (1, 247), None),
    "RRad1": Cadence(1, ALL, (4, 247), None, subset=True, note="given in daylight only"),
    "RRL1c": Cadence(1, ALL, (1, 247), None),
    "RRS1c": Cadence(1, ALL, (1, 247), (1, 240)),
    "SunD1": Cadence(1, ALL, (1, 247), (1, 240)),
    "WPc11": Cadence(1, ALL, (1, 246), None),
    "wwC": Cadence(1, ALL, (1, 247), None),
    "wwD": Cadence(1, ALL, (1, 247), None),
    "wwF": Cadence(1, ALL, (1, 247), None),
    "wwL": Cadence(1, ALL, (1, 247), None),
    "wwM": Cadence(1, ALL, (1, 247), (1, 240)),
    "wwP": Cadence(1, ALL, (1, 247), None),
    "wwS": Cadence(1, ALL, (1, 247), None),
    "wwT": Cadence(1, ALL, (1, 247), None),
    "wwZ": Cadence(1, ALL, (1, 247), None),
    "FX3": Cadence(3, ALL, (1, 246), (1, 240)),
    "RR3c": Cadence(3, EVERY_3, (3, 246), (3, 240), note=_ZERO_TAIL),
    "RRS3c": Cadence(3, EVERY_3, (3, 246), (3, 240)),
    "SunD3": Cadence(3, ALL, (1, 246), None),
    "WPc31": Cadence(3, EVERY_3, (3, 246), None),
    "ww3": Cadence(3, EVERY_3, (3, 246), None),
    "FX625": Cadence(6, EVERY_6, (3, 243), None),
    "FX640": Cadence(6, EVERY_6, (3, 243), None),
    "FX655": Cadence(6, EVERY_6, (3, 243), None),
    "R600": Cadence(6, EVERY_6, (3, 243), None),
    "R602": Cadence(6, EVERY_6, (3, 243), (3, 237)),
    "R610": Cadence(6, EVERY_6, (3, 243), None),
    "R650": Cadence(6, EVERY_6, (3, 243), (3, 237)),
    "RR6c": Cadence(6, EVERY_6, (3, 243), None),
    "W1W2": Cadence(6, EVERY_6, (3, 243), (3, 237)),
    "WPc61": Cadence(6, EVERY_3, (3, 246), None),
    "wwC6": Cadence(6, ALL, (1, 246), None),
    "wwD6": Cadence(6, ALL, (1, 246), None),
    "wwF6": Cadence(6, ALL, (1, 246), None),
    "wwL6": Cadence(6, ALL, (1, 246), None),
    "wwM6": Cadence(
        6, ALL, (1, 246), (1, 240), note="MOSMIX-S: hourly at 2,998 of 5,648 stations and every 3 h at 2,148"
    ),
    "wwP6": Cadence(6, ALL, (1, 246), None),
    "wwS6": Cadence(6, ALL, (1, 246), None),
    "wwT6": Cadence(6, ALL, (1, 246), None),
    "wwZ6": Cadence(6, ALL, (1, 246), None),
    "FXh": Cadence(12, (6, 18), (3, 243), (3, 231)),
    "FXh25": Cadence(12, (6, 18), (3, 243), (3, 231)),
    "FXh40": Cadence(12, (6, 18), (3, 243), (3, 231)),
    "FXh55": Cadence(12, (6, 18), (3, 243), (3, 231)),
    "Rh00": Cadence(12, (6, 18), (3, 243), (3, 231)),
    "Rh02": Cadence(12, (6, 18), (3, 243), (3, 231)),
    "Rh10": Cadence(12, (6, 18), (3, 243), (3, 231)),
    "Rh50": Cadence(12, (6, 18), (3, 243), (3, 231)),
    "RRhc": Cadence(12, (6, 18), (3, 243), None),
    "TG": Cadence(12, (6,), (3, 243), None),
    "TN": Cadence(12, (6, 18), (3, 243), (3, 231), extra=(0, 12), note=_TX_TN),
    "TX": Cadence(12, (6, 18), (3, 243), (3, 231), extra=(0, 12), note=_TX_TN),
    "WPch1": Cadence(
        12, EVERY_6, (9, 243), None, note="the first step is +9 h at 03 UTC, though a 06 UTC step comes sooner (+3 h)"
    ),
    "wwCh": Cadence(12, EVERY_6, (3, 243), None),
    "wwDh": Cadence(12, EVERY_6, (3, 243), None),
    "wwFh": Cadence(12, EVERY_6, (3, 243), None),
    "wwLh": Cadence(12, EVERY_6, (3, 243), None),
    "wwMh": Cadence(12, EVERY_6, (3, 243), (3, 237)),
    "wwPh": Cadence(12, EVERY_6, (3, 243), None),
    "wwSh": Cadence(12, EVERY_6, (3, 243), None),
    "wwTh": Cadence(12, EVERY_6, (3, 243), None),
    "wwZh": Cadence(12, EVERY_6, (3, 243), None),
    "PEvap": Cadence(24, (6,), (27, 171), None, subset=True, note="given on some of the days only"),
    "PSd00": Cadence(24, (6,), (3, 243), None),
    "PSd30": Cadence(24, (6,), (3, 243), None),
    "PSd60": Cadence(24, (6,), (3, 243), None),
    "Rd00": Cadence(24, (6,), (3, 244), None, extra=(7,), note=_RD),
    "Rd02": Cadence(24, (6,), (3, 244), (3, 220), extra=(7,), note=_RD),
    "Rd10": Cadence(24, (6,), (3, 244), None, extra=(7,), note=_RD),
    "Rd50": Cadence(24, (6,), (3, 244), (3, 220), extra=(7,), note=_RD),
    "RRdc": Cadence(24, (6,), (3, 243), None),
    "RSunD": Cadence(24, (6,), (3, 243), None),
    "SunD": Cadence(24, (6,), (3, 243), None),
    "TM": Cadence(24, (6,), (3, 243), None, note="DWD does not say which 24 hours; see the parameter"),
    "WPcd1": Cadence(
        24,
        (0, 12),
        (21, 237),
        None,
        note="the first step is 21 to 27 h after the issue, though a 12 UTC step comes sooner",
    ),
    "wwMd": Cadence(24, (0, 12), (9, 237), None),
    "wwPd": Cadence(24, (0, 12), (9, 237), None),
    "wwTd": Cadence(24, (0, 12), (9, 237), None),
}

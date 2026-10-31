# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The plausibility checks of a request and the mode each one runs in (GH-3676).

A reader judges a number it has parsed: a temperature of 4021 degrees, a sensor that held one value for a month, a
road surface 30 K above the air at night. What it does with the verdict is the caller's to choose, per kind of
check:

- ``hard``: the value is null (or, for ``floor``, the floor of its quantity) and the number the source wrote stays in
  ``quality_flags`` as ``rejected:<check>,raw:<number>``;
- ``soft``: the value is kept and ``quality_flags`` says ``suspect:<check>``.

There is no mode that skips a check: a soft check already keeps the value, and the flag keeps the judgement visible.
What a source documents as a code (``-999``, ``---``, a trace, a calm) is no judgement and has no mode: it is decoded
as the source says and written as ``raw:`` alone.

``Plausibility`` is the nested model of ``Options`` that names the mode of every check. The rules of
``model/quality_flags.py`` each declare the check they belong to, and ``null_sentinels`` reads the mode from the
plausibility in effect: the one a ``TimeseriesValues`` has set for the readers it calls (``applying``), or the
defaults for a reader called on its own.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import TYPE_CHECKING, Literal, get_args

import polars as pl
from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from collections.abc import Iterator

Mode = Literal["soft", "hard"]
Check = Literal["range", "elevation", "stuck", "consistency", "floor"]
#: the checks, as the issue lists them; several that apply to one value are written in alphabetical order
#: (``suspect:range+stuck``, ``_WRITE_ORDER`` of ``model/quality_flags.py``)
CHECKS: tuple[str, ...] = get_args(Check)

#: the kinds of token a check writes into ``quality_flags``, before ``raw:``
SUSPECT = "suspect"
REJECTED = "rejected"
#: a regular expression for the token a soft check writes, in a ``quality_flags`` string
SUSPECT_TOKEN = rf"(^|,){SUSPECT}:"
#: and for the one a hard check writes
REJECTED_TOKEN = rf"(^|,){REJECTED}:"

_HARD_MEANS = (
    "`hard` nulls the value and keeps the number the source wrote as `rejected:{check},raw:<number>` in "
    "`quality_flags`; `soft` keeps the value and flags it `suspect:{check}`."
)


class Plausibility(BaseModel):
    """The mode of each plausibility check: ``hard`` (null the value) or ``soft`` (keep it, flagged).

    A check has exactly one mode at a time and none can be switched off, because a soft check already keeps the value
    and the flag keeps the judgement visible. The missing-value codes and documented meanings a source writes
    (``-999``, ``---``, a trace, a calm) are no check and are not configurable.

    The defaults reproduce what the library did before the modes existed, except ``stuck``, which is soft: the verdict
    on a stuck sensor depends on the window the request asked for, so the value stays and is flagged. Set it from
    ``WD_TS_PLAUSIBILITY__<CHECK>`` (``WD_TS_PLAUSIBILITY__RANGE=soft``) or ``Options(plausibility={"range": "soft"})``;
    a check that is not named keeps its default. A bare mode sets every check at once (``Options(plausibility="soft")``,
    ``WD_TS_PLAUSIBILITY=soft``), and a check named beside it wins.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    range: Mode = Field(
        default="hard",
        description="A reading outside the physical range of its parameter (4021 degrees C for a daily mean, "
        "17,802 mm of rain in a month). " + _HARD_MEANS.format(check="range"),
    )
    elevation: Mode = Field(
        default="hard",
        description="A station pressure the barometric formula does not expect at the elevation of the station "
        "(909.5 hPa at a station at 48 m). " + _HARD_MEANS.format(check="elevation"),
    )
    stuck: Mode = Field(
        default="soft",
        description="A sensor that held one value over a period it should not have (a barometer that writes one "
        "pressure for a whole file, a road sensor that did not move for hours): the verdict depends on the window of "
        "the request, which is why it is soft by default. " + _HARD_MEANS.format(check="stuck"),
    )
    consistency: Mode = Field(
        default="hard",
        description="A reading that contradicts the reading of another parameter in the same file (a road surface "
        "30 K above the air at night, a humidity beside a dew point below frost at a station without frost). "
        "The check never downloads the other parameter and stands aside where it is missing. "
        + _HARD_MEANS.format(check="consistency"),
    )
    floor: Mode = Field(
        default="hard",
        description="A model value a little below the floor of its quantity (-0.02 mm of precipitation). `hard` "
        "sets the floor (0.0), not null, and keeps the number as `rejected:floor,raw:<number>`; `soft` keeps the "
        "value and flags it `suspect:floor`.",
    )

    @model_validator(mode="before")
    @classmethod
    def _one_mode_for_every_check(cls, data: object) -> object:
        """Read a bare mode as that mode for every check, which a check named beside it overrides (GH-3676).

        ``Options(plausibility="soft")`` is ``Options(plausibility={"range": "soft", ...})`` with all five listed.
        """
        if isinstance(data, str):
            if data not in get_args(Mode):
                msg = f"a mode for every check is one of {', '.join(get_args(Mode))}, or give the checks as a mapping"
                raise ValueError(msg)
            return dict.fromkeys(CHECKS, data)
        if isinstance(data, dict) and "__all__" in data:
            msg = "`__all__` is no check: give a bare `soft` or `hard` to set every check at once"
            raise ValueError(msg)
        return data

    def mode(self, check: str) -> Mode:
        """Give the mode of a check, refusing a name that is none."""
        if check not in CHECKS:
            msg = f"{check!r} is no plausibility check: {', '.join(CHECKS)}"
            raise ValueError(msg)
        return getattr(self, check)


#: where each check runs: by check, the networks (`provider/network`) and their datasets (`resolution/dataset`). The
#: table of `docs/data/plausibility.md` is this, and `tests/test_docs_plausibility.py` holds the three to one another:
#: the rules the readers declare, this and the page. A network that is in no list judges no value (extending the checks
#: to the networks that have none is a follow-up)
COVERAGE: dict[str, dict[str, tuple[str, ...]]] = {
    "range": {
        "dmi/observation": ("hourly/data", "daily/data", "monthly/data", "annual/data"),
        "dwd/observation": (
            "10_minutes/temperature_air",
            "10_minutes/urban_pressure",
            "10_minutes/urban_wind",
            "10_minutes/urban_wind_extreme",
            "10_minutes/wind",
            "10_minutes/wind_extreme",
            "hourly/moisture",
            "hourly/pressure",
            "hourly/urban_pressure",
            "hourly/urban_wind",
            "hourly/wind",
            "hourly/wind_extreme",
            "hourly/wind_synoptic",
            "subdaily/pressure",
            "subdaily/wind_extreme",
            "daily/climate_summary",
            "monthly/climate_summary",
            "annual/climate_summary",
        ),
        "dwd/road": ("15_minutes/data",),
        "meteofrance/observation": ("hourly/core", "hourly/others", "daily/core", "monthly/data"),
        "meteofrance/synop": ("subdaily/data",),
        "rmi/observation": ("10_minutes/data", "hourly/data", "daily/data"),
    },
    "elevation": {
        "dwd/observation": (
            "10_minutes/temperature_air",
            "10_minutes/urban_pressure",
            "hourly/moisture",
            "hourly/pressure",
            "hourly/urban_pressure",
            "subdaily/pressure",
            "daily/climate_summary",
        ),
        "meteofrance/synop": ("subdaily/data",),
    },
    "stuck": {
        "dwd/observation": ("hourly/moisture",),
        "dwd/road": ("15_minutes/data",),
        "rmi/observation": ("10_minutes/data", "hourly/data", "daily/data"),
    },
    "consistency": {
        "dwd/road": ("15_minutes/data",),
        "meteofrance/observation": ("hourly/others",),
        "meteofrance/synop": ("subdaily/data",),
    },
    "floor": {
        "dwd/dmo": ("hourly/icon", "hourly/icon_eu"),
    },
}

#: what a reader that is called on its own, with no request around it, applies
DEFAULTS = Plausibility()

_ACTIVE: contextvars.ContextVar[Plausibility] = contextvars.ContextVar("wetterdienst_plausibility", default=DEFAULTS)


def active() -> Plausibility:
    """Give the plausibility in effect: the request's while its readers run, else the defaults."""
    return _ACTIVE.get()


@contextlib.contextmanager
def applying(plausibility: Plausibility) -> Iterator[None]:
    """Run the readers called inside with the modes of ``plausibility``, in this context alone."""
    token = _ACTIVE.set(plausibility)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def leave_out_suspect(df: pl.DataFrame) -> pl.DataFrame:
    """Null the value of every reading a soft plausibility check flagged ``suspect:`` (GH-3676).

    An interpolation, a summary, climate stripes and the coverage of ``skip_empty`` read what a station measured, and a
    number that a check finds implausible has no place in them, whatever mode the request gave the check: the mode
    changes what a station's own values show, not what is made of them. The reading stays a row, as a rejected one
    does, with no value.
    """
    if "quality_flags" not in df.columns:
        return df
    suspect = pl.col("quality_flags").str.contains(SUSPECT_TOKEN).fill_null(value=False)
    return df.with_columns(pl.when(suspect).then(None).otherwise(pl.col("value")).alias("value"))

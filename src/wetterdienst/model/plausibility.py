# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The plausibility checks of a request and the mode each one runs in (GH-3676).

The values core judges the numbers a reader has parsed: a temperature of 4021 degrees, a sensor that held one value for
a month, a road surface 30 K above the air at night (``model/judge.py``). What it does with the verdict is the caller's
to choose, per kind of check:

- ``hard``: the value is null (or, for ``floor``, the floor of its quantity) and the number the source wrote stays in
  ``quality_flags`` as ``rejected:<check>,raw:<number>``;
- ``soft``: the value is kept and ``quality_flags`` says ``suspect:<check>``.

There is no mode that skips a check: a soft check already keeps the value, and the flag keeps the judgement visible.
What a source documents as a code (``-999``, ``---``, a trace, a calm) is no judgement and has no mode: it is decoded
as the source says and written as ``raw:`` alone.

``Plausibility`` is the nested model of ``Options`` that names the mode of every check; the core reads it from the
options of the request.
"""

from __future__ import annotations

from typing import Literal, get_args

import polars as pl
from pydantic import BaseModel, ConfigDict, Field, model_validator

Mode = Literal["soft", "hard"]
Check = Literal["range", "elevation", "stuck", "consistency", "floor", "limits"]
#: the checks, as the issue lists them; several that apply to one value are written in alphabetical order
#: (``suspect:range+stuck``, ``_WRITE_ORDER`` of ``model/quality_flags.py``)
CHECKS: tuple[str, ...] = get_args(Check)
#: the checks that run where the caller sets a bound (``Options(limits=...)``, ``model/limits.py``) and not where the
#: library's tables say: they have no row in ``COVERAGE``, since any network can be judged by them (GH-3687)
CALLER_CHECKS: tuple[str, ...] = ("limits",)

#: the checks that correct a value instead of rejecting it, and so run as they are set on a forecast network
CORRECTING_CHECKS: tuple[str, ...] = ("floor",)

#: the kinds of token a check writes into ``quality_flags``, before ``raw:``
SUSPECT = "suspect"
REJECTED = "rejected"
#: a regular expression for the token a soft check writes, in a ``quality_flags`` string
SUSPECT_TOKEN = rf"(^|,){SUSPECT}:"
#: and for the one a hard check writes
REJECTED_TOKEN = rf"(^|,){REJECTED}:"


def hard_means(check: str) -> str:
    """Say what ``hard`` does for a check: null the value (``floor``: set it to 0.0) and keep the number."""
    does = "sets the value to 0.0" if check == "floor" else "nulls the value"
    return f"{does} and keeps the number as `rejected:{check},raw:<number>` in `quality_flags`"


def forecast_note(check: str) -> str:
    """Say what a forecast network does with the mode of a check (``Plausibility.for_forecast``)."""
    if check in CORRECTING_CHECKS:
        return (
            "A forecast network (`kind` `forecast`) keeps the mode as set for this check, and judges the others soft."
        )
    return "A forecast network (`kind` `forecast`) is judged soft whatever the mode (only `floor` keeps its mode)."


_HARD_MEANS = (
    "`hard` nulls the value and keeps the number the source wrote as `rejected:{check},raw:<number>` in "
    "`quality_flags`; `soft` keeps the value and flags it `suspect:{check}`."
)


class Plausibility(BaseModel):
    """The mode of each plausibility check: ``hard`` (null the value) or ``soft`` (keep it, flagged).

    A check has exactly one mode at a time and none can be switched off, because a soft check already keeps the value
    and the flag keeps the judgement visible. The missing-value codes and documented meanings a source writes
    (``-999``, ``---``, a trace, a calm) are no check and are not configurable.

    On a forecast network (the ``kind`` of its metadata) every check is soft but ``floor``, whatever is set here
    (``for_forecast``): a forecast is a model's output and no reading, so a value a check finds is flagged and never
    nulled.

    The defaults are what the library did for the networks it judged before the modes existed (since GH-3681 ``range``
    and ``elevation`` judge every network), except ``stuck``, which is soft: it judges a
    series and not a value (identical readings are a sign of a stuck sensor and no proof), and what it finds depends
    on what was read: the window of the request for ``dwd/road``, the periods and files read for ``dwd/observation``.
    Set it from ``WD_TS_PLAUSIBILITY__<CHECK>`` (``WD_TS_PLAUSIBILITY__RANGE=soft``) or
    ``Options(plausibility={"range": "soft"})``; a check that is not named keeps its default. A bare mode sets every
    check at once (``Options(plausibility="soft")``, ``WD_TS_PLAUSIBILITY=soft``), and a check named beside it wins.

    ``limits`` is the check of the bounds the caller sets per parameter (``Options(limits=...)``, GH-3687). It is hard
    by default, as ``range`` is, and judges nothing where no bound is set.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    range: Mode = Field(
        default="hard",
        description="A reading outside the physical range of its parameter, the same for every provider (4021 "
        "degrees C for a daily mean, 17,802 mm of rain in a month). " + _HARD_MEANS.format(check="range"),
    )
    elevation: Mode = Field(
        default="hard",
        description="A station pressure the standard atmosphere does not allow at the elevation of the station "
        "(1093.3 hPa at a station at 48 m, 968.6 hPa at the Zugspitze). " + _HARD_MEANS.format(check="elevation"),
    )
    stuck: Mode = Field(
        default="soft",
        description="A sensor that held one value over a period it should not have (a station pressure that is one "
        "value for 72 hourly readings in a row, a road sensor that did not move for hours, a dated period of a dead "
        "sensor): the check judges a series and not a value, and what it finds depends on what was read, which is "
        "why it is soft by default. " + _HARD_MEANS.format(check="stuck"),
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
    limits: Mode = Field(
        default="hard",
        description="A reading outside the bounds you set for its parameter (`Options(limits=...)`), beside the "
        "physical range of the check `range`, which they leave as it is. " + _HARD_MEANS.format(check="limits"),
    )

    def for_forecast(self) -> Plausibility:
        """Give the modes a forecast network is judged with: every check soft, whatever mode it was given (GH-3681).

        A forecast is a model's output and not a reading, and what a check finds in it (a rain above any record, a
        pressure the elevation does not allow) is a flag on a value the model wrote, so no check nulls it, however
        ``hard`` is set (the options, the CLI, the REST API, the environment). The one exception is ``floor``, which
        does not reject: it sets a value a little below the floor of its quantity to the floor and keeps the number
        as ``rejected:floor,raw:<number>``, so it keeps the mode it was given.
        """
        return Plausibility(**{check: self.mode(check) if check in CORRECTING_CHECKS else "soft" for check in CHECKS})

    @model_validator(mode="before")
    @classmethod
    def _one_mode_for_every_check(cls, data: object) -> object:
        """Read a bare mode as that mode for every check, which a check named beside it overrides (GH-3676).

        ``Options(plausibility="soft")`` is ``Options(plausibility={"range": "soft", ...})`` with all six listed.
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


#: where each check runs: by check, the networks (`provider/network`) and their datasets (`resolution/dataset`), or `*`
#: for every dataset of the network that has a parameter the check judges. The table of `docs/data/plausibility.md` is
#: this, and `tests/test_docs_plausibility.py` holds the three to one another: the rules the readers declare, this and
#: the page. `range` and `elevation` run on every network that has a quantity of their tables (GH-3681): the bounds
#: are the same for every provider (`model/plausibility_ranges.py`). `limits` is in none (`CALLER_CHECKS`): it runs
#: on any network, for the parameters the caller sets a bound for. A network that is in no list judges no value
#: by the tables of the library
COVERAGE: dict[str, dict[str, tuple[str, ...]]] = {
    "range": {
        "aemet/observation": ("*",),
        "chmi/observation": ("*",),
        "dmi/observation": ("*",),
        "dwd/derived": ("*",),
        "dwd/dmo": ("*",),
        "dwd/mosmix": ("*",),
        "dwd/observation": ("*",),
        "dwd/phenology": ("*",),
        "dwd/poi": ("*",),
        "dwd/road": ("*",),
        "dwd/swsmos": ("*",),
        "eccc/observation": ("*",),
        "fmi/observation": ("*",),
        "geosphere/observation": ("*",),
        "imgw/hydrology": ("*",),
        "imgw/meteorology": ("*",),
        "ipma/observation": ("*",),
        "knmi/observation": ("*",),
        "lhmt/observation": ("*",),
        "meteofrance/observation": ("*",),
        "meteofrance/synop": ("*",),
        "meteoswiss/observation": ("*",),
        "metno/frost": ("*",),
        "metoffice/observation": ("*",),
        "noaa/ghcn": ("*",),
        "nws/observation": ("*",),
        "rmi/observation": ("*",),
        "smhi/observation": ("*",),
        "wsv/pegel": ("*",),
    },
    "elevation": {
        "aemet/observation": ("*",),
        "chmi/observation": ("*",),
        "dwd/observation": ("*",),
        "eccc/observation": ("*",),
        "geosphere/observation": ("*",),
        "imgw/meteorology": ("*",),
        "knmi/observation": ("*",),
        "meteofrance/observation": ("*",),
        "meteofrance/synop": ("*",),
        "meteoswiss/observation": ("*",),
        "metno/frost": ("*",),
        "metoffice/observation": ("*",),
        "noaa/ghcn": ("*",),
        "rmi/observation": ("*",),
    },
    "stuck": {
        "dwd/observation": (
            "10_minutes/temperature_air",
            "10_minutes/urban_pressure",
            "hourly/moisture",
            "hourly/pressure",
            "hourly/urban_pressure",
            "daily/climate_summary",
        ),
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

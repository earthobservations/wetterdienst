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

from wetterdienst.model.source_flags import source_coverage

Mode = Literal["soft", "hard"]
Check = Literal["range", "elevation", "stuck", "consistency", "floor", "limits", "source", "step", "relations"]
#: the checks, as the issue lists them; several that apply to one value are written in alphabetical order
#: (``suspect:range+stuck``, ``_WRITE_ORDER`` of ``model/quality_flags.py``)
CHECKS: tuple[str, ...] = get_args(Check)
#: the checks that run where the caller sets a bound (``Options(limits=...)``, ``model/limits.py``) and not where the
#: library's tables say: they have no row in ``COVERAGE``, since any network can be judged by them (GH-3687)
CALLER_CHECKS: tuple[str, ...] = ("limits",)

#: the checks whose mode is soft by default: ``stuck`` and ``step`` judge a series and not a value, ``source``
#: repeats a verdict the source has given and returned the value with (GH-3677), and ``relations`` holds two readings
#: to each other without telling which of the two is wrong, so it flags both (GH-3681); every other check is hard
SOFT_BY_DEFAULT: tuple[str, ...] = ("stuck", "source", "step", "relations")


def default_mode(check: str) -> Mode:
    """Give the mode a check has where nothing sets it: ``soft`` for ``SOFT_BY_DEFAULT``, ``hard`` for the rest."""
    return "soft" if check in SOFT_BY_DEFAULT else "hard"


#: the checks that correct a value instead of rejecting it, and so run as they are set on a forecast network
CORRECTING_CHECKS: tuple[str, ...] = ("floor",)

#: the checks that run as they are set on a forecast network: those that correct a value, and the bounds the caller
#: wrote (``limits``, which a forecast follows as any other network: the caller asked for the values outside to go,
#: GH-3687)
FORECAST_KEEPS_MODE: tuple[str, ...] = (*CORRECTING_CHECKS, *CALLER_CHECKS)

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
    text = f"{does} and keeps the number as `rejected:{check},raw:<number>` in `quality_flags`"
    if check == "source":
        text += (
            " (the suspect level of a source that has two, GHCNh `Suspect` and source 382 `R`, CHMI `Suspect`, "
            "MADIS `Questioned`, GHCNh `f`, stays flagged `suspect:source`)"
        )
    return text


def forecast_note(check: str) -> str:
    """Say what a forecast network does with the mode of a check (``Plausibility.for_forecast``)."""
    if check in FORECAST_KEEPS_MODE:
        return (
            "A forecast network (`kind` `forecast`) keeps the mode as set for `floor` and `limits`, and judges the "
            "other checks soft."
        )
    return (
        "A forecast network (`kind` `forecast`) is judged soft whatever the mode "
        "(only `floor` and `limits` keep their mode)."
    )


_HARD_MEANS = (
    "`hard` nulls the value and keeps the number the source wrote as `rejected:{check},raw:<number>` in "
    "`quality_flags`; `soft` keeps the value and flags it `suspect:{check}`."
)


class Plausibility(BaseModel):
    """The mode of each plausibility check: ``hard`` (null the value) or ``soft`` (keep it, flagged).

    A check has exactly one mode at a time and none can be switched off, because a soft check already keeps the value
    and the flag keeps the judgement visible. The missing-value codes and documented meanings a source writes
    (``-999``, ``---``, a trace, a calm) are no check and are not configurable.

    On a forecast network (the ``kind`` of its metadata) every check is soft but ``floor`` and ``limits``, whatever is
    set here (``for_forecast``): a forecast is a model's output and no reading, so a value a built-in check finds is
    flagged and never nulled.

    The defaults are what the library did for the networks it judged before the modes existed (since GH-3681
    ``range`` and ``elevation`` judge every network), except ``stuck``, ``step``, ``source`` and ``relations``,
    which are soft. ``stuck`` judges a series and not a value (identical readings are a sign of a stuck sensor and
    no proof), and what it finds depends on what was read: the window of the request where the provider asks its
    source for the window only (``dwd/road``, FMI, DMI), the periods and files read where it reads whole files
    (``dwd/observation``). ``step`` judges a series as well: a change between two consecutive readings beyond what
    the weather does, or a reading that jumps away and back (``model/rate_of_change.py``); real weather has fronts,
    and the check is a judgement with false positives. Set it from ``WD_TS_PLAUSIBILITY__<CHECK>``
    (``WD_TS_PLAUSIBILITY__RANGE=soft``) or ``Options(plausibility={"range": "soft"})``; a check that is not named
    keeps its default. A bare mode sets every check at once (``Options(plausibility="soft")``,
    ``WD_TS_PLAUSIBILITY=soft``), and a check named beside it wins.

    ``relations`` holds the readings of one row to each other (a maximum below the mean, a dew point above the air
    temperature, a gust below the mean wind, a day of sunshine longer than the day, ``model/relations.py``). It is soft
    by default and flags **both** readings of a broken pair, since nothing says which one is wrong. It is not
    ``consistency``, which is the hard check of the rules a provider hands the core for its own source (a road surface
    far above the air at night): ``consistency`` rejects, ``relations`` only flags.

    ``limits`` is the check of the bounds the caller sets per parameter (``Options(limits=...)``, GH-3687). It is hard
    by default, as ``range`` is, and judges nothing where no bound is set.

    ``source`` is the check of the source's own verdict: a value the source returns and marks, in its own quality flag,
    as erroneous or doubtful (``model/source_flags.py``, GH-3677). It is soft by default, so that the value stays and
    the flag says what the source said, and judges nothing for a network whose source marks no value so.
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
        description="A sensor that held one value over a period it should not have (an hourly air temperature "
        "that is one value for 24 readings in a row, a station pressure for 72, a daily rain of one value above "
        "5 mm for 5 days, a road sensor that did not move for hours, a dated period of a dead sensor): the limits "
        "are those of published quality controls, per parameter and resolution. The check judges a series and not "
        "a value, and what it finds depends on what was read, which is why it is soft by default. "
        + _HARD_MEANS.format(check="stuck"),
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
    source: Mode = Field(
        default="soft",
        description="A value the source itself marks as erroneous or doubtful in its own quality flag and returns all "
        "the same (a GHCN-Daily value that failed a check, a Frost `qualityCode` 7, an Environment Agency reading "
        "`Suspect`, a DMI `validity:false`): the codes counted are those the provider's documentation words so, listed "
        "per provider. It is soft by default, because the verdict is the source's and not ours. "
        + _HARD_MEANS.format(check="source")
        + " The suspect level of a source that has two (GHCNh `Suspect` and source 382 `R`, CHMI `Suspect`, MADIS "
        "`Questioned`, GHCNh `f`) is only flagged `suspect:source` in either mode.",
    )
    step: Mode = Field(
        default="soft",
        description="A change between two consecutive readings of one parameter beyond what the weather does in that "
        "time (an hourly air temperature that jumps 20 K, a pressure that moves 60 hPa in an hour), or a reading that "
        "jumps away from both neighbours and back (a spike: 8 K up and 8 K down at an hour): the limits are those of "
        "published quality controls, per parameter and resolution. Fronts are real, and the check judges a series and "
        "not a value, which is why it is soft by default. " + _HARD_MEANS.format(check="step"),
    )

    relations: Mode = Field(
        default="soft",
        description="Two readings of one row that contradict each other (a daily maximum below the daily mean, a dew "
        "point more than 0.2 K above the air temperature, a gust below the mean wind of its interval) or a day of "
        "sunshine longer than the day at the station: both readings of a broken pair are flagged, since nothing says "
        "which is wrong, and the check never downloads the other parameter. It is not `consistency`, the hard rules "
        "a provider has for its own source. It is soft by default, because it flags a good reading beside a bad one. "
        + _HARD_MEANS.format(check="relations"),
    )

    def for_forecast(self) -> Plausibility:
        """Give the modes a forecast network is judged with: every check soft but two, whatever mode it was given.

        A forecast is a model's output and not a reading, and what a built-in check finds in it (a rain above any
        record, a pressure the elevation does not allow) is a flag on a value the model wrote, so none of them nulls it,
        however ``hard`` is set (the options, the CLI, the REST API, the environment; GH-3681). There are two
        exceptions, which keep the mode they were given:

        - ``floor`` does not reject: it sets a value a little below the floor of its quantity to the floor and keeps the
          number as ``rejected:floor,raw:<number>``;
        - ``limits`` are bounds the caller wrote for a parameter, so the caller has said what is to go: hard (the
          default) nulls a forecast value outside them as ``rejected:limits,raw:<number>``, soft flags it (GH-3687).
        """
        return Plausibility(**{check: self.mode(check) if check in FORECAST_KEEPS_MODE else "soft" for check in CHECKS})

    @model_validator(mode="before")
    @classmethod
    def _one_mode_for_every_check(cls, data: object) -> object:
        """Read a bare mode as that mode for every check, which a check named beside it overrides (GH-3676).

        ``Options(plausibility="soft")`` is ``Options(plausibility={"range": "soft", ...})`` with all eight listed.
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
#: the page. `range`, `elevation`, `stuck` and `step` run on every network that has a quantity of their tables
#: (GH-3681): the bounds, the runs and the jumps are the same for every provider (`model/plausibility_ranges.py`,
#: `model/persistence.py`, `model/rate_of_change.py`).
#: `relations` runs on every observation network that has two parameters of a relation in one dataset
#: (`model/relations.py`, GH-3681).
#: `limits` is in none (`CALLER_CHECKS`): it runs on any network, for the parameters the caller sets a bound for. A
#: network that is in no list judges no value by the tables of the library
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
    # every observation network that serves a parameter of the run table (`model/persistence.py`, GH-3681) at 10
    # minutes, an hour or a day, and the ones whose provider hands the core a run rule of its own (the road sensors,
    # RMI's dated periods)
    "stuck": {
        "aemet/observation": ("*",),
        "chmi/observation": ("*",),
        "dmi/observation": ("*",),
        "dwd/observation": ("*",),
        "dwd/poi": ("*",),
        "dwd/road": ("*",),
        "eccc/observation": ("*",),
        "fmi/observation": ("*",),
        "geosphere/observation": ("*",),
        "imgw/meteorology": ("*",),
        "ipma/observation": ("*",),
        "knmi/observation": ("*",),
        "lhmt/observation": ("*",),
        "meteofrance/observation": ("*",),
        "meteoswiss/observation": ("*",),
        "metno/frost": ("*",),
        "metoffice/observation": ("*",),
        "noaa/ghcn": ("*",),
        "nws/observation": ("*",),
        "rmi/observation": ("*",),
        "smhi/observation": ("*",),
        "wsv/pegel": ("*",),
    },
    # every observation network that serves a parameter of the table of jumps (`model/rate_of_change.py`, GH-3681) at 10
    # minutes, an hour or a day
    "step": {
        "aemet/observation": ("*",),
        "chmi/observation": ("*",),
        "dmi/observation": ("*",),
        "dwd/observation": ("*",),
        "dwd/poi": ("*",),
        "eccc/observation": ("*",),
        "fmi/observation": ("*",),
        "geosphere/observation": ("*",),
        "imgw/meteorology": ("*",),
        "ipma/observation": ("*",),
        "knmi/observation": ("*",),
        "lhmt/observation": ("*",),
        "meteofrance/observation": ("*",),
        "meteoswiss/observation": ("*",),
        "metno/frost": ("*",),
        "metoffice/observation": ("*",),
        "noaa/ghcn": ("*",),
        "nws/observation": ("*",),
        "rmi/observation": ("*",),
        "smhi/observation": ("*",),
        "wsv/pegel": ("*",),
    },
    # every observation network that has two parameters of the table of relations (`model/relations.py`, GH-3681) in
    # one file, or a sunshine duration and a position of the station
    "relations": {
        "aemet/observation": ("*",),
        "chmi/observation": ("*",),
        "dmi/observation": ("*",),
        "dwd/observation": ("*",),
        "dwd/poi": ("*",),
        "dwd/road": ("*",),
        "eccc/observation": ("*",),
        "fmi/observation": ("*",),
        "geosphere/observation": ("*",),
        "imgw/meteorology": ("*",),
        "knmi/observation": ("*",),
        "meteofrance/observation": ("*",),
        "meteofrance/synop": ("*",),
        "meteoswiss/observation": ("*",),
        "metno/frost": ("*",),
        "metoffice/observation": ("*",),
        "noaa/ghcn": ("*",),
        "nws/observation": ("*",),
        "rmi/observation": ("*",),
    },
    "consistency": {
        "dwd/road": ("15_minutes/data",),
        "meteofrance/observation": ("hourly/others",),
        "meteofrance/synop": ("subdaily/data",),
    },
    "floor": {
        "dwd/dmo": ("hourly/icon", "hourly/icon_eu"),
    },
    # the networks whose source marks a value as erroneous or doubtful in a quality flag the reader returns, and the
    # datasets that flag is in: derived from the map of the codes (`model/source_flags.py`, GH-3677)
    "source": source_coverage(),
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

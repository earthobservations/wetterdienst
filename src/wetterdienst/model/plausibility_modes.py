# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The names of the plausibility checks, their default modes and what each mode says (GH-3676, GH-3809).

The part of ``model/plausibility.py`` that is plain data and text: no polars, no pydantic. The command line builds the
``--help`` of ``--plausibility-<check>`` from it when it is imported, and a shell completion or ``--help`` must not
pay for the model (``Plausibility``) and polars to do that. ``model/plausibility.py`` imports everything here and
re-exports it, so ``from wetterdienst.model.plausibility import CHECKS`` works as it always did.
"""

from __future__ import annotations

from typing import Literal, get_args

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

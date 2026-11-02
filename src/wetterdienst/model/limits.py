# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The bounds a caller sets per parameter for the check ``limits`` (GH-3687).

``Options(limits={"temperature_air_mean_2m": (-30, 45), "precipitation_amount": (None, 200)})``: the values core
judges every reading of the parameter against the pair, beside the physical ranges of the check ``range``
(``model/plausibility_ranges.py``), which it leaves as they are. A bound is in the unit of the values the request
returns, that is the one ``unit_targets`` asks for (or the unit of the source where ``convert_units`` is off); the core
converts it to the canonical unit and judges there (``model/judge.py``).

A key names a parameter in one of two ways:

- a canonical parameter name (``temperature_air_mean_2m``), which holds in every dataset that serves the parameter;
- ``resolution/dataset/parameter`` (``daily/climate_summary/temperature_air_mean_2m``), which holds in the datasets of
  that name only. It is written as a request writes a parameter, so ``daily/kl/...``, the source's own names and the
  separators ``.`` and ``:`` work too.

Where both name a parameter, the one with the dataset wins as a whole: its bounds are used and the other's are not
combined with them.

A pair is ``(low, high)``, both ends included in what is plausible. Either may be ``None`` for no bound at that end, but
not both. ``low`` may not exceed ``high``, and a bound is a finite number: NaN and infinity are refused, as a pair that
bounds nothing is no limit.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Mapping
from typing import TYPE_CHECKING, Annotated

from pydantic import AfterValidator, BeforeValidator, Field

from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.metadata.renamed import RENAMED_PARAMETERS
from wetterdienst.model.metadata import POSSIBLE_SEPARATORS, ParameterSearch

if TYPE_CHECKING:
    from wetterdienst.model.metadata import ParameterModel


def _no_truth_value(bound: object) -> object:
    """Refuse a bool for a bound, which Python would read as 0 or 1."""
    if isinstance(bound, bool):
        msg = "a bound is a number, not a truth value"
        raise ValueError(msg)  # noqa: TRY004
    return bound


_Bound = Annotated[float, BeforeValidator(_no_truth_value), Field(allow_inf_nan=False)]

#: what every surface says of the option
LIMITS_DESCRIPTION = (
    "Bounds you set per parameter, `{name: [low, high]}`, for the plausibility check `limits`. A key is a canonical "
    "parameter name (every dataset that serves it) or `resolution/dataset/parameter` (that dataset only, which wins "
    "where both name a parameter). A bound is in the unit of the values this request returns (`unit_targets`, or the "
    "source's unit with `convert_units` off), either may be null but not both, and `low` may not exceed `high`. "
    "A value outside is judged by the mode of `plausibility.limits`: hard (the default) nulls it and keeps the number "
    "as `rejected:limits,raw:<number>`, soft keeps it and flags it `suspect:limits`. A forecast network is judged soft."
)


def _checked_pair(pair: tuple[float | None, float | None]) -> tuple[float | None, float | None]:
    """Refuse a pair that bounds nothing, or whose low end is above its high end."""
    low, high = pair
    if low is None and high is None:
        msg = "a limit needs a low or a high bound, and both are null: leave the parameter out to set none"
        raise ValueError(msg)
    if low is not None and high is not None and low > high:
        msg = f"low ({low:g}) is above high ({high:g})"
        raise ValueError(msg)
    return pair


#: the bounds of one parameter: ``(low, high)``, either one ``None``, finite, ``low <= high``
Limit = Annotated[tuple[_Bound | None, _Bound | None], AfterValidator(_checked_pair)]


def is_dataset_key(key: str) -> bool:
    """Tell whether a key names a parameter of a dataset (``resolution/dataset/parameter``) and not by its name."""
    return any(separator in key for separator in POSSIBLE_SEPARATORS)


@functools.cache
def _parameters_of_all_networks() -> tuple[ParameterModel, ...]:
    """Give every parameter of every network's metadata, to tell what a key names.

    Built on first use, only for a key that names a dataset: the metadata of the networks is declared in the code of
    each provider, which a name alone does not need.
    """
    from wetterdienst.api import Wetterdienst  # noqa: PLC0415

    found: list[ParameterModel] = []
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if Wetterdienst.is_standalone(provider, network):
                continue
            try:
                metadata = Wetterdienst.resolve(provider, network).metadata
            except ImportError:
                # a network that cannot be imported here names nothing; it is left out as `discover` leaves it out
                continue
            found.extend(parameter for resolution in metadata for dataset in resolution for parameter in dataset)
    return tuple(found)


def _search_of(key: str) -> ParameterSearch:
    """Read a key that names a dataset's parameter, as a request reads a parameter: three parts, all of them named."""
    search = ParameterSearch.parse(key)
    if search.parameter is None:
        msg = "a key names a parameter: `resolution/dataset/parameter`, not a whole dataset"
        raise ValueError(msg)
    return search


def search_for(key: str) -> ParameterSearch | None:
    """Read a key as the search of a dataset's parameter, or ``None`` where it is a canonical name."""
    return _search_of(key) if is_dataset_key(key) else None


@functools.cache
def _problem_with(key: object) -> str | None:
    """Say what is wrong with a key, or ``None``."""
    if not isinstance(key, str):
        return f"{key!r} is no name: a key is text"
    if not is_dataset_key(key):
        if key.strip().lower() in PARAMETERS:
            return None
        renamed = RENAMED_PARAMETERS.get(key.strip().lower())
        hint = f" (it is now '{renamed}')" if renamed else ""
        return f"'{key}' is no canonical parameter{hint}"
    try:
        search = _search_of(key)
    except ValueError as error:
        return f"'{key}': {error}"
    if not any(search.matches(parameter) for parameter in _parameters_of_all_networks()):
        return f"'{key}' is no parameter of any dataset of any network"
    return None


@functools.cache
def normal_name(key: str) -> str:
    """Give a valid key its one spelling, so that a key merges with, and replaces, the same parameter spelled otherwise.

    A canonical name is stripped and lowercased. A name with a dataset is written as ``resolution/dataset/parameter``
    by the canonical names of the parameter it names (``daily/kl/tmk`` is
    ``daily/climate_summary/temperature_air_mean_2m``), or, where it names parameters that are not one, as the
    lowercased parts it was given.
    """
    search = search_for(key)
    if search is None:
        return key.strip().lower()
    parameters = _parameters_of_all_networks()
    named = {id(parameter) for parameter in parameters if search.matches(parameter)}
    triples = {
        (parameter.dataset.resolution.name, parameter.dataset.name, parameter.name)
        for parameter in parameters
        if id(parameter) in named
    }
    if len(triples) == 1:
        canonical = ParameterSearch(*next(iter(triples)))
        # only where the canonical spelling names the very parameters the key names: `hourly/ogd-smn/rre150h0` is one
        # network's, and `hourly/data/precipitation_amount` is that of thirteen
        if {id(parameter) for parameter in parameters if canonical.matches(parameter)} == named:
            return "/".join(next(iter(triples)))
    return f"{search.resolution}/{search.dataset}/{search.parameter}"


def with_normal_names(values: Mapping[str, object]) -> dict[str, object]:
    """Give a mapping with the keys that are valid names in their one spelling, and the others as they are.

    Of two keys that name one parameter the later wins, as a key written twice in a dict does.
    """
    return {(normal_name(key) if _problem_with(key) is None else key): value for key, value in values.items()}


def checked_limit_names(values: object) -> object:
    """Refuse a key of ``limits`` that names no parameter, before the pairs are read, and spell the others one way.

    An empty value is no limits, and any other that is not a mapping is left for the field to refuse, which names it.
    A name nothing serves cannot be looked up: the bound would silently do nothing, and a typo would be
    indistinguishable from having set none. A canonical name that no request reaches is not an error, as the options
    may serve requests for any network. The keys come out in their one spelling (``normal_name``), so that a key
    given by a request replaces the host's bound for the same parameter, however either is spelled.
    """
    if not values:
        return {}
    if not isinstance(values, Mapping):
        return values
    problems = [problem for key in values if (problem := _problem_with(key)) is not None]
    if problems:
        msg = (
            f"Invalid names in limits: {'; '.join(problems)}. A key is a canonical parameter name or "
            "`resolution/dataset/parameter`"
        )
        raise ValueError(msg)
    return with_normal_names(values)


def read_limit_text(text: str) -> tuple[str, tuple[float | None, float | None]]:
    """Read ``name=low:high`` (the command line's form) as a name and its pair; an end left empty is no bound.

    ``temperature_air_mean_2m=-30:45``, ``precipitation_amount=:200``, ``temperature_air_mean_2m=-30:``.
    """
    name, separator, bounds = text.rpartition("=")
    low_text, colon, high_text = bounds.partition(":")
    if not separator or not name.strip() or not colon:
        msg = f"{text!r} is not name=low:high (an end may be left empty: precipitation_amount=:200)"
        raise ValueError(msg)
    try:
        low = float(low_text) if low_text.strip() else None
        high = float(high_text) if high_text.strip() else None
    except ValueError:
        msg = f"{text!r}: the bounds are numbers (name=low:high)"
        raise ValueError(msg) from None
    for bound in (low, high):
        if bound is not None and not math.isfinite(bound):
            msg = f"{text!r}: a bound is a finite number, not NaN or infinity"
            raise ValueError(msg)
    return name.strip(), (low, high)

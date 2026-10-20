# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The alias a canonical parameter name keeps after a rename made from 1.0 on (GH-2625).

The policy (`docs/usage/compatibility.md`): until 1.0 a rename is a hard break and the old name is refused with a
hint (`wetterdienst.metadata.renamed`); from 1.0 a rename keeps the old name working, with a warning, for at least two
minor releases, and removes it only in a major release. This module is the second half. A rename that keeps its old
name is declared here, once, and then

- the old name is **accepted** wherever the parameter name is: in `parameters=` of a request (Python, command line,
  REST and MCP all resolve it through `MetadataModel.search_parameter`), as an attribute or item of a dataset, as a
  column of a SQL filter, and, for a name of every dataset, as a key of `Options(geo_station_distance=...)` and the
  `parameter` of `glossary`;
- it **resolves to the new name**, so the answer carries the new name and nothing downstream knows the old one;
- every use of it **warns** (`use_alias`): a `DeprecationWarning` for the Python caller, a `deprecated-parameter`
  warning in the `metadata` block of a REST, MCP or command line answer, and the `Deprecation` header of REST
  (`wetterdienst.ui.deprecation`), each naming the new name, the release that renamed it, and the release that may
  remove the alias.

The tables are empty until a rename is made after the 1.0.0 tag, so that nothing changes before one is declared. An
entry is also a rename for `wetterdienst.metadata.renamed` (it is merged into its tables at import), so that once the
alias is removed the hint that names the new spelling stays, as it does for every name that is gone: moving an entry
from here into the plain rename tables is how an alias ends.

The length of an alias is held by `tests/metadata/test_aliases.py` (`check_alias`: it is declared from 1.0, and ends in
a major release after the one it began in) and by the parameters baseline (`tests/baselines/parameters.py`: an alias
the last release had is still declared).
"""

from __future__ import annotations

import logging
import re
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from wetterdienst.ui.deprecation import Deprecation, mark_deprecated
from wetterdienst.util.response_warnings import warn_response

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Iterator

log = logging.getLogger(__name__)

#: the code of the warning in the `metadata` block of an answer, as every deprecated parameter has it
DEPRECATED_PARAMETER = "deprecated-parameter"

#: where the rename is told, sent as the `Link` with `rel="deprecation"` of a REST answer
_LINK = "https://wetterdienst.readthedocs.io/en/latest/usage/compatibility.html#parameter-names-units-and-timestamps"

_RELEASE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class ParameterAlias:
    """The old name of a renamed parameter, kept working: what it became, when, and when it may go."""

    #: the canonical name it is called now
    new: str
    #: the release that renamed it, `"1.3.0"`
    since: str
    #: the day of that release, which the `Deprecation` header of REST says
    date: dt.date
    #: the first release that may remove the alias, a major one: `"2.0.0"`. Until then it works; at least two minor
    #: releases are to lie between `since` and it, which is for the reviewer of the declaration to see
    until: str


#: canonical names renamed with an alias, old name to alias. It holds in every dataset that has the new name and not
#: the old one, so it is for a name that the table no longer has at all (otherwise it is a rename in a dataset)
PARAMETER_ALIASES: dict[str, ParameterAlias] = {}

#: canonical names renamed with an alias inside one dataset, for a name that another dataset of the provider keeps:
#: keyed as `renamed.RENAMED_PARAMETERS_IN_DATASET` is, by the name of the provider's metadata declaration
#: (`MetadataModel.name`) and `(resolution, dataset)`, to `{old name: alias}`
PARAMETER_ALIASES_IN_DATASET: dict[str, dict[tuple[str, str], dict[str, ParameterAlias]]] = {}


def release(text: str) -> tuple[int, int, int]:
    """Read a release as `major.minor.patch`, and refuse anything else (a pre-release is no release of an alias)."""
    match = _RELEASE.match(text)
    if match is None:
        msg = f"'{text}' is not a release as major.minor.patch"
        raise ValueError(msg)
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def check_alias(old: str, alias: ParameterAlias) -> list[str]:
    """Say what is wrong with the declaration of an alias, as one sentence each; none if it is as the policy has it.

    - it is a rename of 1.0 or later: a rename before is a hard break and has no alias;
    - it ends in a major release (`x.0.0`), and one after the release that renamed it, so a minor release removes
      nothing;
    - it names a new name that is not the old one.
    """
    problems = []
    try:
        since = release(alias.since)
        until = release(alias.until)
    except ValueError as e:
        return [f"the alias '{old}': {e}"]
    if since < (1, 0, 0):
        problems.append(f"the alias '{old}' is since {alias.since}: a rename before 1.0.0 has no alias")
    if until[1:] != (0, 0):
        problems.append(f"the alias '{old}' ends in {alias.until}: an alias is removed only in a major release")
    if until[0] <= since[0]:
        problems.append(f"the alias '{old}' ends in {alias.until}, not after the major release of {alias.since}")
    if alias.new == old:
        problems.append(f"the alias '{old}' is a rename to itself")
    return problems


def find_alias(metadata_name: str, resolution: str, dataset: str, name: str) -> ParameterAlias | None:
    """Find the alias that `name` is in a dataset of a provider, the one declared for the dataset first."""
    in_dataset = PARAMETER_ALIASES_IN_DATASET.get(metadata_name, {}).get((resolution, dataset), {})
    return in_dataset.get(name) or PARAMETER_ALIASES.get(name)


def all_aliases() -> Iterator[tuple[str, ParameterAlias]]:
    """Give every declared alias as `(old name, alias)`, those of a dataset and those of every dataset."""
    for datasets in PARAMETER_ALIASES_IN_DATASET.values():
        for aliases in datasets.values():
            yield from aliases.items()
    yield from PARAMETER_ALIASES.items()


def alias_message(old: str, alias: ParameterAlias) -> str:
    """Word what a caller who wrote `old` is told: the new name, since when, and until when it is accepted."""
    return (
        f"'{old}' was renamed to '{alias.new}' in {alias.since} and is accepted as an alias until {alias.until} "
        f"at the earliest (an alias lasts at least two minor releases and is removed only in a major release): "
        f"use '{alias.new}'"
    )


def _caller_level() -> int:
    """Count the frames up to the first one outside this package, which is where a `DeprecationWarning` belongs.

    The `__init__` that `dataclass` generates (`<string>`) is part of the package: a request is built by one.
    """
    package = str(Path(__file__).parents[1])
    level = 1
    frame = sys._getframe(1)  # noqa: SLF001
    while frame is not None and frame.f_code.co_filename.startswith((package, "<string>")):
        frame = frame.f_back
        level += 1
    return level


def use_alias(old: str, alias: ParameterAlias) -> None:
    """Tell the caller that `old` is an alias: a `DeprecationWarning`, and the warning of the answer being built.

    The answer's `metadata` block gets `deprecated-parameter` and a REST answer the `Deprecation` header; outside a
    request both are no-ops and the warning is a log line next to the `DeprecationWarning`.
    """
    message = alias_message(old, alias)
    warnings.warn(message, DeprecationWarning, stacklevel=_caller_level())
    warn_response(log, DEPRECATED_PARAMETER, message)
    mark_deprecated(Deprecation(since=alias.date, link=_LINK))

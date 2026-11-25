"""Read the advisories that the packages publish in their own repositories against the locked versions.

GitHub's alerts, `uv audit` and `pnpm audit` read the global advisory database, which lists an advisory
days or weeks after the package's own repository published it (GH-4378). This script reads the published
repository advisories directly:

1. the locked packages: `uv.lock` (what `pyproject.toml` needs at runtime, extras included, and everything
   they pull in) and `app/pnpm-lock.yaml` (the direct dependencies, and what the production ones pull in);
2. each package's GitHub repository, from the metadata of PyPI and npm;
3. the published advisories of that repository (`GET /repos/{owner}/{repo}/security-advisories`), the ones
   that name the package, compared with the locked version.

A package that cannot be judged is never reported as safe: an advisory whose range cannot be parsed is
"unclear", a package without a GitHub repository (or whose repository is gone) is "unreadable", and any other
answer of PyPI, npm or GitHub that is not the one expected (a rate limit, a 5xx, a 403, a malformed body) stops
the run with an error (exit code 2) instead of answering "nothing found".

    uv run poe advisories                      # a table on stdout, exit 1 if something is affected or unclear
    uv run python scripts/repo_advisories.py --issue --dry-run   # what the weekly job would write
    # the weekly job (advisories.yml), the only place that writes the issue, under the bot's name:
    uv run --no-project --isolated --with packaging==26.3 python -I scripts/repo_advisories.py --issue

The issue is found by its fixed title, a marker in its body and its author (`github-actions[bot]`), and is
updated while it is open. It is closed by a person; a closed issue is not opened again for the same findings,
and findings that differ from the ones it carries are a new issue. Nothing is assigned and nobody is mentioned:
package names, versions and ranges are written as code, and no text of an advisory is copied.

Known not to affect us: `scripts/repo_advisories_ignore.toml`, one entry per advisory and package, each with
the range and the patched versions the advisory states (or the locked version), a reason and a date (never a
wildcard). An entry stops hiding the finding when the advisory changes.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime as dt
import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from packaging.version import Version

ROOT = Path(__file__).resolve().parent.parent
UV_LOCK = ROOT / "uv.lock"
PNPM_LOCK = ROOT / "app" / "pnpm-lock.yaml"
IGNORE_FILE = Path(__file__).with_name("repo_advisories_ignore.toml")

# a release younger than this is refused by `exclude-newer` (pyproject.toml) and `minimumReleaseAge`
# (app/pnpm-workspace.yaml), so a fix this young cannot be locked yet
COOLDOWN = dt.timedelta(days=3)
# an ignore entry older than this is listed for a second look
IGNORE_REVIEW_AFTER = dt.timedelta(days=180)

ISSUE_TITLE = "security: dependencies behind advisories of their own repositories (scheduled check)"
ISSUE_MARKER = "<!-- repo-advisories-check -->"
ISSUE_LABELS = ["security"]
ISSUE_AUTHOR = "github-actions[bot]"
CHANGED_COMMENT = "The findings changed, see the list above."
GITHUB_API = "https://api.github.com/"
USER_AGENT = "wetterdienst-advisory-check"
SEVERITIES = ("critical", "high", "medium", "low")
GHSA_ID = re.compile(r"^GHSA(-[2-9cfghjmpqrvwx]{4}){3}$")
WORKERS = 8
RETRIES = 3
MAX_RANGE_LENGTH = 500
MAX_PAGES = 20
UNREADABLE_STATUSES = (404, 410, 451)  # a repository or a version that is not there; any other answer stops the run


class AdvisoryCheckError(Exception):
    """A source could not be read: the run stops, since "nothing found" would be a lie."""


class RateLimitError(AdvisoryCheckError):
    """GitHub refused the request because the rate limit is used up."""


class UnclearRange(ValueError):  # noqa: N818
    """A version, or a range of versions, that this script does not understand."""


class Unreadable(Exception):  # noqa: N818
    """One package's advisories cannot be read (no repository, repository not found): the run goes on."""


# --------------------------------------------------------------------------------------------------------------------
# versions and ranges
# --------------------------------------------------------------------------------------------------------------------


_SEMVER = re.compile(
    r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z.-]+)?$",
    re.ASCII,
)


@dataclasses.dataclass(frozen=True, order=True)
class SemVer:
    """An npm version, ordered by the precedence of semver 2.0 (the build metadata does not count)."""

    key: tuple[Any, ...]
    text: str = dataclasses.field(compare=False)

    @classmethod
    def parse(cls, text: str) -> SemVer:
        """Parse a version; raises `ValueError` for what is not one."""
        match = _SEMVER.match(text.strip())
        if not match:
            msg = f"not a semver version: {text!r}"
            raise ValueError(msg)
        core = tuple(int(part) for part in match.groups()[:3])
        pre = match.group(4)
        identifiers = tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre.split(".")) if pre else ()
        # a release is above all of its pre-releases, and a numeric identifier is below an alphanumeric one
        return cls((core, 1, ()) if not pre else (core, 0, identifiers), text)

    @property
    def release(self) -> tuple[int, ...]:
        """Return the major, minor and patch numbers."""
        return self.key[0]

    def __str__(self) -> str:
        """Return the version as written."""
        return self.text


Parsed = Version | SemVer
Comparator = tuple[str, Parsed]


def parse_version(ecosystem: str, text: str) -> Parsed:
    """Parse one version of `pip` (PEP 440) or `npm` (semver); anything else is unclear, not an error."""
    text = text.strip()
    try:
        if len(text) > 100:
            msg = "too long"
            raise ValueError(msg)  # noqa: TRY301
        if ecosystem == "npm":
            return SemVer.parse(text)
        version = Version(text)
        if version.local is not None:
            msg = "local version"
            raise ValueError(msg)  # noqa: TRY301
    except ValueError as exc:
        message = f"version {text[:40]!r} not understood"
        raise UnclearRange(message) from exc
    return version


def _release(version: Parsed) -> tuple[int, ...]:
    return version.release


def _line(version: Parsed) -> tuple[int, ...]:
    """Return the release line a fix belongs to: the major version, or the minor one below 1.0."""
    release = (*_release(version), 0, 0)
    return (0, release[1]) if release[0] == 0 else (release[0],)


_OPERATOR = r"(?:<=|>=|==|!=|<|>|=)"
_HYPHEN = re.compile(r"^(\S+)\s+-\s+(\S+)$")
_COMPARATOR = re.compile(rf"^({_OPERATOR})?(\S+)$")
_PARTIAL = re.compile(r"^v?(\d+)(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?$", re.ASCII)
# `1.0.0-2.0.0` and `1.0-2` are a hyphen range written without spaces as often as a pre-release or a post-release
_DASHED_NUMBERS = re.compile(r"^v?\d+(\.\d+)*-\d+(\.\d+)*$", re.ASCII)


def _compare(version: Parsed, operator: str, bound: Parsed) -> bool:
    return {
        "<": version < bound,
        "<=": version <= bound,
        ">": version > bound,
        ">=": version >= bound,
        "=": version == bound,
        "==": version == bound,
        "!=": version != bound,
    }[operator]


def _normalise(text: str) -> str:
    """Return the range with the spellings of the advisory database that mean a comparator written plainly.

    `≤ 12.2.0`, `=< 2.3.0`, `0.15.0 and earlier`, `>=1.3.3 and <= 1.4.1`, `>=3.8.1<3.15.3` and a parenthesis
    without a number in it. A parenthesis with a number (`< 2.1.13 (up to 2.1.12)`) is not understood.
    """
    for parenthesis in re.findall(r"\([^)]*\)?", text):
        if re.search(r"\d", parenthesis):
            msg = "a range with a number in parentheses is not understood"
            raise UnclearRange(msg)
    text = re.sub(r"\([^)]*\)?", " ", text)
    text = text.replace("≤", "<=").replace("≥", ">=").replace("=<", "<=").replace("=>", ">=")
    text = re.sub(r"(\S+)\s+(?:and|or)\s+(earlier|prior)\b", r"<= \1", text, flags=re.IGNORECASE)
    text = re.sub(r"(\S+)\s+(?:and|or)\s+later\b", r">= \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+and\s+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"(?<=[0-9a-zA-Z])(?=[<>])", " ", text)


def _partial(text: str) -> tuple[list[int], bool]:
    """Return the numbers of `10`, `9.1` or `4.x` and whether a wildcard ended them; `1.x.3` is unclear."""
    match = _PARTIAL.match(text)
    if not match:
        msg = f"version {text[:40]!r} not understood"
        raise UnclearRange(msg)
    parts = [part for part in match.groups() if part is not None]
    numbers: list[int] = []
    wildcard = False
    for part in parts:
        if part in "xX*":
            wildcard = True
        elif wildcard:  # `1.x.3`
            msg = f"version {text[:40]!r} not understood"
            raise UnclearRange(msg)
        else:
            numbers.append(int(part))
    return numbers, wildcard


def _filled(ecosystem: str, text: str) -> Parsed:
    """Parse a version whose missing or `x` parts are zero: `10`, `9.1` and `4.x` as a lower bound or as `<`."""
    try:
        return parse_version(ecosystem, text)
    except UnclearRange:
        numbers, _ = _partial(text)
        return parse_version(ecosystem, ".".join(str(n) for n in [*numbers, 0, 0][:3]))


def _x_range(ecosystem: str, text: str) -> list[Comparator]:
    """Return the comparators of `11.0.x`, `4.x` or `10`: every version that starts with the given parts."""
    numbers, _ = _partial(text)
    upper = [*numbers[:-1], numbers[-1] + 1]
    return [
        (">=", parse_version(ecosystem, ".".join(str(p) for p in [*numbers, 0, 0][:3]))),
        ("<", parse_version(ecosystem, ".".join(str(p) for p in [*upper, 0, 0][:3]))),
    ]


def _segment(ecosystem: str, segment: str) -> list[Comparator]:
    """Return the comparators of one segment, which all hold; `[]` is every version."""
    segment = segment.strip()
    hyphen = _HYPHEN.match(segment)
    if hyphen:
        return [(">=", _filled(ecosystem, hyphen.group(1))), ("<=", parse_version(ecosystem, hyphen.group(2)))]
    if segment in ("*", "x"):
        return []
    tokens = [_COMPARATOR.match(token) for token in re.sub(rf"({_OPERATOR})\s+", r"\1", segment).split()]
    if not tokens or not all(tokens):
        msg = f"range {segment[:60]!r} not understood"
        raise UnclearRange(msg)
    parsed = [(token.group(1), token.group(2)) for token in tokens if token]
    if any(operator is None and _DASHED_NUMBERS.match(text) for operator, text in parsed):
        msg = f"range {segment[:60]!r} not understood"  # `1.0.0-2.0.0`: a range without spaces, or a pre-release?
        raise UnclearRange(msg)
    if len(parsed) == 1 and parsed[0][0] is None:
        try:
            return [("=", parse_version(ecosystem, parsed[0][1]))]
        except UnclearRange:
            return _x_range(ecosystem, parsed[0][1])
    comparators: list[Comparator] = []
    for index, (operator, text) in enumerate(parsed):
        if operator is None:  # `10 <10.2.1`, `7.0.0 < 7.29.1`: the bare version opens the range
            if index + 1 < len(parsed) and parsed[index + 1][0] in ("<", "<="):
                comparators.append((">=", _filled(ecosystem, text)))
                continue
            msg = f"range {segment[:60]!r} not understood"
            raise UnclearRange(msg)
        full = operator in ("<", ">=")  # where a missing part is zero exactly: `< 20`, `>= 9.1`
        comparators.append((operator, _filled(ecosystem, text) if full else parse_version(ecosystem, text)))
    return comparators


_LOWER = (">", ">=")
_UPPER = ("<", "<=")


def _lower(conjunction: list[Comparator]) -> Comparator | None:
    return next((c for c in conjunction if c[0] in _LOWER), None)


def _upper(conjunction: list[Comparator]) -> Comparator | None:
    return next((c for c in conjunction if c[0] in _UPPER), None)


def _valid(conjunction: list[Comparator], text: str) -> list[Comparator]:
    """Return a conjunction that can hold: one exact version, or at most one lower and one upper bound."""
    lowers = [c for c in conjunction if c[0] in _LOWER]
    uppers = [c for c in conjunction if c[0] in _UPPER]
    exact = [c for c in conjunction if c[0] in ("=", "==")]
    if any(c[0] == "!=" for c in conjunction) or (exact and len(conjunction) > 1) or len(lowers) > 1 or len(uppers) > 1:
        msg = f"range {text[:60]!r} not understood"
        raise UnclearRange(msg)
    if lowers and uppers:
        (lower_op, lower), (upper_op, upper) = lowers[0], uppers[0]
        if not (lower < upper or (lower == upper and lower_op == ">=" and upper_op == "<=")):
            msg = f"range {text[:60]!r} can never hold"
            raise UnclearRange(msg)
    return conjunction


def _alternative(ecosystem: str, alternative: str, text: str) -> list[list[Comparator]]:
    """Return the alternatives of one `||`-free part: its comma-separated segments are "and" or "or"."""
    if not alternative.strip():
        msg = f"empty range in {text[:60]!r}"
        raise UnclearRange(msg)
    segments = [_segment(ecosystem, segment) for segment in alternative.split(",")]
    if len(segments) == 1:
        return [_valid(segments[0], text)]
    if any(not segment for segment in segments):
        msg = f"range {text[:60]!r} not understood"
        raise UnclearRange(msg)
    if all(len(segment) == 1 for segment in segments):
        flat = [segment[0] for segment in segments]
        if len(flat) == 2:
            return [_valid(flat, text)]  # `>= 4.5.0, <= 4.16.0`: one lower and one upper bound
        if len(flat) % 2 == 0 and all(
            flat[i][0] in _LOWER and flat[i + 1][0] in _UPPER for i in range(0, len(flat), 2)
        ):
            # `>=2.9.18,<3.0.0,>=3.2.9,<4.0.0`: a lower and an upper bound per release line
            return [_valid(flat[i : i + 2], text) for i in range(0, len(flat), 2)]
        msg = f"range {text[:60]!r} not understood"
        raise UnclearRange(msg)
    # `<1.1.17, >= 2.0.0 < 2.1.3, 4.0.0 - 5.0.7`: a range per segment, whose "and" would be empty
    return [_valid(segment, text) for segment in segments]


def parse_range(ecosystem: str, text: str | None) -> list[list[Comparator]]:
    """Parse a range into alternatives of comparators that all hold.

    Understood, as GitHub and the authors of advisories write them for PyPI and npm: `= 4.2.12`, `4.2.12`,
    `>= 4.5.0, <= 4.16.0`, `< 4.6.2`, `>=2,<=3.14.4`, `>=1.0.0 <2.0.0`, `7.2.0 - 12.3.0` (both ends
    included), `*`, `11.0.x`, `a || b`, `a; b`, `10 <10.2.1` (the bare version is the lower bound) and the
    spellings `≤ 12.2.0`, `=< 2.3.0`, `>=1.3.3 and <= 1.4.1`, `0.15.0 and earlier`, `>=3.8.1<3.15.3`.

    A comma between two single comparators is "and", and only for one lower and one upper bound that can both
    hold; four or more, in the order lower, upper, lower, upper, are one range per pair; a comma between
    segments that hold a range each is "or". Everything else (two exact versions, two upper bounds,
    `^`, `~`, `~=`, `all`, a number in parentheses, an empty range, one over 500 characters) raises `UnclearRange`.
    """
    if text is None or not text.strip():
        msg = "no range"
        raise UnclearRange(msg)
    if len(text) > MAX_RANGE_LENGTH:
        msg = "range too long"
        raise UnclearRange(msg)
    alternatives: list[list[Comparator]] = []
    for alternative in re.split(r"\|\||;", _normalise(text)):
        alternatives.extend(_alternative(ecosystem, alternative, text))
    return alternatives


def in_range(ecosystem: str, version: str, text: str | None) -> bool:
    """Whether `version` is in the range `text`. Raises `UnclearRange` for what it does not understand."""
    installed = parse_version(ecosystem, version)
    return any(_holds(installed, conjunction) for conjunction in parse_range(ecosystem, text))


def _holds(installed: Parsed, conjunction: list[Comparator]) -> bool:
    return all(_compare(installed, operator, bound) for operator, bound in conjunction)


def _has_upper_bound(conjunction: list[Comparator]) -> bool:
    return any(operator in (*_UPPER, "=", "==") for operator, _ in conjunction)


_FIX_ENTRY = re.compile(r"^(?:>=\s*)?v?\d+\.\d+[0-9A-Za-z.+-]*$", re.ASCII)
_PATCHED_SEPARATOR = re.compile(r",|;|\|\|")


@dataclasses.dataclass(frozen=True)
class Patch:
    """What `patched_versions` names: fixes that hold from their version on, and bounded ranges of fixed versions."""

    fixes: tuple[tuple[Parsed, str], ...] = ()
    bounded: tuple[tuple[Comparator, ...], ...] = ()


def _full_version(ecosystem: str, token: str) -> bool:
    if not re.match(r"^v?\d+\.\d+", token, re.ASCII):
        return False
    try:
        parse_version(ecosystem, token)
    except UnclearRange:
        return False
    return True


def patch_of(ecosystem: str, patched: str | None) -> Patch:  # noqa: C901
    """Read `patched_versions`: `0.17.1`, `4.2.4, 3.1.1`, `>= 6.21.2`, `>= 5.28.4 < 6.0.0; >= 6.11.1`, `> 3.21.5, < 4`.

    The text is read as a range (a comma is "and") where every version in it is a whole one; a list that is no
    range (`1.5.3, 2.1.1`, `>= 1.15.9 || >= 2.0.1-rc.17`) gives one fix per entry. `0`, `*`, `2.x` and other
    partial forms name no fix and never override the vulnerable range.
    """
    if not patched or not patched.strip() or patched.strip().lower() == "none" or len(patched) > MAX_RANGE_LENGTH:
        return Patch()
    patched = re.sub(r"(?<=\d)\+(?=\s*(?:[,;]|\|\||$))", "", patched)  # `3.3.2+` says "3.3.2 and above", as a fix does
    tokens = [re.sub(rf"^{_OPERATOR}", "", t) for t in re.split(r"[\s,;|]+", patched) if t]
    tokens = [t for t in tokens if t]
    fixes: list[tuple[Parsed, str]] = []
    bounded: list[tuple[Comparator, ...]] = []
    alternatives: list[list[Comparator]] | None = None
    if tokens and all(_full_version(ecosystem, t) for t in tokens):
        try:
            alternatives = parse_range(ecosystem, patched)
        except UnclearRange:
            alternatives = None
    if alternatives is not None:
        for conjunction in alternatives:
            lower, upper = _lower(conjunction), _upper(conjunction)
            if len(conjunction) == 1 and conjunction[0][0] in ("=", "=="):
                fixes.append((conjunction[0][1], str(conjunction[0][1])))
            elif lower and not upper and lower[0] == ">=":
                fixes.append((lower[1], str(lower[1])))
            elif lower:
                bounded.append(tuple(conjunction))
    else:
        for raw in _PATCHED_SEPARATOR.split(patched):
            entry = raw.strip()
            if _FIX_ENTRY.match(entry):
                text = entry.removeprefix(">=").strip()
                if _full_version(ecosystem, text):
                    fixes.append((parse_version(ecosystem, text), text))
    fixes = [(v, t) for v, t in fixes if any(_release(v))]  # `0` names no fix
    return Patch(tuple(fixes), tuple(bounded))


def _is_fixed(installed: Parsed, patch: Patch, floor: Parsed | None) -> bool:
    """Whether the patch names the locked version as fixed.

    A bounded patched range holds it; or it is at or above the highest fix named; or at or above the highest fix
    of its own release line. A fix at or below the lower bound of the vulnerable range is no fix of it.
    """
    for conjunction in patch.bounded:
        lower = _lower(list(conjunction))
        if (floor is None or (lower and lower[1] > floor)) and _holds(installed, list(conjunction)):
            return True
    relevant = [version for version, _ in patch.fixes if floor is None or version > floor]
    if relevant and installed >= max(relevant):
        return True
    same_line = [version for version in relevant if _line(version) == _line(installed)]
    return bool(same_line) and installed >= max(same_line)


def assess(ecosystem: str, version: str, vulnerable: str | None, patched: str | None) -> str:
    """Judge the locked `version` against one entry of an advisory.

    `out`: not in the vulnerable range. `fixed`: in it, but the patched versions name it fixed. `closed`: in a range
    that has no upper bound and at or above a fix the entry names: a fix and "every later version is affected"
    cannot both be meant, so the fix is the end of the range (read as such, and listed as such). `affected`: the rest.
    Raises `UnclearRange` for a range or a version that is not understood.
    """
    installed = parse_version(ecosystem, version)
    holding = [c for c in parse_range(ecosystem, vulnerable) if _holds(installed, c)]
    if not holding:
        return "out"
    patch = patch_of(ecosystem, patched)
    # fixed for every range that holds it, each against its own lower bound: one that is not makes it affected
    if all(_is_fixed(installed, patch, (_lower(c) or ("", None))[1]) for c in holding):
        return "closed" if not any(_has_upper_bound(c) for c in holding) else "fixed"
    return "affected"


def is_affected(ecosystem: str, version: str, vulnerable: str | None, patched: str | None) -> bool:
    """Whether the locked `version` is affected by one entry of an advisory (see `assess`)."""
    return assess(ecosystem, version, vulnerable, patched) == "affected"


def first_fixed(ecosystem: str, version: str, patched: str | None) -> str | None:
    """Return the lowest fix above the locked version, of its own release line first (`None`: none yet)."""
    installed = parse_version(ecosystem, version)
    patch = patch_of(ecosystem, patched)
    candidates = [(v, t) for v, t in patch.fixes if v > installed]
    candidates += [
        (lower[1], str(lower[1])) for c in patch.bounded if (lower := _lower(list(c))) and lower[1] > installed
    ]
    same_line = [c for c in candidates if _line(c[0]) == _line(installed)]
    pool = sorted(same_line or candidates, key=lambda c: c[0])
    return pool[0][1] if pool else None


# --------------------------------------------------------------------------------------------------------------------
# the locks
# --------------------------------------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Package:
    """One locked package."""

    ecosystem: str  # `pip` or `npm`, the names of GitHub's advisory ecosystems
    name: str
    version: str
    direct: bool
    runtime: bool  # False: a development dependency of the app (direct only, its tree is not read)
    foreign: bool = False  # a git or URL dependency: no registry, no repository to ask

    @property
    def label(self) -> str:
        """Return `name version`."""
        return f"{self.name} {self.version}"


def normalise_name(ecosystem: str, name: str) -> str:
    """Return the name as the registry compares it (PEP 503 on PyPI, lower case on npm)."""
    return re.sub(r"[-_.]+", "-", name).lower() if ecosystem == "pip" else name.lower()


def read_uv_lock(path: Path) -> list[Package]:  # noqa: C901
    """Read the packages `pyproject.toml` needs at runtime: the dependencies and every extra, and what they need.

    Markers are not evaluated: a package that a platform or Python version leaves out is listed too. A lock of
    another version, a dependency the lock does not resolve and an empty result are errors.
    """
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not data.get("package"):
        msg = f"{path.name}: only lock version 1 is read, and it needs packages; has the format changed?"
        raise AdvisoryCheckError(msg)
    by_name: dict[str, list[dict[str, Any]]] = {}
    for entry in data["package"]:
        by_name.setdefault(normalise_name("pip", entry["name"]), []).append(entry)
    root = next((e for e in data["package"] if e.get("source", {}).get("editable") == "."), None)
    if root is None:
        msg = f"{path.name}: the project itself is not in the lock"
        raise AdvisoryCheckError(msg)

    def resolve(dependency: Mapping[str, Any]) -> dict[str, Any]:
        candidates = by_name.get(normalise_name("pip", dependency["name"]), [])
        if "version" in dependency:
            candidates = [c for c in candidates if c["version"] == dependency["version"]]
        if not candidates:
            msg = f"{path.name}: {dependency['name']} {dependency.get('version', '')} is not resolved in the lock"
            raise AdvisoryCheckError(msg)
        return candidates[0]

    roots = list(root.get("dependencies", []))
    for extra_dependencies in root.get("optional-dependencies", {}).values():
        roots.extend(extra_dependencies)
    direct = {id(found) for dependency in roots if (found := resolve(dependency)) is not root}

    seen: dict[tuple[str, str], dict[str, Any]] = {}
    visited_extras: set[tuple[str, str, str]] = set()
    todo = list(roots)
    while todo:
        dependency = todo.pop()
        found = resolve(dependency)
        if found is root:
            continue
        key = (found["name"], found["version"])
        if key not in seen:
            seen[key] = found
            todo.extend(found.get("dependencies", []))
        for extra in dependency.get("extra", []):
            if (*key, extra) not in visited_extras:
                visited_extras.add((*key, extra))
                todo.extend(found.get("optional-dependencies", {}).get(extra, []))
    if not seen:
        msg = f"{path.name}: no runtime dependencies found; has the format changed?"
        raise AdvisoryCheckError(msg)
    return sorted(
        (Package("pip", name, version, id(found) in direct, runtime=True) for (name, version), found in seen.items()),
        key=lambda p: (normalise_name("pip", p.name), p.version),
    )


def _unquote(text: str) -> tuple[str, str]:
    """Return the quoted or plain text at the start of `text` and what follows it."""
    if text[:1] in ("'", '"'):
        quote = text[0]
        end = text.index(quote, 1)
        return text[1:end], text[end + 1 :]
    key, _, rest = text.partition(":")
    return key, ":" + rest if _ else ""


def _yaml_entry(line: str) -> tuple[int, str, str]:
    """`(indent, key, value)` of one `key: value` line of the subset of YAML that pnpm writes."""
    stripped = line.lstrip(" ")
    indent = len(line) - len(stripped)
    stripped = stripped.rstrip()
    if stripped.startswith("? "):  # a key of more than 1,024 characters: `? 'key'`, the value on the next line
        return indent, _unquote(stripped[2:].strip())[0], ""
    key, rest = _unquote(stripped)
    value = rest[1:].strip() if rest.startswith(":") else ""
    return indent, key, value.strip("'\"")


def _pnpm_sections(text: str) -> dict[str, list[tuple[int, str, str]]]:
    sections: dict[str, list[tuple[int, str, str]]] = {}
    current: list[tuple[int, str, str]] | None = None
    for line in text.splitlines():
        stripped = line.lstrip(" ")
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" "):
            current = sections.setdefault(line.split(":", 1)[0], [])
        elif stripped == ":" or stripped.startswith(": "):
            # the value of a long key: `:` and the entries below it, or `: dependencies:` and the first entry
            rest = stripped[2:].strip()
            if current is not None and rest and rest != "{}":
                current.append(_yaml_entry(" " * (len(line) - len(stripped) + 2) + rest))
        elif current is not None and not stripped.startswith("- "):
            current.append(_yaml_entry(line))
    return sections


def _split_pnpm_key(key: str) -> tuple[str, str]:
    """`name@1.2.3(peer@4)` into `("name", "1.2.3")`, scoped names included."""
    without_peers = key.split("(", 1)[0]
    name, _, version = without_peers.rpartition("@")
    return name, version


def _pnpm_dependency(name: str, value: str) -> tuple[str, str, str] | None:
    """Return `(name, version, snapshot key)` of a dependency line, `(name, value, "")` for a git or URL one.

    `None` is what is no package of the registry and none of its own: a link, a file, a workspace package.
    """
    if value.startswith(("link:", "file:", "workspace:", "portal:")):
        return None
    if value.startswith(("git+", "git:", "github:", "http", "ssh:", "git@")):
        return name, value, ""
    if value[:1].isdigit():
        return name, value.split("(", 1)[0], f"{name}@{value}"
    real_name, real_version = _split_pnpm_key(value.removeprefix("npm:"))  # an alias: `name: real@1.2.3`
    return (real_name, real_version, value.removeprefix("npm:")) if real_name and real_version else None


def _pnpm_roots(entries: list[tuple[int, str, str]]) -> dict[tuple[str, str, str], bool]:
    """Return the dependencies the importers name, as `(name, version, snapshot key) -> runtime?`."""
    roots: dict[tuple[str, str, str], bool] = {}
    group = name = ""
    for indent, key, value in entries:
        if indent == 4:
            group = key
        elif indent == 6:
            name = key
        elif indent == 8 and key == "version" and group in ("dependencies", "optionalDependencies", "devDependencies"):
            parsed = _pnpm_dependency(name, value)
            if parsed is not None:
                roots[parsed] = roots.get(parsed, False) or group != "devDependencies"
    return roots


def _pnpm_snapshots(entries: list[tuple[int, str, str]]) -> dict[str, list[tuple[str, str]]]:
    """Return what each snapshot needs at runtime: `snapshot key -> [(name, value)]`."""
    snapshots: dict[str, list[tuple[str, str]]] = {}
    snapshot = ""
    in_dependencies = False
    for indent, key, value in entries:
        if indent == 2:
            snapshot, in_dependencies = key, False
            snapshots[snapshot] = []
        elif indent == 4:
            in_dependencies = key in ("dependencies", "optionalDependencies")
        elif indent == 6 and in_dependencies:
            snapshots[snapshot].append((key, value))
    return snapshots


def read_pnpm_lock(path: Path) -> list[Package]:
    """Read the direct dependencies (production and development) of the app, and the tree of the production ones.

    A lock of another version, no dependencies, and a package without its snapshot are errors, so that a changed
    format cannot shrink the list unnoticed. A git or URL dependency is listed with `foreign=True`.
    """
    text = path.read_text(encoding="utf-8")
    if not re.match(r"lockfileVersion: '?9\.", text):
        msg = f"{path.name}: only lockfile version 9 is read; has the format changed?"
        raise AdvisoryCheckError(msg)
    sections = _pnpm_sections(text)
    roots = _pnpm_roots(sections.get("importers", []))
    snapshots = _pnpm_snapshots(sections.get("snapshots", []))
    if not roots or not snapshots:
        msg = f"{path.name}: no dependencies found; has the format changed?"
        raise AdvisoryCheckError(msg)
    direct = {root[:2] for root in roots}
    packages: dict[tuple[str, str], bool] = {}  # (name, version) -> runtime?
    foreign: dict[tuple[str, str], bool] = {}
    for (name, version, key), runtime in roots.items():
        target = packages if key else foreign
        target[(name, version)] = target.get((name, version), False) or runtime
    todo = [root for root, runtime in roots.items() if runtime and root[2]]  # a development tree is not read
    visited: set[str] = set()
    while todo:
        snapshot_key = todo.pop()[2]
        if snapshot_key in visited:
            continue
        visited.add(snapshot_key)
        if snapshot_key not in snapshots:
            msg = f"{path.name}: no snapshot for {snapshot_key[:80]}; has the format changed?"
            raise AdvisoryCheckError(msg)
        for child_name, child_value in snapshots[snapshot_key]:
            parsed = _pnpm_dependency(child_name, child_value)
            if parsed is None:
                continue
            if parsed[2]:
                packages[parsed[:2]] = True
                todo.append(parsed)
            else:
                foreign[parsed[:2]] = True
    return sorted(
        [
            *(Package("npm", n, v, (n, v) in direct, runtime=r) for (n, v), r in packages.items()),
            *(Package("npm", n, v, (n, v) in direct, runtime=r, foreign=True) for (n, v), r in foreign.items()),
        ],
        key=lambda p: (p.name, p.version),
    )


# --------------------------------------------------------------------------------------------------------------------
# the sources
# --------------------------------------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Response:
    """What one request answered: the status, the headers and the decoded JSON (`None` if it was none)."""

    status: int
    headers: Mapping[str, str]
    body: Any


# the one door to the network: `(url, github=..., method=..., payload=...)`, replaced by the tests
Fetch = Callable[..., Response]


class _Redirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect, but never with the GitHub token to another host, and never a write."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,  # noqa: ANN401
        code: int,
        msg: str,
        headers: Any,  # noqa: ANN401
        newurl: str,
    ) -> urllib.request.Request | None:
        """Return the request to follow, or `None` to let the redirect be the answer."""
        if req.get_method() != "GET":
            return None
        if req.full_url.startswith(GITHUB_API) and not newurl.startswith(GITHUB_API):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_Redirects)


def _open(request: urllib.request.Request) -> Any:  # noqa: ANN401
    return _OPENER.open(request, timeout=30)


def _json(raw: bytes) -> object:
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def make_fetch(token: str | None) -> Fetch:  # noqa: C901
    """HTTP with retries of a transient failure; the token goes to the GitHub API and nowhere else."""

    def fetch(url: str, *, github: bool = False, method: str = "GET", payload: object = None) -> Response:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if github:
            if not url.startswith(GITHUB_API):
                msg = f"refusing to send the GitHub token to {url}"
                raise AdvisoryCheckError(msg)
            headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
            if token:
                headers["Authorization"] = f"Bearer {token}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310
        last = ""
        for attempt in range(RETRIES):
            try:
                with _open(request) as raw:
                    return Response(raw.status, dict(raw.headers), _json(raw.read()))
            except urllib.error.HTTPError as exc:
                if exc.code < 500:
                    return Response(exc.code, dict(exc.headers), _json(exc.read()))
                last = f"HTTP {exc.code}"
            except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
                last = type(exc).__name__
            if attempt < RETRIES - 1:
                time.sleep(2**attempt)
        msg = f"{url} could not be read ({last})"
        raise AdvisoryCheckError(msg)

    return fetch


def github_token() -> str | None:
    """Return the token of the job (`GITHUB_TOKEN`) or of a local `gh` login (none: 60 requests an hour)."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def raise_if_rate_limited(response: Response, url: str) -> None:
    """Raise `RateLimitError` for the answer of a used-up rate limit, which must never read as "nothing found"."""
    message = str((response.body or {}).get("message", "")) if isinstance(response.body, dict) else ""
    headers = {key.lower(): value for key, value in response.headers.items()}
    if response.status == 429 or (
        response.status == 403
        and (headers.get("x-ratelimit-remaining") == "0" or "rate limit" in message.lower() or "retry-after" in headers)
    ):
        msg = f"GitHub rate limit reached at {url}"
        raise RateLimitError(msg)


_GITHUB_URL = re.compile(
    r"^(?:git\+)?(?:(?:https?|git|ssh)://(?:git@)?|git@)?(?:www\.)?github\.com[/:]([^/\s]+)/([^/\s#?]+)",
    re.IGNORECASE | re.ASCII,
)
_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*)$", re.ASCII)
_REPO = re.compile(r"^[A-Za-z0-9._-]+$", re.ASCII)
_NOT_OWNERS = {"sponsors", "orgs", "apps", "marketplace", "features", "about", "settings", "topics", "collections"}
# labels of links that are about the project but are not its code: a link under one of them is not read
_SKIPPED_LABELS = (
    "conduct",
    "contribut",
    "security",
    "fund",
    "doc",
    "sponsor",
    "chang",
    "releas",
    "donat",
    "licen",
    "wiki",
    "blog",
    "support",
    "discuss",
)
_PREFERRED_LABELS = ("source", "repository", "repo", "code", "github", "homepage", "home")


def _repository_of(url: str) -> str | None:
    text = url.strip()
    if text.startswith("github:"):
        text = "github.com/" + text.removeprefix("github:")
    elif re.match(r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+$", text):  # npm shorthand `owner/repo`
        text = "github.com/" + text
    match = _GITHUB_URL.match(text)
    if not match:
        return None
    owner, repo = match.group(1), match.group(2).removesuffix(".git")
    if owner.lower() in _NOT_OWNERS or not _OWNER.match(owner) or not _REPO.match(repo):
        return None
    if repo in (".", "..", ".github") or repo.lower().endswith(".github.io"):
        return None
    return f"{owner}/{repo}"


def github_repository(urls: Iterable[tuple[str, str]], package: str | None = None) -> str | None:
    """Return `owner/repo` from the GitHub URLs of `(label, url)` pairs.

    Links under a label about conduct, contributing, security, funding or documentation are not read (labels are
    matched by word); the repository named like the package comes first, then labels like Source or Repository.
    """
    candidates: list[tuple[int, int, str]] = []
    for index, (label, url) in enumerate(urls):
        words = re.findall(r"[a-z]+", label.lower())
        if any(word.startswith(skipped) for word in words for skipped in _SKIPPED_LABELS):
            continue
        repo = _repository_of(url) if isinstance(url, str) else None
        if repo:
            rank = next((i for i, key in enumerate(_PREFERRED_LABELS) if key in words), len(_PREFERRED_LABELS))
            candidates.append((rank, index, repo))
    if not candidates:
        return None
    if package:
        wanted = normalise_name("pip", package.rsplit("/", 1)[-1])
        named = [c for c in sorted(candidates) if normalise_name("pip", c[2].split("/")[1]) == wanted]
        if named:
            return named[0][2]
    return min(candidates)[2]


def resolve_repository(fetch: Fetch, package: Package) -> str:
    """Return the GitHub repository of the locked version of a package, from the metadata of PyPI or npm.

    Only a version that is not there (404, 410, 451) or has no GitHub link is `Unreadable`; any other answer
    that is not a 200 with a JSON object stops the run.
    """
    name = urllib.parse.quote(package.name, safe="@")
    if package.ecosystem == "pip":
        url, source = f"https://pypi.org/pypi/{name}/{package.version}/json", "PyPI"
    else:
        url, source = f"https://registry.npmjs.org/{name}/{package.version}", "npm"
    response = fetch(url)
    if response.status in UNREADABLE_STATUSES:
        msg = f"{source} has no metadata for this version (HTTP {response.status})"
        raise Unreadable(msg)
    if response.status != 200 or not isinstance(response.body, dict):
        msg = f"{url} answered HTTP {response.status} and no metadata"
        raise AdvisoryCheckError(msg)
    body = response.body
    if package.ecosystem == "pip":
        info = body.get("info") if isinstance(body.get("info"), dict) else {}
        project_urls = info.get("project_urls") if isinstance(info.get("project_urls"), dict) else {}
        urls = [*project_urls.items(), ("home", info.get("home_page") or "")]
    else:
        repository, bugs = body.get("repository"), body.get("bugs")
        urls = [
            ("repository", repository.get("url", "") if isinstance(repository, dict) else repository or ""),
            ("home", body.get("homepage") or ""),
            ("bugs", bugs.get("url", "") if isinstance(bugs, dict) else bugs or ""),
        ]
    repo = github_repository(((str(label), url) for label, url in urls if isinstance(url, str)), package.name)
    if repo is None:
        msg = "no GitHub repository in the package metadata"
        raise Unreadable(msg)
    return repo


def read_repository_advisories(fetch: Fetch, repo: str) -> list[dict[str, Any]]:
    """Read every published advisory of a repository.

    A rate limit raises; so does any answer but a list. Only a repository that is not there is `Unreadable`.
    """
    advisories: list[dict[str, Any]] = []
    url: str | None = f"{GITHUB_API}repos/{repo}/security-advisories?state=published&per_page=100"
    for _ in range(MAX_PAGES):
        response = fetch(url, github=True)
        raise_if_rate_limited(response, url)
        if response.status in UNREADABLE_STATUSES:
            msg = f"the advisories of {repo} cannot be read (HTTP {response.status})"
            raise Unreadable(msg)
        if response.status != 200 or not isinstance(response.body, list):
            msg = f"{url} answered HTTP {response.status} and no list of advisories"
            raise AdvisoryCheckError(msg)
        advisories.extend(response.body)
        link = {key.lower(): value for key, value in response.headers.items()}.get("link", "")
        next_url = re.search(r'<([^>]+)>;\s*rel="next"', link)
        if not next_url or not next_url.group(1).startswith(GITHUB_API):
            return advisories
        url = next_url.group(1)
    msg = f"the advisories of {repo} run over {MAX_PAGES} pages"
    raise AdvisoryCheckError(msg)


def release_date(fetch: Fetch, package: Package, version: str) -> dt.datetime | None:
    """When a version was published (`None` if it cannot be told: the cooldown is then unknown, nothing fails)."""
    name = urllib.parse.quote(package.name, safe="@")
    try:
        if package.ecosystem == "pip":
            response = fetch(f"https://pypi.org/pypi/{name}/{version}/json")
            files = (response.body or {}).get("urls") if isinstance(response.body, dict) else None
            stamp = files[0]["upload_time_iso_8601"] if files else None
        else:
            response = fetch(f"https://registry.npmjs.org/{name}")
            stamp = ((response.body or {}).get("time") or {}).get(version) if isinstance(response.body, dict) else None
        return dt.datetime.fromisoformat(stamp) if stamp else None
    except (AdvisoryCheckError, KeyError, ValueError, AttributeError, TypeError, IndexError):
        return None


# --------------------------------------------------------------------------------------------------------------------
# the findings
# --------------------------------------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Finding:
    """One advisory against one locked package."""

    package: Package
    advisory: str
    severity: str
    fixed: str | None = None
    cooldown: str = "no fix yet"
    reason: str = ""  # why it is unclear
    repo: str = ""  # the repository the advisory was read in
    url: str = ""  # the advisory in that repository
    vulnerable: str = ""  # the range and the patched versions the advisory states for the package
    patched: str = ""


@dataclasses.dataclass(frozen=True)
class IgnoreEntry:
    """One entry of the list of advisories known not to affect us."""

    package: str
    advisory: str
    reason: str
    date: str
    vulnerable: str = ""  # `range`: the range the advisory stated when this was read
    patched: str = ""
    version: str = ""  # or: only this locked version

    def applies_to(self, finding: Finding) -> bool:
        """Whether the advisory still says what it said when this was read (or the locked version is the one)."""
        if self.version and self.version != finding.package.version:
            return False
        if self.vulnerable:
            return (finding.vulnerable, finding.patched) == (self.vulnerable, self.patched)
        return bool(self.version)


@dataclasses.dataclass
class Report:
    """The result of a reading."""

    checked: int = 0
    affected: list[Finding] = dataclasses.field(default_factory=list)
    unclear: list[Finding] = dataclasses.field(default_factory=list)
    closed: list[Finding] = dataclasses.field(default_factory=list)  # read as fixed: no upper bound, a fix named
    unreadable: list[tuple[Package, str]] = dataclasses.field(default_factory=list)
    ignored: list[tuple[Finding, IgnoreEntry]] = dataclasses.field(default_factory=list)
    stale: list[IgnoreEntry] = dataclasses.field(default_factory=list)
    changed: list[IgnoreEntry] = dataclasses.field(default_factory=list)  # the advisory changed since it was read
    expired: list[IgnoreEntry] = dataclasses.field(default_factory=list)  # old enough for a second look

    @property
    def fingerprint(self) -> str:
        """Return a hash of the affected and unclear findings, which tells a closed issue from a new finding."""
        lines = sorted(
            f"{kind}|{f.package.ecosystem}|{f.package.name}|{f.package.version}|{f.advisory}|{f.fixed}"
            for kind, findings in (("affected", self.affected), ("unclear", self.unclear))
            for f in findings
        )
        return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16]


def _ignore_key(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def load_ignore(path: Path) -> list[IgnoreEntry]:
    """Read the checked-in list of advisories known not to affect us.

    An entry names one package and one advisory (never a wildcard), the range and patched versions the advisory
    states or a locked version, a reason and a real date (not in the future is checked by `check`).
    """
    if not path.exists():
        return []
    entries = []
    for raw in tomllib.loads(path.read_text(encoding="utf-8")).get("ignore", []):
        fields = {key: str(raw.get(key, "")).strip() for key in ("package", "advisory", "reason", "date")}
        entry = IgnoreEntry(
            **fields,
            vulnerable=str(raw.get("range", "")).strip(),
            patched=str(raw.get("patched", "")).strip(),
            version=str(raw.get("version", "")).strip(),
        )
        if not entry.package or "*" in entry.package or not GHSA_ID.match(entry.advisory):
            msg = f"{path.name}: an entry names one package and one GHSA id, never a wildcard: {raw}"
            raise AdvisoryCheckError(msg)
        try:
            dt.date.fromisoformat(entry.date)
        except ValueError:
            msg = f"{path.name}: {entry.package} {entry.advisory} needs a reason and a date (YYYY-MM-DD)"
            raise AdvisoryCheckError(msg) from None
        if not entry.reason:
            msg = f"{path.name}: {entry.package} {entry.advisory} needs a reason and a date (YYYY-MM-DD)"
            raise AdvisoryCheckError(msg)
        if not entry.vulnerable and not entry.version:
            msg = f"{path.name}: {entry.package} {entry.advisory} needs the `range` the advisory states, or a `version`"
            raise AdvisoryCheckError(msg)
        entries.append(entry)
    return entries


def _severity(raw: object) -> str:
    return next((severity for severity in SEVERITIES if severity == raw), "unknown")


_ECOSYSTEMS = {"pip": "pip", "pypi": "pip", "npm": "npm"}


def _advisory_url(advisory: Mapping[str, Any], repo: str, ghsa: str) -> str:
    """Return the advisory in its repository: the `html_url` it states if it is that, else the one it must be."""
    expected = f"https://github.com/{repo}/security/advisories/{ghsa}"
    url = advisory.get("html_url")
    return url if isinstance(url, str) and url.lower() == expected.lower() else expected


def judge(  # noqa: C901
    package: Package, advisories: list[dict[str, Any]], repo: str
) -> tuple[list[Finding], list[Finding], list[Finding]]:
    """Return `(affected, unclear, closed)` of one package against the advisories of its repository.

    An entry that names the package under an ecosystem that is not given, an entry without a name or a package,
    and an advisory with an invalid id are unclear for every package of the repository, never dropped.
    """
    wanted = normalise_name(package.ecosystem, package.name)
    affected: dict[str, Finding] = {}
    unclear: dict[str, Finding] = {}
    closed: dict[str, Finding] = {}
    for advisory in advisories:
        if not isinstance(advisory, dict) or advisory.get("withdrawn_at"):
            continue
        raw_id = str(advisory.get("ghsa_id") or "")
        ghsa = raw_id if GHSA_ID.match(raw_id) else re.sub(r"[^\w-]", "?", raw_id)[:40] or "(no id)"
        severity = _severity(advisory.get("severity"))
        url = _advisory_url(advisory, repo, ghsa) if GHSA_ID.match(ghsa) else ""
        entries = advisory.get("vulnerabilities")
        mine: list[Mapping[str, Any]] = []
        reasons: list[str] = []
        for entry in entries if isinstance(entries, list) else [None]:
            named = entry.get("package") if isinstance(entry, dict) else None
            name = str(named.get("name") or "").strip() if isinstance(named, dict) else ""
            if not name:
                reasons.append("the advisory names no package or no name")
            elif normalise_name(package.ecosystem, name) == wanted:
                given = str(named.get("ecosystem") or "").strip().lower()
                if not given:
                    reasons.append("the ecosystem of the advisory is not given")
                elif _ECOSYSTEMS.get(given) == package.ecosystem:
                    mine.append(entry)
        base = {"repo": repo, "url": url}
        if not mine and not reasons:
            continue
        if not GHSA_ID.match(raw_id):
            unclear[ghsa] = Finding(package, ghsa, severity, reason="the advisory id is not valid", **base)
            continue
        if reasons:
            unclear[ghsa] = Finding(package, ghsa, severity, reason=reasons[0], **base)
        for entry in mine:
            vulnerable = str(entry.get("vulnerable_version_range") or "")
            patched = str(entry.get("patched_versions") or "")
            texts = {"vulnerable": vulnerable, "patched": patched, **base}
            try:
                verdict = assess(package.ecosystem, package.version, vulnerable, patched)
            except UnclearRange as exc:
                unclear.setdefault(ghsa, Finding(package, ghsa, severity, reason=str(exc), **texts))
                continue
            if verdict == "affected":
                fixed = first_fixed(package.ecosystem, package.version, patched)
                affected.setdefault(ghsa, Finding(package, ghsa, severity, fixed=fixed, **texts))
            elif verdict == "closed":
                closed.setdefault(ghsa, Finding(package, ghsa, severity, **texts))
    return (
        list(affected.values()),
        [f for ghsa, f in unclear.items() if ghsa not in affected],
        [f for ghsa, f in closed.items() if ghsa not in affected and ghsa not in unclear],
    )


def cooldown_status(published: dt.datetime | None, now: dt.datetime) -> str:
    """Return `past` once a release is old enough to be locked, else the day it will be (`unknown`: not told)."""
    if published is None:
        return "unknown"
    eligible = published + COOLDOWN
    return "past" if now >= eligible else f"from {eligible:%Y-%m-%d}"


def _read_sources(
    packages: list[Package], fetch: Fetch
) -> list[tuple[Package, str | None, list[dict[str, Any]] | str]]:
    """Return each package with its repository (`None`: none) and that repository's advisories or why not read.

    Raises `AdvisoryCheckError` where a source fails, so that an outage never reads as "nothing found".
    """

    def resolve(package: Package) -> tuple[str | None, str]:
        if package.foreign:
            return None, "not a package of the registry (a git or URL dependency)"
        try:
            return resolve_repository(fetch, package), ""
        except Unreadable as exc:
            return None, str(exc)

    def read(repo: str) -> list[dict[str, Any]] | str:
        try:
            return read_repository_advisories(fetch, repo)
        except Unreadable as exc:
            return str(exc)

    with concurrent.futures.ThreadPoolExecutor(WORKERS) as pool:
        resolved = list(pool.map(resolve, packages))
        repos = sorted({repo for repo, _ in resolved if repo})
        advisories = dict(zip(repos, pool.map(read, repos), strict=True))
    if packages and not repos:
        msg = "no package resolves to a GitHub repository"
        raise AdvisoryCheckError(msg)
    if repos and all(isinstance(found, str) for found in advisories.values()):
        msg = f"no repository's advisories could be read: {advisories[repos[0]]}"
        raise AdvisoryCheckError(msg)
    return [
        (package, repo, advisories[repo] if repo else reason)
        for package, (repo, reason) in zip(packages, resolved, strict=True)
    ]


def check(packages: list[Package], fetch: Fetch, ignore: list[IgnoreEntry], now: dt.datetime) -> Report:  # noqa: C901
    """Run the whole reading. Raises `AdvisoryCheckError` where a source fails (never answers "nothing found")."""
    report = Report(checked=len(packages))
    read_packages: set[str] = set()
    findings: list[tuple[str, Finding]] = []  # ("affected" | "unclear", finding)
    for package, repo, found in _read_sources(packages, fetch):
        if repo is None:
            report.unreadable.append((package, str(found)))
            continue
        if isinstance(found, str):
            report.unreadable.append((package, f"{repo}: {found}"))
            continue
        read_packages.add(_ignore_key(package.name))
        affected, unclear, closed = judge(package, found, repo)
        findings += [("affected", f) for f in affected] + [("unclear", f) for f in unclear]
        report.closed += closed

    ignore_by_key = {(_ignore_key(e.package), e.advisory): e for e in ignore}
    matched: set[tuple[str, str]] = set()
    changed: dict[tuple[str, str], IgnoreEntry] = {}
    for kind, finding in findings:
        key = (_ignore_key(finding.package.name), finding.advisory)
        entry = ignore_by_key.get(key)
        if entry is not None and entry.applies_to(finding):
            matched.add(key)
            report.ignored.append((finding, entry))
            continue
        if entry is not None:
            changed[key] = entry  # the advisory says something else than when it was read: reported again
        if kind == "unclear":
            report.unclear.append(finding)
        else:
            published = release_date(fetch, finding.package, finding.fixed) if finding.fixed else None
            cooldown = cooldown_status(published, now) if finding.fixed else "no fix yet"
            report.affected.append(dataclasses.replace(finding, cooldown=cooldown))
    report.changed = list(changed.values())
    report.stale = [
        e
        for e in ignore
        if (_ignore_key(e.package), e.advisory) not in matched
        and (_ignore_key(e.package), e.advisory) not in changed
        and _ignore_key(e.package) in read_packages
    ]
    report.expired = [e for e in ignore if now.date() - dt.date.fromisoformat(e.date) > IGNORE_REVIEW_AFTER]
    for entry in ignore:
        if dt.date.fromisoformat(entry.date) > now.date():
            msg = f"the ignore entry for {entry.package} {entry.advisory} is dated in the future ({entry.date})"
            raise AdvisoryCheckError(msg)

    def order(finding: Finding) -> tuple[str, str, str, str]:
        package = finding.package
        return package.ecosystem, package.name.lower(), package.version, finding.advisory

    for findings_list in (report.affected, report.unclear, report.closed):
        findings_list.sort(key=order)
    report.ignored.sort(key=lambda pair: order(pair[0]))
    report.unreadable.sort(key=lambda pair: (pair[0].ecosystem, pair[0].name.lower(), pair[0].version))
    return report


# --------------------------------------------------------------------------------------------------------------------
# the output
# --------------------------------------------------------------------------------------------------------------------


def _code(text: str, limit: int = 80) -> str:
    """Text as an inline code span: nothing in it is a mention, a link or markup."""
    cleaned = re.sub(r"[`\r\n\t]+", " ", str(text)).strip()
    return f"`{cleaned[:limit]}`"


def _scope(package: Package) -> str:
    where = "python" if package.ecosystem == "pip" else "app"
    kind = "direct" if package.direct else "transitive"
    return f"{where}, {kind}{'' if package.runtime else ', dev'}"


def _advisory_link(finding: Finding) -> str:
    """Return the advisory as a link to the page in its repository; an id that is none is only shown."""
    ghsa = finding.advisory
    url = finding.url
    if GHSA_ID.match(ghsa) and url.startswith("https://github.com/") and url.endswith(f"/security/advisories/{ghsa}"):
        return f"[{ghsa}]({url})"
    return _code(ghsa)


def render_table(report: Report) -> str:
    """Return the plain-text result, for a terminal."""
    lines = [f"{report.checked} locked packages read"]

    def table(title: str, header: list[str], rows: list[list[str]]) -> None:
        if not rows:
            return
        widths = [max(len(str(r[i])) for r in [header, *rows]) for i in range(len(header))]
        lines.extend(["", f"{title} ({len(rows)})"])
        for row in [header, *rows]:
            lines.append("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)).rstrip())

    table(
        "affected",
        ["package", "locked", "advisory", "severity", "fixed in", "cooldown", "scope", "repository"],
        [
            [
                f.package.name,
                f.package.version,
                f.advisory,
                f.severity,
                f.fixed or "none yet",
                f.cooldown,
                _scope(f.package),
                f.repo,
            ]
            for f in report.affected
        ],
    )
    table(
        "unclear",
        ["package", "locked", "advisory", "why", "repository"],
        [[f.package.name, f.package.version, f.advisory, f.reason, f.repo] for f in report.unclear],
    )
    table(
        "read as fixed: no upper bound in the range, and the advisory names a fix at or below the locked version",
        ["package", "locked", "advisory", "range", "patched", "repository"],
        [[f.package.name, f.package.version, f.advisory, f.vulnerable, f.patched, f.repo] for f in report.closed],
    )
    table(
        "unreadable",
        ["package", "locked", "why"],
        [[p.name, p.version, reason] for p, reason in report.unreadable],
    )
    table(
        "ignored (scripts/repo_advisories_ignore.toml)",
        ["package", "locked", "advisory", "since", "reason"],
        [[f.package.name, f.package.version, f.advisory, e.date, e.reason] for f, e in report.ignored],
    )
    table(
        "ignore entries whose advisory changed since they were written: read it again",
        ["package", "advisory", "since"],
        [[e.package, e.advisory, e.date] for e in report.changed],
    )
    table(
        "stale ignore entries (the advisory no longer matches the locked version)",
        ["package", "advisory", "since"],
        [[e.package, e.advisory, e.date] for e in report.stale],
    )
    table(
        f"ignore entries older than {IGNORE_REVIEW_AFTER.days} days: read them again",
        ["package", "advisory", "since"],
        [[e.package, e.advisory, e.date] for e in report.expired],
    )
    if not report.affected and not report.unclear:
        lines.extend(["", "nothing affected, nothing unclear"])
    return "\n".join(lines)


_VOLATILE = re.compile(r"Checked \d{4}-\d{2}-\d{2}, \d+ packages\.| Run: \S+")


def comparable(body: str) -> str:
    """Return the body without the date, the count and the run link, which differ in every run."""
    return _VOLATILE.sub("", body)


def _entry_line(finding: Finding) -> str:
    fields = [
        finding.package.ecosystem,
        finding.package.name,
        finding.package.version,
        finding.advisory,
        finding.severity,
        finding.fixed or "",
        finding.repo,
    ]
    return "|".join(urllib.parse.quote(field, safe="") for field in fields)


def previous_affected(body: str) -> list[Finding]:
    """Read the affected findings an earlier body listed (the hidden `affected` block)."""
    match = re.search(r"<!-- affected\n(.*?)\n-->", body or "", re.DOTALL)
    findings = []
    for line in match.group(1).splitlines() if match else []:
        fields = [urllib.parse.unquote(field) for field in line.split("|")]
        if len(fields) != 7 or fields[0] not in ("pip", "npm") or not GHSA_ID.match(fields[3]):
            continue
        ecosystem, name, version, ghsa, severity, fixed, repo = fields
        package = Package(ecosystem, name, version, direct=False, runtime=True)
        url = f"https://github.com/{repo}/security/advisories/{ghsa}" if repo else ""
        findings.append(
            Finding(
                package, ghsa, _severity(severity), fixed or None, "unknown (not readable this run)", repo=repo, url=url
            )
        )
    return findings


def carry_over(report: Report, previous_body: str) -> None:
    """Keep a package the open issue listed as affected in the list when it can no longer be read.

    An unreadable package is not a package that is safe: it stays until a reading says it is.
    """
    unreadable = {(p.ecosystem, p.name, p.version) for p, _ in report.unreadable}
    listed = {(f.package.ecosystem, f.package.name, f.package.version, f.advisory) for f in report.affected}
    for finding in previous_affected(previous_body):
        package = finding.package
        triple = (package.ecosystem, package.name, package.version)
        if triple in unreadable and (*triple, finding.advisory) not in listed:
            report.affected.append(finding)


def render_issue(report: Report, now: dt.datetime, run_url: str | None = None) -> str:
    """Return the body of the issue: public data only, names, versions and ranges as code, nobody mentioned."""
    parts = [ISSUE_MARKER, f"<!-- fingerprint: {report.fingerprint} -->"]
    if report.affected:
        parts += ["<!-- affected", *[_entry_line(f) for f in report.affected], "-->"]
    parts.append("")
    parts.append(
        "The published advisories in the repositories of the locked packages (`uv.lock`, `app/pnpm-lock.yaml`), "
        "read against the locked versions, since the global advisory database lists them later. "
        f"Checked {now:%Y-%m-%d}, {report.checked} packages."
    )
    if report.affected:
        parts += [
            "",
            f"## Affected ({len(report.affected)})",
            "",
            "| Package | Locked | Advisory | Severity | Fixed in | Past the cooldown | Scope | Repository |",
            "|---|---|---|---|---|---|---|---|",
        ]
        parts += [
            f"| {_code(f.package.name)} | {_code(f.package.version)} | {_advisory_link(f)} | {f.severity} "
            f"| {_code(f.fixed) if f.fixed else 'none yet'} | {f.cooldown} | {_scope(f.package)} | {_code(f.repo)} |"
            for f in report.affected
        ]
        parts += [
            "",
            (
                "Past the cooldown: the fixed version is old enough to be locked (3 days, `exclude-newer` and "
                "`minimumReleaseAge`); `from <date>` is the day it will be."
            ),
        ]
    else:
        parts += ["", "## Affected", "", "None now."]
    if report.unclear:
        parts += ["", f"## Unclear ({len(report.unclear)})", "", "Read by hand; none of these is assumed safe.", ""]
        parts += [
            f"- {_code(f.package.name)} {_code(f.package.version)}: {_advisory_link(f)}, {_code(f.reason, 160)}"
            for f in report.unclear
        ]
    if report.closed:
        parts += [
            "",
            f"## Read as fixed ({len(report.closed)})",
            "",
            (
                "The range has no upper bound and the advisory names a fix at or below the locked version, "
                "which is read as the end of the range."
            ),
            "",
        ]
        parts += [
            f"- {_code(f.package.name)} {_code(f.package.version)}: {_advisory_link(f)}, {_code(f.vulnerable, 120)}, "
            f"fixed in {_code(f.fixed or f.patched, 60)}"
            for f in report.closed
        ]
    if report.unreadable:
        parts += [
            "",
            f"## Unreadable ({len(report.unreadable)})",
            "",
            "No GitHub repository or no readable advisories: these are not checked.",
            "",
        ]
        parts += [f"- {_code(p.name)} {_code(p.version)}: {_code(reason, 120)}" for p, reason in report.unreadable]
    if report.ignored:
        parts += ["", f"## Known not to affect us ({len(report.ignored)})", ""]
        parts += [
            f"- {_code(f.package.name)} {_code(f.package.version)}: {_advisory_link(f)}, "
            f"{_code(e.reason, 300)} ({e.date})"
            for f, e in report.ignored
        ]
    for title, note, entries in (
        (
            "Ignore entries to read again",
            "The advisory says something else than when the entry was written.",
            report.changed,
        ),
        ("Ignore entries to remove", "The advisory no longer matches the locked version.", report.stale),
        (
            "Ignore entries to review",
            f"Written more than {IGNORE_REVIEW_AFTER.days} days ago.",
            report.expired,
        ),
    ):
        if entries:
            parts += ["", f"## {title}", "", note, ""]
            parts += [f"- {_code(e.package)} `{e.advisory}` ({e.date})" for e in entries]
    footer = (
        "This issue is updated by the weekly check while it is open; close it when it is dealt with. "
        "Advisories that do not affect us go to `scripts/repo_advisories_ignore.toml`."
    )
    if run_url:
        footer += f" Run: {run_url}"
    parts += ["", "---", footer, ""]
    return "\n".join(parts)


# --------------------------------------------------------------------------------------------------------------------
# the issue
# --------------------------------------------------------------------------------------------------------------------


def find_issues(fetch: Fetch, repo: str) -> list[dict[str, Any]]:
    """Return the issues of this check, newest first: the bot's, with the label, the title and the marker.

    Only an issue that `github-actions[bot]` created counts, so that nobody else can hold the title and turn
    the check off, or make it write into an issue of theirs.
    """
    creator = urllib.parse.quote(ISSUE_AUTHOR, safe="")
    label = urllib.parse.quote(ISSUE_LABELS[0], safe="")
    url = (
        f"{GITHUB_API}repos/{repo}/issues?creator={creator}&labels={label}&state=all"
        "&sort=created&direction=desc&per_page=100"
    )
    response = fetch(url, github=True)
    raise_if_rate_limited(response, url)
    if response.status != 200 or not isinstance(response.body, list):
        msg = f"the issues of {repo} cannot be listed (HTTP {response.status})"
        raise AdvisoryCheckError(msg)
    found = []
    for item in response.body:
        user = item.get("user") if isinstance(item, dict) else None
        if (
            isinstance(user, dict)
            and user.get("login") == ISSUE_AUTHOR
            and user.get("type") == "Bot"
            and item.get("title") == ISSUE_TITLE
            and ISSUE_MARKER in (item.get("body") or "")
            and "pull_request" not in item
        ):
            found.append(item)
    return found


def _fingerprint_of(body: str) -> str:
    match = re.search(r"fingerprint: ([0-9a-f]+) ", body or "")
    return match.group(1) if match else ""


def sync_issue(
    fetch: Fetch,
    repo: str,
    report: Report,
    body: str,
    *,
    dry_run: bool,
    issues: list[dict[str, Any]] | None = None,
) -> str:
    """Create or update the one issue; returns what was (or, in a dry run, would be) done.

    When the findings of an open issue change, its body is rewritten and one comment of a fixed text is added to
    it, so that the change is notified (the body of an issue is not).
    """
    issues = find_issues(fetch, repo) if issues is None else issues
    open_issue = next((i for i in issues if i.get("state") == "open"), None)
    findings = bool(report.affected or report.unclear)

    def write(method: str, url: str, payload: dict[str, Any]) -> None:
        response = fetch(url, github=True, method=method, payload=payload)
        raise_if_rate_limited(response, url)
        if response.status not in (200, 201):
            msg = f"{method} {url} failed (HTTP {response.status})"
            raise AdvisoryCheckError(msg)

    if open_issue is not None:
        number = open_issue["number"]
        old = open_issue.get("body") or ""
        if comparable(old) == comparable(body):
            return f"issue #{number} is up to date"
        changed = _fingerprint_of(old) != report.fingerprint
        if not dry_run:
            write("PATCH", f"{GITHUB_API}repos/{repo}/issues/{number}", {"body": body})
            if changed:
                write("POST", f"{GITHUB_API}repos/{repo}/issues/{number}/comments", {"body": CHANGED_COMMENT})
        verb = "would be updated" if dry_run else "updated"
        return (
            f"issue #{number} {verb}"
            + ("" if findings else " to none now")
            + (f" and {'would get' if dry_run else 'got'} a comment" if changed else "")
        )
    if not findings:
        return "nothing affected or unclear, no open issue: no issue"
    closed = issues[0] if issues else None
    if closed is not None and _fingerprint_of(closed.get("body") or "") == report.fingerprint:
        return f"closed issue #{closed['number']} holds the same findings: no new issue"
    if not dry_run:
        write(
            "POST",
            f"{GITHUB_API}repos/{repo}/issues",
            {"title": ISSUE_TITLE, "body": body, "labels": ISSUE_LABELS},
        )
    return f"issue {'would be created' if dry_run else 'created'}"


# --------------------------------------------------------------------------------------------------------------------
# the command line
# --------------------------------------------------------------------------------------------------------------------


def _issue_repository(option: str | None) -> str:
    repo = option or os.environ.get("GITHUB_REPOSITORY", "")
    if not re.match(r"^[\w.-]+/[\w.-]+$", repo):
        msg = "--issue needs --repo or GITHUB_REPOSITORY (owner/name)"
        raise AdvisoryCheckError(msg)
    return repo


def _run(args: argparse.Namespace, fetch: Fetch, now: dt.datetime) -> int:
    if args.issue and not args.dry_run and os.environ.get("GITHUB_ACTIONS") != "true":
        msg = "the issue is written by the workflow, under the bot's name; use --dry-run here"
        raise AdvisoryCheckError(msg)
    packages: list[Package] = []
    if args.only != "app":
        packages += read_uv_lock(args.uv_lock)
    if args.only != "python":
        packages += read_pnpm_lock(args.pnpm_lock)
    report = check(packages, fetch, load_ignore(args.ignore_file), now)
    if not args.issue:
        print(render_table(report))
        return 1 if report.affected or report.unclear else 0
    repo = _issue_repository(args.repo)
    issues = find_issues(fetch, repo)
    open_issue = next((i for i in issues if i.get("state") == "open"), None)
    if open_issue is not None:
        carry_over(report, open_issue.get("body") or "")
    print(render_table(report))
    run_id = os.environ.get("GITHUB_RUN_ID")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    body = render_issue(report, now, f"{server}/{repo}/actions/runs/{run_id}" if run_id else None)
    if args.dry_run:
        print(f"\n--- issue body ({ISSUE_TITLE})\n{body}")
    result = sync_issue(fetch, repo, report, body, dry_run=args.dry_run, issues=issues)
    print(f"\n{result}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and not args.dry_run:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(f"{body}\n\n{result}\n")
    return 0


def main(argv: list[str] | None = None, *, fetch: Fetch | None = None, now: dt.datetime | None = None) -> int:
    """Run the command line: exit 0 (nothing found, or the issue is filed), 1 (a table with findings), 2 (an error)."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--uv-lock", type=Path, default=UV_LOCK)
    parser.add_argument("--pnpm-lock", type=Path, default=PNPM_LOCK)
    parser.add_argument("--ignore-file", type=Path, default=IGNORE_FILE)
    parser.add_argument("--only", choices=["python", "app"], help="read one lock only")
    parser.add_argument(
        "--issue",
        action="store_true",
        help="file the result as the one issue of this check (only the workflow may write it; use --dry-run)",
    )
    parser.add_argument("--repo", help="the repository of the issue (owner/name); default $GITHUB_REPOSITORY")
    parser.add_argument("--dry-run", action="store_true", help="only print: read, and write nothing")
    args = parser.parse_args(argv)
    try:
        return _run(args, fetch or make_fetch(github_token()), now or dt.datetime.now(dt.UTC))
    except AdvisoryCheckError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

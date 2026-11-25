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
"unclear", a package without a readable GitHub repository is "unreadable", and a rate limit or an outage
of a source stops the run with an error (exit code 2) instead of answering "nothing found".

    uv run poe advisories                      # a table on stdout, exit 1 if something is affected or unclear
    uv run python scripts/repo_advisories.py --issue --dry-run   # what the weekly job would write
    uv run python scripts/repo_advisories.py --issue             # the weekly job: one issue, updated

The issue is found by its fixed title and a marker in its body, and is updated while it is open. It is
closed by a person; a closed issue is not opened again for the same findings, and findings that differ from
the ones it carries are a new issue. Nothing is assigned and nobody is mentioned: package names, versions and
ranges are written as code, and no text of an advisory is copied.

Known not to affect us: `scripts/repo_advisories_ignore.toml`, one entry per advisory and package, each with
a reason and a date (never a wildcard).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime as dt
import hashlib
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

from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parent.parent
UV_LOCK = ROOT / "uv.lock"
PNPM_LOCK = ROOT / "app" / "pnpm-lock.yaml"
IGNORE_FILE = Path(__file__).with_name("repo_advisories_ignore.toml")

# a release younger than this is refused by `exclude-newer` (pyproject.toml) and `minimumReleaseAge`
# (app/pnpm-workspace.yaml), so a fix this young cannot be locked yet
COOLDOWN = dt.timedelta(days=3)

ISSUE_TITLE = "security: dependencies behind advisories of their own repositories (scheduled check)"
ISSUE_MARKER = "<!-- repo-advisories-check -->"
ISSUE_LABELS = ["security"]
GITHUB_API = "https://api.github.com/"
USER_AGENT = "wetterdienst-advisory-check"
SEVERITIES = ("critical", "high", "medium", "low")
GHSA_ID = re.compile(r"^GHSA(-[2-9cfghjmpqrvwx]{4}){3}$")
WORKERS = 8
RETRIES = 3


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
    r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z.-]+)?$"
)


@dataclasses.dataclass(frozen=True, order=True)
class SemVer:
    """An npm version, ordered by the precedence of semver 2.0 (the build metadata does not count)."""

    key: tuple[Any, ...]
    text: str = dataclasses.field(compare=False)

    @classmethod
    def parse(cls, text: str) -> SemVer:
        """Parse a version; raises `InvalidVersion` for what is not one."""
        match = _SEMVER.match(text.strip())
        if not match:
            msg = f"not a semver version: {text!r}"
            raise InvalidVersion(msg)
        core = tuple(int(part) for part in match.groups()[:3])
        pre = match.group(4)
        identifiers = tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre.split(".")) if pre else ()
        # a release is above all of its pre-releases, and a numeric identifier is below an alphanumeric one
        return cls((core, 1, ()) if not pre else (core, 0, identifiers), text)

    def __str__(self) -> str:
        """Return the version as written."""
        return self.text


def parse_version(ecosystem: str, text: str) -> Version | SemVer:
    """Parse one version of `pip` (PEP 440) or `npm` (semver); anything else is unclear, not an error."""
    text = text.strip()
    try:
        return SemVer.parse(text) if ecosystem == "npm" else Version(text)
    except InvalidVersion as exc:
        msg = f"version {text!r} not understood"
        raise UnclearRange(msg) from exc


_OPERATOR = r"(?:<=|>=|==|!=|<|>|=)"
_HYPHEN = re.compile(r"^(\S+)\s+-\s+(\S+)$")
_COMPARATOR = re.compile(rf"^({_OPERATOR})?(\S+)$")
_PARTIAL = re.compile(r"^v?(\d+)(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?$")

Comparator = tuple[str, "Version | SemVer"]


def _compare(version: Version | SemVer, operator: str, bound: Version | SemVer) -> bool:
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

    `≤ 12.2.0`, `=< 2.3.0`, `0.15.0 and earlier`, `>=1.3.3 and <= 1.4.1`, `>=3.8.1<3.15.3` and a trailing
    `(all versions up to and including 2.1.12)`.
    """
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("≤", "<=").replace("≥", ">=").replace("=<", "<=").replace("=>", ">=")
    text = re.sub(r"(\S+)\s+(?:and|or)\s+(earlier|prior)\b", r"<= \1", text, flags=re.IGNORECASE)
    text = re.sub(r"(\S+)\s+(?:and|or)\s+later\b", r">= \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+and\s+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"(?<=[0-9a-zA-Z])(?=[<>])", " ", text)


def _filled(ecosystem: str, text: str) -> Version | SemVer:
    """Parse a version whose missing or `x` parts are zero: `10`, `9.1` and `4.x` as a lower bound or as `<`."""
    try:
        return parse_version(ecosystem, text)
    except UnclearRange:
        match = _PARTIAL.match(text)
        if not match:
            raise
        parts = [part if part and part not in "xX*" else "0" for part in match.groups()]
        return parse_version(ecosystem, ".".join(parts))


def _x_range(ecosystem: str, text: str) -> list[Comparator]:
    """Return the comparators of `11.0.x`, `4.x` or `10`: every version that starts with the given parts."""
    match = _PARTIAL.match(text)
    if not match:
        msg = f"version {text!r} not understood"
        raise UnclearRange(msg)
    given = [int(part) for part in match.groups() if part and part not in "xX*"]
    upper = [*given[:-1], given[-1] + 1]
    return [
        (">=", parse_version(ecosystem, ".".join(str(p) for p in [*given, 0, 0][:3]))),
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
        msg = f"range {segment!r} not understood"
        raise UnclearRange(msg)
    parsed = [(token.group(1), token.group(2)) for token in tokens if token]
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
            msg = f"range {segment!r} not understood"
            raise UnclearRange(msg)
        full = operator in ("<", ">=")  # where a missing part is zero exactly: `< 20`, `>= 9.1`
        comparators.append((operator, _filled(ecosystem, text) if full else parse_version(ecosystem, text)))
    return comparators


def parse_range(ecosystem: str, text: str | None) -> list[list[Comparator]]:
    """Parse a range into alternatives of comparators that all hold.

    Understood, as GitHub and the authors of advisories write them for PyPI and npm: `= 4.2.12`, `4.2.12`,
    `>= 4.5.0, <= 4.16.0`, `< 4.6.2`, `>=2,<=3.14.4`, `>=1.0.0 <2.0.0`, `7.2.0 - 12.3.0` (both ends
    included), `*`, `11.0.x`, `a || b`, `a; b`, `10 <10.2.1` (the bare version is the lower bound) and the
    spellings `≤ 12.2.0`, `=< 2.3.0`, `>=1.3.3 and <= 1.4.1`, `0.15.0 and earlier`, `>=3.8.1<3.15.3`.

    A comma between single comparators is "and" (`>= 4.5.0, <= 4.16.0`); a comma between segments that hold a
    range each (`<1.1.17, >= 2.0.0 < 2.1.3, 4.0.0 - 5.0.7`) is "or", since the "and" of them is empty.
    Everything else (`^`, `~`, `~=`, `all`, an empty range) raises `UnclearRange`.
    """
    if text is None or not text.strip():
        msg = "no range"
        raise UnclearRange(msg)
    alternatives: list[list[Comparator]] = []
    for alternative in re.split(r"\|\||;", _normalise(text)):
        if not alternative.strip():
            msg = f"empty range in {text!r}"
            raise UnclearRange(msg)
        segments = [_segment(ecosystem, segment) for segment in alternative.split(",")]
        if all(len(segment) <= 1 for segment in segments):
            alternatives.append([comparator for segment in segments for comparator in segment])
        else:
            alternatives.extend(segments)
    return alternatives


def in_range(ecosystem: str, version: str, text: str | None) -> bool:
    """Whether `version` is in the range `text`. Raises `UnclearRange` for what it does not understand."""
    installed = parse_version(ecosystem, version)
    return any(
        all(_compare(installed, operator, bound) for operator, bound in comparators)
        for comparators in parse_range(ecosystem, text)
    )


def _has_upper_bound(comparators: list[Comparator]) -> bool:
    return any(operator in ("<", "<=", "=", "==") for operator, _ in comparators)


_PATCHED_SEPARATOR = re.compile(r",|;|\|\|")


def _fixes(ecosystem: str, patched: str | None) -> list[tuple[Version | SemVer, str]]:
    """Return the versions an advisory's `patched_versions` names (`0.17.1`, `4.2.4, 3.1.1`, `>= 6.21.2`)."""
    if not patched or patched.strip().lower() == "none":
        return []
    fixes: list[tuple[Version | SemVer, str]] = []
    for raw in _PATCHED_SEPARATOR.split(patched):
        entry = raw.strip()
        text = entry.removeprefix(">=").strip() if entry.startswith(">=") else entry
        if re.match(r"^[0-9v]", text):
            try:
                fixes.append((parse_version(ecosystem, text), text))
            except UnclearRange:
                continue
    return fixes


def patched_matches(ecosystem: str, version: str, patched: str | None) -> bool:
    """Whether `version` is one of the `patched_versions` of an advisory (never a guess: unparsable is `False`).

    GitHub writes them as a version (`0.17.1`), a list (`4.2.4, 3.1.1`) or a range (`>= 6.21.2`), also
    mixed (`>= 1.15.6, >= 2.0.1-rc.15`): each entry is read on its own.
    """
    if not patched or patched.strip().lower() == "none":
        return False
    for entry in _PATCHED_SEPARATOR.split(patched):
        try:
            if entry.strip() and in_range(ecosystem, version, entry):
                return True
        except UnclearRange:
            continue
    return False


def first_fixed(ecosystem: str, version: str, patched: str | None) -> str | None:
    """Return the lowest patched version above the installed one, as the advisory writes it (`None`: none yet)."""
    installed = parse_version(ecosystem, version)
    above = sorted(fix for fix in _fixes(ecosystem, patched) if fix[0] > installed)
    return above[0][1] if above else None


def is_affected(ecosystem: str, version: str, vulnerable: str | None, patched: str | None) -> bool:
    """Whether the locked `version` is in the vulnerable range of one entry of an advisory.

    An installed version that is one of the patched ones is not affected, whatever the range says. So is one
    that holds a range without an upper bound (`>= 4.5.0`) and is at or above a fix the entry names (4.6.2):
    a fix and "every later version is affected" cannot both be meant, and the fix is taken as the end of the
    range, as the entries of the advisory database are read by hand. A range without an upper bound and
    without a fix is affected. Raises `UnclearRange` for a range or a version that is not understood.
    """
    installed = parse_version(ecosystem, version)
    holding = [c for c in parse_range(ecosystem, vulnerable) if all(_compare(installed, op, b) for op, b in c)]
    if not holding or patched_matches(ecosystem, version, patched):
        return False
    fixes = _fixes(ecosystem, patched)
    return not (fixes and installed >= min(fixes)[0] and not any(map(_has_upper_bound, holding)))


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

    @property
    def label(self) -> str:
        """Return `name version`."""
        return f"{self.name} {self.version}"


def normalise_name(ecosystem: str, name: str) -> str:
    """Return the name as the registry compares it (PEP 503 on PyPI, lower case on npm)."""
    return re.sub(r"[-_.]+", "-", name).lower() if ecosystem == "pip" else name.lower()


def read_uv_lock(path: Path) -> list[Package]:
    """Read the packages `pyproject.toml` needs at runtime: the dependencies and every extra, and what they need.

    Markers are not evaluated: a package that a platform or Python version leaves out is listed too.
    """
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    by_name: dict[str, list[dict[str, Any]]] = {}
    for entry in data["package"]:
        by_name.setdefault(normalise_name("pip", entry["name"]), []).append(entry)
    root = next(entry for entry in data["package"] if entry.get("source", {}).get("editable") == ".")

    def resolve(dependency: Mapping[str, Any]) -> dict[str, Any] | None:
        candidates = by_name.get(normalise_name("pip", dependency["name"]), [])
        if "version" in dependency:
            candidates = [c for c in candidates if c["version"] == dependency["version"]]
        return candidates[0] if candidates else None

    roots = list(root.get("dependencies", []))
    for extra_dependencies in root.get("optional-dependencies", {}).values():
        roots.extend(extra_dependencies)
    direct = {id(found) for dependency in roots if (found := resolve(dependency)) is not None}

    seen: dict[tuple[str, str], dict[str, Any]] = {}
    visited_extras: set[tuple[str, str, str]] = set()
    todo = list(roots)
    while todo:
        dependency = todo.pop()
        found = resolve(dependency)
        if found is None or found is root:
            continue
        key = (found["name"], found["version"])
        if key not in seen:
            seen[key] = found
            todo.extend(found.get("dependencies", []))
        for extra in dependency.get("extra", []):
            if (*key, extra) not in visited_extras:
                visited_extras.add((*key, extra))
                todo.extend(found.get("optional-dependencies", {}).get(extra, []))
    return sorted(
        (Package("pip", name, version, id(found) in direct, runtime=True) for (name, version), found in seen.items()),
        key=lambda p: (normalise_name("pip", p.name), p.version),
    )


def _yaml_entry(line: str) -> tuple[int, str, str]:
    """`(indent, key, value)` of one `key: value` line of the subset of YAML that pnpm writes."""
    stripped = line.lstrip(" ")
    indent = len(line) - len(stripped)
    stripped = stripped.rstrip()
    if stripped[:1] in ("'", '"'):
        quote = stripped[0]
        end = stripped.index(quote, 1)
        key, rest = stripped[1:end], stripped[end + 1 :]
        value = rest[1:].strip() if rest.startswith(":") else ""
    else:
        key, _, value = stripped.partition(":")
        value = value.strip()
    return indent, key, value.strip("'\"")


def _pnpm_sections(text: str) -> dict[str, list[tuple[int, str, str]]]:
    sections: dict[str, list[tuple[int, str, str]]] = {}
    current: list[tuple[int, str, str]] | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            key = line.split(":", 1)[0]
            current = sections.setdefault(key, [])
        elif current is not None and not line.lstrip().startswith("- "):
            current.append(_yaml_entry(line))
    return sections


def _split_pnpm_key(key: str) -> tuple[str, str]:
    """`name@1.2.3(peer@4)` into `("name", "1.2.3")`, scoped names included."""
    without_peers = key.split("(", 1)[0]
    name, _, version = without_peers.rpartition("@")
    return name, version


def _pnpm_dependency(name: str, value: str) -> tuple[str, str, str] | None:
    """`(name, version, snapshot key)` of a dependency line; `None` for what is no registry package."""
    if value.startswith(("link:", "file:", "workspace:", "git+", "http")):
        return None
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
    """Read the direct dependencies (production and development) of the app, and the tree of the production ones."""
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
    for (name, version, _), runtime in roots.items():
        packages[(name, version)] = packages.get((name, version), False) or runtime
    todo = [root for root, runtime in roots.items() if runtime]  # the tree of a development dependency is not read
    visited: set[str] = set()
    while todo:
        snapshot_key = todo.pop()[2]
        if snapshot_key in visited:
            continue
        visited.add(snapshot_key)
        for child_name, child_value in snapshots.get(snapshot_key, []):
            parsed = _pnpm_dependency(child_name, child_value)
            if parsed is not None:
                packages[parsed[:2]] = True
                todo.append(parsed)
    return sorted(
        (Package("npm", n, v, (n, v) in direct, runtime=runtime) for (n, v), runtime in packages.items()),
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


def make_fetch(token: str | None) -> Fetch:
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
                with urllib.request.urlopen(request, timeout=30) as raw:  # noqa: S310
                    return Response(raw.status, dict(raw.headers), _json(raw.read()))
            except urllib.error.HTTPError as exc:
                if exc.code < 500:
                    return Response(exc.code, dict(exc.headers), _json(exc.read()))
                last = f"HTTP {exc.code}"
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = type(exc).__name__
            time.sleep(2**attempt)
        msg = f"{url} could not be read ({last})"
        raise AdvisoryCheckError(msg)

    return fetch


def _json(raw: bytes) -> object:
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


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


_GITHUB_REPOSITORY = re.compile(r"github\.com[/:]([\w.-]+)/([\w.-]+)", re.IGNORECASE)
_NOT_OWNERS = {"sponsors", "orgs", "apps", "marketplace", "features", "about"}
_URL_KEYS = ("source", "repository", "code", "github", "homepage", "home")


def github_repository(urls: Iterable[tuple[str, str]]) -> str | None:
    """Return `owner/repo` from the first GitHub URL of `(label, url)` pairs; Source-like labels come first."""
    ranked = sorted(
        enumerate(urls),
        key=lambda item: (
            next((i for i, key in enumerate(_URL_KEYS) if key in item[1][0].lower()), len(_URL_KEYS)),
            item[0],
        ),
    )
    for _, (_, url) in ranked:
        text = url.strip()
        if text.startswith("github:"):
            text = "github.com/" + text.removeprefix("github:")
        elif re.match(r"^[\w.-]+/[\w.-]+$", text):  # npm shorthand `owner/repo`
            text = "github.com/" + text
        match = _GITHUB_REPOSITORY.search(text)
        if match and match.group(1).lower() not in _NOT_OWNERS:
            return f"{match.group(1)}/{match.group(2).removesuffix('.git')}"
    return None


def resolve_repository(fetch: Fetch, package: Package) -> str:
    """Return the GitHub repository of the locked version of a package, from the metadata of PyPI or npm."""
    name = urllib.parse.quote(package.name, safe="@")
    if package.ecosystem == "pip":
        response = fetch(f"https://pypi.org/pypi/{name}/{package.version}/json")
        if response.status != 200 or not isinstance(response.body, dict):
            msg = f"PyPI has no metadata for this version (HTTP {response.status})"
            raise Unreadable(msg)
        info = response.body.get("info") or {}
        urls = [*(info.get("project_urls") or {}).items(), ("home", info.get("home_page") or "")]
    else:
        response = fetch(f"https://registry.npmjs.org/{name}/{package.version}")
        if response.status != 200 or not isinstance(response.body, dict):
            msg = f"npm has no metadata for this version (HTTP {response.status})"
            raise Unreadable(msg)
        body = response.body
        repository, bugs = body.get("repository"), body.get("bugs")
        urls = [
            ("repository", repository.get("url", "") if isinstance(repository, dict) else repository or ""),
            ("home", body.get("homepage") or ""),
            ("bugs", bugs.get("url", "") if isinstance(bugs, dict) else bugs or ""),
        ]
    repo = github_repository((label, url) for label, url in urls if isinstance(url, str))
    if repo is None:
        msg = "no GitHub repository in the package metadata"
        raise Unreadable(msg)
    return repo


def read_repository_advisories(fetch: Fetch, repo: str) -> list[dict[str, Any]]:
    """Read every published advisory of a repository; a rate limit raises, a repository not found is `Unreadable`."""
    advisories: list[dict[str, Any]] = []
    url: str | None = f"{GITHUB_API}repos/{repo}/security-advisories?state=published&per_page=100"
    for _ in range(20):
        response = fetch(url, github=True)
        raise_if_rate_limited(response, url)
        if response.status != 200 or not isinstance(response.body, list):
            msg = f"the advisories of {repo} cannot be read (HTTP {response.status})"
            raise Unreadable(msg)
        advisories.extend(response.body)
        link = {key.lower(): value for key, value in response.headers.items()}.get("link", "")
        next_url = re.search(r'<([^>]+)>;\s*rel="next"', link)
        if not next_url or not next_url.group(1).startswith(GITHUB_API):
            return advisories
        url = next_url.group(1)
    msg = f"the advisories of {repo} run over 20 pages"
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
    except (AdvisoryCheckError, KeyError, ValueError, AttributeError, TypeError):
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
    reason: str = ""  # why it is unclear, or why it is ignored


@dataclasses.dataclass(frozen=True)
class IgnoreEntry:
    """One entry of the list of advisories known not to affect us."""

    package: str
    advisory: str
    reason: str
    date: str


@dataclasses.dataclass
class Report:
    """The result of a reading."""

    checked: int = 0
    affected: list[Finding] = dataclasses.field(default_factory=list)
    unclear: list[Finding] = dataclasses.field(default_factory=list)
    unreadable: list[tuple[Package, str]] = dataclasses.field(default_factory=list)
    ignored: list[tuple[Finding, IgnoreEntry]] = dataclasses.field(default_factory=list)
    stale: list[IgnoreEntry] = dataclasses.field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        """Return a hash of the affected and unclear findings, which tells a closed issue from a new finding."""
        lines = sorted(
            f"{kind}|{f.package.ecosystem}|{f.package.name}|{f.package.version}|{f.advisory}"
            for kind, findings in (("affected", self.affected), ("unclear", self.unclear))
            for f in findings
        )
        return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16]


def _ignore_key(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def load_ignore(path: Path) -> list[IgnoreEntry]:
    """Read the checked-in list of advisories known not to affect us; a wildcard, no reason or no date is an error."""
    if not path.exists():
        return []
    entries = []
    for raw in tomllib.loads(path.read_text(encoding="utf-8")).get("ignore", []):
        entry = IgnoreEntry(*(str(raw.get(key, "")).strip() for key in ("package", "advisory", "reason", "date")))
        if not entry.package or "*" in entry.package or not GHSA_ID.match(entry.advisory):
            msg = f"{path.name}: an entry names one package and one GHSA id, never a wildcard: {raw}"
            raise AdvisoryCheckError(msg)
        if not entry.reason or not re.match(r"^\d{4}-\d{2}-\d{2}$", entry.date):
            msg = f"{path.name}: {entry.package} {entry.advisory} needs a reason and a date (YYYY-MM-DD)"
            raise AdvisoryCheckError(msg)
        entries.append(entry)
    return entries


def _severity(raw: object) -> str:
    return next((severity for severity in SEVERITIES if severity == raw), "unknown")


def judge(package: Package, advisories: list[dict[str, Any]], repo: str) -> tuple[list[Finding], list[Finding]]:
    """`(affected, unclear)` of one package against the advisories of its repository."""
    affected: dict[str, Finding] = {}
    unclear: dict[str, Finding] = {}
    wanted = normalise_name(package.ecosystem, package.name)
    for advisory in advisories:
        ghsa = str(advisory.get("ghsa_id", ""))
        if advisory.get("withdrawn_at") or not GHSA_ID.match(ghsa):
            continue
        severity = _severity(advisory.get("severity"))
        entries = advisory.get("vulnerabilities") or []
        mine = [
            v
            for v in entries
            if (v.get("package") or {}).get("ecosystem", "").lower() == package.ecosystem
            and normalise_name(package.ecosystem, (v.get("package") or {}).get("name", "")) == wanted
        ]
        if not mine:
            # an advisory that names no package at all might be about the one this repository is named for
            if not any(v.get("package") for v in entries) and wanted == normalise_name(
                package.ecosystem, repo.split("/")[1]
            ):
                unclear[ghsa] = Finding(package, ghsa, severity, reason="the advisory names no package")
            continue
        for entry in mine:
            vulnerable, patched = entry.get("vulnerable_version_range"), entry.get("patched_versions")
            try:
                if is_affected(package.ecosystem, package.version, vulnerable, patched):
                    affected[ghsa] = Finding(
                        package, ghsa, severity, fixed=first_fixed(package.ecosystem, package.version, patched)
                    )
            except UnclearRange as exc:
                unclear.setdefault(ghsa, Finding(package, ghsa, severity, reason=str(exc)))
    return list(affected.values()), [f for ghsa, f in unclear.items() if ghsa not in affected]


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
    if repos and all(isinstance(found, str) for found in advisories.values()):
        msg = f"no repository's advisories could be read: {advisories[repos[0]]}"
        raise AdvisoryCheckError(msg)
    return [
        (package, repo, advisories[repo] if repo else reason)
        for package, (repo, reason) in zip(packages, resolved, strict=True)
    ]


def check(packages: list[Package], fetch: Fetch, ignore: list[IgnoreEntry], now: dt.datetime) -> Report:
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
        affected, unclear = judge(package, found, repo)
        findings += [("affected", f) for f in affected] + [("unclear", f) for f in unclear]

    ignore_by_key = {(_ignore_key(e.package), e.advisory): e for e in ignore}
    matched: set[tuple[str, str]] = set()
    for kind, finding in findings:
        key = (_ignore_key(finding.package.name), finding.advisory)
        if key in ignore_by_key:
            matched.add(key)
            report.ignored.append((finding, ignore_by_key[key]))
        elif kind == "unclear":
            report.unclear.append(finding)
        else:
            published = release_date(fetch, finding.package, finding.fixed) if finding.fixed else None
            cooldown = cooldown_status(published, now) if finding.fixed else "no fix yet"
            report.affected.append(dataclasses.replace(finding, cooldown=cooldown))
    report.stale = [
        e
        for e in ignore
        if (_ignore_key(e.package), e.advisory) not in matched and _ignore_key(e.package) in read_packages
    ]

    def order(finding: Finding) -> tuple[str, str, str, str]:
        package = finding.package
        return package.ecosystem, package.name.lower(), package.version, finding.advisory

    report.affected.sort(key=order)
    report.unclear.sort(key=order)
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


def _advisory_link(ghsa: str) -> str:
    return f"[{ghsa}](https://github.com/advisories/{ghsa})" if GHSA_ID.match(ghsa) else _code(ghsa)


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
        ["package", "locked", "advisory", "severity", "fixed in", "cooldown", "scope"],
        [
            [
                f.package.name,
                f.package.version,
                f.advisory,
                f.severity,
                f.fixed or "none yet",
                f.cooldown,
                _scope(f.package),
            ]
            for f in report.affected
        ],
    )
    table(
        "unclear",
        ["package", "locked", "advisory", "why"],
        [[f.package.name, f.package.version, f.advisory, f.reason] for f in report.unclear],
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
        "stale ignore entries (the advisory no longer matches the locked version)",
        ["package", "advisory", "since"],
        [[e.package, e.advisory, e.date] for e in report.stale],
    )
    if not report.affected and not report.unclear:
        lines.extend(["", "nothing affected, nothing unclear"])
    return "\n".join(lines)


def render_issue(report: Report, now: dt.datetime, run_url: str | None = None) -> str:
    """Return the body of the issue: public data only, names, versions and ranges as code, nobody mentioned."""
    parts = [ISSUE_MARKER, f"<!-- fingerprint: {report.fingerprint} -->", ""]
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
            "| Package | Locked | Advisory | Severity | Fixed in | Past the cooldown | Scope |",
            "|---|---|---|---|---|---|---|",
        ]
        parts += [
            f"| {_code(f.package.name)} | {_code(f.package.version)} | {_advisory_link(f.advisory)} | {f.severity} "
            f"| {_code(f.fixed) if f.fixed else 'none yet'} | {f.cooldown} | {_scope(f.package)} |"
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
            f"- {_code(f.package.name)} {_code(f.package.version)}: {_advisory_link(f.advisory)}, "
            f"{_code(f.reason, 160)}"
            for f in report.unclear
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
            f"- {_code(f.package.name)} {_code(f.package.version)}: {_advisory_link(f.advisory)}, "
            f"{_code(e.reason, 200)} ({e.date})"
            for f, e in report.ignored
        ]
    if report.stale:
        parts += ["", "## Ignore entries to remove", "", "The advisory no longer matches the locked version.", ""]
        parts += [f"- {_code(e.package)}: {_advisory_link(e.advisory)} ({e.date})" for e in report.stale]
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
    """Return the issues of this check (title and marker), newest first."""
    query = urllib.parse.quote(f'repo:{repo} is:issue in:title "{ISSUE_TITLE}"')
    url = f"{GITHUB_API}search/issues?q={query}&sort=created&order=desc&per_page=30"
    response = fetch(url, github=True)
    raise_if_rate_limited(response, url)
    if response.status != 200 or not isinstance(response.body, dict):
        msg = f"the issues of {repo} cannot be searched (HTTP {response.status})"
        raise AdvisoryCheckError(msg)
    return [
        item
        for item in response.body.get("items", [])
        if item.get("title") == ISSUE_TITLE and ISSUE_MARKER in (item.get("body") or "") and "pull_request" not in item
    ]


def sync_issue(fetch: Fetch, repo: str, report: Report, body: str, *, dry_run: bool) -> str:
    """Create or update the one issue; returns what was (or, in a dry run, would be) done."""
    issues = find_issues(fetch, repo)
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
        if open_issue.get("body") == body:
            return f"issue #{number} is up to date"
        if not dry_run:
            write("PATCH", f"{GITHUB_API}repos/{repo}/issues/{number}", {"body": body})
        return f"issue #{number} {'would be updated' if dry_run else 'updated'}" + ("" if findings else " to none now")
    if not findings:
        return "nothing affected or unclear, no open issue: no issue"
    closed = issues[0] if issues else None
    if closed is not None and f"fingerprint: {report.fingerprint} " in (closed.get("body") or ""):
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
    packages: list[Package] = []
    if args.only != "app":
        packages += read_uv_lock(args.uv_lock)
    if args.only != "python":
        packages += read_pnpm_lock(args.pnpm_lock)
    report = check(packages, fetch, load_ignore(args.ignore_file), now)
    print(render_table(report))
    if not args.issue:
        return 1 if report.affected or report.unclear else 0
    repo = _issue_repository(args.repo)
    run_id = os.environ.get("GITHUB_RUN_ID")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    body = render_issue(report, now, f"{server}/{repo}/actions/runs/{run_id}" if run_id else None)
    if args.dry_run:
        print(f"\n--- issue body ({ISSUE_TITLE})\n{body}")
    result = sync_issue(fetch, repo, report, body, dry_run=args.dry_run)
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
        help="file the result as the one issue of this check, in the repository of $GITHUB_REPOSITORY",
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

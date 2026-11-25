# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for `scripts/repo_advisories.py`, the check of the advisories the packages publish in their own repositories.

Offline: every answer is replayed from `tests/scripts/recorded` (real answers of PyPI, npm and the GitHub API of
2026-11-25, cut down to the fields the script reads) or written in the test. The fake network refuses any URL
nobody gave it an answer for.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import pytest

if TYPE_CHECKING:
    from types import ModuleType

SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "repo_advisories.py"
RECORDED = Path(__file__).parent / "recorded"
NOW = dt.datetime(2026, 11, 25, 12, 0, tzinfo=dt.UTC)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("repo_advisories", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["repo_advisories"] = module
    spec.loader.exec_module(module)
    return module


ra = _load()


def recorded(name: str) -> Any:  # noqa: ANN401
    """Return a recorded answer."""
    return json.loads((RECORDED / name).read_text(encoding="utf-8"))


class FakeNet:
    """The one door to the network, answering from a table and noting every request."""

    def __init__(self, routes: dict[str, Any]) -> None:
        """Answer from `routes`, which maps a URL to an answer or to a function of the method and the payload."""
        self.routes = routes
        self.requests: list[tuple[str, str]] = []

    def __call__(self, url: str, *, github: bool = False, method: str = "GET", payload: Any = None) -> Any:  # noqa: ANN401, ARG002
        """Answer one request."""
        self.requests.append((method, url))
        answer = self.routes[url]  # a KeyError is a request nobody expected
        return answer(method, payload) if callable(answer) else answer

    @property
    def writes(self) -> list[tuple[str, str]]:
        """Return the requests that are not reads."""
        return [request for request in self.requests if request[0] != "GET"]


def ok(body: Any, **headers: str) -> Any:  # noqa: ANN401
    """Return a 200 answer."""
    return ra.Response(200, headers, body)


def status(code: int, body: Any = None, **headers: str) -> Any:  # noqa: ANN401
    """Return an answer with a status."""
    return ra.Response(code, headers, body)


def advisories_url(repo: str) -> str:
    """Return the URL of the published advisories of a repository."""
    return f"{ra.GITHUB_API}repos/{repo}/security-advisories?state=published&per_page=100"


def search_url() -> str:
    """Return the URL of the search for the issue of the check in `owner/repo`."""
    query = ra.urllib.parse.quote(f'repo:owner/repo is:issue in:title "{ra.ISSUE_TITLE}"')
    return f"{ra.GITHUB_API}search/issues?q={query}&sort=created&order=desc&per_page=30"


def pkg(name: str, version: str, ecosystem: str = "pip", *, direct: bool = True, runtime: bool = True) -> Any:  # noqa: ANN401
    """Return a locked package."""
    return ra.Package(ecosystem, name, version, direct, runtime)


# --------------------------------------------------------------------------------------------------------------------
# the comparer
# --------------------------------------------------------------------------------------------------------------------

# (ecosystem, installed, vulnerable range as GitHub or the author wrote it, patched versions, affected?)
AFFECTED = [
    # the forms GitHub writes
    ("pip", "4.2.12", "= 4.2.12", "4.3.0", True),
    ("pip", "4.2.13", "= 4.2.12", "4.3.0", False),
    ("pip", "4.15.1", ">= 4.5.0, <= 4.16.0", None, True),
    ("pip", "4.16.1", ">= 4.5.0, <= 4.16.0", None, False),
    ("pip", "4.4.9", ">= 4.5.0, <= 4.16.0", None, False),
    ("pip", "4.16.0", ">= 4.5.0, <= 4.16.0", None, True),
    ("pip", "4.6.1", "< 4.6.2", "4.6.2", True),
    ("pip", "4.6.2", "< 4.6.2", "4.6.2", False),
    ("pip", "3.14.4", ">=2,<=3.14.4", None, True),
    ("pip", "3.14.5", ">=2,<=3.14.4", None, False),
    ("npm", "12.3.0", "7.2.0 - 12.3.0", None, True),
    ("npm", "7.2.0", "7.2.0 - 12.3.0", None, True),
    ("npm", "12.3.1", "7.2.0 - 12.3.0", None, False),
    ("npm", "7.1.9", "7.2.0 - 12.3.0", None, False),
    ("npm", "4.6.4", ">= 4.0.0, < 4.7.0", "4.7.0", True),
    ("npm", "4.7.0", ">= 4.0.0, < 4.7.0", "4.7.0", False),
    # a patched version is not affected, whatever the range says
    ("pip", "0.17.1", ">= 0.16.0, < 0.17.1", "0.17.1", False),
    ("pip", "6.21.2", "<= 6.21.2", ">= 6.21.2", False),
    ("pip", "6.22.0", "<= 6.22.0", ">= 6.21.2", False),
    ("npm", "1.15.11", "<= 2.0.1-rc.14", ">= 1.15.6, >= 2.0.1-rc.15", False),
    ("npm", "1.15.5", "<= 2.0.1-rc.14", ">= 1.15.6, >= 2.0.1-rc.15", True),
    # a range without an upper bound: affected where nothing is fixed or the fix is above, taken as closed by the fix
    ("pip", "3.14.4", ">=3.10.6", "3.10.11", False),
    ("pip", "3.10.8", ">=3.10.6", "3.10.11", True),
    ("pip", "5.0.0", ">= 4.5.0", None, True),
    # what the authors of advisories write
    ("pip", "12.2.0", "≤ 12.2.0", ">= 12.3.0", True),
    ("pip", "12.3.0", "≤ 12.2.0", ">= 12.3.0", False),
    ("pip", "2.3.0", "=< 2.3.0", "2.3.1", True),
    ("pip", "2.3.2", "=< 2.3.0", "2.3.1", False),
    ("pip", "0.15.0", "0.15.0 and earlier", "0.16.0", True),
    ("pip", "0.16.0", "0.15.0 and earlier", "0.16.0", False),
    ("pip", "1.4.1", ">=1.3.3 and <= 1.4.1", "1.3.5, 1.4.2", True),
    ("pip", "1.4.2", ">=1.3.3 and <= 1.4.1", "1.3.5, 1.4.2", False),
    ("npm", "3.9.0", ">=3.8.1<3.15.3", ">=3.15.3", True),
    ("npm", "3.15.3", ">=3.8.1<3.15.3", ">=3.15.3", False),
    ("npm", "10.2.0", "10 <10.2.1 || 3 <3.1.3 || 4 <4.2.4", "10.2.1 || 3.1.3 || 4.2.4", True),
    ("npm", "10.2.1", "10 <10.2.1 || 3 <3.1.3 || 4 <4.2.4", "10.2.1 || 3.1.3 || 4.2.4", False),
    ("npm", "3.1.2", "10 <10.2.1 || 3 <3.1.3 || 4 <4.2.4", "10.2.1 || 3.1.3 || 4.2.4", True),
    ("npm", "8.13.1", "< 6.28.1; 7.0.0 < 7.29.1; 8.0.0 < 8.10.2", "6.28.1; 7.29.1; 8.10.2", False),
    ("npm", "8.10.1", "< 6.28.1; 7.0.0 < 7.29.1; 8.0.0 < 8.10.2", "6.28.1; 7.29.1; 8.10.2", True),
    ("npm", "7.5.0", "< 6.28.1; 7.0.0 < 7.29.1; 8.0.0 < 8.10.2", "6.28.1; 7.29.1; 8.10.2", True),
    ("npm", "2.1.5", "<1.1.17, >= 2.0.0 < 2.1.3, 4.0.0 - 5.0.7", "5.0.8, 3.0.3, 2.1.3, 1.1.17", False),
    ("npm", "2.1.2", "<1.1.17, >= 2.0.0 < 2.1.3, 4.0.0 - 5.0.7", "5.0.8, 3.0.3, 2.1.3, 1.1.17", True),
    ("npm", "5.0.7", "<1.1.17, >= 2.0.0 < 2.1.3, 4.0.0 - 5.0.7", "5.0.8, 3.0.3, 2.1.3, 1.1.17", True),
    ("npm", "5.0.13", "<1.1.17, >= 2.0.0 < 2.1.3, 4.0.0 - 5.0.7", "5.0.8, 3.0.3, 2.1.3, 1.1.17", False),
    ("npm", "11.0.3", "11.0.x", "11.1.0", True),
    ("npm", "11.1.0", "11.0.x", "11.1.0", False),
    ("npm", "19.9.9", "<20", "20", True),
    ("npm", "20.0.0", "<20", "20", False),
    ("npm", "2.1.12", "< 2.1.13 (all versions up to and including 2.1.12)", "2.1.13", True),
    ("pip", "9.9.9", "*", None, True),
    # a pre-release is below its release
    ("npm", "2.0.1-rc.14", "<= 2.0.1-rc.14", None, True),
    ("npm", "2.0.1-rc.15", "<= 2.0.1-rc.14", None, False),
    ("npm", "2.0.1", "<= 2.0.1-rc.14", None, False),
    ("pip", "2.0rc1", "< 2.0", "2.0", True),
]

UNCLEAR = [
    ("pip", "2.14.4", "all", "v1.8.2,v1.7.4,v1.6.2"),  # the real range of a 2021 pydantic advisory
    ("pip", "1.0", None, "1.1"),
    ("pip", "1.0", "", "1.1"),
    ("pip", "1.0", "   ", None),
    ("pip", "1.0", "~=1.4", "1.5"),
    ("npm", "1.2.3", "^1.2.0", "1.3.0"),
    ("npm", "1.2.3", "~1.2.0", "1.3.0"),
    ("npm", "1.2.3", ">= 1.2.0, < banana", None),
    ("npm", "1.2.3", "1.2.3 1.2.4", None),
    ("npm", "1.2.3", "||", None),
    ("npm", "1.2.3", "> 1.x", None),
    ("npm", "1.2.3", "<= 1", None),  # npm reads it as < 2.0.0, so not guessed
    ("npm", "not-a-version", "< 2.0.0", None),
]


@pytest.mark.parametrize(("ecosystem", "installed", "vulnerable", "patched", "expected"), AFFECTED)
def test_the_comparer_reads_the_ranges_as_found(
    ecosystem: str,
    installed: str,
    vulnerable: str,
    patched: str | None,
    expected: bool,  # noqa: FBT001
) -> None:
    """Test that the locked version is compared with the range as GitHub and the authors of advisories write it."""
    assert ra.is_affected(ecosystem, installed, vulnerable, patched) is expected


@pytest.mark.parametrize(("ecosystem", "installed", "vulnerable", "patched"), UNCLEAR)
def test_a_range_that_is_not_understood_is_unclear_never_safe(
    ecosystem: str, installed: str, vulnerable: str | None, patched: str | None
) -> None:
    """Test that a range or a version nobody can read raises, which the report lists as unclear and never as safe."""
    with pytest.raises(ra.UnclearRange):
        ra.is_affected(ecosystem, installed, vulnerable, patched)


def test_semver_precedence_follows_the_specification() -> None:
    """Test the order of the semver 2.0 specification: numeric before alphanumeric identifiers, a release last."""
    ordered = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11"]
    ordered += ["1.0.0-rc.1", "1.0.0", "1.0.1", "1.10.0", "2.0.0"]
    versions = [ra.SemVer.parse(text) for text in ordered]

    assert versions == sorted(versions)
    assert ra.SemVer.parse("1.0.0+build.1") == ra.SemVer.parse("1.0.0+build.2")
    assert str(ra.SemVer.parse("v1.2.3")) == "v1.2.3"


@pytest.mark.parametrize(
    ("installed", "patched", "fixed"),
    [
        ("4.1.3", "4.2.4", "4.2.4"),
        ("4.2.4", "4.2.4", None),
        ("1.4.0", "1.3.5, 1.4.2", "1.4.2"),
        ("1.3.0", "1.3.5, 1.4.2", "1.3.5"),
        ("6.1.0", ">= 6.21.2", "6.21.2"),
        ("1.0", None, None),
        ("1.0", "None", None),
        ("1.0", "", None),
    ],
)
def test_the_fixed_version_is_the_lowest_one_above_the_locked_version(
    installed: str, patched: str | None, fixed: str | None
) -> None:
    """Test which fixed version an affected package is told to move to."""
    assert ra.first_fixed("pip", installed, patched) == fixed


# --------------------------------------------------------------------------------------------------------------------
# the lock readers
# --------------------------------------------------------------------------------------------------------------------

UV_LOCK = """\
version = 1
requires-python = ">=3.11"

[[package]]
name = "aiohttp"
version = "3.14.4"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "yarl" },
]

[[package]]
name = "fsspec"
version = "2026.9.0"
source = { registry = "https://pypi.org/simple" }

[package.optional-dependencies]
http = [
    { name = "aiohttp" },
]

[[package]]
name = "pyproj"
version = "3.7.2"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "pyproj"
version = "3.8.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "pytest"
version = "9.2.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "utm"
version = "0.8.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "pyproj", version = "3.8.0", marker = "python_full_version >= '3.12'" },
    { name = "pyproj", version = "3.7.2", marker = "python_full_version < '3.12'" },
]

[[package]]
name = "wetterdienst"
version = "0.199.0"
source = { editable = "." }
dependencies = [
    { name = "fsspec", extra = ["http"] },
]

[package.optional-dependencies]
interpolation = [
    { name = "utm" },
]
restapi = [
    { name = "wetterdienst" },
]

[package.dev-dependencies]
dev = [
    { name = "pytest" },
]

[[package]]
name = "yarl"
version = "1.25.1"
source = { registry = "https://pypi.org/simple" }
"""


def test_the_uv_lock_gives_runtime_and_extras_with_what_they_pull_in(tmp_path: Path) -> None:
    """Test that runtime dependencies, every extra, the extra of a dependency and the tree come out, dev groups not."""
    path = tmp_path / "uv.lock"
    path.write_text(UV_LOCK, encoding="utf-8")

    packages = {(p.name, p.version): p for p in ra.read_uv_lock(path)}

    assert sorted(packages) == [
        ("aiohttp", "3.14.4"),  # through `fsspec[http]`
        ("fsspec", "2026.9.0"),
        ("pyproj", "3.7.2"),  # both: markers are not evaluated
        ("pyproj", "3.8.0"),
        ("utm", "0.8.1"),
        ("yarl", "1.25.1"),
    ]
    assert packages[("fsspec", "2026.9.0")].direct
    assert packages[("utm", "0.8.1")].direct
    assert not packages[("yarl", "1.25.1")].direct
    assert not packages[("aiohttp", "3.14.4")].direct
    assert all(p.ecosystem == "pip" and p.runtime for p in packages.values())


def test_the_real_uv_lock_is_read() -> None:
    """Test that the lock of this repository gives its runtime packages and no development one."""
    names = {p.name for p in ra.read_uv_lock(ra.UV_LOCK)}

    assert {"fastapi", "polars", "aiohttp", "filelock"} <= names
    assert "pytest" not in names
    assert "wetterdienst" not in names


PNPM_LOCK = """\
lockfileVersion: '9.0'

settings:
  autoInstallPeers: true

importers:

  .:
    dependencies:
      '@nuxt/icon':
        specifier: ^2.5.1
        version: 2.5.1(@nuxt/schema@4.6.4)(vite@8.3.8(@types/node@26.6.4))
      nuxt:
        specifier: ^4.6.4
        version: 4.6.4(@parcel/watcher@2.5.6)
      shared:
        specifier: workspace:*
        version: link:../shared
      aliased:
        specifier: npm:real-name@^1.0.0
        version: real-name@1.0.2
    devDependencies:
      vitest:
        specifier: ^5.1.1
        version: 5.1.1(@types/node@26.6.4)
      tinyexec:
        specifier: ^1.0.0
        version: 1.0.1

packages:

  nuxt@4.6.4:
    resolution: {integrity: sha512-abc}

snapshots:

  '@nuxt/icon@2.5.1(@nuxt/schema@4.6.4)(vite@8.3.8(@types/node@26.6.4))':
    dependencies:
      '@nuxt/kit': 4.6.4
      vue: 3.5.44(typescript@7.0.2)
    transitivePeerDependencies:
      - supports-color

  '@nuxt/kit@4.6.4':
    dependencies:
      ufo: 1.6.3
    optionalDependencies:
      fsevents: 2.3.3

  nuxt@4.6.4(@parcel/watcher@2.5.6):
    dependencies:
      '@nuxt/kit': 4.6.4
      h3: 1.15.11

  real-name@1.0.2:
    dependencies:
      left-pad: 1.3.0

  vitest@5.1.1(@types/node@26.6.4):
    dependencies:
      vite: 8.3.8(@types/node@26.6.4)
      tinyexec: 1.0.1

  tinyexec@1.0.1: {}

  vite@8.3.8(@types/node@26.6.4):
    dependencies:
      esbuild: 0.28.2
"""


def test_the_pnpm_lock_gives_direct_dependencies_and_the_production_tree(tmp_path: Path) -> None:
    """Test direct dependencies (peer suffixes, aliases, links), the production tree and no tree of a dev dependency."""
    path = tmp_path / "pnpm-lock.yaml"
    path.write_text(PNPM_LOCK, encoding="utf-8")

    packages = {(p.name, p.version): p for p in ra.read_pnpm_lock(path)}

    assert sorted(packages) == [
        ("@nuxt/icon", "2.5.1"),
        ("@nuxt/kit", "4.6.4"),
        ("fsevents", "2.3.3"),
        ("h3", "1.15.11"),
        ("left-pad", "1.3.0"),
        ("nuxt", "4.6.4"),
        ("real-name", "1.0.2"),  # an alias: the real name is the one that has advisories
        ("tinyexec", "1.0.1"),
        ("ufo", "1.6.3"),
        ("vitest", "5.1.1"),
        ("vue", "3.5.44"),
    ]
    assert packages[("nuxt", "4.6.4")].direct
    assert packages[("nuxt", "4.6.4")].runtime
    assert packages[("h3", "1.15.11")].runtime
    assert not packages[("h3", "1.15.11")].direct
    assert packages[("vitest", "5.1.1")].direct
    assert not packages[("vitest", "5.1.1")].runtime
    assert not packages[("tinyexec", "1.0.1")].runtime  # only a development dependency reaches it
    assert all(p.ecosystem == "npm" for p in packages.values())
    # vite is a dependency of a development dependency only: its tree is not read
    assert ("vite", "8.3.8") not in packages
    assert ("esbuild", "0.28.2") not in packages


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (PNPM_LOCK.replace("'9.0'", "'10.0'"), "only lockfile version 9"),
        (PNPM_LOCK.split("importers:", maxsplit=1)[0] + "snapshots:\n  a@1.0.0: {}\n", "no dependencies found"),
        (PNPM_LOCK.split("snapshots:", maxsplit=1)[0], "no dependencies found"),
        ("", "only lockfile version 9"),
    ],
)
def test_a_pnpm_lock_in_a_format_it_does_not_know_is_an_error_not_an_empty_list(
    tmp_path: Path, text: str, message: str
) -> None:
    """Test that a changed format fails the run and does not read as "no packages, nothing found"."""
    path = tmp_path / "pnpm-lock.yaml"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ra.AdvisoryCheckError, match=message):
        ra.read_pnpm_lock(path)


# --------------------------------------------------------------------------------------------------------------------
# repositories
# --------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("urls", "repo"),
    [
        ([("Homepage", "https://github.com/zarr-developers/numcodecs")], "zarr-developers/numcodecs"),
        (
            [("Funding", "https://github.com/sponsors/authlib"), ("Source", "https://github.com/authlib/joserfc")],
            "authlib/joserfc",
        ),
        ([("Documentation", "https://github.com/a/docs"), ("Source", "https://github.com/a/code.git")], "a/code"),
        ([("repository", "git+https://github.com/nuxt/nuxt.git")], "nuxt/nuxt"),
        ([("repository", "git@github.com:vuejs/core.git")], "vuejs/core"),
        ([("repository", "github:unjs/h3")], "unjs/h3"),
        ([("repository", "unjs/h3")], "unjs/h3"),
        ([("Homepage", "https://numcodecs.readthedocs.io/"), ("Tracker", "https://gitlab.com/x/y")], None),
        ([("Homepage", "")], None),
    ],
)
def test_the_github_repository_is_read_from_the_metadata_urls(urls: list[tuple[str, str]], repo: str | None) -> None:
    """Test the spellings of a repository URL, the preference for a Source link and a sponsors page that is none."""
    assert ra.github_repository(urls) == repo


def test_a_repository_is_resolved_from_pypi_and_from_npm() -> None:
    """Test the repository of a PyPI and of an npm package, from the recorded metadata."""
    net = FakeNet(
        {
            "https://pypi.org/pypi/numcodecs/0.17.0/json": ok(recorded("pypi_numcodecs_0.17.0.json")),
            "https://registry.npmjs.org/nuxt/4.6.4": ok(recorded("npm_nuxt_4.6.4.json")),
            "https://registry.npmjs.org/@nuxt%2Fkit/4.6.4": ok(
                {"repository": {"url": "git+https://github.com/nuxt/nuxt.git"}}
            ),
        }
    )

    assert ra.resolve_repository(net, pkg("numcodecs", "0.17.0")) == "zarr-developers/numcodecs"
    assert ra.resolve_repository(net, pkg("nuxt", "4.6.4", "npm")) == "nuxt/nuxt"
    assert ra.resolve_repository(net, pkg("@nuxt/kit", "4.6.4", "npm")) == "nuxt/nuxt"


def test_a_package_without_a_github_repository_is_unreadable() -> None:
    """Test that missing metadata and a repository elsewhere are `Unreadable`, not an empty answer."""
    net = FakeNet(
        {
            "https://pypi.org/pypi/cftime/1.6.6/json": ok(recorded("pypi_cftime_1.6.6.json")),
            "https://pypi.org/pypi/gone/1.0/json": status(404, {"message": "Not Found"}),
        }
    )

    with pytest.raises(ra.Unreadable, match="no GitHub repository"):
        ra.resolve_repository(net, pkg("cftime", "1.6.6"))
    with pytest.raises(ra.Unreadable, match="HTTP 404"):
        ra.resolve_repository(net, pkg("gone", "1.0"))


# --------------------------------------------------------------------------------------------------------------------
# the reading
# --------------------------------------------------------------------------------------------------------------------


def numcodecs_net(**extra: Any) -> FakeNet:  # noqa: ANN401
    """Return a network that knows numcodecs 0.17.0 and its repository, and what `extra` adds."""
    routes = {
        "https://pypi.org/pypi/numcodecs/0.17.0/json": ok(recorded("pypi_numcodecs_0.17.0.json")),
        "https://pypi.org/pypi/numcodecs/0.17.1/json": ok(recorded("pypi_numcodecs_0.17.1.json")),
        advisories_url("zarr-developers/numcodecs"): ok(recorded("advisories_numcodecs.json")),
    }
    return FakeNet(routes | extra)


def test_a_locked_numcodecs_is_affected_by_the_advisory_of_its_repository() -> None:
    """Test the advisory that GitHub's alerts did not list: found, with its fix and whether the fix is old enough."""
    report = ra.check([pkg("numcodecs", "0.17.0")], numcodecs_net(), [], NOW)

    (finding,) = report.affected
    assert (finding.package.name, finding.advisory, finding.severity, finding.fixed) == (
        "numcodecs",
        "GHSA-jqc8-qjfv-5m6r",
        "high",
        "0.17.1",
    )
    assert finding.cooldown == "past"  # 0.17.1 was published on 2026-09-17
    assert not report.unclear
    assert not report.unreadable


def test_the_cooldown_of_a_fix_says_when_it_may_be_locked() -> None:
    """Test `past`, `from <date>` and `unknown` for a fixed version of three days or more, less, and not told."""
    day = dt.timedelta(days=1)

    assert ra.cooldown_status(NOW - 3 * day, NOW) == "past"
    assert ra.cooldown_status(NOW - 2 * day, NOW) == "from 2026-11-26"
    assert ra.cooldown_status(None, NOW) == "unknown"


def test_a_package_at_the_fixed_version_is_not_affected() -> None:
    """Test that the locked 0.17.1 is not reported, and that no fixed version is asked for."""
    net = numcodecs_net(**{"https://pypi.org/pypi/numcodecs/0.17.1/json": ok(recorded("pypi_numcodecs_0.17.1.json"))})

    report = ra.check([pkg("numcodecs", "0.17.1")], net, [], NOW)

    assert not report.affected
    assert not report.unclear


def test_an_advisory_of_another_package_in_the_repository_does_not_count() -> None:
    """Test a monorepo: the advisories of nuxt do not name `@nuxt/kit`, and do name `nuxt` and `@nuxt/nitro-server`."""
    net = FakeNet(
        {
            "https://registry.npmjs.org/nuxt/4.6.4": ok(recorded("npm_nuxt_4.6.4.json")),
            "https://registry.npmjs.org/@nuxt%2Fkit/4.6.4": ok({"repository": "github:nuxt/nuxt"}),
            "https://registry.npmjs.org/@nuxt%2Fnitro-server/4.6.4": ok({"repository": "github:nuxt/nuxt"}),
            advisories_url("nuxt/nuxt"): ok(recorded("advisories_nuxt.json")),
            "https://registry.npmjs.org/nuxt": ok({"time": {"4.7.0": "2026-11-25T15:00:00.000Z"}}),
            "https://registry.npmjs.org/@nuxt%2Fnitro-server": ok({"time": {"4.7.0": "2026-11-25T15:00:00.000Z"}}),
        }
    )
    packages = [pkg(n, "4.6.4", "npm") for n in ("nuxt", "@nuxt/kit", "@nuxt/nitro-server")]

    report = ra.check(packages, net, [], NOW)

    assert [(f.package.name, f.advisory, f.fixed, f.cooldown) for f in report.affected] == [
        ("@nuxt/nitro-server", "GHSA-jxc9-w3j6-pwp2", "4.7.0", "from 2026-11-28"),
        ("@nuxt/nitro-server", "GHSA-vrh2-cfcx-c3fg", "4.7.0", "from 2026-11-28"),
        ("nuxt", "GHSA-vrh2-cfcx-c3fg", "4.7.0", "from 2026-11-28"),
    ]
    advisory_reads = [url for _, url in net.requests if url == advisories_url("nuxt/nuxt")]
    assert len(advisory_reads) == 1  # one repository, one read


def test_a_withdrawn_advisory_does_not_count() -> None:
    """Test that an advisory with a `withdrawn_at` is left out."""
    advisories = recorded("advisories_numcodecs.json")
    advisories[0]["withdrawn_at"] = "2026-10-21T00:00:00Z"
    net = numcodecs_net(**{advisories_url("zarr-developers/numcodecs"): ok(advisories)})

    report = ra.check([pkg("numcodecs", "0.17.0")], net, [], NOW)

    assert not report.affected


def test_an_advisory_with_a_range_that_is_not_understood_is_unclear() -> None:
    """Test the real advisory of pydantic with the range `all`: unclear, and not "nothing found"."""
    net = FakeNet(
        {
            "https://pypi.org/pypi/pydantic/2.14.4/json": ok(
                {"info": {"project_urls": {"Source": "https://github.com/pydantic/pydantic"}}}
            ),
            advisories_url("pydantic/pydantic"): ok(recorded("advisories_pydantic.json")),
        }
    )

    report = ra.check([pkg("pydantic", "2.14.4")], net, [], NOW)

    assert not report.affected
    assert [(f.advisory, f.reason) for f in report.unclear] == [("GHSA-5jqp-qgf6-3pvh", "version 'all' not understood")]


@pytest.mark.parametrize(
    ("name", "version", "repo", "file", "ghsa"),
    [
        ("pillow", "13.0.0", "python-pillow/Pillow", "advisories_pillow.json", "GHSA-45hq-cxwh-f6vc"),
        ("joserfc", "1.4.1", "authlib/joserfc", "advisories_joserfc.json", "GHSA-frfh-8v73-gjg4"),
    ],
)
def test_the_ranges_authors_wrote_in_real_advisories_are_read(
    name: str, version: str, repo: str, file: str, ghsa: str
) -> None:
    """Test `≤ 12.2.0` (Pillow 13 is above it) and `>=1.3.3 and <= 1.4.1` (joserfc 1.4.1 is in it) from real answers."""
    net = FakeNet(
        {
            f"https://pypi.org/pypi/{name}/{version}/json": ok(
                {"info": {"project_urls": {"Source": f"https://github.com/{repo}"}}}
            ),
            advisories_url(repo): ok(recorded(file)),
            f"https://pypi.org/pypi/{name}/1.4.2/json": ok(
                {"urls": [{"upload_time_iso_8601": "2026-11-01T00:00:00Z"}]}
            ),
        }
    )

    report = ra.check([pkg(name, version)], net, [], NOW)

    assert not report.unclear
    assert [f.advisory for f in report.affected] == ([ghsa] if name == "joserfc" else [])


def test_the_undici_ranges_with_semicolons_are_read() -> None:
    """Test the real undici advisory, written as `< 6.24.0; 7.0.0 < 7.24.0`, against a version above both."""
    net = FakeNet(
        {
            "https://registry.npmjs.org/undici/8.13.1": ok({"repository": "github:nodejs/undici"}),
            advisories_url("nodejs/undici"): ok(recorded("advisories_undici.json")),
        }
    )

    report = ra.check([pkg("undici", "8.13.1", "npm")], net, [], NOW)

    assert not report.affected
    assert not report.unclear


def test_a_package_without_a_repository_or_with_a_missing_one_is_listed_as_unreadable() -> None:
    """Test `no GitHub repository` and a repository that answers 404: listed, and the rest is still read."""
    net = numcodecs_net(
        **{
            "https://pypi.org/pypi/cftime/1.6.6/json": ok(recorded("pypi_cftime_1.6.6.json")),
            "https://pypi.org/pypi/lost/1.0/json": ok(
                {"info": {"project_urls": {"Source": "https://github.com/gone/lost"}}}
            ),
            advisories_url("gone/lost"): status(404, {"message": "Not Found"}),
        }
    )

    report = ra.check([pkg("numcodecs", "0.17.0"), pkg("cftime", "1.6.6"), pkg("lost", "1.0")], net, [], NOW)

    assert [f.package.name for f in report.affected] == ["numcodecs"]
    assert [(p.name, reason) for p, reason in report.unreadable] == [
        ("cftime", "no GitHub repository in the package metadata"),
        ("lost", "gone/lost: the advisories of gone/lost cannot be read (HTTP 404)"),
    ]


def test_when_no_advisory_can_be_read_the_run_fails_instead_of_finding_nothing() -> None:
    """Test that every repository unreadable (for instance a token that may not read advisories) is an error."""
    net = FakeNet(
        {
            "https://pypi.org/pypi/numcodecs/0.17.0/json": ok(recorded("pypi_numcodecs_0.17.0.json")),
            advisories_url("zarr-developers/numcodecs"): status(
                403, {"message": "Resource not accessible by integration"}
            ),
        }
    )

    with pytest.raises(ra.AdvisoryCheckError, match="no repository's advisories could be read"):
        ra.check([pkg("numcodecs", "0.17.0")], net, [], NOW)


@pytest.mark.parametrize(
    "answer",
    [
        status(429, {"message": "Too Many Requests"}),
        status(403, {"message": "API rate limit exceeded for installation."}, **{"x-ratelimit-remaining": "0"}),
        status(403, {"message": "You have exceeded a secondary rate limit."}),
        status(403, {"message": "Forbidden"}, **{"retry-after": "60"}),
    ],
)
def test_a_rate_limit_fails_loudly_and_is_not_an_empty_answer(answer: Any) -> None:  # noqa: ANN401
    """Test that GitHub's four ways to say "later" raise `RateLimitError`, in the reading and in the issue search."""
    net = numcodecs_net(**{advisories_url("zarr-developers/numcodecs"): answer})

    with pytest.raises(ra.RateLimitError):
        ra.check([pkg("numcodecs", "0.17.0")], net, [], NOW)

    with pytest.raises(ra.RateLimitError):
        ra.find_issues(FakeNet({search_url(): answer}), "owner/repo")


def test_the_main_command_exits_2_on_a_rate_limit_and_writes_no_issue(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that a rate limit makes the job fail (exit 2, a message on stderr) and leaves the issue as it was."""
    net = numcodecs_net(
        **{
            advisories_url("zarr-developers/numcodecs"): status(
                403, {"message": "rate limit"}, **{"x-ratelimit-remaining": "0"}
            )
        }
    )
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

    code = ra.main(["--only", "python", "--uv-lock", str(_small_lock(tmp_path)), "--issue"], fetch=net, now=NOW)

    assert code == 2
    assert "rate limit" in capsys.readouterr().err
    assert not net.writes


# --------------------------------------------------------------------------------------------------------------------
# the ignore list
# --------------------------------------------------------------------------------------------------------------------


def ignore_entry(**changes: str) -> Any:  # noqa: ANN401
    """Return an entry of the ignore list for the numcodecs advisory."""
    values = {
        "package": "numcodecs",
        "advisory": "GHSA-jqc8-qjfv-5m6r",
        "reason": "the Pickle codec is never used",
        "date": "2026-11-25",
    } | changes
    return ra.IgnoreEntry(**values)


def test_an_ignored_advisory_is_listed_with_its_reason_and_not_as_a_finding() -> None:
    """Test that the entry moves the finding to `ignored` and that the entry is not stale."""
    entry = ignore_entry()

    report = ra.check([pkg("numcodecs", "0.17.0")], numcodecs_net(), [entry], NOW)

    assert not report.affected
    assert [(f.package.name, e.reason) for f, e in report.ignored] == [("numcodecs", "the Pickle codec is never used")]
    assert not report.stale


def test_an_entry_that_matches_nothing_any_more_is_stale_but_only_for_a_package_that_was_read() -> None:
    """Test that a fixed version leaves its entry stale, while the entry of a package not in this run is not."""
    net = numcodecs_net()
    other = ignore_entry(package="anyio", advisory="GHSA-g36m-r6gw-cj73")

    report = ra.check([pkg("numcodecs", "0.17.1")], net, [ignore_entry(), other], NOW)

    assert [e.package for e in report.stale] == ["numcodecs"]


def test_an_unclear_finding_can_be_ignored_too() -> None:
    """Test that the entry for the pydantic advisory with the range `all` removes it from the unclear list."""
    net = FakeNet(
        {
            "https://pypi.org/pypi/pydantic/2.14.4/json": ok(
                {"info": {"project_urls": {"Source": "https://github.com/pydantic/pydantic"}}}
            ),
            advisories_url("pydantic/pydantic"): ok(recorded("advisories_pydantic.json")),
        }
    )
    entry = ignore_entry(package="pydantic", advisory="GHSA-5jqp-qgf6-3pvh")

    report = ra.check([pkg("pydantic", "2.14.4")], net, [entry], NOW)

    assert not report.unclear
    assert len(report.ignored) == 1


def test_the_checked_in_ignore_list_is_valid_and_every_entry_has_a_reason_and_a_date() -> None:
    """Test the real file: the entries load, name a package and one advisory, and carry a reason and a date."""
    entries = ra.load_ignore(ra.IGNORE_FILE)

    assert entries
    assert all(e.package and ra.GHSA_ID.match(e.advisory) and e.reason and e.date for e in entries)
    assert len({(e.package, e.advisory) for e in entries}) == len(entries)


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ('package = "*"\nadvisory = "GHSA-jqc8-qjfv-5m6r"\nreason = "x"\ndate = "2026-11-25"', "never a wildcard"),
        ('package = "numcodecs"\nadvisory = "GHSA-*"\nreason = "x"\ndate = "2026-11-25"', "never a wildcard"),
        ('package = "numcodecs"\nadvisory = ""\nreason = "x"\ndate = "2026-11-25"', "never a wildcard"),
        ('package = "numcodecs"\nadvisory = "GHSA-jqc8-qjfv-5m6r"\nreason = ""\ndate = "2026-11-25"', "needs a reason"),
        ('package = "numcodecs"\nadvisory = "GHSA-jqc8-qjfv-5m6r"\nreason = "x"', "needs a reason and a date"),
        ('package = "numcodecs"\nadvisory = "GHSA-jqc8-qjfv-5m6r"\nreason = "x"\ndate = "yesterday"', "needs a reason"),
    ],
)
def test_an_ignore_entry_without_a_reason_or_a_date_or_with_a_wildcard_is_refused(
    tmp_path: Path, entry: str, message: str
) -> None:
    """Test that the list refuses a wildcard, a missing reason and a missing or malformed date."""
    path = tmp_path / "ignore.toml"
    path.write_text(f"[[ignore]]\n{entry}\n", encoding="utf-8")

    with pytest.raises(ra.AdvisoryCheckError, match=message):
        ra.load_ignore(path)


# --------------------------------------------------------------------------------------------------------------------
# the issue
# --------------------------------------------------------------------------------------------------------------------


def report_with(
    *, affected: bool = True, unclear: bool = False, unreadable: bool = False, ignored: bool = False
) -> Any:  # noqa: ANN401
    """Return a report with the lists asked for."""
    report = ra.Report(checked=130)
    if affected:
        report.affected.append(
            ra.Finding(pkg("numcodecs", "0.17.0"), "GHSA-jqc8-qjfv-5m6r", "high", fixed="0.17.1", cooldown="past")
        )
        report.affected.append(
            ra.Finding(
                pkg("@nuxt/kit", "4.6.4", "npm", direct=False), "GHSA-vrh2-cfcx-c3fg", "medium", cooldown="no fix yet"
            )
        )
    if unclear:
        report.unclear.append(
            ra.Finding(pkg("pydantic", "2.14.4"), "GHSA-5jqp-qgf6-3pvh", "medium", reason="range `all` not understood")
        )
    if unreadable:
        report.unreadable.append((pkg("cftime", "1.6.6"), "no GitHub repository in the package metadata"))
    if ignored:
        report.ignored.append(
            (
                ra.Finding(pkg("anyio", "4.15.1"), "GHSA-g36m-r6gw-cj73", "high"),
                ignore_entry(package="anyio", advisory="GHSA-g36m-r6gw-cj73", reason="run_process is not used"),
            )
        )
        report.stale.append(ignore_entry())
    return report


def test_the_issue_lists_the_findings_in_tables_and_lists() -> None:
    """Test the sections of the body: affected with its columns, unclear, unreadable, ignored and stale entries."""
    body = ra.render_issue(
        report_with(unclear=True, unreadable=True, ignored=True), NOW, "https://github.com/o/r/actions/runs/1"
    )

    assert body.startswith(ra.ISSUE_MARKER)
    assert f"fingerprint: {report_with(unclear=True, unreadable=True, ignored=True).fingerprint}" in body
    assert "| Package | Locked | Advisory | Severity | Fixed in | Past the cooldown | Scope |" in body
    assert (
        "| `numcodecs` | `0.17.0` | [GHSA-jqc8-qjfv-5m6r](https://github.com/advisories/GHSA-jqc8-qjfv-5m6r) "
        "| high | `0.17.1` | past | python, direct |" in body
    )
    assert "| `@nuxt/kit` | `4.6.4` |" in body
    assert "| none yet | no fix yet | app, transitive |" in body
    assert "## Unclear (1)" in body
    assert "## Unreadable (1)" in body
    assert "- `cftime` `1.6.6`: `no GitHub repository in the package metadata`" in body
    assert "## Known not to affect us (1)" in body
    assert "`run_process is not used` (2026-11-25)" in body
    assert "## Ignore entries to remove" in body
    assert "Run: https://github.com/o/r/actions/runs/1" in body


def test_the_issue_mentions_nobody_and_copies_no_text_of_an_advisory() -> None:
    """Test that a scoped name, a hostile reason and an advisory summary come out as code or not at all."""
    report = report_with()
    report.affected[0] = ra.Finding(pkg("@evil/team", "1.0.0`@someone", "npm"), "GHSA-jqc8-qjfv-5m6r", "high")
    report.unclear.append(
        ra.Finding(pkg("x", "1"), "GHSA-5jqp-qgf6-3pvh", "low", reason="@maintainer please look\nsecond line `@x`")
    )

    body = ra.render_issue(report, NOW)

    assert "`@evil/team`" in body
    assert "`1.0.0 @someone`" in body
    assert "`@maintainer please look second line  @x`" in body
    for line in body.splitlines():
        stripped = line.replace("`@evil/team`", "").replace("`@nuxt/kit`", "")
        for chunk in stripped.split("`")[::2]:  # the text outside code spans
            assert "@" not in chunk, line
    assert "summary" not in body.lower()


def test_an_advisory_id_that_is_none_is_not_linked() -> None:
    """Test that only a well-formed GHSA id becomes a link."""
    assert ra._advisory_link("GHSA-jqc8-qjfv-5m6r").startswith("[GHSA-jqc8-qjfv-5m6r](https://github.com/advisories/")  # noqa: SLF001
    assert ra._advisory_link("javascript:alert(1)") == "`javascript:alert(1)`"  # noqa: SLF001


def test_the_issue_says_none_now_when_nothing_is_affected() -> None:
    """Test the body of an update when nothing is affected any more."""
    body = ra.render_issue(report_with(affected=False), NOW)

    assert "## Affected\n\nNone now." in body
    assert "| Package |" not in body


def test_the_fingerprint_changes_with_the_findings_and_not_with_the_ignored_or_unreadable() -> None:
    """Test that a new finding changes the fingerprint, while an ignored or unreadable one does not."""
    base = report_with()

    assert base.fingerprint == report_with(unreadable=True, ignored=True).fingerprint
    assert base.fingerprint != report_with(unclear=True).fingerprint
    assert base.fingerprint != report_with(affected=False).fingerprint


def issue_item(number: int, state: str, body: str, title: str | None = None, **extra: Any) -> dict[str, Any]:  # noqa: ANN401
    """Return an item of an issue search."""
    return {"number": number, "state": state, "title": title or ra.ISSUE_TITLE, "body": body} | extra


def issues_net(items: list[dict[str, Any]]) -> FakeNet:
    """Return a network with an issue search that finds `items`, and that accepts the writes."""
    routes: dict[str, Any] = {search_url(): ok({"items": items})}
    net = FakeNet(routes)
    routes[f"{ra.GITHUB_API}repos/owner/repo/issues"] = lambda method, _payload: (
        ok({"number": 99}) if method == "POST" else status(405)
    )
    for item in items:
        routes[f"{ra.GITHUB_API}repos/owner/repo/issues/{item['number']}"] = lambda method, _payload: (
            ok({}) if method == "PATCH" else status(405)
        )
    return net


def sync(net: FakeNet, report: Any, *, dry_run: bool = False) -> str:  # noqa: ANN401
    """Run `sync_issue` for `report`."""
    return ra.sync_issue(net, "owner/repo", report, ra.render_issue(report, NOW), dry_run=dry_run)


def test_a_first_finding_opens_one_issue_with_the_fixed_title_and_no_assignee() -> None:
    """Test the issue that is created: title, label and body, and nothing about assignees."""
    net = issues_net([])

    result = sync(net, report_with())

    assert result == "issue created"
    assert [method for method, _ in net.writes] == ["POST"]


def test_the_issue_is_posted_with_a_fixed_title_a_label_and_no_assignee() -> None:
    """Test the payload of the one write."""
    payloads: list[Any] = []
    net = issues_net([])
    net.routes[f"{ra.GITHUB_API}repos/owner/repo/issues"] = lambda method, payload: (
        payloads.append((method, payload)) or ok({})
    )

    sync(net, report_with())

    ((method, payload),) = payloads
    assert method == "POST"
    assert payload["title"] == ra.ISSUE_TITLE
    assert payload["labels"] == ["security"]
    assert "assignees" not in payload
    assert ra.ISSUE_MARKER in payload["body"]


def test_an_open_issue_is_updated_and_never_a_second_one_opened() -> None:
    """Test that the open issue gets the new body (a PATCH) and no issue is created."""
    net = issues_net([issue_item(7, "open", f"{ra.ISSUE_MARKER}\nold")])

    result = sync(net, report_with())

    assert result == "issue #7 updated"
    assert net.writes == [("PATCH", f"{ra.GITHUB_API}repos/owner/repo/issues/7")]


def test_an_open_issue_that_is_up_to_date_is_left_alone() -> None:
    """Test that the same body is not written again."""
    report = report_with()
    net = issues_net([issue_item(7, "open", ra.render_issue(report, NOW))])

    assert sync(net, report) == "issue #7 is up to date"
    assert not net.writes


def test_when_nothing_is_affected_an_open_issue_is_updated_to_none_now_and_left_open() -> None:
    """Test that the issue is not closed and not commented on: its body says none now, and a person closes it."""
    net = issues_net([issue_item(7, "open", f"{ra.ISSUE_MARKER}\nold")])

    result = sync(net, report_with(affected=False))

    assert result == "issue #7 updated to none now"
    assert net.writes == [("PATCH", f"{ra.GITHUB_API}repos/owner/repo/issues/7")]


def test_when_nothing_is_affected_and_no_issue_is_open_none_is_opened() -> None:
    """Test that a clean run opens nothing, with no issue and with a closed one."""
    assert sync(issues_net([]), report_with(affected=False)) == "nothing affected or unclear, no open issue: no issue"
    closed = issues_net([issue_item(7, "closed", f"{ra.ISSUE_MARKER}\nold")])

    assert sync(closed, report_with(affected=False)) == "nothing affected or unclear, no open issue: no issue"
    assert not closed.writes


def test_a_closed_issue_with_the_same_findings_is_not_opened_again_but_new_findings_open_one() -> None:
    """Test that a person's close stands for the findings it had, and that a different finding is a new issue."""
    report = report_with()
    closed_same = issue_item(7, "closed", ra.render_issue(report, NOW - dt.timedelta(days=14)))
    closed_other = issue_item(7, "closed", ra.render_issue(report_with(affected=False, unclear=True), NOW))

    same = issues_net([closed_same])
    different = issues_net([closed_other])

    assert sync(same, report) == "closed issue #7 holds the same findings: no new issue"
    assert not same.writes
    assert sync(different, report) == "issue created"
    assert [method for method, _ in different.writes] == ["POST"]


def test_only_the_issue_of_this_check_is_found() -> None:
    """Test that a pull request, another title and an issue without the marker are not taken for the check's issue."""
    items = [
        issue_item(1, "open", f"{ra.ISSUE_MARKER}\nbody", pull_request={"url": "x"}),
        issue_item(2, "open", f"{ra.ISSUE_MARKER}\nbody", title="something else"),
        issue_item(3, "open", "somebody wrote the same title"),
        issue_item(4, "open", None),
        issue_item(5, "closed", f"{ra.ISSUE_MARKER}\nbody"),
    ]

    found = ra.find_issues(issues_net(items), "owner/repo")

    assert [item["number"] for item in found] == [5]


def test_a_dry_run_reads_and_writes_nothing() -> None:
    """Test that `dry_run` names the action and makes no POST and no PATCH."""
    net = issues_net([])
    open_net = issues_net([issue_item(7, "open", f"{ra.ISSUE_MARKER}\nold")])

    assert sync(net, report_with(), dry_run=True) == "issue would be created"
    assert sync(open_net, report_with(), dry_run=True) == "issue #7 would be updated"
    assert not net.writes
    assert not open_net.writes


def test_a_failed_write_is_an_error() -> None:
    """Test that a refused POST fails the run instead of passing silently."""
    net = issues_net([])
    net.routes[f"{ra.GITHUB_API}repos/owner/repo/issues"] = lambda _method, _payload: status(
        403, {"message": "Resource not accessible"}
    )

    with pytest.raises(ra.AdvisoryCheckError, match="failed"):
        sync(net, report_with())


# --------------------------------------------------------------------------------------------------------------------
# the table, the command line
# --------------------------------------------------------------------------------------------------------------------


def test_the_table_lists_what_the_issue_lists() -> None:
    """Test the plain-text table of a local run."""
    table = ra.render_table(report_with(unclear=True, unreadable=True, ignored=True))

    assert table.splitlines()[0] == "130 locked packages read"
    assert "affected (2)" in table
    assert "numcodecs" in table
    assert "GHSA-jqc8-qjfv-5m6r" in table
    assert "unclear (1)" in table
    assert "unreadable (1)" in table
    assert "ignored (scripts/repo_advisories_ignore.toml) (1)" in table
    assert "nothing affected" not in table
    assert "nothing affected, nothing unclear" in ra.render_table(ra.Report(checked=3))


def _small_lock(tmp_path: Path) -> Path:
    path = tmp_path / "uv.lock"
    path.write_text(
        "version = 1\n\n"
        '[[package]]\nname = "numcodecs"\nversion = "0.17.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n\n'
        '[[package]]\nname = "wetterdienst"\nversion = "1"\nsource = { editable = "." }\n'
        'dependencies = [\n    { name = "numcodecs" },\n]\n',
        encoding="utf-8",
    )
    return path


def test_the_command_prints_a_table_and_exits_1_when_something_is_affected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test the local mode: a table on stdout, exit 1 for a finding, no write to GitHub."""
    net = numcodecs_net()

    code = ra.main(
        ["--only", "python", "--uv-lock", str(_small_lock(tmp_path)), "--ignore-file", str(tmp_path / "none.toml")],
        fetch=net,
        now=NOW,
    )

    assert code == 1
    assert "GHSA-jqc8-qjfv-5m6r" in capsys.readouterr().out
    assert not net.writes


def test_the_command_exits_0_when_the_only_finding_is_ignored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that an entry of the ignore list turns the exit code to 0."""
    ignore = tmp_path / "ignore.toml"
    ignore.write_text(
        '[[ignore]]\npackage = "numcodecs"\nadvisory = "GHSA-jqc8-qjfv-5m6r"\n'
        'reason = "never used"\ndate = "2026-11-25"\n',
        encoding="utf-8",
    )

    code = ra.main(
        ["--only", "python", "--uv-lock", str(_small_lock(tmp_path)), "--ignore-file", str(ignore)],
        fetch=numcodecs_net(),
        now=NOW,
    )

    assert code == 0
    assert "never used" in capsys.readouterr().out


def test_the_command_with_issue_and_dry_run_prints_the_body_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the dry run of the weekly job: the body and the action are printed, nothing is written."""
    net = numcodecs_net()
    net.routes[search_url()] = ok({"items": []})
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    code = ra.main(
        ["--only", "python", "--uv-lock", str(_small_lock(tmp_path)), "--issue", "--dry-run"], fetch=net, now=NOW
    )

    out = capsys.readouterr().out
    assert code == 0
    assert ra.ISSUE_MARKER in out
    assert "issue would be created" in out
    assert "https://github.com/owner/repo/actions/runs/42" in out
    assert not net.writes


def test_the_command_with_issue_needs_the_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that `--issue` without `GITHUB_REPOSITORY` is an error and not a guess."""
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    code = ra.main(
        ["--only", "python", "--uv-lock", str(_small_lock(tmp_path)), "--issue"], fetch=numcodecs_net(), now=NOW
    )

    assert code == 2
    assert "GITHUB_REPOSITORY" in capsys.readouterr().err


# --------------------------------------------------------------------------------------------------------------------
# the network layer
# --------------------------------------------------------------------------------------------------------------------


class _Raw:
    status = 200
    headers: dict[str, str] = {"Content-Type": "application/json"}  # noqa: RUF012

    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_the_token_goes_to_the_github_api_and_nowhere_else(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the Authorization header goes to api.github.com only, and a GitHub call to another host is refused."""
    seen: list[Any] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Raw:  # noqa: ARG001
        seen.append(request)
        return _Raw(b'{"ok": true}')

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    fetch = ra.make_fetch("secret-token")

    fetch("https://pypi.org/pypi/numcodecs/json")
    fetch(f"{ra.GITHUB_API}rate_limit", github=True)
    with pytest.raises(ra.AdvisoryCheckError, match="refusing to send"):
        fetch("https://example.org/", github=True)

    assert seen[0].get_header("Authorization") is None
    assert seen[1].get_header("Authorization") == "Bearer secret-token"
    assert len(seen) == 2


def test_a_server_error_is_retried_and_then_fails_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a 502 is tried three times and then raises, and that a 404 is an answer and is not retried."""
    calls: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Raw:  # noqa: ARG001
        calls.append(request.full_url)
        code = 404 if "missing" in request.full_url else 502
        raise urllib.error.HTTPError(request.full_url, code, "x", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(ra.time, "sleep", lambda _: None)
    fetch = ra.make_fetch(None)

    with pytest.raises(ra.AdvisoryCheckError, match="could not be read"):
        fetch("https://pypi.org/pypi/down/json")
    assert len(calls) == ra.RETRIES

    calls.clear()
    assert fetch("https://pypi.org/pypi/missing/json").status == 404
    assert len(calls) == 1


def test_a_connection_error_fails_the_run_after_the_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an unreachable host is an error and not an empty answer."""

    def urlopen(request: urllib.request.Request, timeout: int) -> _Raw:  # noqa: ARG001
        reason = "no route"
        raise urllib.error.URLError(reason)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(ra.time, "sleep", lambda _: None)

    with pytest.raises(ra.AdvisoryCheckError, match="URLError"):
        ra.make_fetch(None)("https://pypi.org/pypi/x/json")


def test_the_advisories_of_a_repository_are_read_page_by_page() -> None:
    """Test the `Link` header: the second page is read, and a next link to another host is not followed."""
    first = advisories_url("o/r")
    second = f"{ra.GITHUB_API}repositories/1/security-advisories?page=2"
    net = FakeNet(
        {
            first: ok([{"ghsa_id": "GHSA-aaaa-bbbb-cccc"}], link=f'<{second}>; rel="next"'),
            second: ok([{"ghsa_id": "GHSA-dddd-eeee-ffff"}], link='<https://evil.example/?page=3>; rel="next"'),
        }
    )

    assert [a["ghsa_id"] for a in ra.read_repository_advisories(net, "o/r")] == [
        "GHSA-aaaa-bbbb-cccc",
        "GHSA-dddd-eeee-ffff",
    ]
    assert [url for _, url in net.requests] == [first, second]

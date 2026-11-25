# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for `scripts/repo_advisories.py`, the check of the advisories the packages publish in their own repositories.

Offline: every answer is replayed from `tests/scripts/recorded` (real answers of PyPI, npm and the GitHub API of
2026-11-25, cut down to the fields the script reads) or written in the test. The fake network refuses any URL
nobody gave it an answer for. The comparer has its own file (`test_comparer.py`).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import http.client
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Self

import pytest

from tests.scripts.support import (
    BOT,
    NOW,
    FakeNet,
    advisories_url,
    advisory,
    issues_url,
    ok,
    pkg,
    ra,
    recorded,
    status,
)

REPO_ROOT = Path(__file__).parent.parent.parent

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
    assert all(p.ecosystem == "pip" and p.runtime and not p.foreign for p in packages.values())


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (UV_LOCK.replace("version = 1\n", "version = 2\n", 1), "only lock version 1"),
        ("version = 1\n", "only lock version 1"),
        (UV_LOCK.replace('{ name = "yarl" }', '{ name = "gone" }'), "gone  is not resolved"),
        (UV_LOCK.replace('version = "3.8.0", marker', 'version = "9.9.9", marker'), "pyproj 9.9.9 is not resolved"),
        (UV_LOCK.replace('source = { editable = "." }', 'source = { registry = "x" }'), "project itself"),
        (
            UV_LOCK.split("[package.optional-dependencies]\ninterpolation", maxsplit=1)[0].replace(
                '{ name = "fsspec", extra = ["http"] },', ""
            ),
            "no runtime dependencies",
        ),
    ],
)
def test_a_uv_lock_that_shrank_or_changed_is_an_error_not_a_short_list(tmp_path: Path, text: str, message: str) -> None:
    """Test the version of the lock, an unresolved dependency, a missing project and an empty result."""
    path = tmp_path / "uv.lock"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ra.AdvisoryCheckError, match=message):
        ra.read_uv_lock(path)


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
      forked:
        specifier: github:someone/forked
        version: https://codeload.github.com/someone/forked/tar.gz/abc123
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

  fsevents@2.3.3: {}

  h3@1.15.11: {}

  left-pad@1.3.0: {}

  nuxt@4.6.4(@parcel/watcher@2.5.6):
    dependencies:
      '@nuxt/kit': 4.6.4
      h3: 1.15.11
      sub: git+https://github.com/someone/sub.git#abc

  real-name@1.0.2:
    dependencies:
      left-pad: 1.3.0

  tinyexec@1.0.1: {}

  ufo@1.6.3: {}

  vitest@5.1.1(@types/node@26.6.4):
    dependencies:
      vite: 8.3.8(@types/node@26.6.4)
      tinyexec: 1.0.1

  vite@8.3.8(@types/node@26.6.4):
    dependencies:
      esbuild: 0.28.2

  vue@3.5.44(typescript@7.0.2): {}
"""


def test_the_pnpm_lock_gives_direct_dependencies_and_the_production_tree(tmp_path: Path) -> None:
    """Test direct dependencies (peer suffixes, aliases, links), the production tree and no tree of a dev dependency."""
    path = tmp_path / "pnpm-lock.yaml"
    path.write_text(PNPM_LOCK, encoding="utf-8")

    packages = {(p.name, p.version): p for p in ra.read_pnpm_lock(path) if not p.foreign}

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


def test_a_git_or_url_dependency_is_listed_and_not_dropped(tmp_path: Path) -> None:
    """Test that a dependency that is no package of the registry is a `foreign` package, direct or in the tree."""
    path = tmp_path / "pnpm-lock.yaml"
    path.write_text(PNPM_LOCK, encoding="utf-8")

    foreign = [p for p in ra.read_pnpm_lock(path) if p.foreign]

    assert sorted((p.name, p.direct) for p in foreign) == [("forked", True), ("sub", False)]
    assert all(p.version.startswith(("git+", "https://")) for p in foreign)


def test_a_dependency_without_its_snapshot_is_an_error(tmp_path: Path) -> None:
    """Test that a lock whose snapshots lost an entry fails, so that the list cannot shrink unnoticed."""
    path = tmp_path / "pnpm-lock.yaml"
    path.write_text(PNPM_LOCK.replace("  left-pad@1.3.0: {}\n", ""), encoding="utf-8")

    with pytest.raises(ra.AdvisoryCheckError, match=r"no snapshot for left-pad@1\.3\.0"):
        ra.read_pnpm_lock(path)


LONG_KEY = "a-very-long-package@1.0.0(" + "(".join(f"peer{i}@1.{i}.0" for i in range(200)) + ")" * 200


@pytest.mark.parametrize(
    "block",
    [
        f"  ? '{LONG_KEY}'\n  :\n    dependencies:\n      leaf: 2.0.0\n\n",
        f"  ? '{LONG_KEY}'\n  : dependencies:\n      leaf: 2.0.0\n\n",
        f"  ? {LONG_KEY}\n  : {{}}\n\n",
    ],
)
def test_a_key_of_more_than_1024_characters_is_read(tmp_path: Path, block: str) -> None:
    """Test the `? key` form of YAML that pnpm writes for a long snapshot key, with the value in either layout."""
    text = PNPM_LOCK.replace(
        "      shared:\n", f"      long:\n        specifier: ^1.0.0\n        version: {LONG_KEY}\n      shared:\n"
    ).replace("snapshots:\n\n", f"snapshots:\n\n  leaf@2.0.0: {{}}\n\n{block}")
    path = tmp_path / "pnpm-lock.yaml"
    path.write_text(text, encoding="utf-8")

    names = {p.name for p in ra.read_pnpm_lock(path)}

    assert "a-very-long-package" in names
    assert ("leaf" in names) == ("leaf: 2.0.0" in block)


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


def test_the_real_pnpm_lock_is_read_when_the_lock_is_there() -> None:
    """Test the app's own lock, if this checkout has it: no snapshot may be missing and the tree is read."""
    path = REPO_ROOT / "app" / "pnpm-lock.yaml"
    if not path.exists():
        pytest.skip("no app lock in this checkout")

    packages = ra.read_pnpm_lock(path)

    assert {"nuxt", "vue"} <= {p.name for p in packages if p.direct}
    assert len(packages) > 500


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
        ([("repository", "ssh://git@github.com/vuejs/core.git")], "vuejs/core"),
        ([("repository", "github:unjs/h3")], "unjs/h3"),
        ([("repository", "unjs/h3")], "unjs/h3"),
        ([("Homepage", "https://numcodecs.readthedocs.io/"), ("Tracker", "https://gitlab.com/x/y")], None),
        ([("Homepage", "")], None),
        # B4: never the `.github` repository of an organisation, and links by the word of their label
        ([("Code of Conduct", "https://github.com/aio-libs/.github/blob/master/CODE_OF_CONDUCT.md")], None),
        (
            [
                ("Code of Conduct", "https://github.com/aio-libs/.github/blob/master/CODE_OF_CONDUCT.md"),
                ("Source Code", "https://github.com/aio-libs/frozenlist"),
            ],
            "aio-libs/frozenlist",
        ),
        ([("Security Policy", "https://github.com/a/policy"), ("Home", "https://github.com/a/code")], "a/code"),
        ([("Contributing", "https://github.com/a/contrib")], None),
        (
            [("bugs", "https://github.com/iconify/icon-sets/issues")],
            "iconify/icon-sets",
        ),  # an issue tracker is its repository
        ([("Bug Tracker", "https://github.com/a/tracker/issues"), ("Source", "https://github.com/a/code")], "a/code"),
        ([("Docs", "https://github.com/a/documents")], None),
        ([("Sponsor", "https://github.com/a/fund")], None),
        # the host is anchored
        ([("Source", "https://notgithub.com/x/y")], None),
        ([("Source", "https://gitlab.com/x/github.com")], None),
        ([("Source", "https://github.com.evil.example/x/y")], None),
        ([("Source", "https://evil.example/github.com/x/y")], None),
        ([("Source", "https://www.github.com/x/y")], "x/y"),
        ([("Source", "https://github.com/x/..")], None),
        ([("Source", "https://github.com/x/.")], None),
        ([("Source", "https://github.com/x/.github")], None),
        ([("Source", "https://github.com/x/pages.github.io")], None),
        ([("Source", "https://github.com/ünï/repo")], None),
        ([("Source", "https://github.com/x/rëpo")], None),
    ],
)
def test_the_github_repository_is_read_from_the_metadata_urls(urls: list[tuple[str, str]], repo: str | None) -> None:
    """Test the spellings of a repository URL, the labels that are skipped, and the hosts and names that are refused."""
    assert ra.github_repository(urls) == repo


def test_the_repository_named_like_the_package_wins() -> None:
    """Test that of two candidates the one that carries the package's name is taken, whatever their labels."""
    urls = [("Source", "https://github.com/org/umbrella"), ("Homepage", "https://github.com/org/frozenlist")]

    assert ra.github_repository(urls) == "org/umbrella"
    assert ra.github_repository(urls, "frozenlist") == "org/frozenlist"
    assert ra.github_repository(urls, "@scope/Frozenlist") == "org/frozenlist"


@pytest.mark.parametrize(
    ("name", "version"), [("frozenlist", "1.8.0"), ("yarl", "1.25.1"), ("multidict", "6.9.1"), ("propcache", "0.5.4")]
)
def test_the_aio_libs_packages_no_longer_resolve_to_the_dot_github_repository(name: str, version: str) -> None:
    """Test the real PyPI metadata that gave `aio-libs/.github`, through its "Code of Conduct" link."""
    net = FakeNet({f"https://pypi.org/pypi/{name}/{version}/json": ok(recorded(f"pypi_{name}_{version}.json"))})

    assert ra.resolve_repository(net, pkg(name, version)) == f"aio-libs/{name}"


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
    """Test that a missing version (404, 410, 451) and a repository elsewhere are `Unreadable`, not an empty answer."""
    net = FakeNet(
        {
            "https://pypi.org/pypi/cftime/1.6.6/json": ok(recorded("pypi_cftime_1.6.6.json")),
            "https://pypi.org/pypi/gone/1.0/json": status(404, {"message": "Not Found"}),
            "https://pypi.org/pypi/gone/2.0/json": status(410),
            "https://pypi.org/pypi/gone/3.0/json": status(451),
        }
    )

    with pytest.raises(ra.Unreadable, match="no GitHub repository"):
        ra.resolve_repository(net, pkg("cftime", "1.6.6"))
    for version in ("1.0", "2.0", "3.0"):
        with pytest.raises(ra.Unreadable, match="HTTP 4"):
            ra.resolve_repository(net, pkg("gone", version))


@pytest.mark.parametrize(
    "answer",
    [
        status(429),
        status(403),
        status(401),
        status(304),
        status(302),
        status(200, ["not", "an", "object"]),
        status(200, None),
        status(200, "text"),
    ],
)
def test_any_other_answer_of_pypi_or_npm_stops_the_run_and_is_not_unreadable(answer: Any) -> None:  # noqa: ANN401
    """Test that a rate limit, a refusal, a redirect and a malformed 200 raise: an empty set would read "None now"."""
    for ecosystem, url in (("pip", "https://pypi.org/pypi/x/1.0/json"), ("npm", "https://registry.npmjs.org/x/1.0.0")):
        version = "1.0" if ecosystem == "pip" else "1.0.0"
        with pytest.raises(ra.AdvisoryCheckError) as excinfo:
            ra.resolve_repository(FakeNet({url: answer}), pkg("x", version, ecosystem))
        assert not isinstance(excinfo.value, ra.Unreadable)


@pytest.mark.parametrize(
    "answer",
    [
        status(429),
        status(403, {"message": "Forbidden"}),
        status(401),
        status(302),
        status(304),
        status(500),
        status(200, {"a": 1}),
        status(200, None),
    ],
)
def test_any_other_answer_of_the_advisory_api_stops_the_run(answer: Any) -> None:  # noqa: ANN401
    """Test that only a repository that is not there (404, 410, 451) is unreadable; the rest raises."""
    net = FakeNet({advisories_url("o/r"): answer})

    with pytest.raises(ra.AdvisoryCheckError) as excinfo:
        ra.read_repository_advisories(net, "o/r")
    assert not isinstance(excinfo.value, ra.Unreadable)


@pytest.mark.parametrize("code", [404, 410, 451])
def test_a_repository_that_is_not_there_is_unreadable(code: int) -> None:
    """Test the three statuses that mean the repository or its advisories are gone."""
    with pytest.raises(ra.Unreadable):
        ra.read_repository_advisories(FakeNet({advisories_url("o/r"): status(code)}), "o/r")


def test_no_package_resolving_to_a_repository_is_an_error() -> None:
    """Test that a run in which every package is unreadable fails instead of reporting an empty result."""
    net = FakeNet({"https://pypi.org/pypi/cftime/1.6.6/json": ok(recorded("pypi_cftime_1.6.6.json"))})

    with pytest.raises(ra.AdvisoryCheckError, match="no package resolves"):
        ra.check([pkg("cftime", "1.6.6")], net, [], NOW)


def test_the_advisories_of_a_repository_are_read_page_by_page() -> None:
    """Test the `Link` header: the second page is read, and a next link to another host is not followed."""
    first = advisories_url("o/r")
    second = f"{ra.GITHUB_API}repositories/1/security-advisories?page=2"
    net = FakeNet(
        {
            first: ok([{"ghsa_id": "GHSA-2222-3333-4444"}], link=f'<{second}>; rel="next"'),
            second: ok([{"ghsa_id": "GHSA-5555-6666-7777"}], link='<https://evil.example/?page=3>; rel="next"'),
        }
    )

    assert [a["ghsa_id"] for a in ra.read_repository_advisories(net, "o/r")] == [
        "GHSA-2222-3333-4444",
        "GHSA-5555-6666-7777",
    ]
    assert [url for _, url in net.requests] == [first, second]


def test_twenty_pages_without_an_end_is_an_error_and_not_partial_data() -> None:
    """Test that a listing that never ends fails, instead of answering with the first twenty pages."""
    url = advisories_url("o/r")
    net = FakeNet({url: ok([{"ghsa_id": "GHSA-2222-3333-4444"}], link=f'<{url}>; rel="next"')})

    with pytest.raises(ra.AdvisoryCheckError, match="run over 20 pages"):
        ra.read_repository_advisories(net, "o/r")
    assert len(net.requests) == ra.MAX_PAGES


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
    """Test the advisory that GitHub's alerts did not list: found, with its fix, its link and the cooldown."""
    report = ra.check([pkg("numcodecs", "0.17.0")], numcodecs_net(), [], NOW)

    (finding,) = report.affected
    assert (finding.package.name, finding.advisory, finding.severity, finding.fixed) == (
        "numcodecs",
        "GHSA-jqc8-qjfv-5m6r",
        "high",
        "0.17.1",
    )
    assert finding.cooldown == "past"  # 0.17.1 was published on 2026-09-17
    assert finding.repo == "zarr-developers/numcodecs"
    assert finding.url == "https://github.com/zarr-developers/numcodecs/security/advisories/GHSA-jqc8-qjfv-5m6r"
    assert (finding.vulnerable, finding.patched) == (">= 0.17.0, < 0.17.1", "0.17.1")
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
    report = ra.check([pkg("numcodecs", "0.17.1")], numcodecs_net(), [], NOW)

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


def _one_repo_net(
    *advisories: dict[str, Any], package: str = "x", version: str = "1.0", eco: str = "pip"
) -> tuple[FakeNet, Any]:
    """Return a network with one package whose repository `o/r` holds `advisories`."""
    metadata = (
        {"info": {"project_urls": {"Source": "https://github.com/o/r"}}}
        if eco == "pip"
        else {"repository": "github:o/r"}
    )
    url = (
        f"https://pypi.org/pypi/{package}/{version}/json"
        if eco == "pip"
        else f"https://registry.npmjs.org/{package}/{version}"
    )
    net = FakeNet({url: ok(metadata), advisories_url("o/r"): ok(list(advisories))})
    return net, pkg(package, version, eco)


@pytest.mark.parametrize(
    ("entry", "bucket"),
    [
        (("pip", "x", ">= 0.5, < 2.0", None), "affected"),
        (("pypi", "x", ">= 0.5, < 2.0", None), "affected"),  # PyPI's other name for pip
        (("PyPI", "X", ">= 0.5, < 2.0", None), "affected"),
        (("npm", "x", ">= 0.5, < 2.0", None), "none"),  # another ecosystem's package of the same name
        (("rust", "x", ">= 0.5, < 2.0", None), "none"),
        (("", "x", ">= 0.5, < 2.0", None), "unclear"),  # a name that matches, an ecosystem nobody gave
        ((None, "x", ">= 0.5, < 2.0", None), "unclear"),
        (("pip", "", ">= 0.5, < 2.0", None), "unclear"),  # an entry without a name is about nobody and everybody
        (("pip", None, ">= 0.5, < 2.0", None), "unclear"),
        (("pip", "other", ">= 0.5, < 2.0", None), "none"),
    ],
)
def test_sloppy_entries_are_unclear_and_never_dropped(entry: tuple[Any, ...], bucket: str) -> None:
    """Test aliases, a missing ecosystem, a null or empty name: affected, unclear or about another package, no crash."""
    net, package = _one_repo_net(advisory("GHSA-2222-3333-4444", entry))

    report = ra.check([package], net, [], NOW)

    assert [len(report.affected), len(report.unclear)] == {"affected": [1, 0], "unclear": [0, 1], "none": [0, 0]}[
        bucket
    ]


def test_an_advisory_that_names_no_package_is_unclear_for_every_package_of_the_repository() -> None:
    """Test an advisory with no `package` and one with no list: both are about every package of its repository."""
    advisories = [
        {
            "ghsa_id": "GHSA-2222-3333-4444",
            "severity": "high",
            "vulnerabilities": [{"package": None, "vulnerable_version_range": "< 2"}],
        },
        {"ghsa_id": "GHSA-5555-6666-7777", "severity": "low", "vulnerabilities": None},
        {"ghsa_id": "GHSA-cfgh-jmpq-rvwx", "severity": "low"},
        "not even a dict",
    ]
    net = FakeNet(
        {
            "https://pypi.org/pypi/x/1.0/json": ok({"info": {"project_urls": {"Source": "https://github.com/o/r"}}}),
            "https://pypi.org/pypi/y/1.0/json": ok({"info": {"project_urls": {"Source": "https://github.com/o/r"}}}),
            advisories_url("o/r"): ok(advisories),
        }
    )

    report = ra.check([pkg("x", "1.0"), pkg("y", "1.0")], net, [], NOW)

    assert sorted((f.package.name, f.advisory) for f in report.unclear) == [
        (name, ghsa)
        for name in ("x", "y")
        for ghsa in ("GHSA-2222-3333-4444", "GHSA-5555-6666-7777", "GHSA-cfgh-jmpq-rvwx")
    ]
    assert not report.affected


@pytest.mark.parametrize(
    "ghsa", ["", "GHSA-short", "not-an-id", None, "GHSA-2222-3333-4444\n@someone", "javascript:alert(1)"]
)
def test_an_advisory_with_an_id_that_is_not_valid_is_unclear_and_shown_as_text(ghsa: Any) -> None:  # noqa: ANN401
    """Test that it is listed and not dropped, that no link is made of it, and that it can not be ignored by id."""
    net, package = _one_repo_net(advisory(ghsa, ("pip", "x", "< 2", None)))

    report = ra.check([package], net, [], NOW)

    (finding,) = report.unclear
    assert finding.reason == "the advisory id is not valid"
    assert not report.affected
    link = ra._advisory_link(finding)  # noqa: SLF001
    assert link.startswith("`")
    assert "(" not in link.replace("(no id)", "")
    assert "\n" not in link


def test_the_first_entry_does_not_decide_for_the_package() -> None:
    """Test that an advisory with an entry for another range first is judged by the entry that holds the version."""
    net, package = _one_repo_net(
        advisory("GHSA-2222-3333-4444", ("pip", "x", ">= 5.0, < 6.0", "6.0"), ("pip", "x", ">= 1.0, < 2.0", "2.0")),
        advisory("GHSA-5555-6666-7777", ("pip", "other", "< 9", None), ("pip", "x", "< 2", None)),
    )

    report = ra.check([package], net, [], NOW)

    assert sorted(f.advisory for f in report.affected) == ["GHSA-2222-3333-4444", "GHSA-5555-6666-7777"]
    assert next(f for f in report.affected if f.advisory == "GHSA-2222-3333-4444").fixed == "2.0"


def test_an_entry_that_affects_wins_over_one_that_is_unclear_in_the_same_advisory() -> None:
    """Test that the advisory is `affected` and not also `unclear` when one entry holds and another is unreadable."""
    net, package = _one_repo_net(
        advisory("GHSA-2222-3333-4444", ("pip", "x", "all", None), ("pip", "x", "< 2", None)),
        advisory("GHSA-5555-6666-7777", ("pip", "x", "< 2", None), ("pip", "x", "all", None)),
        advisory("GHSA-cfgh-jmpq-rvwx", ("pip", "x", "all", None)),
    )

    report = ra.check([package], net, [], NOW)

    assert sorted(f.advisory for f in report.affected) == ["GHSA-2222-3333-4444", "GHSA-5555-6666-7777"]
    assert [f.advisory for f in report.unclear] == ["GHSA-cfgh-jmpq-rvwx"]


def test_a_range_closed_by_a_fix_is_listed_as_read_as_fixed_and_not_as_affected() -> None:
    """Test the reading of a range without an upper bound whose fix is below the locked version: reported as such."""
    net, package = _one_repo_net(advisory("GHSA-2222-3333-4444", ("pip", "x", ">= 0.5", "0.9")), version="1.0")

    report = ra.check([package], net, [], NOW)

    assert not report.affected
    assert not report.unclear
    (finding,) = report.closed
    assert (finding.advisory, finding.vulnerable, finding.patched) == ("GHSA-2222-3333-4444", ">= 0.5", "0.9")
    assert "GHSA-2222-3333-4444" in ra.render_table(report)
    assert "## Read as fixed (1)" in ra.render_issue(report, NOW)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("high", "high"),
        ("critical", "critical"),
        ("medium", "medium"),
        ("low", "low"),
        ("HIGH", "unknown"),
        ("urgent", "unknown"),
        (None, "unknown"),
        ("@someone", "unknown"),
        (3, "unknown"),
    ],
)
def test_the_severity_is_one_of_four_words_or_unknown(raw: Any, expected: str) -> None:  # noqa: ANN401
    """Test that nothing but the four words of GitHub reaches the issue."""
    net, package = _one_repo_net(advisory("GHSA-2222-3333-4444", ("pip", "x", "< 2", None), severity=raw))

    (finding,) = ra.check([package], net, [], NOW).affected

    assert finding.severity == expected


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


@pytest.mark.parametrize(
    ("file", "repo", "package", "versions"),
    [
        ("advisories_h3.json", "unjs/h3", "h3", ["1.15.11", "1.15.5", "2.0.0-rc.10"]),
        ("advisories_vite.json", "vitejs/vite", "vite", ["5.4.21", "5.4.20", "6.2.6", "7.0.0"]),
        ("advisories_nuxt_all.json", "nuxt/nuxt", "nuxt", ["4.6.4", "4.4.5", "3.21.5", "3.21.6"]),
        ("advisories_fastmcp_all.json", "PrefectHQ/fastmcp", "fastmcp", ["4.1.3", "4.2.4", "2.14.0"]),
        ("advisories_pypdf.json", "py-pdf/pypdf", "pypdf", ["6.0.0", "5.0.0", "6.9.9"]),
        ("advisories_cryptography.json", "pyca/cryptography", "cryptography", ["50.0.2", "41.0.0", "46.0.0"]),
    ],
)
def test_whole_recorded_repositories_are_judged_without_a_crash(
    file: str, repo: str, package: str, versions: list[str]
) -> None:
    """Test every advisory of six real repositories against locked versions: affected, unclear or neither, no crash."""
    advisories = recorded(file)
    ecosystem = "npm" if package in ("h3", "vite", "nuxt") else "pip"

    for version in versions:
        affected, unclear, closed = ra.judge(pkg(package, version, ecosystem), advisories, repo)

        ids = {f.advisory for f in [*affected, *unclear, *closed]}
        assert len(ids) == len(affected) + len(unclear) + len(closed)  # each advisory in one bucket only
        assert all(
            f.repo == repo and f.url.startswith(f"https://github.com/{repo}/security/advisories/GHSA-")
            for f in [*affected, *unclear, *closed]
        )


def test_the_advisory_link_is_the_page_in_its_repository() -> None:
    """Test that the link goes to `html_url` of the advisory in its repository and not to the global database."""
    finding = ra.judge(pkg("numcodecs", "0.17.0"), recorded("advisories_numcodecs.json"), "zarr-developers/numcodecs")[
        0
    ][0]

    link = ra._advisory_link(finding)  # noqa: SLF001

    assert (
        link
        == "[GHSA-jqc8-qjfv-5m6r](https://github.com/zarr-developers/numcodecs/security/advisories/GHSA-jqc8-qjfv-5m6r)"
    )
    assert "github.com/advisories/" not in link


def test_an_html_url_of_another_page_is_not_used() -> None:
    """Test that a `html_url` that is not the advisory's own page is replaced by the page it must be."""
    entry = advisory("GHSA-2222-3333-4444", ("pip", "x", "< 2", None), html_url="https://evil.example/phish")

    (finding,) = ra.judge(pkg("x", "1.0"), [entry], "o/r")[0]

    assert finding.url == "https://github.com/o/r/security/advisories/GHSA-2222-3333-4444"


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


def test_a_foreign_package_is_unreadable_and_asks_nobody() -> None:
    """Test that a git or URL dependency is listed as unreadable without a request for it."""
    net = numcodecs_net()
    foreign = ra.Package(
        "npm", "forked", "git+https://github.com/someone/forked.git#abc", direct=True, runtime=True, foreign=True
    )

    report = ra.check([pkg("numcodecs", "0.17.0"), foreign], net, [], NOW)

    assert [(p.name, "git or URL" in reason) for p, reason in report.unreadable] == [("forked", True)]
    assert not [url for _, url in net.requests if "forked" in url]


def test_when_every_repository_is_unreadable_the_run_fails() -> None:
    """Test that 404 for every repository (all unreadable) is an error and not an empty result."""
    net = FakeNet(
        {
            "https://pypi.org/pypi/numcodecs/0.17.0/json": ok(recorded("pypi_numcodecs_0.17.0.json")),
            advisories_url("zarr-developers/numcodecs"): status(404),
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
    """Test that GitHub's four ways to say "later" raise `RateLimitError`, in the reading and in the issue listing."""
    net = numcodecs_net(**{advisories_url("zarr-developers/numcodecs"): answer})

    with pytest.raises(ra.RateLimitError):
        ra.check([pkg("numcodecs", "0.17.0")], net, [], NOW)
    with pytest.raises(ra.RateLimitError):
        ra.find_issues(FakeNet({issues_url(): answer}), "owner/repo")


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
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    code = ra.main(["--only", "python", "--uv-lock", str(_small_lock(tmp_path)), "--issue"], fetch=net, now=NOW)

    assert code == 2
    assert "rate limit" in capsys.readouterr().err
    assert not net.writes


# --------------------------------------------------------------------------------------------------------------------
# the ignore list
# --------------------------------------------------------------------------------------------------------------------


def ignore_entry(**changes: str) -> Any:  # noqa: ANN401
    """Return an entry of the ignore list for the numcodecs advisory as it is recorded."""
    values = {
        "package": "numcodecs",
        "advisory": "GHSA-jqc8-qjfv-5m6r",
        "reason": "the Pickle codec is never used",
        "date": "2026-11-25",
        "vulnerable": ">= 0.17.0, < 0.17.1",
        "patched": "0.17.1",
    } | changes
    return ra.IgnoreEntry(**values)


def test_an_ignored_advisory_is_listed_with_its_reason_and_not_as_a_finding() -> None:
    """Test that the entry moves the finding to `ignored` and that the entry is not stale."""
    report = ra.check([pkg("numcodecs", "0.17.0")], numcodecs_net(), [ignore_entry()], NOW)

    assert not report.affected
    assert [(f.package.name, e.reason) for f, e in report.ignored] == [("numcodecs", "the Pickle codec is never used")]
    assert not report.stale
    assert not report.changed


def test_an_entry_for_another_advisory_of_the_package_hides_nothing() -> None:
    """Test that the ignore key holds the advisory: an entry for GHSA-xxxx of numcodecs does not hide GHSA-jqc8."""
    other = ignore_entry(advisory="GHSA-2222-3333-4444")

    report = ra.check([pkg("numcodecs", "0.17.0")], numcodecs_net(), [other], NOW)

    assert [f.advisory for f in report.affected] == ["GHSA-jqc8-qjfv-5m6r"]
    assert not report.ignored


@pytest.mark.parametrize("changes", [{"vulnerable": ">= 0.17.0, < 0.17.5"}, {"patched": "0.17.5"}, {"patched": ""}])
def test_an_ignore_entry_stops_hiding_an_advisory_that_says_something_else(changes: dict[str, str]) -> None:
    """Test that the range or the patched versions of the advisory having changed brings the finding back."""
    report = ra.check([pkg("numcodecs", "0.17.0")], numcodecs_net(), [ignore_entry(**changes)], NOW)

    assert [f.advisory for f in report.affected] == ["GHSA-jqc8-qjfv-5m6r"]
    assert not report.ignored
    assert [e.advisory for e in report.changed] == ["GHSA-jqc8-qjfv-5m6r"]
    assert not report.stale
    assert "## Ignore entries to read again" in ra.render_issue(report, NOW)


def test_an_entry_for_one_locked_version_holds_for_that_version_only() -> None:
    """Test the `version` form: it hides the advisory at that version and not at another."""
    entry = ignore_entry(vulnerable="", patched="", version="0.17.0")

    assert ra.check([pkg("numcodecs", "0.17.0")], numcodecs_net(), [entry], NOW).ignored
    moved = ignore_entry(vulnerable="", patched="", version="0.16.0")
    assert ra.check([pkg("numcodecs", "0.17.0")], numcodecs_net(), [moved], NOW).affected


def test_an_entry_that_matches_nothing_any_more_is_stale_but_only_for_a_package_that_was_read() -> None:
    """Test that a fixed version leaves its entry stale, while the entry of a package not in this run is not."""
    other = ignore_entry(package="anyio", advisory="GHSA-g36m-r6gw-cj73")

    report = ra.check([pkg("numcodecs", "0.17.1")], numcodecs_net(), [ignore_entry(), other], NOW)

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
    entry = ignore_entry(
        package="pydantic", advisory="GHSA-5jqp-qgf6-3pvh", vulnerable="all", patched="v1.8.2,v1.7.4,v1.6.2"
    )

    report = ra.check([pkg("pydantic", "2.14.4")], net, [entry], NOW)

    assert not report.unclear
    assert len(report.ignored) == 1


def test_the_checked_in_ignore_list_is_valid_and_matches_what_the_advisories_state() -> None:
    """Test the real file: each entry names one advisory with its range, a reason and a date, and none repeats."""
    entries = ra.load_ignore(ra.IGNORE_FILE)

    assert entries
    assert all(e.package and ra.GHSA_ID.match(e.advisory) and e.reason and e.date and e.vulnerable for e in entries)
    assert len({(e.package, e.advisory) for e in entries}) == len(entries)
    # and each is what the recorded advisory says today
    for entry, file in zip(
        sorted(entries, key=lambda e: e.package),
        ["advisories_anyio.json", "advisories_fastmcp.json", "advisories_pydantic.json"],
        strict=True,
    ):
        (vulnerability,) = [v for a in recorded(file) if a["ghsa_id"] == entry.advisory for v in a["vulnerabilities"]]
        assert entry.vulnerable == vulnerability["vulnerable_version_range"]
        assert entry.patched == (vulnerability["patched_versions"] or "")


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (
            'package = "*"\nadvisory = "GHSA-jqc8-qjfv-5m6r"\nreason = "x"\ndate = "2026-11-25"\nrange = "< 1"',
            "never a wildcard",
        ),
        (
            'package = "numcodecs"\nadvisory = "GHSA-*"\nreason = "x"\ndate = "2026-11-25"\nrange = "< 1"',
            "never a wildcard",
        ),
        ('package = "numcodecs"\nadvisory = ""\nreason = "x"\ndate = "2026-11-25"\nrange = "< 1"', "never a wildcard"),
        (
            'package = "numcodecs"\nadvisory = "GHSA-jqc8-qjfv-5m6r"\nreason = ""\ndate = "2026-11-25"\nrange = "< 1"',
            "needs a reason",
        ),
        (
            'package = "numcodecs"\nadvisory = "GHSA-jqc8-qjfv-5m6r"\nreason = "x"\nrange = "< 1"',
            "needs a reason and a date",
        ),
        (
            'package = "numcodecs"\nadvisory = "GHSA-jqc8-qjfv-5m6r"\nreason = "x"\ndate = "yesterday"\nrange = "< 1"',
            "needs a reason",
        ),
        (
            'package = "numcodecs"\nadvisory = "GHSA-jqc8-qjfv-5m6r"\nreason = "x"\ndate = "2026-13-45"\nrange = "< 1"',
            "needs a reason",
        ),
        (
            'package = "numcodecs"\nadvisory = "GHSA-jqc8-qjfv-5m6r"\nreason = "x"\ndate = "2026-11-25"',
            "needs the `range`",
        ),
    ],
)
def test_an_ignore_entry_without_a_reason_or_a_date_or_the_range_or_with_a_wildcard_is_refused(
    tmp_path: Path, entry: str, message: str
) -> None:
    """Test that the list refuses a wildcard, a missing reason, a missing or impossible date and a missing range."""
    path = tmp_path / "ignore.toml"
    path.write_text(f"[[ignore]]\n{entry}\n", encoding="utf-8")

    with pytest.raises(ra.AdvisoryCheckError, match=message):
        ra.load_ignore(path)


def test_an_old_entry_is_listed_for_a_second_look_and_one_from_the_future_is_an_error() -> None:
    """Test the date: older than 180 days is listed in the report, and a date after today fails the run."""
    old = ignore_entry(date="2026-05-01")
    future = ignore_entry(date="2026-12-31")

    report = ra.check([pkg("numcodecs", "0.17.0")], numcodecs_net(), [old], NOW)

    assert [e.date for e in report.expired] == ["2026-05-01"]
    assert not report.affected  # an old entry still hides what it hides: it is a warning
    assert "## Ignore entries to review" in ra.render_issue(report, NOW)
    with pytest.raises(ra.AdvisoryCheckError, match="dated in the future"):
        ra.check([pkg("numcodecs", "0.17.0")], numcodecs_net(), [future], NOW)


# --------------------------------------------------------------------------------------------------------------------
# the issue
# --------------------------------------------------------------------------------------------------------------------


def finding(name: str = "numcodecs", version: str = "0.17.0", ecosystem: str = "pip", **changes: Any) -> Any:  # noqa: ANN401
    """Return a finding of an advisory in its repository."""
    values = {
        "advisory": "GHSA-jqc8-qjfv-5m6r",
        "severity": "high",
        "fixed": "0.17.1",
        "cooldown": "past",
        "repo": "zarr-developers/numcodecs",
        "url": "https://github.com/zarr-developers/numcodecs/security/advisories/GHSA-jqc8-qjfv-5m6r",
    } | changes
    return ra.Finding(pkg(name, version, ecosystem), **values)


def report_with(
    *, affected: bool = True, unclear: bool = False, unreadable: bool = False, ignored: bool = False
) -> Any:  # noqa: ANN401
    """Return a report with the lists asked for."""
    report = ra.Report(checked=130)
    if affected:
        report.affected.append(finding())
        report.affected.append(
            finding(
                "@nuxt/kit",
                "4.6.4",
                "npm",
                advisory="GHSA-vrh2-cfcx-c3fg",
                severity="medium",
                fixed=None,
                cooldown="no fix yet",
                repo="nuxt/nuxt",
                url="https://github.com/nuxt/nuxt/security/advisories/GHSA-vrh2-cfcx-c3fg",
            )
        )
    if unclear:
        report.unclear.append(
            finding(
                "pydantic",
                "2.14.4",
                advisory="GHSA-5jqp-qgf6-3pvh",
                reason="range `all` not understood",
                fixed=None,
                repo="pydantic/pydantic",
                url="https://github.com/pydantic/pydantic/security/advisories/GHSA-5jqp-qgf6-3pvh",
            )
        )
    if unreadable:
        report.unreadable.append((pkg("cftime", "1.6.6"), "no GitHub repository in the package metadata"))
    if ignored:
        report.ignored.append(
            (
                finding(
                    "anyio",
                    "4.15.1",
                    advisory="GHSA-g36m-r6gw-cj73",
                    repo="agronholm/anyio",
                    url="https://github.com/agronholm/anyio/security/advisories/GHSA-g36m-r6gw-cj73",
                ),
                ignore_entry(package="anyio", advisory="GHSA-g36m-r6gw-cj73", reason="run_process is not used"),
            )
        )
        report.stale.append(ignore_entry())
    return report


def test_the_issue_lists_the_findings_in_tables_and_lists() -> None:
    """Test the sections of the body: affected with its columns, unclear, unreadable, ignored and stale entries."""
    report = report_with(unclear=True, unreadable=True, ignored=True)
    body = ra.render_issue(report, NOW, "https://github.com/o/r/actions/runs/1")

    assert body.startswith(ra.ISSUE_MARKER)
    assert f"fingerprint: {report.fingerprint} " in body
    assert "| Package | Locked | Advisory | Severity | Fixed in | Past the cooldown | Scope | Repository |" in body
    assert (
        "| `numcodecs` | `0.17.0` "
        "| [GHSA-jqc8-qjfv-5m6r](https://github.com/zarr-developers/numcodecs/security/advisories/GHSA-jqc8-qjfv-5m6r) "
        "| high | `0.17.1` | past | python, direct | `zarr-developers/numcodecs` |"
    ) in body
    assert "| `@nuxt/kit` | `4.6.4` |" in body
    assert "| none yet | no fix yet | app, direct | `nuxt/nuxt` |" in body
    assert "## Unclear (1)" in body
    assert "## Unreadable (1)" in body
    assert "- `cftime` `1.6.6`: `no GitHub repository in the package metadata`" in body
    assert "## Known not to affect us (1)" in body
    assert "`run_process is not used` (2026-11-25)" in body
    assert "## Ignore entries to remove" in body
    assert "Run: https://github.com/o/r/actions/runs/1" in body
    assert "github.com/advisories/" not in body


def test_the_issue_mentions_nobody_and_copies_no_text_of_an_advisory() -> None:
    """Test that a scoped name, a hostile reason and an advisory summary come out as code or not at all."""
    report = report_with()
    report.affected[0] = finding("@evil/team", "1.0.0`@someone", "npm")
    report.unclear.append(
        finding("x", "1", advisory="GHSA-5jqp-qgf6-3pvh", reason="@maintainer please look\nsecond line `@x`")
    )

    body = ra.render_issue(report, NOW)

    assert "`@evil/team`" in body
    assert "`1.0.0 @someone`" in body
    assert "`@maintainer please look second line  @x`" in body
    for line in body.splitlines():
        if line.startswith(("<!--", "npm|", "pip|")):
            continue  # the hidden list, percent-encoded
        stripped = line.replace("`@evil/team`", "").replace("`@nuxt/kit`", "")
        for chunk in stripped.split("`")[::2]:  # the text outside code spans
            assert "@" not in chunk, line
    assert "summary" not in body.lower()


def test_the_hidden_list_of_affected_findings_has_no_at_sign() -> None:
    """Test that names are written percent-encoded in the comment, so that nothing in it can be read as a mention."""
    body = ra.render_issue(report_with(), NOW)
    block = re.search(r"<!-- affected\n(.*?)\n-->", body, re.DOTALL)

    assert block
    assert "@" not in block.group(1)
    assert "%40nuxt%2Fkit" in block.group(1)


def test_an_advisory_id_that_is_none_is_not_linked() -> None:
    """Test that only a well-formed id with a page in its repository becomes a link."""
    good = finding()

    assert ra._advisory_link(good).startswith("[GHSA-jqc8-qjfv-5m6r](https://github.com/")  # noqa: SLF001
    assert ra._advisory_link(dataclasses.replace(good, advisory="javascript:alert(1)")) == "`javascript:alert(1)`"  # noqa: SLF001
    assert ra._advisory_link(dataclasses.replace(good, url="")) == "`GHSA-jqc8-qjfv-5m6r`"  # noqa: SLF001
    elsewhere = dataclasses.replace(good, url="https://evil.example/x/security/advisories/GHSA-jqc8-qjfv-5m6r")
    assert ra._advisory_link(elsewhere) == "`GHSA-jqc8-qjfv-5m6r`"  # noqa: SLF001


def test_the_issue_says_none_now_when_nothing_is_affected() -> None:
    """Test the body of an update when nothing is affected any more."""
    body = ra.render_issue(report_with(affected=False), NOW)

    assert "## Affected\n\nNone now." in body
    assert "| Package |" not in body
    assert "<!-- affected" not in body


def test_the_fingerprint_changes_with_the_findings_the_version_and_the_fix() -> None:
    """Test that a new finding, another locked version and another fix change it; an ignored one does not."""
    base = report_with()

    assert base.fingerprint == report_with(unreadable=True, ignored=True).fingerprint
    assert base.fingerprint != report_with(unclear=True).fingerprint
    assert base.fingerprint != report_with(affected=False).fingerprint
    other_version = report_with()
    other_version.affected[0] = dataclasses.replace(other_version.affected[0], package=pkg("numcodecs", "0.17.3"))
    assert base.fingerprint != other_version.fingerprint
    other_fix = report_with()
    other_fix.affected[0] = dataclasses.replace(other_fix.affected[0], fixed="0.18.0")
    assert base.fingerprint != other_fix.fingerprint
    unclear_instead = report_with()
    unclear_instead.unclear.append(unclear_instead.affected.pop(0))
    assert base.fingerprint != unclear_instead.fingerprint  # affected and unclear are not the same finding


def test_the_body_compares_without_the_date_the_count_and_the_run() -> None:
    """Test that what differs in every run does not make an identical issue look changed."""
    report = report_with()
    first = ra.render_issue(report, NOW, "https://github.com/o/r/actions/runs/1")
    later = ra.render_issue(
        dataclasses.replace(report, checked=131), NOW + dt.timedelta(days=7), "https://github.com/o/r/actions/runs/9"
    )

    assert first != later
    assert ra.comparable(first) == ra.comparable(later)
    assert ra.comparable(first) != ra.comparable(ra.render_issue(report_with(unclear=True), NOW))


def issue_item(number: int, state: str, body: str | None, title: str | None = None, **extra: Any) -> dict[str, Any]:  # noqa: ANN401
    """Return an item of the issue listing: made by the bot, with the title of the check."""
    return {"number": number, "state": state, "title": title or ra.ISSUE_TITLE, "body": body, "user": BOT} | extra


def issues_net(items: list[dict[str, Any]]) -> FakeNet:
    """Return a network with an issue listing that holds `items`, and that accepts the writes."""
    routes: dict[str, Any] = {issues_url(): ok(items)}
    routes[f"{ra.GITHUB_API}repos/owner/repo/issues"] = lambda method, _payload: (
        ok({"number": 99}) if method == "POST" else status(405)
    )
    for item in items:
        routes[f"{ra.GITHUB_API}repos/owner/repo/issues/{item['number']}"] = lambda method, _payload: (
            ok({}) if method == "PATCH" else status(405)
        )
        routes[f"{ra.GITHUB_API}repos/owner/repo/issues/{item['number']}/comments"] = lambda method, _payload: (
            ok({}) if method == "POST" else status(405)
        )
    return FakeNet(routes)


def sync(net: FakeNet, report: Any, *, dry_run: bool = False) -> str:  # noqa: ANN401
    """Run `sync_issue` for `report`."""
    return ra.sync_issue(net, "owner/repo", report, ra.render_issue(report, NOW), dry_run=dry_run)


def test_a_first_finding_opens_one_issue_with_the_fixed_title_a_label_and_no_assignee() -> None:
    """Test the issue that is created: title, label and body, and nothing about assignees."""
    net = issues_net([])

    result = sync(net, report_with())

    assert result == "issue created"
    assert [method for method, _ in net.writes] == ["POST"]
    payload = net.payloads[-1]
    assert payload["title"] == ra.ISSUE_TITLE
    assert payload["labels"] == ["security"]
    assert set(payload) == {"title", "body", "labels"}  # no assignees, no milestone
    assert ra.ISSUE_MARKER in payload["body"]


def test_an_open_issue_is_updated_and_never_a_second_one_opened() -> None:
    """Test that the open issue gets the new body (a PATCH), one comment says it changed, and no issue is created."""
    net = issues_net([issue_item(7, "open", f"{ra.ISSUE_MARKER}\nold")])

    result = sync(net, report_with())

    assert result == "issue #7 updated and got a comment"
    assert net.writes == [
        ("PATCH", f"{ra.GITHUB_API}repos/owner/repo/issues/7"),
        ("POST", f"{ra.GITHUB_API}repos/owner/repo/issues/7/comments"),
    ]
    assert net.payloads[-1] == {"body": ra.CHANGED_COMMENT}
    assert ra.CHANGED_COMMENT == "The findings changed, see the list above."


def test_an_update_that_changes_no_finding_is_no_comment() -> None:
    """Test that a body that differs in its date only is neither written nor commented."""
    report = report_with()
    old = ra.render_issue(report, NOW - dt.timedelta(days=7), "https://github.com/o/r/actions/runs/1")
    net = issues_net([issue_item(7, "open", old)])

    assert sync(net, report) == "issue #7 is up to date"
    assert not net.writes


def test_a_changed_unclear_text_without_a_new_finding_updates_the_body_but_is_no_comment() -> None:
    """Test that the body is rewritten when a list changes, and the comment follows the fingerprint only."""
    report = report_with()
    old = ra.render_issue(report, NOW)
    report.unreadable.append((pkg("cftime", "1.6.6"), "no GitHub repository in the package metadata"))
    net = issues_net([issue_item(7, "open", old)])

    result = sync(net, report)

    assert result == "issue #7 updated"
    assert net.writes == [("PATCH", f"{ra.GITHUB_API}repos/owner/repo/issues/7")]


def test_when_nothing_is_affected_an_open_issue_is_updated_to_none_now_and_left_open() -> None:
    """Test that the issue is not closed: its body says none now, one comment says it changed, a person closes it."""
    net = issues_net([issue_item(7, "open", ra.render_issue(report_with(), NOW))])

    result = sync(net, report_with(affected=False))

    assert result == "issue #7 updated to none now and got a comment"
    assert [method for method, _ in net.writes] == ["PATCH", "POST"]


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


def test_only_the_issue_of_this_check_made_by_the_bot_is_found() -> None:
    """Test that a pull request, another title, no marker, another author and a user that is no bot are not taken."""
    marked = f"{ra.ISSUE_MARKER}\nbody"
    items = [
        issue_item(1, "open", marked, pull_request={"url": "x"}),
        issue_item(2, "open", marked, title="something else"),
        issue_item(3, "open", "somebody wrote the same title"),
        issue_item(4, "open", None),
        issue_item(5, "open", marked, user={"login": "someone", "type": "User"}),
        issue_item(6, "open", marked, user={"login": "github-actions[bot]", "type": "User"}),
        issue_item(7, "open", marked, user={"login": "github-actions", "type": "Bot"}),
        issue_item(8, "open", marked, user=None),
        issue_item(9, "closed", marked),
    ]

    found = ra.find_issues(issues_net(items), "owner/repo")

    assert [item["number"] for item in found] == [9]


def test_the_listing_asks_for_the_bots_issues_with_the_label_and_not_the_search() -> None:
    """Test the request: the creator, the label and every state, through the issues listing and not the search."""
    net = issues_net([])

    ra.find_issues(net, "owner/repo")

    ((method, url),) = net.requests
    assert method == "GET"
    assert "/repos/owner/repo/issues?" in url
    assert "creator=github-actions%5Bbot%5D" in url
    assert "labels=security" in url
    assert "state=all" in url
    assert "search" not in url


@pytest.mark.parametrize(
    "answer",
    [status(500), status(403, {"message": "Forbidden"}), status(404), status(200, {"items": []}), status(200, None)],
)
def test_a_listing_that_fails_stops_the_run_instead_of_finding_no_issue(answer: Any) -> None:  # noqa: ANN401
    """Test that no listing is not "no issue": that would open one every week."""
    with pytest.raises(ra.AdvisoryCheckError, match="cannot be listed"):
        ra.find_issues(FakeNet({issues_url(): answer}), "owner/repo")


def test_a_dry_run_reads_and_writes_nothing() -> None:
    """Test that `dry_run` names the action and makes no POST and no PATCH."""
    net = issues_net([])
    open_net = issues_net([issue_item(7, "open", f"{ra.ISSUE_MARKER}\nold")])

    assert sync(net, report_with(), dry_run=True) == "issue would be created"
    assert sync(open_net, report_with(), dry_run=True) == "issue #7 would be updated and would get a comment"
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


def test_a_package_the_open_issue_listed_does_not_leave_the_list_when_it_becomes_unreadable() -> None:
    """Test the carry-over: affected last week, unreadable this week, so still listed, and not "none now"."""
    last_week = ra.render_issue(report_with(), NOW - dt.timedelta(days=7))
    report = ra.Report(checked=130)
    report.unreadable += [
        (pkg("numcodecs", "0.17.0"), "gone/lost: cannot be read (HTTP 404)"),
        (pkg("@nuxt/kit", "4.6.4", "npm"), "x"),
    ]

    ra.carry_over(report, last_week)

    assert sorted(f.package.name for f in report.affected) == ["@nuxt/kit", "numcodecs"]
    carried = next(f for f in report.affected if f.package.name == "numcodecs")
    assert (carried.advisory, carried.fixed, carried.repo) == (
        "GHSA-jqc8-qjfv-5m6r",
        "0.17.1",
        "zarr-developers/numcodecs",
    )
    assert carried.cooldown.startswith("unknown")
    assert ra.render_issue(report, NOW).count("GHSA-jqc8-qjfv-5m6r") >= 1
    assert report.fingerprint == report_with().fingerprint  # nothing changed for a reader of the issue


def test_a_package_that_is_read_and_clean_leaves_the_list_and_a_new_version_does_not_carry() -> None:
    """Test that only an unreadable package is carried: a package read this week and found clean is not."""
    last_week = ra.render_issue(report_with(), NOW - dt.timedelta(days=7))
    clean = ra.Report(checked=130)
    other_version = ra.Report(checked=130)
    other_version.unreadable.append((pkg("numcodecs", "0.17.3"), "x"))

    ra.carry_over(clean, last_week)
    ra.carry_over(other_version, last_week)

    assert not clean.affected
    assert not other_version.affected


def test_a_hidden_list_that_somebody_edited_is_read_with_care() -> None:
    """Test that lines that are not a finding are dropped, and nothing in them is trusted."""
    body = "<!-- affected\nnot|enough\npip|x|1.0|not-an-id|high||o/r\nrust|x|1.0|GHSA-2222-3333-4444|high||o/r\n-->"

    assert ra.previous_affected(body) == []
    assert ra.previous_affected("") == []
    assert ra.previous_affected(None) == []  # type: ignore[arg-type]


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
    assert "zarr-developers/numcodecs" in table  # the repository that was read
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
        'range = ">= 0.17.0, < 0.17.1"\npatched = "0.17.1"\n'
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
    """Test the dry run of the weekly job: the body and the action are printed, nothing is written, no summary file."""
    net = numcodecs_net()
    net.routes[issues_url()] = ok([])
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    code = ra.main(
        ["--only", "python", "--uv-lock", str(_small_lock(tmp_path)), "--issue", "--dry-run"], fetch=net, now=NOW
    )

    out = capsys.readouterr().out
    assert code == 0
    assert ra.ISSUE_MARKER in out
    assert "issue would be created" in out
    assert "https://github.com/owner/repo/actions/runs/42" in out
    assert not net.writes
    assert not summary.exists()  # a dry run writes no job summary either


def test_the_real_run_writes_the_job_summary_and_the_issue(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the weekly job: the issue is created, the summary file holds the body and the result."""
    net = issues_net([])
    net.routes |= numcodecs_net().routes
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    code = ra.main(["--only", "python", "--uv-lock", str(_small_lock(tmp_path)), "--issue"], fetch=net, now=NOW)

    assert code == 0
    assert [method for method, _ in net.writes] == ["POST"]
    assert "issue created" in summary.read_text(encoding="utf-8")
    assert "issue created" in capsys.readouterr().out


def test_the_issue_is_written_by_the_workflow_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that `--issue` without `--dry-run` outside Actions is refused: a person's issue would not be the bot's."""
    net = numcodecs_net()
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    code = ra.main(["--only", "python", "--uv-lock", str(_small_lock(tmp_path)), "--issue"], fetch=net, now=NOW)

    assert code == 2
    assert "dry-run" in capsys.readouterr().err
    assert not net.requests


def test_the_command_with_issue_needs_the_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that `--issue` without a repository is an error and not a guess."""
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

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
    """Test that the Authorization header goes to api.github.com only, and a GitHub call elsewhere is refused."""
    seen: list[Any] = []

    def opened(request: urllib.request.Request) -> _Raw:
        seen.append(request)
        return _Raw(b'{"ok": true}')

    monkeypatch.setattr(ra, "_open", opened)
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
    sleeps: list[float] = []

    def opened(request: urllib.request.Request) -> _Raw:
        calls.append(request.full_url)
        code = 404 if "missing" in request.full_url else 502
        raise urllib.error.HTTPError(request.full_url, code, "x", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(ra, "_open", opened)
    monkeypatch.setattr(ra.time, "sleep", sleeps.append)
    fetch = ra.make_fetch(None)

    with pytest.raises(ra.AdvisoryCheckError, match="could not be read"):
        fetch("https://pypi.org/pypi/down/json")
    assert len(calls) == ra.RETRIES
    assert len(sleeps) == ra.RETRIES - 1  # no wait after the last try

    calls.clear()
    assert fetch("https://pypi.org/pypi/missing/json").status == 404
    assert len(calls) == 1


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("no route"),
        http.client.IncompleteRead(b"par"),
        http.client.RemoteDisconnected("gone"),
        TimeoutError(),
    ],
)
def test_a_transient_failure_is_retried_and_then_fails_the_run(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """Test that an unreachable host, a body cut short and a closed connection are retried, and then an error."""
    calls: list[int] = []

    def opened(request: urllib.request.Request) -> _Raw:  # noqa: ARG001
        calls.append(1)
        raise error

    monkeypatch.setattr(ra, "_open", opened)
    monkeypatch.setattr(ra.time, "sleep", lambda _: None)

    with pytest.raises(ra.AdvisoryCheckError, match="could not be read"):
        ra.make_fetch(None)("https://pypi.org/pypi/x/json")
    assert len(calls) == ra.RETRIES


def test_a_transient_failure_that_passes_is_an_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the second try of a body cut short answers."""
    outcomes: list[Any] = [http.client.IncompleteRead(b"par"), _Raw(b'{"ok": 1}')]

    def opened(request: urllib.request.Request) -> _Raw:  # noqa: ARG001
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(ra, "_open", opened)
    monkeypatch.setattr(ra.time, "sleep", lambda _: None)

    assert ra.make_fetch(None)("https://pypi.org/pypi/x/json").body == {"ok": 1}


def _redirect(url: str, new_url: str, method: str = "GET") -> Any:  # noqa: ANN401
    request = urllib.request.Request(url, method=method, headers={"Authorization": "Bearer t"})  # noqa: S310
    handler = ra._Redirects()  # noqa: SLF001
    return handler.redirect_request(request, None, 301, "Moved", {}, new_url)  # type: ignore[arg-type]


def test_a_redirect_never_takes_the_token_to_another_host_and_a_write_is_never_redirected() -> None:
    """Test the redirect handler: GitHub to GitHub is followed; to another host, or a POST or PATCH, it is not."""
    api = f"{ra.GITHUB_API}repos/o/r/security-advisories"

    followed = _redirect(api, f"{ra.GITHUB_API}repositories/1/security-advisories")
    assert followed is not None
    assert followed.get_header("Authorization") == "Bearer t"
    assert _redirect(api, "https://evil.example/steal") is None
    assert _redirect(api, "http://api.github.com.evil.example/x") is None
    assert _redirect(f"{ra.GITHUB_API}repos/o/r/issues", f"{ra.GITHUB_API}repos/o/r/issues/1", "POST") is None
    assert _redirect(f"{ra.GITHUB_API}repos/o/r/issues/1", f"{ra.GITHUB_API}repos/o/r/issues/2", "PATCH") is None
    # a registry may redirect anywhere: it holds no token
    assert _redirect("https://pypi.org/pypi/x/json", "https://files.example/x.json") is not None


@pytest.mark.parametrize("code", [301, 302, 307, 308])
def test_a_redirect_that_is_not_followed_is_an_answer_that_stops_the_run(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    """Test that an unfollowed redirect of the advisory API is read as what it is: an unexpected answer."""

    def opened(request: urllib.request.Request) -> _Raw:
        raise urllib.error.HTTPError(request.full_url, code, "Moved", {"Location": "https://evil.example/"}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(ra, "_open", opened)
    fetch = ra.make_fetch("t")

    with pytest.raises(ra.AdvisoryCheckError):
        ra.read_repository_advisories(fetch, "o/r")


# --------------------------------------------------------------------------------------------------------------------
# the workflow
# --------------------------------------------------------------------------------------------------------------------

WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "advisories.yml").read_text(encoding="utf-8")


def test_the_workflow_has_the_permissions_the_triggers_and_the_pins_it_should() -> None:
    """Test the file as text: minimal permissions, schedule and dispatch only, pinned actions, one credential."""
    assert re.search(r"^permissions: \{\}$", WORKFLOW, re.MULTILINE)
    assert re.search(r"^    permissions:\n      contents: read\n      issues: write$", WORKFLOW, re.MULTILINE)
    assert "pull_request" not in WORKFLOW.split("\njobs:")[0].replace("never on a pull request", "")
    assert "schedule:" in WORKFLOW
    assert "workflow_dispatch:" in WORKFLOW
    assert "persist-credentials: false" in WORKFLOW
    uses = re.findall(r"uses: (\S+)@(\S+) # (v\S+)", WORKFLOW)
    assert len(uses) == 2
    assert all(re.fullmatch(r"[0-9a-f]{40}", sha) for _, sha, _ in uses)
    assert len(re.findall(r"\$\{\{ ?secrets\.", WORKFLOW)) == 0
    assert WORKFLOW.count("${{ github.token }}") == 1


def test_the_token_reaches_a_script_that_runs_in_an_isolated_environment_without_the_project() -> None:
    """Test that nothing of the project is installed beside the token, and that the interpreter runs isolated."""
    run = re.search(r"run: (uv run .*)$", WORKFLOW, re.MULTILINE)

    assert run
    command = run.group(1)
    assert "--no-project" in command
    assert "--isolated" in command
    assert re.search(r"--with packaging==\d+\.\d+", command)
    assert "python -I scripts/repo_advisories.py --issue" in command
    assert "uv sync" not in WORKFLOW
    assert "uv run poe" not in WORKFLOW.replace("`uv run poe advisories`", "")
    assert command.count("${{") == 0  # nothing of the event in the shell


def test_the_workflow_runs_on_main_only_and_never_two_at_once() -> None:
    """Test that a manual run from a branch does not write the issue with that branch's script."""
    assert "if: github.ref == 'refs/heads/main'" in WORKFLOW
    assert re.search(r"concurrency:\n  cancel-in-progress: false\n  group:", WORKFLOW)


def test_the_pinned_packaging_is_the_one_the_lock_has() -> None:
    """Test that the version the job installs is a version of `packaging` the project locks as well."""
    pinned = re.search(r"packaging==(\S+)", WORKFLOW)
    lock = (REPO_ROOT / "uv.lock").read_text(encoding="utf-8")

    assert pinned
    assert f'name = "packaging"\nversion = "{pinned.group(1)}"' in lock

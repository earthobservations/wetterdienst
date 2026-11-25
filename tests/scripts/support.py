# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the tests of `scripts/repo_advisories.py` share: the script, the recorded answers and a fake network."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import ModuleType

SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "repo_advisories.py"
RECORDED = Path(__file__).parent / "recorded"
NOW = dt.datetime(2026, 11, 25, 12, 0, tzinfo=dt.UTC)
BOT = {"login": "github-actions[bot]", "type": "Bot"}


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
        self.payloads: list[Any] = []

    def __call__(self, url: str, *, github: bool = False, method: str = "GET", payload: Any = None) -> Any:  # noqa: ANN401, ARG002
        """Answer one request."""
        self.requests.append((method, url))
        self.payloads.append(payload)
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


def issues_url(repo: str = "owner/repo") -> str:
    """Return the URL of the listing of the bot's issues."""
    return (
        f"{ra.GITHUB_API}repos/{repo}/issues?creator=github-actions%5Bbot%5D&state=all"
        "&sort=created&direction=desc&per_page=100"
    )


def pkg(name: str, version: str, ecosystem: str = "pip", *, direct: bool = True, runtime: bool = True) -> Any:  # noqa: ANN401
    """Return a locked package."""
    return ra.Package(ecosystem, name, version, direct, runtime)


def advisory(ghsa: str, *entries: tuple[Any, ...], **fields: Any) -> dict[str, Any]:  # noqa: ANN401
    """Return an advisory as the API writes it, with `(ecosystem, name, range, patched)` entries."""
    return {
        "ghsa_id": ghsa,
        "severity": "high",
        "withdrawn_at": None,
        "html_url": f"https://github.com/o/r/security/advisories/{ghsa}",
        "vulnerabilities": [
            {"package": {"ecosystem": e, "name": n}, "vulnerable_version_range": r, "patched_versions": p}
            for e, n, r, p in entries
        ],
    } | fields

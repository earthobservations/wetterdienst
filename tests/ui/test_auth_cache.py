# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The provider is probed for its credentials at most once a minute per network (GH-2607)."""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from wetterdienst import Wetterdienst
from wetterdienst.ui import core
from wetterdienst.ui.core import (
    _AUTH_PROBE_TTL_SECONDS,
    _AUTH_PROBE_UNKNOWN_TTL_SECONDS,
    _ProbeCache,
    get_auth,
)
from wetterdienst.ui.restapi import app

KEY = ("metno", "frost")


class _Clock:
    """A clock that moves only when told to."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class _Probe:
    """A probe that answers from a list, the last answer for ever, and counts its calls."""

    def __init__(self, answers: list[bool | None]) -> None:
        self.answers = answers
        self.calls = 0

    def __call__(self) -> bool | None:
        self.calls += 1
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def test_a_second_call_within_the_ttl_does_not_probe() -> None:
    """The answer of the first call is the answer of the second."""
    clock, probe = _Clock(), _Probe([True, False])
    cache = _ProbeCache(clock)
    assert cache.get(KEY, probe) is True
    clock.now += _AUTH_PROBE_TTL_SECONDS - 1
    assert cache.get(KEY, probe) is True
    assert probe.calls == 1


def test_a_call_after_the_ttl_probes_again() -> None:
    """The answer expires, and the provider is asked once more, once."""
    clock, probe = _Clock(), _Probe([True, False])
    cache = _ProbeCache(clock)
    assert cache.get(KEY, probe) is True
    clock.now += _AUTH_PROBE_TTL_SECONDS
    assert cache.get(KEY, probe) is False
    assert cache.get(KEY, probe) is False
    assert probe.calls == 2


def test_a_rejection_is_kept_as_long_as_an_acceptance() -> None:
    """`False` is an answer, not a failure to get one."""
    clock, probe = _Clock(), _Probe([False, True])
    cache = _ProbeCache(clock)
    assert cache.get(KEY, probe) is False
    clock.now += _AUTH_PROBE_UNKNOWN_TTL_SECONDS + 1
    assert cache.get(KEY, probe) is False
    assert probe.calls == 1


def test_an_unknown_answer_is_kept_for_a_few_seconds_only() -> None:
    """A probe that could not tell is asked again soon, so that an outage that ends is not reported for a minute."""
    clock, probe = _Clock(), _Probe([None, True])
    cache = _ProbeCache(clock)
    assert cache.get(KEY, probe) is None
    clock.now += _AUTH_PROBE_UNKNOWN_TTL_SECONDS - 1
    assert cache.get(KEY, probe) is None
    assert probe.calls == 1
    clock.now += 1
    assert cache.get(KEY, probe) is True
    assert probe.calls == 2
    assert _AUTH_PROBE_UNKNOWN_TTL_SECONDS < _AUTH_PROBE_TTL_SECONDS


def test_networks_are_answered_apart() -> None:
    """The answer for one network is not the answer for another."""
    cache = _ProbeCache(_Clock())
    assert cache.get(("metno", "frost"), _Probe([True])) is True
    assert cache.get(("aemet", "observation"), _Probe([False])) is False


def test_clear_forgets_every_answer() -> None:
    """The cache can be bypassed, which tests that change the credentials rely on."""
    probe = _Probe([True, False])
    cache = _ProbeCache(_Clock())
    assert cache.get(KEY, probe) is True
    cache.clear()
    assert cache.get(KEY, probe) is False
    assert probe.calls == 2


def test_a_probe_that_raises_leaves_nothing_behind() -> None:
    """An exception escaping the probe is not an answer, and the next call probes again."""
    cache = _ProbeCache(_Clock())

    def failing() -> bool:
        msg = "boom"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError):
        cache.get(KEY, failing)
    probe = _Probe([True])
    assert cache.get(KEY, probe) is True
    assert probe.calls == 1


def test_concurrent_callers_make_one_probe() -> None:
    """Callers that start together wait for the probe that runs and reuse its answer."""
    threads_n = 12
    cache = _ProbeCache(_Clock())
    # every thread and the test: nobody calls before all are ready, and the probe is held until all are let go
    barrier = threading.Barrier(threads_n + 1, timeout=10)
    release = threading.Event()
    calls: list[int] = []
    answers: list[bool | None] = []

    def probe() -> bool:
        calls.append(1)
        assert release.wait(timeout=10)
        return True

    def call() -> None:
        barrier.wait()
        answers.append(cache.get(KEY, probe))

    threads = [threading.Thread(target=call) for _ in range(threads_n)]
    for thread in threads:
        thread.start()
    barrier.wait()
    release.set()
    for thread in threads:
        thread.join(timeout=10)
    assert len(calls) == 1
    assert answers == [True] * threads_n


class _Api:
    """A request class that needs credentials, as far as `get_auth` asks."""

    metadata = type("Metadata", (), {"auth": True})()


@pytest.fixture
def probes(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Have the provider configured and every probe of it accepted; return the probes made."""
    calls: list[object] = []
    monkeypatch.setattr(Wetterdienst, "is_configured", staticmethod(lambda _api: True))
    monkeypatch.setattr(Wetterdienst, "is_valid", staticmethod(lambda api: calls.append(api) or True))
    return calls


def test_get_auth_probes_once_and_answers_the_same(probes: list[object]) -> None:
    """The three surfaces share `get_auth`, so a repeated call is answered without the provider."""
    first = get_auth(_Api, "metno", "frost")
    second = get_auth(_Api, "metno", "frost")
    assert first == second == {"provider": "metno", "network": "frost", "auth": True, "configured": True, "valid": True}
    assert len(probes) == 1


def test_get_auth_probes_again_after_the_cache_is_cleared(probes: list[object]) -> None:
    """The cache is cleared as a test does, to probe again."""
    get_auth(_Api, "metno", "frost")
    core._auth_probes.clear()  # noqa: SLF001
    get_auth(_Api, "metno", "frost")
    assert len(probes) == 2


def test_get_auth_does_not_probe_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """A network that is not configured is answered as before, without a probe."""
    monkeypatch.setattr(Wetterdienst, "is_configured", staticmethod(lambda _api: False))

    def probe(_api: object) -> None:
        pytest.fail("the provider was probed")

    monkeypatch.setattr(Wetterdienst, "is_valid", staticmethod(probe))
    assert get_auth(_Api, "metno", "frost")["valid"] is False


def test_the_rest_route_probes_once_in_a_minute(probes: list[object], monkeypatch: pytest.MonkeyPatch) -> None:
    """Repeated `/api/auth` calls within the TTL are answered with the first answer, in the same shape."""
    monkeypatch.setattr(core, "_auth_probes", _ProbeCache(_Clock()))
    client = TestClient(app)
    params = {"provider": "aemet", "network": "observation"}
    bodies = [client.get("/api/auth", params=params).json() for _ in range(3)]
    expected = {"provider": "aemet", "network": "observation", "auth": True, "configured": True, "valid": True}
    assert bodies == [expected] * 3
    assert len(probes) == 1


def test_every_spelling_of_a_network_is_one_probe_and_one_key(probes: list[object]) -> None:
    """The key is the resolved network, so another spelling of its name neither probes again nor adds a key."""
    api = Wetterdienst.resolve("metno", "frost")
    assert Wetterdienst.resolve(" METNO", "frost ") is api
    for provider, network in [("metno", "frost"), ("METNO", "Frost"), (" metno", "frost ")]:
        get_auth(api, provider, network)
    assert len(probes) == 1
    assert len(core._auth_probes._entries) == 1  # noqa: SLF001


def test_the_spellings_of_a_network_on_the_rest_route_are_one_probe(probes: list[object]) -> None:
    """`/api/auth` resolves the name before the cache is asked, whichever way it is written."""
    client = TestClient(app)
    statuses = []
    for provider in ["aemet", "AEMET", " aemet"]:
        response = client.get("/api/auth", params={"provider": provider, "network": "observation"})
        statuses.append(response.status_code)
    assert statuses == [200, 200, 200]
    assert len(probes) == 1
    assert len(core._auth_probes._entries) == 1  # noqa: SLF001


def test_an_unknown_network_adds_no_key(probes: list[object]) -> None:
    """A name that does not resolve is refused before the cache is asked, and no probe or key comes of it."""
    client = TestClient(app)
    for provider, network in [("nonexistent", "fake"), ("metno", "nonexistent")]:
        response = client.get("/api/auth", params={"provider": provider, "network": network})
        assert response.status_code == 404
    assert probes == []
    assert core._auth_probes._entries == {}  # noqa: SLF001

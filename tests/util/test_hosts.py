# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The host names the REST API's `Host` and `Origin` check reads (GH-3087)."""

from __future__ import annotations

import pytest

from wetterdienst.util.hosts import (
    host_of_header,
    host_of_origin,
    is_allowed,
    is_loopback,
    loopback_allowed_hosts,
    normalize_host,
    split_listen_address,
)


@pytest.mark.parametrize(
    ("entry", "normal"),
    [
        ("Example.COM", "example.com"),
        (" localhost:7890 ", "localhost:7890"),
        ("127.0.0.1", "127.0.0.1"),
        ("[::1]", "[::1]"),
        ("::1", "[::1]"),
        ("[::1]:7890", "[::1]:7890"),
        ("*.example.org", "*.example.org"),
        ("my_host-1", "my_host-1"),
    ],
)
def test_an_entry_is_read_as_a_host_name_with_an_optional_port(entry: str, normal: str) -> None:
    """The case is dropped, an IPv6 address gets its brackets, and a port or a wildcard is kept."""
    assert normalize_host(entry) == normal


@pytest.mark.parametrize(
    "entry",
    [
        "",
        "  ",
        "http://localhost",
        "localhost/path",
        "user@localhost",
        "local host",
        "localhost:",
        "localhost:99999",
        "localhost:abc",
        "[::1",
        "[nonsense]",
        "*",
        "exa mple.org",
        "-bad.example",
        "a..b",
    ],
)
def test_an_entry_that_is_no_host_is_refused(entry: str) -> None:
    """A URL, a path, a user, a space, a bad port or an address that is none say what is expected."""
    with pytest.raises(ValueError, match=r"host name|empty entry"):
        normalize_host(entry)


def test_the_host_of_a_header_and_of_an_origin_keep_the_port() -> None:
    """A `Host` is lower-cased as it is; an `Origin` is a scheme and an authority, `null` is none."""
    assert host_of_header("Example.com:7890") == "example.com:7890"
    assert host_of_header("") is None
    assert host_of_header(None) is None
    assert host_of_origin("https://Example.com:8443") == "example.com:8443"
    assert host_of_origin("http://[::1]:4000") == "[::1]:4000"
    assert host_of_origin("http://localhost") == "localhost"
    assert host_of_origin("null") is None
    assert host_of_origin("not an origin") is None
    assert host_of_origin("https://") is None


def test_a_name_without_a_port_lets_every_port_in_and_a_name_with_one_only_that() -> None:
    """The port is checked only where the entry names one; a wildcard is for the names below the domain."""
    allowed = ("localhost", "[::1]", "example.org:8080", "*.example.net")

    assert is_allowed("localhost", allowed)
    assert is_allowed("localhost:7890", allowed)
    assert is_allowed("[::1]:7890", allowed)
    assert is_allowed("example.org:8080", allowed)
    assert not is_allowed("example.org:9090", allowed)
    assert not is_allowed("example.org", allowed)
    assert is_allowed("a.example.net:1", allowed)
    assert not is_allowed("example.net", allowed)
    assert not is_allowed("evilexample.net", allowed)
    assert not is_allowed("evil.example", allowed)
    assert not is_allowed("localhost.evil.example", allowed)
    assert not is_allowed(None, allowed)
    # nothing listed: any host, also none
    assert is_allowed("anything", ())
    assert is_allowed(None, ())


@pytest.mark.parametrize(
    ("host", "loopback"),
    [
        ("127.0.0.1", True),
        ("localhost", True),
        ("LOCALHOST", True),
        ("::1", True),
        ("[::1]", True),
        ("127.0.0.2", True),
        ("0.0.0.0", False),  # noqa: S104
        ("192.168.1.2", False),
        ("::", False),
        ("example.org", False),
    ],
)
def test_a_loopback_listen_host_is_told_from_the_rest(host: str, *, loopback: bool) -> None:
    """The loopback interface is `localhost` or an address of it; the wildcard address is not."""
    assert is_loopback(host) is loopback


def test_a_listen_address_is_split_at_its_last_colon() -> None:
    """An IPv6 host is taken with or without its brackets."""
    assert split_listen_address("127.0.0.1:7890") == ("127.0.0.1", 7890)
    assert split_listen_address("[::1]:7890") == ("::1", 7890)
    assert split_listen_address("::1:7890") == ("::1", 7890)
    assert split_listen_address("localhost:1") == ("localhost", 1)
    for bad in ("7890", "localhost", "localhost:", ":7890", "localhost:abc"):
        with pytest.raises(ValueError, match="listen address"):
            split_listen_address(bad)


def test_a_loopback_server_lists_the_loopback_names_and_the_host_it_listens_on() -> None:
    """The three names, and the host of `--listen` where it is one of its own (127.0.0.2)."""
    assert loopback_allowed_hosts("127.0.0.1") == ("localhost", "127.0.0.1", "[::1]")
    assert loopback_allowed_hosts("::1") == ("localhost", "127.0.0.1", "[::1]")
    assert loopback_allowed_hosts("127.0.0.2") == ("localhost", "127.0.0.1", "[::1]", "127.0.0.2")

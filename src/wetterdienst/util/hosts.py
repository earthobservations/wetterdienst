# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Host names as the REST API's `Host` and `Origin` check reads them (GH-3087).

A name is compared without its case, and without the port unless the entry that lists it has one: `localhost` lets
`localhost:7890` and `localhost:3000` in, `localhost:7890` only the first. An IPv6 address is written in brackets, as
in a `Host` header (`[::1]`). `*.example.com` lists every name below `example.com`, not `example.com` itself.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

#: the names a server listening on the loopback interface lets in unless it is told otherwise
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "[::1]")

#: a DNS name (a leading `*.` allowed), without a port
_NAME = re.compile(r"(\*\.)?[a-z0-9_]([a-z0-9_-]*[a-z0-9_])?(\.[a-z0-9_]([a-z0-9_-]*[a-z0-9_])?)*")


def normalize_host(entry: str) -> str:
    """Read an entry of the allowed hosts, or refuse it with a message that says what is expected.

    An entry is a host name, an IPv4 address or an IPv6 address in brackets, with a port if the port is to be
    checked as well; `*.example.com` stands for every name below `example.com`. A bare IPv6 address gets its brackets.
    """
    text = entry.strip().lower()
    expected = "a host name, optionally with a port (`example.com`, `localhost:7890`, `[::1]`, `*.example.com`)"
    if not text:
        msg = f"an empty entry; expected {expected}"
        raise ValueError(msg)
    if "/" in text or "@" in text or "?" in text or "#" in text or any(character.isspace() for character in text):
        msg = f"{entry.strip()!r} is not {expected}; give the host alone, no scheme, path or user"
        raise ValueError(msg)
    try:
        if isinstance(ipaddress.ip_address(text), ipaddress.IPv6Address):
            return f"[{text}]"
    except ValueError:
        pass
    host, port = _split_port(text)
    if host.startswith("["):
        try:
            ipaddress.IPv6Address(host[1:-1])
        except ValueError:
            host = ""
    elif not _NAME.fullmatch(host):
        host = ""
    if not host or (port is not None and not (port.isdigit() and 0 < int(port) < 65536)):
        msg = f"{entry.strip()!r} is not {expected}"
        raise ValueError(msg)
    return text


def _split_port(authority: str) -> tuple[str, str | None]:
    """Split the host and the port of a `Host` header value or an entry, the port None if there is none."""
    if authority.startswith("["):
        host, bracket, rest = authority.partition("]")
        if not bracket or (rest and not rest.startswith(":")):
            return "", None
        return f"{host}]", rest[1:] if rest else None
    host, colon, port = authority.partition(":")
    return host, port if colon else None


def host_of_header(value: str | None) -> str | None:
    """Read the host of a `Host` header value, its port kept (`example.com:7890`), None where there is none."""
    if not value:
        return None
    return value.strip().lower() or None


def host_of_origin(value: str | None) -> str | None:
    """Read the host of an `Origin` header value, its port kept; None for `null` or what is no origin."""
    if not value:
        return None
    try:
        parts = urlsplit(value.strip().lower())
        host, port = parts.hostname, parts.port
    except ValueError:
        return None
    if not parts.scheme or not host:
        return None
    if ":" in host:
        host = f"[{host}]"
    return f"{host}:{port}" if port is not None else host


def is_allowed(authority: str | None, allowed: tuple[str, ...]) -> bool:
    """Tell whether a `Host` or `Origin` host (`name` or `name:port`) is listed; anything is where nothing is listed."""
    if not allowed:
        return True
    if not authority:
        return False
    host, _port = _split_port(authority)
    for entry in allowed:
        if entry.startswith("*."):
            if host.endswith(entry[1:]) and len(host) > len(entry) - 1:
                return True
        elif entry in {authority, host}:
            return True
    return False


def is_loopback(host: str) -> bool:
    """Tell whether a `--listen` host is the loopback interface: `localhost` or a loopback address."""
    text = host.strip().strip("[]").lower()
    if text == "localhost":
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


def split_listen_address(listen_address: str) -> tuple[str, int]:
    """Split a `host:port` listen address, the host of an IPv6 address in brackets or not (`[::1]:7890`, `::1:7890`)."""
    host, colon, port = listen_address.rpartition(":")
    if not colon or not host or not port.isdigit():
        msg = f"{listen_address!r} is not a listen address as host:port"
        raise ValueError(msg)
    return host.strip("[]"), int(port)


def loopback_allowed_hosts(listen_host: str) -> tuple[str, ...]:
    """Give the hosts a server listening on a loopback `listen_host` lets in: the loopback names, and that host."""
    host = f"[{listen_host.strip('[]')}]" if ":" in listen_host else listen_host
    return tuple(dict.fromkeys((*LOOPBACK_HOSTS, host.lower())))

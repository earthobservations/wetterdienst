# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The one way the library reads XML a provider sent (GH-3350).

Every provider that parses XML does it here, so that what a document may make the parser do is written down once
and not left to a default of lxml, which has changed between releases and differs between `iterparse`, `fromstring`
and `XMLParser`: no entity is replaced (`resolve_entities=False`; libxml2 refuses a document whose entities
amplify, a billion-laughs one, as a syntax error), no external DTD or entity is fetched from the network
(`no_network=True`), no DTD is loaded or validated against, none supplies default attributes, and the limits of
libxml2 on the depth of a tree and the length of a text stay on (`huge_tree=False`). A reader of a document that
needs more gets an option here, not a parser of its own: `tests/util/test_xml.py` fails for a module of the package
that builds one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lxml.etree import XMLParser, fromstring, iterparse

if TYPE_CHECKING:
    from typing import BinaryIO

    from lxml.etree import _Element

#: what the parsers of `lxml` are given, each written out although some are the default of the lxml in use
SAFE_OPTIONS: dict[str, bool] = {
    "resolve_entities": False,
    "no_network": True,
    "load_dtd": False,
    "dtd_validation": False,
    "attribute_defaults": False,
    "huge_tree": False,
}


def xml_parser() -> XMLParser:
    """Give a parser for one document, with the options of `SAFE_OPTIONS`."""
    return XMLParser(**SAFE_OPTIONS)


def parse_xml(content: bytes | str) -> _Element:
    """Parse a whole document and give its root element, with the options of `SAFE_OPTIONS`."""
    return fromstring(content, parser=xml_parser())


def iterparse_xml(source: BinaryIO | str, events: tuple[str, ...] = ("end",)) -> Any:  # noqa: ANN401
    """Parse a document as it is read and give its `(event, element)` pairs, with the options of `SAFE_OPTIONS`.

    `source` is a file object or a path, as for `lxml.etree.iterparse`, which returns an iterator of its own type.
    """
    return iterparse(source, events=events, **SAFE_OPTIONS)

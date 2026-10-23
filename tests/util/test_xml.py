# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the one way the library reads XML a provider sent (GH-3350).

Three things are held. A document that names an external DTD and external entities, on the network and on disk, is
read by the helper's parsers without fetching either; every reader of a provider parses through those parsers; and no
module of the package builds a parser of its own, which is how one comes to leave an option to a default of lxml.

What the hostile document can and cannot tell: the libxml2 of the lxml wheels (2.14) has no HTTP client, so a parser
given `no_network=False` does not reach the listener either (the `minimum-versions` job, lxml 4.9.1 on libxml2 2.9,
may), and the file entity of a provider's document lands in an element no reader returns. So the test of the
helper's parsers has a control (a parser that resolves entities does read the file), the options each parser is given
are pinned, and the providers are held to the helper by recording what reaches lxml and by the scan of the package.
"""

from __future__ import annotations

import ast
import re
import socket
import threading
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from lxml.etree import XMLParser, fromstring, iterparse, tostring

import wetterdienst
from tests.provider.dwd.alerts.test_parser import CAP_XML
from wetterdienst import Settings
from wetterdienst.provider.dwd.alerts.parser import parse_cap_alert
from wetterdienst.provider.dwd.dmo.api import _placemark_metadata
from wetterdienst.provider.dwd.mosmix.access import KMLReader
from wetterdienst.provider.fmi.observation.parser import (
    extract_exception_text,
    parse_fmi_observations,
    parse_fmi_stations,
)
from wetterdienst.util import xml as wd_xml
from wetterdienst.util.xml import SAFE_OPTIONS, iterparse_xml, parse_xml, xml_parser

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

SECRET = "TOPSECRET-READ-FROM-DISK"  # noqa: S105

FMI_STATIONS = b"""<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection
    xmlns:wfs="http://www.opengis.net/wfs/2.0"
    xmlns:gml="http://www.opengis.net/gml/3.2"
    xmlns:ef="http://inspire.ec.europa.eu/schemas/ef/4.0">
  <wfs:member>
    <ef:EnvironmentalMonitoringFacility>
      <gml:identifier codeSpace="http://xml.fmi.fi/namespace/stationcode/fmisid">100971</gml:identifier>
      <gml:name codeSpace="http://xml.fmi.fi/namespace/locationcode/name">Helsinki Kaisaniemi</gml:name>
      <gml:pos>60.17523 24.94459</gml:pos>
    </ef:EnvironmentalMonitoringFacility>
  </wfs:member>
</wfs:FeatureCollection>"""

FMI_OBSERVATIONS = b"""<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection
    xmlns:wfs="http://www.opengis.net/wfs/2.0"
    xmlns:BsWfs="http://xml.fmi.fi/schema/wfs/2.0">
  <wfs:member>
    <BsWfs:BsWfsElement>
      <BsWfs:Time>2024-01-01T00:00:00Z</BsWfs:Time>
      <BsWfs:ParameterName>tday</BsWfs:ParameterName>
      <BsWfs:ParameterValue>-1.0</BsWfs:ParameterValue>
    </BsWfs:BsWfsElement>
  </wfs:member>
</wfs:FeatureCollection>"""

FMI_EXCEPTION = b"""<?xml version="1.0" encoding="UTF-8"?>
<ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows/1.1">
  <ows:Exception exceptionCode="OperationProcessingFailed">
    <ows:ExceptionText>too many</ows:ExceptionText>
  </ows:Exception>
</ows:ExceptionReport>"""

DMO_RUN = (
    b'<kml:kml xmlns:kml="http://www.opengis.net/kml/2.2"><kml:Document>'
    b"<kml:Placemark><kml:name>10382</kml:name><kml:description>BERLIN-TEGEL</kml:description>"
    b"<kml:Point><kml:coordinates>13.31,52.56,36.0</kml:coordinates></kml:Point></kml:Placemark>"
    b"</kml:Document></kml:kml>"
)

MOSMIX_RUN = b"""<kml:kml xmlns:kml="http://www.opengis.net/kml/2.2"
    xmlns:dwd="https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd">
  <kml:Document>
    <kml:ExtendedData>
      <dwd:ProductDefinition>
        <dwd:Issuer>DWD</dwd:Issuer>
        <dwd:ProductID>MOSMIX</dwd:ProductID>
        <dwd:GeneratingProcess>L</dwd:GeneratingProcess>
        <dwd:IssueTime>2026-10-23T09:00:00.000Z</dwd:IssueTime>
        <dwd:ForecastTimeSteps>
          <dwd:TimeStep>2026-10-23T10:00:00.000Z</dwd:TimeStep>
          <dwd:TimeStep>2026-10-23T11:00:00.000Z</dwd:TimeStep>
        </dwd:ForecastTimeSteps>
      </dwd:ProductDefinition>
    </kml:ExtendedData>
    <kml:Placemark>
      <kml:name>01001</kml:name>
      <kml:ExtendedData>
        <dwd:Forecast dwd:elementName="TTT"><dwd:value>270.0 271.5</dwd:value></dwd:Forecast>
      </kml:ExtendedData>
    </kml:Placemark>
  </kml:Document>
</kml:kml>"""


class Listener:
    """A socket on the loopback interface that records who connects, and answers nobody."""

    def __init__(self) -> None:
        """Listen on a port the system picks, and accept in a thread."""
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen()
        self.sock.settimeout(0.05)
        self.port = self.sock.getsockname()[1]
        self.peers: list[object] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept, daemon=True)
        self._thread.start()

    def _accept(self) -> None:
        while not self._stop.is_set():
            try:
                connection, peer = self.sock.accept()
            except OSError:
                continue
            self.peers.append(peer)
            connection.close()

    def connections(self) -> list[object]:
        """Stop accepting, then take what is still waiting in the backlog, and give everyone who connected."""
        self._stop.set()
        self._thread.join()
        self.sock.settimeout(0)
        while True:
            try:
                connection, peer = self.sock.accept()
            except OSError:
                break
            self.peers.append(peer)
            connection.close()
        return self.peers

    def close(self) -> None:
        """Stop and close the socket."""
        self._stop.set()
        self._thread.join()
        self.sock.close()


@pytest.fixture
def listener() -> Iterator[Listener]:
    """Listen where the hostile documents point."""
    server = Listener()
    yield server
    server.close()


@pytest.fixture
def secret(tmp_path: Path) -> Path:
    """Write the file a document names as an external entity."""
    path = tmp_path / "secret.txt"
    path.write_text(SECRET, encoding="utf-8")
    return path


def hostile(document: bytes, listener: Listener, secret: Path) -> bytes:
    """Give a document with an external DTD, a parameter entity and two external entities, referenced in its root.

    The DTD and one entity are on the listener, the other entity is a file. The references stand in a `<note>` that
    is the first child of the root, an element no reader looks at.
    """
    start = re.search(rb"<([A-Za-z_][\w.:-]*)", document)
    assert start is not None
    root = start.group(1)
    url = f"http://127.0.0.1:{listener.port}".encode()
    doctype = (
        b'<!DOCTYPE %s SYSTEM "%s/evil.dtd" [\n'
        b'  <!ENTITY %% remote SYSTEM "%s/parameter.dtd">\n'
        b'  <!ENTITY net SYSTEM "%s/entity">\n'
        b'  <!ENTITY disk SYSTEM "%s">\n'
        b"  %%remote;\n"
        b"]>\n" % (root, url, url, url, secret.as_uri().encode())
    )
    document = document[: start.start()] + doctype + document[start.start() :]
    # the end of the root's start tag, which no document of this file writes a `>` inside of
    tag_end = document.index(b">", document.index(b"<" + root, document.index(b"]>")))
    return document[: tag_end + 1] + b"<note>before &net; and &disk; after</note>" + document[tag_end + 1 :]


def _kml_reader_data(document: bytes) -> object:
    reader = KMLReader(station_ids=["01001"], settings=Settings(cache_disable=True))
    reader.fetch = lambda _url: BytesIO(document)  # ty: ignore[invalid-assignment]
    reader.read("https://example.invalid/run.kmz")
    return reader.data, reader.metadata["product_id"], reader.timesteps


def _whole_tree(document: bytes) -> object:
    return tostring(parse_xml(document))


def _iterated(document: bytes) -> object:
    return [(element.tag, element.text) for _, element in iterparse_xml(BytesIO(document))]


#: each reader the library has, with the document it reads and the answer it gives a document without the DOCTYPE
READERS: dict[str, tuple[bytes, Callable[[bytes], object]]] = {
    "parse_xml": (b"<a><b>1</b></a>", _whole_tree),
    "iterparse_xml": (b"<a><b>1</b></a>", _iterated),
    "mosmix": (MOSMIX_RUN, _kml_reader_data),
    "dmo": (DMO_RUN, lambda document: _placemark_metadata(BytesIO(document)).to_dicts()),
    "alerts": (CAP_XML, parse_cap_alert),
    "fmi_stations": (FMI_STATIONS, lambda document: parse_fmi_stations(document).to_dicts()),
    "fmi_observations": (FMI_OBSERVATIONS, lambda document: parse_fmi_observations(document).to_dicts()),
    "fmi_exception": (FMI_EXCEPTION, extract_exception_text),
}


@pytest.mark.parametrize("name", READERS)
def test_a_document_naming_an_external_dtd_and_entities_is_read_without_fetching_them(
    name: str, listener: Listener, secret: Path
) -> None:
    """A DOCTYPE with external DTD and entities does not change what a reader answers, and nothing is fetched."""
    document, read = READERS[name]
    plain = read(document)
    assert plain not in (None, [], {}, ()), "a reader that answers nothing proves nothing"

    answer = read(hostile(document, listener, secret))

    assert listener.connections() == []
    assert SECRET not in repr(answer)
    if name not in {"parse_xml", "iterparse_xml"}:
        assert answer == plain


@pytest.mark.parametrize("name", [name for name in READERS if name not in {"parse_xml", "iterparse_xml"}])
def test_every_reader_of_a_provider_parses_through_the_helper(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """What reaches lxml from a provider's reader is a parser built with the safe options, and at least one.

    The hostile document does not show it for a provider (see the module docstring), so this does: `XMLParser` and
    `iterparse` as the helper calls them are recorded, and each call must carry `SAFE_OPTIONS` and nothing less.
    """
    given: list[dict[str, object]] = []

    def parser(**kwargs: object) -> XMLParser:
        given.append(kwargs)
        return XMLParser(**kwargs)

    def parse_incrementally(source: object, **kwargs: object) -> object:
        given.append({k: v for k, v in kwargs.items() if k != "events"})
        return iterparse(source, **kwargs)

    monkeypatch.setattr(wd_xml, "XMLParser", parser)
    monkeypatch.setattr(wd_xml, "iterparse", parse_incrementally)
    document, read = READERS[name]

    read(document)

    assert given != []
    assert all(kwargs == SAFE_OPTIONS for kwargs in given)


def test_a_parser_that_resolves_entities_does_read_the_file(secret: Path) -> None:
    """The control of the test above: what it holds the readers back from is there to be read."""
    document = f'<!DOCTYPE a [<!ENTITY disk SYSTEM "{secret.as_uri()}">]><a><note>&disk;</note></a>'.encode()

    unsafe = fromstring(document, parser=XMLParser(resolve_entities=True, no_network=True))
    safe = parse_xml(document)

    assert SECRET in (unsafe.findtext("note") or "")
    assert SECRET not in tostring(safe, encoding="unicode")
    assert b"&disk;" in tostring(safe)


def test_the_hostile_document_is_one_the_parser_accepts(listener: Listener, secret: Path) -> None:
    """A document that is refused for its DOCTYPE would pass the test above for the wrong reason."""
    root = parse_xml(hostile(b"<a><b>1</b></a>", listener, secret))

    assert root.findtext("b") == "1"
    assert root.getroottree().docinfo.system_url == f"http://127.0.0.1:{listener.port}/evil.dtd"


def test_every_parser_is_given_the_safe_options(monkeypatch: pytest.MonkeyPatch) -> None:
    """The options are passed, not left to the default of the lxml in use.

    The libxml2 of the wheels cannot fetch from the network at all, so what no behaviour shows is held here: each
    option reaches `XMLParser` and `iterparse` by name.
    """
    given: list[tuple[str, dict[str, object]]] = []

    def parser(**kwargs: object) -> object:
        given.append(("XMLParser", kwargs))
        return XMLParser(**kwargs)

    def parse_incrementally(_source: object, **kwargs: object) -> object:
        given.append(("iterparse", kwargs))
        return iter(())

    monkeypatch.setattr(wd_xml, "XMLParser", parser)
    monkeypatch.setattr(wd_xml, "iterparse", parse_incrementally)

    xml_parser()
    iterparse_xml(BytesIO(b"<a/>"), events=("start", "end"))
    iterparse_xml(BytesIO(b"<a/>"))

    assert given[0] == ("XMLParser", SAFE_OPTIONS)
    assert given[1] == ("iterparse", {"events": ("start", "end"), **SAFE_OPTIONS})
    assert given[2] == ("iterparse", {"events": ("end",), **SAFE_OPTIONS})
    assert SAFE_OPTIONS == {
        "resolve_entities": False,
        "no_network": True,
        "load_dtd": False,
        "dtd_validation": False,
        "attribute_defaults": False,
        "huge_tree": False,
    }


#: the packages whose parsers a module may not import: `xml_parser`, `parse_xml` and `iterparse_xml` are the way
_PARSER_PACKAGES = frozenset({"lxml", "xml", "defusedxml"})
#: modules of those packages that write XML and parse none
_NOT_PARSERS = frozenset({"xml.sax.saxutils"})
#: the functions that import a module by the name they are given
_IMPORTERS = frozenset({"import_optional", "import_module"})


def _is_parser_module(name: str) -> bool:
    return name.split(".", maxsplit=1)[0] in _PARSER_PACKAGES and name not in _NOT_PARSERS


def _called(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    return func.attr if isinstance(func, ast.Attribute) else None


def _parsers_built_outside_the_helper(source: str) -> list[int]:
    """Give the lines of a module that import an XML parser, or call `read_xml`, outside `if TYPE_CHECKING`.

    An import is a statement or a call of `import_optional` or `import_module` with the name as a string. The
    `else` branch of `if TYPE_CHECKING` is run, and so is read.
    """
    tree = ast.parse(source)
    type_checking = {
        id(node)
        for block in ast.walk(tree)
        if isinstance(block, ast.If) and ast.unparse(block.test) in {"TYPE_CHECKING", "typing.TYPE_CHECKING"}
        for statement in block.body
        for node in ast.walk(statement)
    }
    lines = []
    for node in ast.walk(tree):
        if id(node) in type_checking:
            continue
        hit = False
        if isinstance(node, ast.Import):
            hit = any(_is_parser_module(alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            hit = node.level == 0 and _is_parser_module(node.module or "")
        elif isinstance(node, ast.Call):
            first = node.args[0] if node.args else None
            hit = _called(node) == "read_xml" or (
                _called(node) in _IMPORTERS
                and isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and _is_parser_module(first.value)
            )
        if hit:
            lines.append(node.lineno)  # ty: ignore[unresolved-attribute]
    return lines


def test_no_module_builds_an_xml_parser_of_its_own() -> None:
    """XML is read through `util/xml.py`, so that a new reader is given the same options as the others (GH-3350).

    A module that imports `lxml`, `xml` or `defusedxml` outside `if TYPE_CHECKING` (for the type of an element),
    or calls `read_xml`, builds a parser with whatever its defaults are. The reader a provider needs is a function
    of `util/xml.py` or a new option of it, not a parser of the module's own.
    """
    root = Path(wetterdienst.__file__).parent
    found = {}
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        if relative == "util/xml.py":
            continue
        lines = _parsers_built_outside_the_helper(path.read_text(encoding="utf-8"))
        if lines:
            found[relative] = lines
    assert found == {}


@pytest.mark.parametrize(
    "source",
    [
        "from lxml.etree import XMLParser",
        "import lxml.etree",
        "from lxml import etree",
        "import xml.etree.ElementTree as ET",
        "from xml.dom import minidom",
        "import defusedxml.ElementTree",
        "import pandas as pd\nframe = pd.read_xml(path)",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    pass\nfrom lxml.etree import fromstring",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    pass\nelse:\n    from lxml.etree import XMLParser",
        'etree = import_optional("lxml.etree", "radar")',
        'etree = importlib.import_module("lxml.etree")',
    ],
)
def test_the_scan_finds_a_parser_built_outside_the_helper(source: str) -> None:
    """The scan above is not silent: each way of building a parser is found."""
    assert _parsers_built_outside_the_helper(source) != []


@pytest.mark.parametrize(
    "source",
    [
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from lxml.etree import _Element\n",
        "from xml.sax.saxutils import escape",
        'frame = import_optional("polars", "x")',
    ],
)
def test_the_scan_leaves_alone_what_parses_nothing(source: str) -> None:
    """An element is typed under `if TYPE_CHECKING`, and `xml.sax.saxutils` only writes."""
    assert _parsers_built_outside_the_helper(source) == []

# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the one way the library reads XML a provider sent (GH-3350).

Two things are held. A document that names an external DTD and external entities, on the network and on disk, is read
by every parser the library builds without fetching either; and no module of the package builds a parser of its own,
which is how one comes to leave an option to a default of lxml.

What the network half can and cannot tell: the libxml2 of the lxml wheels (2.14) has no HTTP client, so a parser given
`no_network=False` does not reach the listener either, and the listener alone would stay silent on a parser that is
wrong. The file half has a control (a parser that resolves entities does read the file), and the options half pins
what each parser is given, so the guarantee does not rest on that build.
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
from lxml.etree import XMLParser, fromstring, tostring

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
    reader.fetch = lambda _url: BytesIO(document)  # type: ignore[method-assign]
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
    """Every reader answers a document with a DOCTYPE as one without, and reaches neither its DTD nor its entities."""
    document, read = READERS[name]
    plain = read(document)
    assert plain not in (None, [], {}, ()), "a reader that answers nothing proves nothing"

    answer = read(hostile(document, listener, secret))

    assert listener.connections() == []
    assert SECRET not in repr(answer)
    if name not in {"parse_xml", "iterparse_xml"}:
        assert answer == plain


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
    iterparse_xml(BytesIO(b"<a/>"), events=["start", "end"])
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


def _parsers_built_outside_the_helper(source: str) -> list[int]:
    """Give the lines of a module that import an XML parser, or call pandas' `read_xml`, outside `if TYPE_CHECKING`."""
    tree = ast.parse(source)
    type_checking = {
        id(node)
        for block in ast.walk(tree)
        if isinstance(block, ast.If) and ast.unparse(block.test) in {"TYPE_CHECKING", "typing.TYPE_CHECKING"}
        for node in ast.walk(block)
    }
    lines = []
    for node in ast.walk(tree):
        if id(node) in type_checking:
            continue
        if isinstance(node, ast.Import):
            hit = any(alias.name.split(".")[0] in _PARSER_PACKAGES for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            hit = node.level == 0 and (node.module or "").split(".")[0] in _PARSER_PACKAGES
        elif isinstance(node, ast.Call):
            func = node.func
            hit = (isinstance(func, ast.Name) and func.id == "read_xml") or (
                isinstance(func, ast.Attribute) and func.attr == "read_xml"
            )
        else:
            hit = False
        if hit:
            lines.append(node.lineno)
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
    ],
)
def test_the_scan_finds_a_parser_built_outside_the_helper(source: str) -> None:
    """The scan above is not silent: each way of building a parser is found."""
    assert _parsers_built_outside_the_helper(source) != []


def test_the_scan_leaves_the_types_of_elements_alone() -> None:
    """An element is typed under `if TYPE_CHECKING`, which parses nothing."""
    source = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from lxml.etree import _Element\n"
    assert _parsers_built_outside_the_helper(source) == []

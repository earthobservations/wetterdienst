"""
About
=====

Read XML/KML files efficiently, in terms of CPU and RAM usage.
Here, we are looking at the DWD ``MOSMIX_L/all_stations`` (large) dataset,
which is essentially a single XML file with 1.8 GB file size.

-- https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/all_stations/kml/


Why?
====

- `Acquire data from MOSMIX_L/all_stations dataset <https://github.com/earthobservations/wetterdienst/issues/586>`_
- `Improve efficiency when reading large XML/KML files <https://github.com/earthobservations/wetterdienst/pull/607>`_

All other implementations are not efficient enough, as they load the whole file
content into memory. This is not feasible in resource-constrained environments.

- https://github.com/FL550/simple_dwd_weatherforecast
- https://github.com/jeremiahpslewis/dwdbulk
- https://pypi.org/project/pykml/
- https://pypi.org/project/fastkml/


Reference
=========

- http://blog.behnel.de/posts/faster-xml-stream-processing-in-python.html


Setup
=====
::

    pip install lxml pykml psutil


Synopsis
========
::

    # Acquire data.
    wget https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/all_stations/kml/MOSMIX_L_LATEST.kmz
    unzip MOSMIX_L_LATEST.kmz

    # Decode data.
    KMLFILE=MOSMIX_L_2022030215.kml
    time python wetterdienst/provider/dwd/mosmix/mosmix_large_stream.py lxml-stream ${KMLFILE}
    time python wetterdienst/provider/dwd/mosmix/mosmix_large_stream.py pykml ${KMLFILE}

"""
import sys
from pathlib import Path
from typing import Union

import lxml.etree as ET

MOSMIX_L_URL = "https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/all_stations/kml/MOSMIX_L_LATEST.kmz"


class KMLStreamReader:
    def __init__(self, uri: Union[Path, str]):
        self.uri = uri

    def read(self):
        count = 0
        for event, element in ET.iterparse(self.uri, events=("end",)):
            if event == "end":
                # if elem.tag == 'location' and elem.text and 'Africa' in elem.text:
                #    count += 1
                #
                # print(f"Element: {element}")
                element.clear()
                count += 1
        return count


def memory_used():
    # pip install psutil
    import os

    import psutil

    process = psutil.Process(os.getpid())
    return process.memory_info().rss


def parse_lxml_stream(path: str):
    ksr = KMLStreamReader(uri=path)
    count = ksr.read()
    print(f"Elements seen: {count}")
    print(f"Memory used:   {memory_used()}")


def parse_pykml(path: str):
    from pykml.parser import parse

    with open(path, "rb") as f:
        obj = parse(f)
        count = 0
        for element in obj.iter():
            # print(f"Element: {element}")
            # element.clear()
            count += 1
        print(f"Elements seen: {count}")
        print(f"Memory used:   {memory_used()}")


if __name__ == "__main__":
    parser = sys.argv[1]
    path = sys.argv[2]
    if parser == "lxml-stream":
        parse_lxml_stream(path)
    elif parser == "pykml":
        parse_pykml(path)
    else:
        raise KeyError(f"Unknown parser")

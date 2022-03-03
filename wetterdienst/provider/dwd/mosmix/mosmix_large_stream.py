"""
About
=====

Read DWD MOSMIX LARGE XML/KML files efficiently.

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

"""
About
=====

Read DWD MOSMIX LARGE XML/KML files efficiently.

Reference
=========

- http://blog.behnel.de/posts/faster-xml-stream-processing-in-python.html

Synopsis
========
::

    wget https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/all_stations/kml/MOSMIX_L_LATEST.kmz
    unzip MOSMIX_L_LATEST.kmz
    time python wetterdienst/provider/dwd/mosmix/mosmix_large_stream.py MOSMIX_L_2022030215.kml

"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Union

MOSMIX_L_URL = "https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/all_stations/kml/MOSMIX_L_LATEST.kmz"


class KMLStreamReader:
    def __init__(self, uri: Union[Path, str]):
        self.uri = uri

    def read(self):
        print(f"Parsing KML")
        for event, elem in ET.iterparse(self.uri, events=("end",)):
            if event == "end":
                # if elem.tag == 'location' and elem.text and 'Africa' in elem.text:
                #    count += 1
                #
                print(f"Element: {elem}")
                elem.clear()


if __name__ == "__main__":
    path = sys.argv[1]
    ksr = KMLStreamReader(uri=path)
    ksr.read()

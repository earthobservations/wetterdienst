# Source:
# https://github.com/jlewis91/dwdbulk/blob/master/dwdbulk/api/forecasts.py
import logging
from enum import Enum
from io import BytesIO
from typing import List, Optional
from zipfile import ZipFile
from os.path import basename

from lxml.etree import parse, XMLParser  # noqa: S410
from pandas import DatetimeIndex
from tqdm import tqdm
import numpy as np
import pandas as pd

from wetterdienst.dwd.network import create_dwd_session

log = logging.getLogger(__name__)


class KMLReader:
    def __init__(
        self,
        station_ids: Optional[List[str]] = None,
        parameters: Optional[List[Enum]] = None,
    ) -> None:
        if parameters:
            parameters = [parameter.value for parameter in parameters]

        self.station_ids = station_ids
        self.parameters = parameters
        self.metadata = {}
        self.root = None
        self.timesteps = []
        self.items = []

        self.dwd_session = create_dwd_session()

    def download(self, url: str):
        # https://stackoverflow.com/questions/37573483/progress-bar-while-download-file-over-http-with-requests  # noqa:E501,B950

        response = self.dwd_session.get(url, stream=True)
        response.raise_for_status()

        total = int(response.headers.get("content-length", 0))

        buffer = BytesIO()
        with tqdm(
            desc=url,
            total=total,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for data in response.iter_content(chunk_size=1024):
                size = buffer.write(data)
                bar.update(size)

        return buffer

    def fetch(self, url) -> bytes:
        """
        Fetch weather forecast file (zipped xml).
        """
        buffer = self.download(url)
        kmz = ZipFile(buffer, "r")
        kml = kmz.open(kmz.namelist()[0], "r").read()
        return kml

    def read(self, url: str):
        """
        Download and read DWD XML Weather Forecast File of Type KML.
        """

        log.info(f"Downloading KMZ file {basename(url)}")
        kml = self.fetch(url)

        log.info("Parsing KML data")
        # TODO: Check if XML parsing performance can be improved by using libxml2.
        tree = parse(BytesIO(kml), parser=XMLParser(huge_tree=True))  # noqa: S320
        self.root = root = tree.getroot()

        prod_items = {
            "issuer": "Issuer",
            "product_id": "ProductID",
            "generating_process": "GeneratingProcess",
            "issue_time": "IssueTime",
        }

        # Get Basic Metadata
        prod_definition = root.findall(
            "kml:Document/kml:ExtendedData/dwd:ProductDefinition", root.nsmap
        )[0]

        self.metadata = {
            k: prod_definition.find(f"{{{root.nsmap['dwd']}}}{v}").text
            for k, v in prod_items.items()
        }
        self.metadata["issue_time"] = pd.Timestamp(self.metadata["issue_time"])

        # Get time steps.
        timesteps = root.findall(
            "kml:Document/kml:ExtendedData/dwd:ProductDefinition/dwd:ForecastTimeSteps",
            root.nsmap,
        )[0]
        self.timesteps = DatetimeIndex(
            [pd.Timestamp(i.text) for i in timesteps.getchildren()]
        )

        # Find all kml:Placemark items.
        self.items = root.findall("kml:Document/kml:Placemark", root.nsmap)

    def iter_items(self):
        for item in self.items:
            station_id = item.find("kml:name", self.root.nsmap).text

            if (self.station_ids is None) or station_id in self.station_ids:
                yield item

    def get_metadata(self):
        return pd.DataFrame([self.metadata])

    def get_forecasts(self):
        for station_forecast in self.iter_items():
            station_ids = station_forecast.find("kml:name", self.root.nsmap).text

            measurement_list = station_forecast.findall(
                "kml:ExtendedData/dwd:Forecast", self.root.nsmap
            )
            df = pd.DataFrame({"station_id": station_ids, "datetime": self.timesteps})

            for measurement_item in measurement_list:

                measurement_parameter = measurement_item.get(
                    f"{{{self.root.nsmap['dwd']}}}elementName"
                )

                if self.parameters is None or measurement_parameter in self.parameters:
                    measurement_string = measurement_item.getchildren()[0].text

                    measurement_values = " ".join(measurement_string.split()).split(" ")
                    measurement_values = [
                        np.nan if i == "-" else float(i) for i in measurement_values
                    ]

                    assert len(measurement_values) == len(  # noqa:S101
                        self.timesteps
                    ), "Number of timesteps does not match number of measurement values"

                    df[measurement_parameter] = measurement_values

            yield df

# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
# Source:
# https://github.com/jlewis91/dwdbulk/blob/master/dwdbulk/api/forecasts.py
import logging
from io import BytesIO
from os.path import basename
from typing import List

import numpy as np
import pandas as pd
from fsspec.implementations.zip import ZipFileSystem
from lxml.etree import XMLParser, parse  # noqa: S410
from pandas import DatetimeIndex
from tqdm import tqdm

from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.io import read_in_chunks
from wetterdienst.util.logging import TqdmToLogger
from wetterdienst.util.network import NetworkFilesystemManager

log = logging.getLogger(__name__)


class KMLReader:
    def __init__(
        self,
        station_ids: List[str],
        parameters: List[str],
    ) -> None:
        self.station_ids = station_ids
        self.parameters = parameters
        self.metadata = {}
        self.root = None
        self.timesteps = []
        self.items = []

        self.dwdfs = NetworkFilesystemManager.get(ttl=CacheExpiry.FIVE_MINUTES)

    def download(self, url: str) -> BytesIO:
        """Download kml file as bytes.
        https://stackoverflow.com/questions/37573483/progress-bar-while-download-file-over-http-with-requests

        block_size: int or None
                    Bytes to download in one request; use instance value if None. If
                    zero, will return a streaming Requests file-like instance.

        :param url: url string to kml file
        :return: kml file as bytes
        """

        response = self.dwdfs.open(url, block_size=0)
        total = self.dwdfs.size(url)

        buffer = BytesIO()

        tqdm_out = TqdmToLogger(log, level=logging.INFO)

        with tqdm(
            desc=url,
            total=total,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
            file=tqdm_out,
        ) as bar:
            for data in read_in_chunks(response, chunk_size=1024):
                size = buffer.write(data)
                bar.update(size)

        return buffer

    def fetch(self, url) -> bytes:
        """
        Fetch weather mosmix file (zipped xml).
        """
        buffer = self.download(url)
        zfs = ZipFileSystem(buffer, "r")
        return zfs.open(zfs.glob("*")[0]).read()

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
        prod_definition = root.findall("kml:Document/kml:ExtendedData/dwd:ProductDefinition", root.nsmap)[0]

        self.metadata = {k: prod_definition.find(f"{{{root.nsmap['dwd']}}}{v}").text for k, v in prod_items.items()}
        self.metadata["issue_time"] = pd.Timestamp(self.metadata["issue_time"])

        # Get time steps.
        timesteps = root.findall(
            "kml:Document/kml:ExtendedData/dwd:ProductDefinition/dwd:ForecastTimeSteps",
            root.nsmap,
        )[0]
        self.timesteps = DatetimeIndex([pd.Timestamp(i.text) for i in timesteps.getchildren()])

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

            measurement_list = station_forecast.findall("kml:ExtendedData/dwd:Forecast", self.root.nsmap)

            data_dict = {"station_id": station_ids, "datetime": self.timesteps}

            for measurement_item in measurement_list:

                measurement_parameter = measurement_item.get(f"{{{self.root.nsmap['dwd']}}}elementName")

                if measurement_parameter.lower() in self.parameters:
                    measurement_string = measurement_item.getchildren()[0].text

                    measurement_values = " ".join(measurement_string.split()).split(" ")
                    measurement_values = [np.nan if i == "-" else float(i) for i in measurement_values]

                    assert len(measurement_values) == len(  # noqa:S101
                        self.timesteps
                    ), "Number of time steps does not match number of measurement values"

                    data_dict[measurement_parameter.lower()] = measurement_values

            yield pd.DataFrame.from_dict(data_dict)

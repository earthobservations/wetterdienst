# Source:
# https://github.com/jlewis91/dwdbulk/blob/master/dwdbulk/api/forecasts.py
import logging
from io import BytesIO
from typing import List
from zipfile import ZipFile
from os.path import basename

from lxml import etree  # noqa:S410
from pandas import DatetimeIndex
from tqdm import tqdm
from urllib.parse import urljoin
from dataclasses import dataclass

import numpy as np
import pandas as pd

from wetterdienst.constants.access_credentials import (
    DWD_SERVER,
    DWD_MOSMIX_S_PATH,
    DWD_MOSMIX_L_PATH,
    DWD_MOSMIX_L_SINGLE_PATH,
)
from wetterdienst.download.https_handling import create_dwd_session
from wetterdienst.file_path_handling.path_handling import list_remote_files

log = logging.getLogger(__name__)


class KMLReader:
    def __init__(self, station_ids: List = None, parameters: List = None):

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

    def fetch(self, url) -> str:
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
        tree = etree.parse(BytesIO(kml))  # noqa:S320
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
        self.items += root.findall("kml:Document/kml:Placemark", root.nsmap)

    def iter_items(self):
        for item in self.items:
            station_id = item.find("kml:name", self.root.nsmap).text

            if (self.station_ids is None) or station_id in self.station_ids:
                yield item

    def get_metadata(self):
        return pd.DataFrame([self.metadata])

    def get_stations(self):
        stations = []
        for station_forecast in self.iter_items():
            station = {
                "station_id": station_forecast.find("kml:name", self.root.nsmap).text,
                "station_name": station_forecast.find(
                    "kml:description", self.root.nsmap
                ).text,
            }

            coordinates = station_forecast.find(
                "kml:Point/kml:coordinates", self.root.nsmap
            ).text.split(",")

            station["longitude"] = float(coordinates[0])
            station["latitude"] = float(coordinates[1])
            station["height"] = float(coordinates[2])

            stations.append(station)

        return pd.DataFrame(stations)

    def get_forecasts(self):
        df_list = []
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

                df_list.append(df)

        df = pd.concat(df_list, axis=0)

        self.coerce_columns(df)

        return df

    def coerce_columns(self, df):
        for column in df.columns:
            if column == "W1W2" or column.startswith("WPc") or column in ["ww", "ww3"]:
                df[column] = df[column].astype("Int64")


@dataclass
class MOSMIXResult:
    """
    Result object encapsulating metadata, station information and forecast data.
    """

    metadata: pd.DataFrame
    stations: pd.DataFrame
    forecasts: pd.DataFrame


class MOSMIXReader:
    """

    Fetch weather forecast data (KML/MOSMIX_S dataset).

    Parameters
    ----------
    station_ids : List
        - If None, data for all stations is returned.
        - If not None, station_ids are a list of station ids for which data is desired.

    parameters: List
        - If None, data for all parameters is returned.
        - If not None, list of parameters, per MOSMIX definition, see
          https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/kml/mosmix_elemente_pdf.pdf?__blob=publicationFile&v=2  # noqa:E501,B950
    """

    def __init__(self, station_ids: List = None, parameters: List = None):

        self.station_ids = None
        self.parameters = None

        if station_ids:
            assert isinstance(  # noqa:S101
                station_ids, list
            ), "station_ids must be None or a list"
            self.station_ids = [str(station_id) for station_id in station_ids]

        if parameters:
            assert isinstance(  # noqa:S101
                parameters, list
            ), "parameters must be None or a list"
            self.parameters = [str(param) for param in parameters]

        self.kml = KMLReader(station_ids=self.station_ids, parameters=self.parameters)

    def read_mosmix_s_latest(self) -> MOSMIXResult:
        """
        Fetch weather forecast data (KML/MOSMIX_S dataset).
        """
        url = urljoin(DWD_SERVER, DWD_MOSMIX_S_PATH)

        return self.read_mosmix_single(url)

    def read_mosmix_l_latest(self) -> MOSMIXResult:
        """
        Fetch weather forecast data (KML/MOSMIX_L dataset).
        """
        if self.station_ids is None:  # pragma: no cover
            url = urljoin(DWD_SERVER, DWD_MOSMIX_L_PATH)
            return self.read_mosmix_single(url)
        else:
            url = urljoin(DWD_SERVER, DWD_MOSMIX_L_SINGLE_PATH)
            return self.read_mosmix_multi(url)

    def read_mosmix_single(self, url) -> MOSMIXResult:

        url = self.get_url_latest(url)
        self.kml.read(url)

        result = MOSMIXResult(
            metadata=self.kml.get_metadata(),
            stations=self.kml.get_stations(),
            forecasts=self.kml.get_forecasts(),
        )

        return result

    def read_mosmix_multi(self, url) -> MOSMIXResult:
        for station_id in self.station_ids:
            station_url = url.format(station_id=station_id)
            station_url = self.get_url_latest(station_url)
            self.kml.read(station_url)

        result = MOSMIXResult(
            metadata=self.kml.get_metadata(),
            stations=self.kml.get_stations(),
            forecasts=self.kml.get_forecasts(),
        )

        return result

    def get_url_latest(self, url):
        urls = list_remote_files(url, False)
        try:
            url = list(filter(lambda url: "LATEST" in url, urls))[0]
            return url
        except:  # noqa:E722,B001
            raise KeyError(f"Unable to find LATEST file within {url}")

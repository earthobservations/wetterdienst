import json
from enum import Enum
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from aiohttp import BasicAuth

from wetterdienst import Kind, Period, Provider, Resolution, Settings
from wetterdienst.core.scalar.request import ScalarRequestCore
from wetterdienst.core.scalar.values import ScalarValuesCore
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.period import PeriodType
from wetterdienst.metadata.resolution import ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import NetworkFilesystemManager, download_file
from wetterdienst.util.parameter import DatasetTreeCore


class MetnoForstPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value


class MetnoForstResolution(Enum):
    DYNAMIC = Resolution.DYNAMIC.value


class MetnoFrostParameter(DatasetTreeCore):
    class DYNAMIC(Enum):
        PRECIPITATION_HEIGHT = "air_temperature"


class MetnoFrostUnit(DatasetTreeCore):
    class DYNAMIC(UnitEnum):
        PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER, SIUnit.KILOGRAM_PER_SQUARE_METER


class MetnoFrostValues(ScalarValuesCore):
    _string_parameters = ()
    _irregular_parameters = ()
    _date_parameters = ()
    _data_tz = Timezone.UTC

    _endpoint = "https://frost.met.no/observations/v0.jsonld?sources={source}:0&elements={parameters}&referencetime={referencetime}"  # ?user_agent={authKey}

    def _collect_station_parameter(self, station_id: str, parameter: Enum, dataset: Enum) -> pd.DataFrame:
        url = self._endpoint.format(
            source=station_id,
            parameters=parameter.value,
            referencetime=f"{self.sr.stations.start_date.to_pydatetime().replace(tzinfo=None).isoformat()}/{self.sr.stations.end_date.to_pydatetime().replace(tzinfo=None).isoformat()}",
        )
        print(url)
        Settings.fsspec_client_kwargs["auth"] = BasicAuth(self.sr.stations.auth_metno_frost, "")
        payload = download_file(url, CacheExpiry.METAINDEX)
        print(payload)
        data = json.loads(payload.read())
        print(data)
        df = pd.DataFrame.from_records(data["data"])
        print(df)


class MetnoFrostRequest(ScalarRequestCore):
    _tz = Timezone.UTC

    _unit_tree = MetnoFrostUnit

    _values = MetnoFrostValues

    _has_tidy_data = True
    _has_datasets = False

    _data_range = DataRange.LOOSELY

    _parameter_base = MetnoFrostParameter

    _period_base = MetnoForstPeriod

    _period_type = PeriodType.FIXED

    _resolution_type = ResolutionType.DYNAMIC
    _resolution_base = MetnoForstResolution

    provider = Provider.METNO
    kind = Kind.OBSERVATION

    _endpoint = "https://frost.met.no/sources/v0.jsonld"  # ?user_agent={authKey}

    def __init__(self, parameter, start_date, end_date):
        super().__init__(
            parameter=parameter,
            resolution=Resolution.DYNAMIC,
            period=Period.HISTORICAL,
            start_date=start_date,
            end_date=end_date,
        )
        self.auth_metno_frost = Settings.auth_metno_frost

    def _all(self):
        url = self._endpoint.format(authKey=self.auth_metno_frost)
        Settings.fsspec_client_kwargs["auth"] = BasicAuth(self.auth_metno_frost, "")
        payload = download_file(url, CacheExpiry.METAINDEX)
        data = json.loads(payload.read())
        print(data)
        df = pd.DataFrame.from_records(data["data"])
        df = df.loc[:, ["id", "name", "geometry", "masl", "validFrom", "county", "wmoId"]]
        df = df.rename(
            columns={
                "id": Columns.STATION_ID.value,
                "masl": Columns.HEIGHT.value,
                "county": Columns.STATE.value,
                "validFrom": Columns.FROM_DATE.value,
            }
        )
        mask_geom = df.geometry.map(type) == dict
        df = df.loc[mask_geom, :]
        geometry = df.pop("geometry")
        df.loc[:, ["longitude", "latitude"]] = geometry.map(lambda x: x["coordinates"]).apply(pd.Series).values
        return df


if __name__ == "__main__":
    Settings.auth_metno_frost = ""
    stations = MetnoFrostRequest(
        parameter=["air_temperature"], start_date="1990-01-01", end_date="2000-01-01"
    ).filter_by_station_id("SN88680")
    print(stations.df)

    values = stations.values.all()
    print(values.df)

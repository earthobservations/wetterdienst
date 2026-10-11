import json
from enum import Enum
from typing import Optional, Tuple

import pandas as pd

from wetterdienst import Kind, Period, Provider, Resolution
from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.period import PeriodType
from wetterdienst.metadata.resolution import ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import UnitEnum, OriginUnit, SIUnit
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file
from wetterdienst.util.parameter import DatasetTreeCore


class NoaaTCParameter(DatasetTreeCore):
    class DYNAMIC(Enum):
        WATER_LEVEL = "water_level"


class NoaaTCUnit(DatasetTreeCore):
    class DYNAMIC(UnitEnum):
        WATER_LEVEL = OriginUnit.METER.value, SIUnit.METER.value


class NoaaTCResolution(Enum):
    DYNAMIC = Resolution.DYNAMIC.value




class NoaaTCValues(TimeseriesValues):
    _data_tz = Timezone.DYNAMIC

    _endpoint = (
        "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?station={station_id}&product={parameter}&"
        "begin_date={start_date}&end_date={end_date}&datum=navd&units=metric&time_zone=gmt&"
        "application=wetterdienst/https://github.com/earthobservations/wetterdienst&format=json"
    )

    def _collect_station_parameter(self, station_id: str, parameter: Enum, dataset: Enum) -> pd.DataFrame:
        url = self._endpoint.format(
            station_id=station_id, parameter=parameter.value, start_date=self.sr.start_date.isoformat(), end_date=self.sr.end_date.isoformat()
        )

        payload = download_file(url, CacheExpiry.FIVE_MINUTES)

        df = pd.DataFrame.from_records(json.load(payload)["data"])

        print(df)


class NoaaTCRequest(TimeseriesRequest):
    _values = NoaaTCValues
    _tz = Timezone.USA
    _parameter_base = NoaaTCParameter
    _unit_base = NoaaTCUnit
    _has_tidy_data = True
    _has_datasets = False
    _data_range = DataRange.FIXED
    _period_base = Period.HISTORICAL
    _period_type = PeriodType.FIXED
    _resolution_type = ResolutionType.DYNAMIC
    _resolution_base = NoaaTCResolution
    _kind = Kind.OBSERVATION
    _provider = Provider.NOAA
    _endpoint = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?units=metric"

    def __init__(self, parameter, start_date, end_date):
        super(NoaaTCRequest, self).__init__(
            parameter=parameter,
            resolution=Resolution.DYNAMIC,
            period=Period.HISTORICAL,
            start_date=start_date,
            end_date=end_date,
        )

    def _all(self) -> pd.DataFrame:
        def _extract_ortho_msl(url):
            payload = download_file(url, self.settings, CacheExpiry.METAINDEX)

            datum_dict = json.load(payload)

            datum_msl = None
            if datum_dict["datums"]:
                datum_msl = [datum for datum in datum_dict["datums"] if datum["name"] == "MSL"]

            datum_msl = datum_msl and datum_msl[0]["value"] or None

            return datum_dict["OrthometricDatum"], datum_msl

        payload = download_file(self._endpoint, self.settings, CacheExpiry.METAINDEX)

        df = pd.DataFrame.from_records(json.load(payload)["stations"])

        df = df.loc[:, ["id", "name", "state", "lat", "lng", "datums"]]

        df.loc[:, ["orthodatum", "msl"]] = df.pop("datums").map(lambda x: x["self"]).map(_extract_ortho_msl).tolist()

        df = df.loc[df.loc[:, "orthodatum"] == "NAVD88", :]

        return df.rename(
            columns={
                "id": Columns.STATION_ID.value,
                "name": Columns.NAME.value,
                "state": Columns.STATE.value,
                "lat": Columns.LATITUDE.value,
                "lng": Columns.LONGITUDE.value,
            }
        )


if __name__ == "__main__":
    request = NoaaTCRequest(parameter="water_level", start_date="1970-01-01", end_date="1970-01-02").all()
    print(request.df)
    values = next(request.values.query())
    print(values.df)
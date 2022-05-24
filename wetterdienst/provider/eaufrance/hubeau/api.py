import json
from enum import Enum

import pandas as pd

from wetterdienst.core.scalar.request import ScalarRequestCore
from wetterdienst.core.scalar.values import ScalarValuesCore
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import OriginUnit, SIUnit
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file
from wetterdienst.util.parameter import DatasetTreeCore


class HubeauResolution(Enum):
    DYNAMIC = Resolution.DYNAMIC.value


class HubeauParameter(DatasetTreeCore):
    class DYNAMIC(Enum):
        FLOW = "Q"
        STAGE = "H"


class HubeauUnit(DatasetTreeCore):
    class DYNAMIC(Enum):
        FLOW = OriginUnit.LITERS_PER_SECOND.value, SIUnit.CUBIC_METERS_PER_SECOND.value
        STAGE = OriginUnit.MILLIMETER.value, SIUnit.METER.value


class HubeauValues(ScalarValuesCore):
    _string_parameters = ()
    _irregular_parameters = ()
    _date_parameters = ()

    _data_tz = Timezone.DYNAMIC

    _endpoint = (
        "https://hubeau.eaufrance.fr/api/v1/hydrometrie/observations_tr?code_entite={station_id}"
        "&grandeur_hydro={grandeur_hydro}&sort=asc"
    )
    _endpoint_freq = f"{_endpoint}&size=2"

    def fetch_dynamic_frequency(self, station_id, parameter, dataset):
        url = self._endpoint_freq.format(station_id=station_id, grandeur_hydro=parameter.value)
        response = download_file(url)
        values_dict = json.load(response)["data"]

        try:
            second_date = values_dict[1]["date_obs"]
            first_date = values_dict[0]["date_obs"]
        except IndexError:
            return "1H"

        date_diff = pd.to_datetime(second_date) - pd.to_datetime(first_date)

        minutes = int(date_diff.seconds / 60)

        return f"{minutes}min"

    def _collect_station_parameter(self, station_id: str, parameter: Enum, dataset: Enum) -> pd.DataFrame:
        url = self._endpoint.format(station_id=station_id, grandeur_hydro=parameter.value)
        response = download_file(url)
        values_dict = json.load(response)["data"]

        df = pd.DataFrame.from_records(values_dict)

        df = df.rename(
            columns={
                "code_station": Columns.STATION_ID.value,
                "date_obs": Columns.DATE.value,
                "resultat_obs": Columns.VALUE.value,
                "code_qualification_obs": Columns.QUALITY.value,
            }
        )

        return df.loc[
            :,
            [
                Columns.STATION_ID.value,
                Columns.DATE.value,
                Columns.VALUE.value,
                Columns.QUALITY.value,
            ],
        ]


class HubeauRequest(ScalarRequestCore):
    _values = HubeauValues

    _unit_tree = HubeauUnit

    _tz = Timezone.FRANCE

    _parameter_base = HubeauParameter

    _has_tidy_data = True

    _has_datasets = False

    _data_range = DataRange.FIXED

    _period_base = None

    _resolution_type = ResolutionType.DYNAMIC
    _resolution_base = HubeauResolution

    _period_type = PeriodType.FIXED

    provider = Provider.EAUFRANCE
    kind = Kind.OBSERVATION

    _endpoint = "https://hubeau.eaufrance.fr/api/v1/hydrometrie/referentiel/stations?format=json&en_service=true"

    def __init__(self, parameter, start_date=None, end_date=None):
        super(HubeauRequest, self).__init__(
            parameter=parameter,
            resolution=Resolution.DYNAMIC,
            period=Period.HISTORICAL,
            start_date=start_date,
            end_date=end_date,
        )

    def _all(self) -> pd.DataFrame:
        """

        :return:
        """
        response = download_file(self._endpoint, CacheExpiry.METAINDEX)
        stations_dict = json.load(response)["data"]
        df = pd.DataFrame.from_records(stations_dict)

        df = df.rename(
            columns={
                "code_station": Columns.STATION_ID.value,
                "libelle_station": Columns.NAME.value,
                "longitude_station": Columns.LONGITUDE.value,
                "latitude_station": Columns.LATITUDE.value,
                "altitude_ref_alti_station": Columns.HEIGHT.value,
                "libelle_departement": Columns.STATE.value,
                "date_ouverture_station": Columns.FROM_DATE.value,
                "date_fermeture_station": Columns.TO_DATE.value,
            }
        )

        return df.loc[df[Columns.STATION_ID.value].str[0].str.isalpha(), :]

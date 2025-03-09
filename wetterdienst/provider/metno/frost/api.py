import polars as pl

from wetterdienst.core.timeseries.metadata import DATASET_NAME_DEFAULT, build_metadata_model

from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import download_file

MetnoFrostMetadata = {
    "name_short": "MET Norway",
    "name_english": "Norwegian Meteorological Institute",
    "name_local": "Meteorologisk institutt",
    "country": "Norway",
    "copyright": "© Norwegian Meteorological Institute (MET Norway)",
    "url": "https://www.met.no",
    "kind": "observation",
    "timezone": "Europe/Oslo",
    "timezone_data": "Europe/Oslo",
    "resolutions": [
        {
            "name": "daily",
            "name_original": "daily",
            "periods": ["historical"],
            "date_required": False,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "precipitation_height",
                            "name_original": "precipitation_height",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        }
                    ]
                }
            ]
        }
    ]
}
MetnoFrostMetadata = build_metadata_model(MetnoFrostMetadata, "MetnoFrostMetadata")



class MetnoFrostValues:
    """Values class for MetNo Frost API."""


class MetnoFrostRequest(TimeseriesRequest):
    """Request class for MetNo Frost API."""
    metadata = MetnoFrostMetadata
    _values = MetnoFrostValues
    
    _url = "https://frost.met.no/sources/v0.jsonld?types=SensorSystem"

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        settings: _SETTINGS_TYPE = None,
    ):
        super().__init__(
            parameters=parameters,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )
        
    def _all(self) -> pl.LazyFrame:
        client_kwargs = self.settings.fsspec_client_kwargs
        try:
            client_kwargs["auth"] = self.settings.auth
        payload = download_file(
            url=self._url,
            cache_dir=self.settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=client_kwargs,
            cache_disable=self.settings.cache_disable,
        )
        df = pl.read_json(payload)
        print(df)

if __name__ == "__main__":
    request = MetnoFrostRequest(
        parameters=("daily", "data", "precipitation_height"),
        start_date="2023-01-01",
        end_date="2023-01-31",
    ).filter_by_station_id("SN50865")
    print(request.df)
    values = request.values.all()
    print(values.df)


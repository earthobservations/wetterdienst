from dataclasses import dataclass

import polars as pl
from aiohttp import BasicAuth, ClientResponseError

from wetterdienst.core.timeseries.metadata import DATASET_NAME_DEFAULT, build_metadata_model, ParameterModel, \
    DatasetModel

from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
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
                            "name_original": "sum(precipitation_amount P1D)",
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



class MetnoFrostValues(TimeseriesValues):
    """Values class for MetNo Frost API."""
    _url = "https://frost.met.no/observations/v0.jsonld?sources={station_id}&elements={parameter}&referencetime=2010-04-01/2010-04-03"
    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        url = self._url.format(
            station_id=station_id,
            parameter=parameter_or_dataset.name_original,
        )
        client_kwargs = self.sr.stations.settings.fsspec_client_kwargs
        client_kwargs["auth"] = BasicAuth(*self.sr.stations.settings.auth.metno_frost)
        try:
            payload = download_file(
                url=url,
                cache_dir=self.sr.stations.settings.cache_dir,
                ttl=CacheExpiry.METAINDEX,
                client_kwargs=client_kwargs,
                cache_disable=self.sr.stations.settings.cache_disable,
            )
        except ClientResponseError as e:
            if e.status == 412:
                return pl.DataFrame()
            raise e
        df = pl.read_json(payload)
        return df
        


@dataclass
class MetnoFrostRequest(TimeseriesRequest):
    """Request class for MetNo Frost API."""
    metadata = MetnoFrostMetadata
    _values = MetnoFrostValues
    
    _url = "https://frost.met.no/sources/v0.jsonld?types=SensorSystem"
        
    def _all(self) -> pl.LazyFrame:
        client_kwargs = self.settings.fsspec_client_kwargs
        client_kwargs["auth"] = BasicAuth(*self.settings.auth.metno_frost)
        payload = download_file(
            url=self._url,
            cache_dir=self.settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=client_kwargs,
            cache_disable=self.settings.cache_disable,
        )
        df_raw = pl.read_json(payload)
        df_raw = df_raw.lazy()
        df_raw = df_raw.select(pl.col("data").explode())
        df_raw = df_raw.unnest("data")
        df_raw = df_raw.select(
            pl.col("id").alias("station_id"),
            pl.col("validFrom").str.to_datetime().alias("start_date"),
            pl.lit(None, dtype=pl.Datetime(time_zone="UTC")).alias("end_date"),
            pl.col("geometry").struct.field("coordinates").list.get(1).alias("latitude"),
            pl.col("geometry").struct.field("coordinates").list.get(0).alias("longitude"),
            pl.lit(None, dtype=pl.Float64).alias("height"),
            pl.col("name").alias("name"),
            pl.col("county").alias("state"),
            pl.col("country").alias("country"),
        )
        # combinations of resolution and dataset
        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name) for parameter in self.parameters
        }
        data = []
        # for each combination of resolution and dataset create a new DataFrame with the columns
        for resolution, dataset in resolutions_and_datasets:
            data.append(
                df_raw.with_columns(
                    pl.lit(resolution, pl.String).alias("resolution"),
                    pl.lit(dataset, pl.String).alias("dataset"),
                ),
            )
        df = pl.concat(data)
        return df.select(self._base_columns)


if __name__ == "__main__":
    request = MetnoFrostRequest(
        parameters=("daily", "data", "precipitation_height"),
        start_date="2023-01-01",
        end_date="2023-01-31",
    ).filter_by_station_id("SN50865")
    print(request.df)
    values = request.values.all()
    print(values.df)


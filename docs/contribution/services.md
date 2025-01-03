# Services

The core of wetterdienst is to provide data but as we don't collect the data ourselves we rely on consuming data of
already existing services - mostly governmental services. To simplify the implementation of weather services we created
data models, enumerations and classes that should be used in order to adapt whatever API is offered by a service to the
general scheme of wetterdienst with some handful of attributes to define each API and streamline internal workflows. The
following paragraphs describe how we can/may/should implement a new weather service in wetterdienst as far as our own
experience goes. We'll give examples based on the `DwdObservationRequest` implementation.


## Step 1: Metadata

The basis for the implementation of a new service is the extensive metadata model. The metadata model is a layered
abstraction of inheritance looking roughly like resolutions -> datasets -> parameters which means that the uppermost
layer is the resolution, which contains one or more datasets, which in turn contain one or more parameters. The
following example reflects this structure for the `MINUTE_1` dataset `PRECIPITATION` of `DwdObservationRequest`.

```python
DwdObservationMetadata = {
    "resolutions": [
        {
            "name": "1_minute",
            "name_original": "1_minute",
            "periods": ["historical", "recent", "now"],
            "date_required": False,
            "datasets": [
                {
                    "name": "precipitation",
                    "name_original": "precipitation",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rs_01",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_droplet",
                            "name_original": "rth_01",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_rocker",
                            "name_original": "rwh_01",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_index",
                            "name_original": "rs_ind_01",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                    ],
                }
            ],
        }
    ]
}
```

The attributes `periods` and `date_required` are actually required for each dataset but if they are equal for all 
datasets of a resolution they can be defined on the resolution level instead saving you some lines of code.
The `grouped` attribute is used to define if data is provided eather as one for the whole dataset or for each
parameter separately. If `grouped` is `True` the data is provided as one for the whole dataset, if `False` the data
is provided for each parameter separately. If `grouped` is `True` the `collect_station_parameter_or_dataset` method
expects `parameter_or_dataset` to be of `DatasetModel` type, if `False` it expects `ParameterModel` type.

Given the metadata model above you can request either the whole dataset or a specific parameter of the dataset.

Requesting the whole dataset:

```python
from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationMetadata

DwdObservationRequest(
    parameters=[DwdObservationMetadata.minute_1.precipitation]
)
```

or equally

```python
from wetterdienst.provider.dwd.observation import DwdObservationRequest

DwdObservationRequest(
    parameters=[("minute_1", "precipitation")]
)
```

Requesting a specific parameter of the dataset:

```python
from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationMetadata

DwdObservationRequest(
    parameters=[DwdObservationMetadata.minute_1.precipitation.precipitation_height]
)
```

or equally

```python
from wetterdienst.provider.dwd.observation import DwdObservationRequest

DwdObservationRequest(
    parameters=[("minute_1", "precipitation", "precipitation_height")]
)
```

## Step 2: Request class

The request class represents a request and carries all the required attributes as well as the values class that is
responsible for acquiring the data later on. The implementation is based on `TimeseriesRequest` from `wetterdienst.core`.

Attributes:

```python
@property
@abstractmethod
def provider(self) -> Provider:
    """Optional enumeration for multiple resolutions"""
    pass

@property
@abstractmethod
def kind(self) -> Kind:
    """Optional enumeration for multiple resolutions"""
    pass

@property
@abstractmethod
def _values(self):
    """Class to get the values for a request"""
    pass


@property
@abstractmethod
def metadata(self):
    """Metadata for the request"""
    pass
```

`TimeseriesRequest` has one abstract method that has to be implemented: the `_all` which manages to get a listing of
stations for the requested datasets/parameters. The listing includes:

- station_id
- start_date
- end_date
- height
- name
- state
- latitude
- longitude

The names can be mapped using the `Columns` enumeration.

## Step 3: Values class

The values class is based on `TimeseriesValues` and manages the acquisition of actual data. The
class is also part of the `TimeseriesRequest` being accessed via the `_values` property. It has to implement the
`_collect_station_parameter` method that takes care of getting values of a parameter/dataset for a station id.

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
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_amount",
                            "name_original": "rs_01",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_amount_droplet",
                            "name_original": "rth_01",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_amount_rocker",
                            "name_original": "rwh_01",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_index",
                            "name_original": "rs_ind_01",
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
is provided for each parameter separately. If `grouped` is `True` the `_collect_station_parameter_or_dataset` method
expects `parameter_or_dataset` to be of `DatasetModel` type, if `False` it expects `ParameterModel` type.

A parameter declares only what the service itself knows: the canonical `name`, the service's own
`name_original` and the `unit` the service publishes the values in. It does **not** declare a
`unit_type` -- that is a property of the measured quantity rather than of the service, so it is read
from the [canonical parameter table](../data/parameters.md)
(`wetterdienst.metadata.parameter_table`) via the canonical `name`. Declaring one is rejected,
because a service overriding it would let a single name mean two different unit types and so return
two different units.

This means the canonical `name` you pick has to already exist in that table. If your service reports
a quantity that is not in it yet, add it there first. If it reports something that looks like an
existing name but is a *different* physical quantity, give it its own name rather than reusing the
existing one -- see the `radiation_global` and `radiation_global_intensity` pair, which are
irradiation (accumulated energy per area) and irradiance (power per area) and are not convertible
into one another without the accumulation interval.

The canonical name also carries the *statistic* of the value, and that is read from the service's
own definition of the field, never from the nearest name in the table. The same quantity has a
name for the maximum or minimum over the dataset's own interval (`temperature_air_max_2m`), for the
mean of the daily maxima (`temperature_air_max_2m_mean`), and for an extreme over a window that is
not that interval (`temperature_air_max_2m_last_12h`, `_yesterday`, `_multiday`). Check, for each
field, what the service says it is, over which interval, and whether that interval ends at the
timestamp or starts there. A monthly file that holds the mean of the daily maxima and a daily file
that holds the day's maximum are different parameters even though both are called `TMA`, and a
service that does not say which statistic a field is must be asked rather than guessed. Where the
service's description states the statistic or the window,
`tests/metadata/test_parameter_statistics.py` holds the name to it. That includes a reading at one
moment against the mean over the interval: a temperature the service calls an instant or current
value takes the spot name (`temperature_air_2m`, `temperature_dew_point_2m`,
`temperature_soil_0_05m`), and one it calls a mean or an average takes the `_mean_` name. Where the
service says neither, a temperature below daily resolution takes the spot name and one at daily or
coarser resolution keeps the `_mean_` name (GH-2651, GH-2657). A mean the service computes from
the day's two extremes, `(max + min) / 2`, as ECCC and Geosphere's daily mean do, is neither: it
takes `temperature_air_mean_minmax_2m` and not `temperature_air_mean_2m`, which is a mean of
readings through the day and can differ from the midrange of the extremes by a degree or more
(GH-2839).

`unit` stays mandatory even where a service already publishes canonical units, since silently
defaulting it is how values end up wrong by a factor of ten with nothing to catch it. Note that it is
the unit at the point of declaration: if the parser transforms values before they are returned, the
declared unit is the one *after* that transformation.

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
    parameters=[DwdObservationMetadata.minute_1.precipitation.precipitation_amount]
)
```

or equally

```python
from wetterdienst.provider.dwd.observation import DwdObservationRequest

DwdObservationRequest(
    parameters=[("minute_1", "precipitation", "precipitation_amount")]
)
```

## Step 2: Request class

The request class represents a request and carries all the required attributes as well as the values class that is
responsible for acquiring the data later on. The implementation is based on `TimeseriesRequest` from `wetterdienst.model.request`.

Attributes:

```python
@dataclass
class DwdObservationRequest(TimeseriesRequest):
    metadata = DwdObservationMetadata  # the metadata model of Step 1
    _values = DwdObservationValues  # the values class of Step 3, the class itself
    _history = DwdObservationHistory  # optional: the class that reads the station history
```

`TimeseriesRequest` has one abstract method that has to be implemented: the `_all` which manages to get a listing of
stations for the requested datasets/parameters. The listing includes:

- station_id
- start_timestamp
- end_timestamp
- elevation
- name
- region
- latitude
- longitude

## Step 3: Values class

The values class is based on `TimeseriesValues` and manages the acquisition of actual data. The
request class refers to it in its `_values` attribute. It has to implement the
`_collect_station_parameter_or_dataset` method that takes care of getting values of a parameter/dataset for a station id.

The frame it returns has the columns `resolution`, `dataset`, `parameter`, `station_id`, `timestamp` and
`value`. A source that publishes a quality flag for a reading adds the string column `quality_flags`,
built with `join_quality_flags` from `wetterdienst.model.quality_flags`: the source's ordinary quality
flag as the first argument, written as the plain code, and every further kind it publishes as
`kind=expression`, which is written `kind:code` after it, comma-separated and in the order given
(`join_quality_flags(pl.col("QFLAG"), measurement=pl.col("MFLAG"), source=pl.col("SFLAG"))` gives
`G,measurement:T,source:7`). A blank flag is left out and a reading without a flag is null. A provider
that publishes none leaves the column out, and the base class fills it with a null. Document each
code of the source next to the provider's page and quote its documentation in the test.

A source that writes a number or a text for a value it does not have (`-999`, `99.9`, `NaN`, `---`, a wind
direction `0`) is mapped to null in the reader, before the unit conversion, and its text is not lost: map it
with `null_sentinels` from the same module, which returns the cleaned value and the `raw` text together, and
pass the text as the last kind of the flags, `join_quality_flags(plain_flag, raw=raw)`, which writes
`raw:-999` after the plain flag. Declare the text as the source writes it (`Sentinel("-999")`, not
`-999.0`); a value read from text keeps the text of its own cell. `Sentinel(..., where=...)` limits it to a
parameter, `to=0.0` makes it a value the source documents (no precipitation), and `non_numeric=True` takes
every text that is no number for one. A value no sensor can have produced (4021 degrees) has no
sentinel to name: `OutOfRange(low, high)` takes it the same way, with bounds in the unit of the source
taken from `tests/provider/physical_ranges.py` and kept per resolution (the rain and the sunshine of a day
are not those of a minute; generous, so that a real reading of the provider is never outside). A reader may
be narrower than that range where its source's own records or precision allow it, never wider; the
narrower entries are named in `test_physical_ranges.py`, and the `raw` text is the number as it is written. A wide frame keeps the text beside each
column with `clear_sentinels` and `unpivot_with_raw`. Add a stub of the source with the sentinel written as the source writes it to
`tests/provider/value_stubs.py` and name each `raw:` token it must carry in `tokens`.

# Services

The core of wetterdienst is to provide data but as we don't collect the data ourselves we rely on consuming data of
already existing services - mostly governmental services. To simplify the implementation of weather services we created
data models, enumerations and classes that should be used in order to adapt whatever API is offered by a service to the
general scheme of wetterdienst with some handful of attributes to define each API and streamline internal workflows. The
following paragraphs describe how we can/may/should implement a new weather service in wetterdienst as far as our own
experience goes. We'll give examples based on the `DwdObservationRequest` implementation. How the pieces fit together is in the [Architecture](architecture.md).


## Step 1: Metadata

The basis for the implementation of a new service is the extensive metadata model. The metadata model is a layered
abstraction of inheritance looking roughly like resolutions -> datasets -> parameters which means that the uppermost
layer is the resolution, which contains one or more datasets, which in turn contain one or more parameters. The
following example reflects this structure for the `precipitation` dataset of the `1_minute` resolution of
`DwdObservationRequest`.

```python
from wetterdienst.model.metadata import build_metadata_model
from wetterdienst.provider.dwd.metadata import _METADATA

_DwdObservationMetadataSpec = {
    **_METADATA,  # what the provider is, shared by its networks, see below
    "kind": "observation",
    "timezone": "Europe/Berlin",
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
DwdObservationMetadata = build_metadata_model(_DwdObservationMetadataSpec, "DwdObservationMetadata")
```

The fields above `resolutions` say what the provider is, and none can be left out: `name_short`,
`name_english`, `name_local`, `country`, `country_code` (the ISO 3166-1 alpha-2 code, or `None` for a provider of
several countries), `copyright`, `license` (a `LicenseModel`, or `None` where the provider states no terms),
`attribution` (the credit line, or `None`), `url`, `kind`, `timezone` and, for a network that needs credentials,
`auth`. A provider with several networks declares them once in a `_METADATA` dict of its own (DWD's is
`provider/dwd/metadata.py`) and spreads it into each network's spec, as above. They are what the REST API's
[`metadata` block](../usage/restapi.md#response-metadata) and the [providers](../usage/restapi.md#providers)
listing report, so a provider that omits one fails validation instead of answering a null.

The dict has a name of its own and the public name is bound to the model alone, which is what a type checker
reads (mypy takes the first assignment of a name for its type).

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
from dataclasses import dataclass

from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata
from wetterdienst.provider.dwd.observation.api import DwdObservationHistory, DwdObservationValues


@dataclass
class DwdObservationRequest(TimeseriesRequest):
    metadata = DwdObservationMetadata  # the metadata model of Step 1
    _values = DwdObservationValues  # the values class of Step 3, the class itself
    _history = DwdObservationHistory  # optional: the class that reads the station history
```

`TimeseriesRequest` has one abstract method that has to be implemented: the `_all` which manages to get a listing of
stations for the requested datasets/parameters, as a `pl.LazyFrame`. A row is a station of a dataset, so a station
that has two of the datasets has two rows. The listing has the columns of `STATIONS_SCHEMA`
(`wetterdienst.model.schema`):

| Column | Type | |
| --- | --- | --- |
| `resolution`, `dataset` | String | both or neither: the values step finds the datasets of a station by them, and the core adds them to a frame that has neither |
| `station_id` | String | required: the id the values are collected by, and the station filters key on it |
| `start_timestamp`, `end_timestamp` | Datetime (UTC) | may be left out; a missing start says nothing about when the station began |
| `latitude`, `longitude`, `elevation` | Float64 | may be left out; a station without a position is listed but no distance filter reaches it |
| `name`, `region` | String | may be left out |

The provider hands over the stations of its catalogue and the core shapes them (`add_resolution_and_dataset` and
`shape_stations_frame` in `wetterdienst.model.request`, GH-2627):

- `station_id` is the one column every frame must have. A provider with one catalogue for all its datasets leaves
  `resolution` and `dataset` out, and the core copies the frame once per requested resolution and dataset, in the order
  of the request. A provider whose stations differ per dataset (their bounds, a catalogue per product) hands a frame
  with both, one row per station and dataset, and it is left as it is. A frame with only one of the two is a
  `ProviderContractError`: the core cannot tell which half of a pair is missing.
- A column that is left out is filled with null, and the others are cast to their types (a naive datetime is read as
  UTC, a zoned one is converted to it). A coordinate or elevation that is a text and no number is null, and the core
  logs one debug line per column with the count; a timestamp that is a string or an integer, or a missing `station_id`,
  is a `ProviderContractError`.
- A column the request does not list in `_base_columns` is dropped, with a debug line naming it. A provider's own
  columns (WSV's river kilometre) are kept only if the request lists them there, and a reader may not build one that
  `_base_columns` leaves out: the `station_column_findings` fixture of `tests/provider/conftest.py` fails the provider
  tests for it (a column the reader keeps on purpose and drops itself is named in `INTERMEDIATE_STATION_COLUMNS`).
- A frame with no rows is no stations, and a bare `pl.DataFrame()` is right: the core makes of it the empty frame of the
  columns. A provider whose catalogue can come back empty still returns early with an empty frame, because on polars
  before 2.0 a frame without columns given a `pl.lit` column has one row, not none.

## Step 3: Values class

The values class is based on `TimeseriesValues` and manages the acquisition of actual data. The
request class refers to it in its `_values` attribute. It has to implement the
`_collect_station_parameter_or_dataset` method that takes care of getting values of a parameter/dataset for a station id.

The frame it returns is the long form of the readings of that station for the parameter (or, for a `grouped`
dataset, the dataset), and it is all the core asks of a provider: the docstring of
`_collect_station_parameter_or_dataset` is the contract, and these are its rules.

| Column | Type | |
| --- | --- | --- |
| `parameter` | String | required: the source's own name, `name_original`; a `grouped` dataset's frame is cut to the requested parameters by an exact match |
| `timestamp` | Datetime | required: the instant of the reading, not null on a row that has a value; the core casts it to Datetime(us, UTC) |
| `value` | Float64 | required: in the unit the metadata declares, null where the source has no reading |
| `quality_flags` | String | optional: a provider that publishes none leaves the column out |
| `resolution`, `dataset`, `station_id` | String | not the provider's: the core writes them (`dataset.resolution.name`, `dataset.name.lower()`, the id the values were asked for) and replaces whatever the provider put there |

A provider hands over its rows and nothing else; the core shapes the frame (`shape_provider_frame` in
`wetterdienst.model.values`, GH-2627). It writes the identity columns, casts `parameter` to String, `timestamp` to
Datetime(us, UTC) and `value` to Float64, fills `quality_flags` with a null where it is missing, orders the columns as
the long form does and drops any other, and does so before the units are converted and the duplicates removed. A
naive timestamp is read as UTC and a zoned one is converted to it, so a source that writes local time is converted by
the provider, which knows the zone. A `value` that is no number (a text such as `n/a`) is not an error: it becomes
null, and the core logs one debug line per frame with the count. (A provider that reads its numbers through a declared
schema, such as `pl.read_json(schema=...)` with Float64 in ECCC, NWS, EA and Hubeau, raises at the read on a text,
before the core sees it.) What cannot be made to fit is an error, `ProviderContractError`: a frame without
`parameter`, `timestamp` or `value`, a `timestamp` that is a string or an integer, a `value` that is a list. Parse the
text of a time stamp in the provider.

A frame with no rows is a station without data, and a bare `pl.DataFrame()` is the right way to say so: whatever
columns it has or lacks, the core makes of it the empty frame of `LONG_SCHEMA` and no rows follow from it, so a
provider builds no empty schema of its own. A connection that cannot be made is an error, never an empty frame. Rows
may come in any order, more than once (the first of a `resolution`, `dataset`, `parameter` and `timestamp` is kept)
and outside the requested window (the core cuts it). A column that is not in the table is not part of the contract
and is dropped. `tests/provider/frames.snapshot.json` holds what the core hands out for every offline test of a
provider (`uv run poe frames:snapshot`), so that a change to what a provider hands over shows in its diff. A
source that publishes a quality flag for a reading adds the string column `quality_flags`,
built with `join_quality_flags` from `wetterdienst.model.quality_flags`: the source's ordinary quality
flag as the first argument, written as the plain code, and every further kind it publishes as
`kind=expression`, which is written `kind:code` after it, comma-separated and in the order given
(`join_quality_flags(pl.col("QFLAG"), measurement=pl.col("MFLAG"), source=pl.col("SFLAG"))` gives
`G,measurement:T,source:7`). A blank flag is left out and a reading without a flag is null. A provider
that publishes none leaves the column out, and the base class fills it with a null. Document each
code of the source next to the provider's page and quote its documentation in the test. Tell what each
kind of token means in `LEGENDS` of `wetterdienst.model.quality_legend`, under `provider/network`: the answers
of `with_metadata` carry it as `metadata.quality.legend`, and `tests/model/test_quality_legend.py` fails until
the kinds the reader passes to `join_quality_flags` are the kinds listed there. Give `codes` only for a set the
source documents; for the others say in the `meaning` where the source tells them. A network with no flag is
listed with an empty legend.

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
narrower entries are named in `test_physical_ranges.py`, and the `raw` text is the number as it is written. A model's amount that is a little below its floor (-0.02 mm of rain) is `Floor(0.0)`: the floor, with the number as `raw`. A wide frame keeps the text beside each
column with `clear_sentinels` and `unpivot_with_raw`. Add a stub of the source with the sentinel written as the source writes it to
`tests/provider/value_stubs.py` and name each `raw:` token it must carry in `tokens`.

## Step 4: What a new provider brings with it

The tests hold every provider to the same rules, and fail until a new one has what they look for:

- **A provider page** under `docs/data/provider/<provider>/`, with its resolutions, datasets and the parameter tables,
  and an entry in the [overview](../data/overview.md). `tests/test_docs.py` compares them with the metadata and the
  registry, and the README states how many services there are.
- **Its licence and credit line**: `license` and `attribution` in the metadata (Step 1). A provider that states no
  terms declares `"license": None` and is named with the reason in `LICENSE_NOT_STATED` of
  `tests/ui/test_response_metadata.py`.
- **A stub of its station catalogue** in `tests/provider/station_catalogue_stubs.py`: rows of the real list, served
  through the provider's own reader. The rules of `tests/provider/station_catalogue.py` apply to it, and to the live
  list in `test_station_catalogues_live.py` (marker `remote`). A provider of one country adds its bounding box to
  `COUNTRY_BBOX` there, so that a station outside the country is found.
- **A stub of its values** in `tests/provider/value_stubs.py`, or the network and the reason it has none yet in
  `NO_STUB` (Step 3).
- **An offline test** of the request, built from a response of the source as it is served, so that it runs without
  the network (`uv run poe "test:offline"` runs the selection on its own; a test that reaches upstream carries the
  `remote` marker). A test under `tests/provider` that goes through `TimeseriesValues` is held to the generous
  ranges of `tests/provider/physical_ranges.py`; one that serves numbers that are no readings carries
  `@pytest.mark.synthetic_values`. A network with no offline fixture is named with the reason in
  `NO_VALUES_FIXTURE` or `NO_STATIONS_FIXTURE` of `tests/provider/test_frames_snapshot.py`.
- **The snapshots**: `uv run poe "frames:snapshot"` records the frames the core handed out for the new tests, and
  `uv run poe "contracts:snapshot"` the Python surface, which lists the request class, and the OpenAPI document and
  the command line help where the provider adds an option. The diff of both is read in the pull request.
- **A changelog entry** for what a caller can observe, with the issue number.

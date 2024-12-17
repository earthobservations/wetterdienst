# Python Examples

## DWD

### Observation

Get available parameters for daily historical data of DWD:

```python exec="on" source="above"
from wetterdienst.provider.dwd.observation import DwdObservationRequest

observations_meta = DwdObservationRequest.discover(
    resolutions="daily",
)

# Available datasets/parameters.
print(observations_meta)

print(observations_meta)
```

Get stations for daily historical precipitation:

```python exec="on" source="above"
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "precipitation_more"),
    periods="historical",
)

print(request.all().df.head())
```

Get data for a dataset:

```python exec="on" source="above"
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "precipitation_more"),
    periods="historical",
)

print(next(request.all().values.query()))
```

Get data for a parameter:

```python exec="on" source="above"
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "climate_summary", "precipitation_height"),
    periods="historical",
)

print(next(request.all().values.query()))
```

Get data for a parameter from another dataset:

```python exec="on" source="above"
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=[("daily", "precipitation_more", "precipitation_height")],
    periods="historical",
)

print(next(request.all().values.query()))
```

### Mosmix

Get stations for MOSMIX-SMALL:

```python exec="on" source="above"
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest

request = DwdMosmixRequest(
    parameters=("hourly", "small"),
)

print(request.all().df.head())
```

Get data for MOSMIX-LARGE:

```python exec="on" source="above"
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest

stations = DwdMosmixRequest(
    parameters=("hourly", "large"),
)

print(request.all().df.head())
```

### Radar

#### Sites

Retrieve information about all OPERA radar sites.

```python exec="on" source="above"
from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites

# Acquire information for all OPERA sites.
sites = OperaRadarSites().all()
print(f"Number of OPERA radar sites: {len(sites)}")

# Acquire information for a specific OPERA site.
site_ukdea = OperaRadarSites().by_odim_code("ukdea")
print(site_ukdea)
```

Retrieve information about the DWD radar sites.

```python exec="on" source="above"
from wetterdienst.provider.dwd.radar.api import DwdRadarSites

# Acquire information for a specific site.
site_asb = DwdRadarSites().by_odim_code("ASB")
print(site_asb)
```

#### Data

To use ``DWDRadarRequest``, you have to provide a ``RadarParameter``,
which designates the type of radar data you want to obtain. There is
radar data available at different locations within the DWD data repository:

- [composite](https://opendata.dwd.de/weather/radar/composite/)
- [radolan](https://opendata.dwd.de/weather/radar/radolan/)
- [radvor](https://opendata.dwd.de/weather/radar/radvor/)
- [sites](https://opendata.dwd.de/weather/radar/sites/)
- [radolan cdc daily](https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/)
- [radolan cdc hourly](https://opendata.dwd.de/climate_environment/CDC/grids_germany/hourly/radolan/)
- [radolan cdc 5 minutes](https://opendata.dwd.de/climate_environment/CDC/grids_germany/5_minutes/radolan/)

For ``RADOLAN_CDC``-data, the time resolution parameter (either hourly or daily)
must be specified.

The ``date_times`` (list of datetimes or strings) or a ``start_date``
and ``end_date`` parameters can optionally be specified to obtain data
from specific points in time.

For ``RADOLAN_CDC``-data, datetimes are rounded to ``HH:50min``, as the
data is packaged for this minute step.

This is an example on how to acquire ``RADOLAN_CDC`` data using
``wetterdienst`` and process it using ``wradlib``.

For more examples, please have a look at 
[examples/radar/](https://github.com/earthobservations/wetterdienst/tree/main/examples/radar).

```python
from wetterdienst.provider.dwd.radar import DwdRadarValues, DwdRadarParameter, DwdRadarResolution
import wradlib as wrl

radar = DwdRadarValues(
    parameter=DwdRadarParameter.RADOLAN_CDC,
    resolution=DwdRadarResolution.DAILY,
    start_date="2020-09-04T12:00:00",
    end_date="2020-09-04T12:00:00"
)

for item in radar.query():

    # Decode item.
    timestamp, buffer = item

    # Decode data using wradlib.
    data, attributes = wrl.io.read_radolan_composite(buffer)

    # Do something with the data (numpy.ndarray) here.
```

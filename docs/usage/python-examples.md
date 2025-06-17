---
file_format: mystnb
kernelspec:
  name: python3
---

# Python Examples

## DWD

### Observation

Get available parameters for daily historical data of DWD:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

metadata = DwdObservationRequest.discover(
    resolutions="daily",
)

metadata
```

Get stations for daily historical precipitation:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "precipitation_more"),
    periods="historical",
)

stations = request.all()
df = stations.df
df
```

Get data for a dataset:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "precipitation_more"),
    periods="historical",
)

first_values = next(request.all().values.query())
df = first_values.df
df
```

Get data for a parameter:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("daily", "climate_summary", "precipitation_height"),
    periods="historical",
)

first_values = next(request.all().values.query())
df = first_values.df
df
```

Get data for a parameter from another dataset:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=[("daily", "precipitation_more", "precipitation_height")],
    periods="historical",
)

first_values = next(request.all().values.query())
df = first_values.df
df
```

### Mosmix

Get stations for MOSMIX-SMALL:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest

request = DwdMosmixRequest(
    parameters=("hourly", "small"),
)

stations = request.all()
df = stations.df
df
```

Get data for MOSMIX-LARGE:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest

stations = DwdMosmixRequest(
    parameters=("hourly", "large"),
)

stations = request.all()
df = stations.df
df
```

### Radar

#### Sites

Retrieve information about all OPERA radar sites.

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites

# Acquire information for all OPERA sites.
sites = OperaRadarSites().all()
print(f"Number of OPERA radar sites: {len(sites)}")

# Acquire information for a specific OPERA site.
site_ukdea = OperaRadarSites().by_odim_code("ukdea")
site_ukdea
```

Retrieve information about the DWD radar sites.

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.radar.api import DwdRadarSites

# Acquire information for a specific site.
site_asb = DwdRadarSites().by_odim_code("ASB")
site_asb
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

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.radar import DwdRadarValues, DwdRadarParameter, DwdRadarResolution
import wradlib as wrl

radar = DwdRadarValues(
    parameter=DwdRadarParameter.RADOLAN_CDC,
    resolution=DwdRadarResolution.DAILY,
    start_date="2020-09-04T12:00:00",
    end_date="2020-09-04T12:00:00"
)

for item in radar.query():
    # Decode data using wradlib.
    data, attributes = wrl.io.read_radolan_composite(item.data)

    # Do something with the data (numpy.ndarray) here.
    break
    
attributes
```
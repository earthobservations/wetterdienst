# Observation

## Overview

Environment and Climate Change Canada (ECCC) publishes historical weather observations for the
Canadian station network at hourly, daily, monthly and annual resolution. The network is large
and reaches back to the 19th century, though the parameters and period covered vary strongly
between stations.

Data is retrieved as bulk CSV exports from the ECCC climate data service
([bulk data](https://climate.weather.gc.ca/climate_data/bulk_data_e.html)), with station
metadata resolved from the same service. No authentication is required. As only historical data
is offered, a date range is required when requesting values.

```{toctree}
:hidden:

hourly.md
daily.md
monthly.md
annual.md
```
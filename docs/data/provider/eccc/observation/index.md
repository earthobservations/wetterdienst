# Observation

## Overview

Environment and Climate Change Canada (ECCC) publishes historical weather observations for the
Canadian station network at hourly, daily and monthly resolution. The network is large
and reaches back to the 19th century, though the parameters and period covered vary strongly
between stations.

Data is retrieved from the ECCC OGC API
([api.weather.gc.ca](https://api.weather.gc.ca)), with station metadata resolved from the same
service. No authentication is required. As only historical data is offered, a date range is
required when requesting values.

```{toctree}
:hidden:

hourly.md
daily.md
monthly.md
```
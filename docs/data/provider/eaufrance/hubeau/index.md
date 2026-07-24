# Hubeau

## Overview

Hubeau is the open API platform of Eaufrance, the French public water-information service.
Wetterdienst uses its hydrometry API to provide real-time river observations for the French
river network, covering roughly the last 30 days.

Two parameters are available — water level (`stage`) and discharge (`flow`) — served from the
`hydrometrie/observations_tr` ("temps réel") endpoint as JSON, with station metadata coming
from the `hydrometrie/referentiel/stations` endpoint. The API is key-less; no authentication
is required.

Because only real-time data is exposed, there is a single "dynamic" resolution rather than the
fixed resolutions used by the observation providers.

```{toctree}
:hidden:

dynamic.md
```
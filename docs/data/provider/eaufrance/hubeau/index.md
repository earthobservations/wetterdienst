# Hubeau

## Overview

Hubeau is the open API platform of Eaufrance, the French public water-information service.
Wetterdienst uses its hydrometry API to provide real-time river observations for the French
river network, covering roughly the last 30 days. The network includes the overseas departments —
Guadeloupe, Martinique, Guyane, La Réunion and Mayotte — whose station codes begin with a digit
where metropolitan ones begin with the letter of their hydrographic basin.

Two parameters are available — water level (`stage`) and discharge (`flow`) — served from the
`hydrometrie/observations_tr` ("temps réel") endpoint as JSON, with station metadata coming
from the `hydrometrie/referentiel/stations` endpoint and each station's elevation, the altitude of
its hydrometric site, from `hydrometrie/referentiel/sites`. The API is key-less; no authentication
is required.

Only stations in service are listed, and the referential gives none of them a closing date, so a
station's `end_timestamp` is null.

A site publishes no altitude for about a quarter of the stations, and a few publish 0 or a value
no ground in France lies at (-999 m, or 12 km and more); their `elevation` is null. The altitude
of the gauge's zero, the datum a stage is read from, is listed separately as `gauge_zero`, and the
vertical reference system it is given in as `gauge_zero_datum`: the Sandre label of the station's
`code_systeme_alti_site` (nomenclature 76), such as `IGN 1969` or
`Nivellement Général de la France 1884`, or the code itself for one without a label. Stations
differ in it, mainland ones too, so compare two gauge zeros only where their datums agree and name
a datum: two stations labelled `Système altimétrique inconnu` (unknown) or
`Système local - hauteur relative` (each a gauge's own local reference) share no datum.

The recording interval is a property of the station rather than of the network, and unlike most
services Hubeau publishes it nowhere: neither the station referential nor the observations carry
it. It is therefore measured from the timestamps a station has just published — the network does
transmit on a grid — and each station is listed under the interval it was measured at. Roughly
five in eight French gauges transmit every five minutes, most of the rest every ten or fifteen,
and about a hundred hourly.

Two consequences are worth knowing. A station that has published nothing recent cannot be
measured and is listed under no resolution until it transmits again, which is the state of most
of the thousand-odd gauges the referential still marks as in service. And a station transmitting
on its own phase rather than on the wall clock — hourly at seven minutes past, say — is described
correctly by its interval even though its timestamps do not land on the wall-clock hour.

```{toctree}
:hidden:

5_minutes.md
6_minutes.md
10_minutes.md
15_minutes.md
hourly.md
```

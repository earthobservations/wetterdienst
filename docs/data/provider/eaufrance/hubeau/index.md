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

A station's `end_timestamp` is the closing date the referential gives it, and null where it gives
none. Only stations in service are listed, and none of them had a closing date on 2026-10-07.

The referential writes the position of some stations wrongly: on 2026-10-28, 54 metropolitan
stations with latitude and longitude swapped (Anor at latitude 4.10 and longitude 49.99, a point
near Somalia) and the Blavet (`J543211003`) at 35.1 N, 0.84 E, in Algeria. A position that lies in
none of metropolitan France, Guadeloupe and Martinique, Guyane, Reunion and Mayotte is swapped
back when the swapped one lies in one of them, so that Anor is at 50.0 N, 4.1 E; no station
overseas is moved. One that no swap puts right is listed with a null `latitude` and `longitude`,
and the answer carries the warning `position-unplaced`, which names the station and the position
the referential wrote as `raw:<latitude>,<longitude>`. It is there when the station is in the answer
(selected by id, name or SQL, or the whole list) and when a search by place (a rank, a distance, a
bounding box, an interpolation or a summary) had to leave it out, which every search by place of a
resolution that lists the station does, whether or not the place is near where the source put it;
a request for other stations, or for a resolution that does not list it, does not carry it. An
answer for a window (`timestamp`), whether a stations listing, the values of stations or an
interpolation or a summary, tells it for the whole list and for a search by place only if the
station has a record in the window, as it would otherwise not be in the answer; a station named
by id or SQL is told whatever the window does to it, and a name is matched among the stations with
a record in the window like any other. In the Python library, where `all()` holds
the station it is told too, and the warning is also a log line, once for the process.

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

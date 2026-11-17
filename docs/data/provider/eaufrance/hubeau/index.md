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
a record in the window like any other. In the Python library `all()` and the filters by id, SQL,
rank, distance and bounding box tell it whatever the `start` and `end` of the request, as they cut
nothing to them; a name is matched among the stations with a record in the window there too, and
`interpolate` and `summarize` cut to it as the command line and REST do. The warning is also a log line there, once
for the process.

A site publishes no altitude for about a quarter of the stations, and a few publish 0 or a value
no ground in France lies at (-999 m, or 12 km and more); their `elevation` is null. The altitude
of the gauge's zero, the datum a stage is read from, is listed separately as `gauge_zero`, and the
vertical reference system it is given in as `gauge_zero_datum`: the Sandre label of the station's
`code_systeme_alti_site` (nomenclature 76), such as `IGN 1969` or
`Nivellement Général de la France 1884`, or the code itself for one without a label. Stations
differ in it, mainland ones too, so compare two gauge zeros only where their datums agree and name
a datum: two stations labelled `Système altimétrique inconnu` (unknown) or
`Système local - hauteur relative` (each a gauge's own local reference) share no datum.

A station's `station_id` is its `code_station`, ten characters (`1011000101`). `site_id` is the `code_site` of the
referential, the eight characters of the hydrometric site the station is one of (`10110001`): a station's code is its
site's and two digits, and a site can have more than one station (the Seine at Austerlitz, `F7000001`, has two), so
it names a place and no single station. All 6,543 stations of the referential have one (read 2026-11-14). Find the
stations of a site with `filter_by_sql("site_id = 'F7000001'")`. The referential has no WMO, WIGOS or ICAO id:
those columns are null.

The recording interval is a property of the station rather than of the network, and unlike most
services Hubeau publishes it nowhere: neither the station referential nor the observations carry
it. It is therefore measured from the timestamps a station has just published — the network does
transmit on a grid — and each station is listed under the interval it was measured at. Roughly
five in eight French gauges transmit every five minutes, most of the rest every ten or fifteen,
and about a hundred hourly.

The stage of every station over the last two hours is read in one go; a station quiet in them is
asked for by name over the last 24 hours, and one that has published only discharge is measured on
that. Its interval is the commonest spacing of its records (the shorter on a tie), but only if
its records settle on it: at least 90 % of the spacings must be multiples of that interval (a
missed transmission leaves twice the interval, which counts for it), and that interval must be at
least 50 % of the spacings, from at least three spacings. A station that fails the test in the two
hours is measured again over 24 hours under the same test. A sparse gauge that sends in bursts
has a commonest spacing that means nothing, and listing it at that spacing put it under a
different resolution from one lookup to the next (H502301401 was listed at 5, 10, 15 and 60
minutes by turns over 30 days, measured on 2026-11-17).

Three consequences are worth knowing. A station that has published nothing recent cannot be
measured and is listed under no resolution until it transmits again, which is the state of most
of the thousand-odd gauges the referential still marks as in service. A station whose steps don't
settle is served under no resolution until they do: it is not listed at its commonest spacing,
and the log says once per process how many there are. Of the 267 stations listed at 15 minutes
on 2026-11-17, 7 did not keep that cadence; three of them are 60 to 80 % regular, so their steps
settle in some windows and not in others. And a station transmitting
on its own phase rather than on the wall clock — hourly at seven minutes past, say — is described
correctly by its interval even though its timestamps do not land on the wall-clock hour.
A station whose cadence changes (one was half-hourly until 2026-10-22 and quarter-hourly since)
is listed under the new one once its recent records settle on it. A half-hourly station is
served under no resolution, as no resolution covers that interval.

## The source's own verdict (`source`)

Every observation carries a `code_qualification_obs`, the plain flag of `quality_flags`. The
[API documentation](https://hubeau.eaufrance.fr/api/v2/hydrometrie/api-docs) (read 2026-11-02) words it as
"Qualification de la donnée d'observation hydrométrique. 7 valeurs possibles : 0, 4, 8, 12, 16, 20, 30 (Neutre, Faible,
Forte, Douteuse, Non qualifiée, Bonne, Estimée)" and points to the Sandre nomenclature 515, which words `12` as
"Valeur douteuse". The check `source` reads `12` "Douteuse". Not read: `0` "Neutre", `4` "Faible" and `8` "Forte" (the
Sandre's "Valeur inconnue" with its direction, no verdict on a measured value), `16` "Non qualifiée" (no control),
`20` "Bonne" and `30` "Valeur estimée". The code is the only one that says a value is doubtful, and it is common: of the
first 20,000 rows of the real time observations of 2026-11-02 (the last day, all stations) 17,830 were `16` and 2,170 `12`,
so in `hard` mode a doubtful value of the rolling 30 days is null.

With `plausibility={"source": "hard"}` the value is null and the token is `rejected:source,raw:<text>`; the default is
`soft`, which keeps the value and writes `12,suspect:source`, so interpolation, summaries and climate stripes leave it
out. See [the check `source`](../../../plausibility.md#the-sources-own-verdict-source).

```{toctree}
:hidden:

5_minutes.md
6_minutes.md
10_minutes.md
15_minutes.md
hourly.md
```

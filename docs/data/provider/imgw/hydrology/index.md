# Hydrology

## Overview

IMGW publishes hydrological observations for the Polish river-gauge network at daily and monthly
resolution, as open data from the
[public data portal](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/).
No authentication is required.

Values are downloaded as zipped CSV archives and decoded as `latin-1`. The archive layout has
changed over time — daily data is split into per-month files (`codz_YYYY_MM.zip`) historically
and consolidated into a single per-year file (`codz_YYYY.zip`) from 2023 onwards — which
wetterdienst normalizes transparently.

The stations come from IMGW's
[station-code list](https://dane.imgw.pl/datastore/getfiledown/Arch/Telemetria/Hydro/kody_stacji.csv).
Besides the core columns, each station names the river the gauge is on, with its hydrographic code
as IMGW lists it (`Odra (1)`), as `river`, and the gauge's position along it, in kilometres from the
river's mouth, as `river_kilometer`; the Baltic coast gauges are on the sea (`Morze Bałtyckie (0)`)
and their kilometre is at or near `0`, or none. The altitude of the gauge's zero, in metres above
sea level and negative for some coastal gauges, is `gauge_zero`. The list does not state which
vertical datum that altitude refers to, so `gauge_zero_datum` is null. Each of them is null for a
station whose field IMGW leaves empty. The names are those `wsv/pegel` uses, but IMGW counts the
kilometre from the river's mouth, while Pegelonline uses the German waterway kilometre, which grows
downstream, so the values of the two networks on one river are not comparable.

## Stations that are only in the archive

The station-code list is the list of the stations IMGW runs today, so a station that was closed, or
whose code changed, has archive values (back to 1951) but no station row. `stations` does not find
it, and its values cannot be requested, since a request only serves the stations it knows. About 500
of the roughly 1,370 station codes in the monthly archive are in this case, Brudnice (`153190160`)
among them. IMGW publishes no position for them: the archive's own list of stations,
[`lista_stacji_hydro.csv`](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/lista_stacji_hydro.csv),
gives only the code, the name, the river and IMGW's hydro code, and neither the content maps nor the
CSV files carry coordinates. IMGW's telemetry API
(`danepubliczne.imgw.pl/api/data/hydro`) lists 32 stations that are not in the station-code list, 30
of them in the archive, and writes `0` for the latitude and the longitude of each, which is no
position. These stations get no row rather than one at a guessed position or at `0, 0`.

## The gauge zero can move

`stage` and `stage_*` are the height of the water above the zero of the gauge, and IMGW has moved
the zero of some gauges without saying when. A stage series that crosses such a move is not
continuous, and wetterdienst passes the values on as IMGW publishes them and sets no flag on the
jump. `gauge_zero` is one altitude per station, not one per date of a value.

Known cases, each seen as a step in the stage that the discharge does not share:

- Warszawa-Nadwilanówka (`152210040`, Wisła): the monthly mean stage goes from 118 cm (October
  1990) to 311 cm (November 1990, the first month of hydrological year 1991) and stays about 200 cm
  higher, while the discharge goes from 396 to 379 m³/s.
- Brudnice (`153190160`, only in the archive, see above): the stage jumps from about 35 to 334 cm
  at the same boundary.
- Kozłowa Góra (`150180270`): the annual mean drops by 391 cm in 2011, which may be a reservoir
  rather than a move of the zero.

Ten stations in all change their annual mean stage by more than 150 cm from one year to the next;
not each of them is a moved zero. Compare the stage with the discharge of the same station, or with
its neighbours, before reading a trend across a step, and use `discharge`, which a move of the zero
does not touch, where the question allows it.

```{toctree}
:hidden:

daily.md
monthly.md
```
# Observation

## Overview

"Données climatologiques de base", covering a much larger network of several thousand stations across
metropolitan France and overseas territories, sharded by French department. Station identity, coordinates and
start/end dates are sourced from Météo-France's canonical station metadata registry rather than the (much
larger) per-department archives themselves; a small fraction of listed stations may not actually have
downloadable daily/monthly records.

A station's `region` is the code of its département, as the registry lists it and written with two digits
(`09` for the Ariège, `29` for Finistère), or three for an overseas one (`972` for Martinique). It is the code
and not the name, and the registry does not tell Corsica's two départements apart: both are `20`, not `2A` and
`2B`. The `meteofrance/synop` list gives no region.

- **daily**: split into a `core` dataset (precipitation, temperature, wind) and an `others` dataset (pressure,
  radiation, humidity, snow) — roughly balanced in size, so neither gets the generic name
- **monthly**: a single dataset, so it keeps the generic `data` name
- **hourly**: also split into `core`/`others`, though this split only exists at the wetterdienst level — the
  source publishes one unsplit file per department/period covering all ~100 parameters
- **6_minutes**: a single dataset, covering only precipitation (the only parameter published at this resolution)

## Plausibility checks

Three [checks](../../../plausibility.md) judge values here, all hard by default: `range`, the one table of bounds of
every provider and a temperature below 0 °C (the air at 2 m, its extremes and the dew point) at a station of Guadeloupe,
Martinique, Guyane, Mayotte, Wallis-et-Futuna, French Polynesia or the Îles Éparses, where there is no frost
(`rejected:range,raw:-20.0`; the datasets `hourly/core`, `hourly/others`, `daily/core` and `monthly/data`);
`elevation`, the hourly station pressure `PSTAT` of a station with an elevation in the list, which the standard
atmosphere does not allow, from 870/1013.25 of it (143 hPa below at sea level) to 75 hPa above it (a slip such as 1093.3 hPa at 3 m is
`rejected:elevation,raw:1093.3`; Hurricane Irma's 917.4 hPa at St-Barthélemy, 3 m, 2017-09-06, is kept; 14.6 million readings of the files of 2025 and
2026 and of 77 of the 210 department files of 2010 to 2024 held none that the rule rejects; `hourly/others`); and `consistency`, the hourly humidity `U` of an hour whose dew point
`TD` is such a temperature (`rejected:consistency,raw:15`; `hourly/others`). The dew point is read from the same dataset (collected whole), whether it is asked for or not, and nothing is
downloaded for the check. With `plausibility={"range":
"soft"}` the value is kept and flagged `suspect:range`.

`source` is the fourth check, soft by default: the validation code `Q<parameter>` of a value is the plain flag of
`quality_flags`, and the check reads the one code the four "descriptif" documents of the base climatological data word as a
doubt, `2`: "donnée douteuse en cours de vérification (la donnée a été mise en doute par contrôle automatique)". The
documents say "Pour certains paramètres, un code qualité est associé à la mesure (noté Qparamètre). Il qualifie l’état de
validation de la donnée : 9 : donnée filtrée (la donnée a passé les filtres/contrôles de premiers niveaux) ; 0 : donnée
protégée (la donnée a été validée définitivement par le climatologue) ; 1 : donnée validée (la donnée a été validée par
contrôle automatique ou par le climatologue) ; 2 : donnée douteuse en cours de vérification (la donnée a été mise en doute
par contrôle automatique)." ([quotidiennes](https://static.data.gouv.fr/resources/donnees-climatologiques-de-base-quotidiennes/20260603-085232/climatologie-donnees-quotidiennes-descriptif-20260603.pdf),
[horaires](https://static.data.gouv.fr/resources/donnees-climatologiques-de-base-horaires/20260603-085646/climatologie-donnees-horaires-descriptif-20260603.pdf),
[mensuelles](https://static.data.gouv.fr/resources/donnees-climatologiques-de-base-mensuelles/20260603-085345/climatologie-donnees-mensuelles-descriptif-20260603.pdf),
[6 minutes](https://static.data.gouv.fr/resources/donnees-climatologiques-de-base-6-minutes/20260401-151040/climatologie-donnees-6-minutes-descriptif-20250604.pdf),
read 2026-11-02). Soft keeps the value and writes `2,suspect:source`; `hard` nulls it, `2,rejected:source,raw:<text>`, with
the text of the file as `raw:`. The codes `9`, `0` and `1` are no doubt and are not read. A `2` is rare: the daily file of département 75 (`Q_75_latest-2025-2026_RR-T-Vent`, 3,228 rows, read 2026-11-02) holds the codes 9, 1, 0 and blank and no 2, so the test of the mapping is a row written after the documents. The synop network has no such flag.
See [the check `source`](../../../plausibility.md#the-sources-own-verdict-source).

```{toctree}
:hidden:

daily.md
hourly.md
6_minutes.md
monthly.md
```

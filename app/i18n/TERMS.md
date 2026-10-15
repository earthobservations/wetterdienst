# Terminology

The project's own terms, and the word each locale uses for them. A translation of a new string
uses the word in this table wherever the English text says the term, so the same thing is not
called two things on two pages of one language.

The table is read back by `tests/unit/i18n-quality.test.ts`: a cell that differs from the catalog
fails, so it can only say what the catalogs say. The same test checks, for station, parameter,
dataset, resolution, provider, network and period, that each locale's text contains its word wherever
the English text has the term. To change a word, change it in the catalog, here and in the stem
table at the bottom of that test, in one commit.

## The terms

Each cell is the label the app shows for the term, from the key in the second row (`glossary:` keys
are in `glossary/<locale>.ts`).

| Locale | Station | Parameter | Dataset | Resolution | Period | Quality | Provider | Network | Date range | Weather service |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Source key | `stripes.station` | `dataViewer.statParameter` | `parameterSelection.datasetLabel` | `parameterSelection.resolutionLabel` | `history.periods` | `glossary:parameters.quality` | `parameterSelection.providerLabel` | `parameterSelection.networkLabel` | `dateRange.label` | `home.dataProvidersTitle` |
| `en` | Station | Parameter | Dataset | Resolution | Periods | Quality | Provider | Network | Date Range | Weather services |
| `de` | Station | Parameter | Datensatz | Auflösung | Zeiträume | Qualität | Anbieter | Netzwerk | Zeitraum | Wetterdienste |
| `de-hh` | Station | Parameter | Datensatz | Auflösung | Zeiträume | Gööd | Anbieter | Netzwerk | Zeitraum | Wetterdienste |
| `fr` | Station | Paramètre | Jeu de données | Résolution | Périodes | Qualité | Fournisseur | Réseau | Plage de dates | Services météorologiques |
| `es` | Estación | Parámetro | Conjunto de datos | Resolución | Periodos | Calidad | Proveedor | Red | Rango de fechas | Servicios meteorológicos |
| `it` | Stazione | Parametro | Dataset | Risoluzione | Periodi | Qualità | Fornitore | Rete | Intervallo di date | Servizi meteorologici |
| `nl` | Station | Parameter | Dataset | Resolutie | Perioden | Kwaliteit | Aanbieder | Netwerk | Datumbereik | Weerdiensten |
| `pl` | Stacja | Parametr | Zbiór danych | Rozdzielczość | Okresy | Jakość | Dostawca | Sieć | Zakres dat | Służby meteorologiczne |
| `cs` | Stanice | Parametr | Datová sada | Rozlišení | Období | Kvalita | Poskytovatel | Síť | Rozsah dat | Meteorologické služby |
| `da` | Station | Parameter | Datasæt | Opløsning | Perioder | Kvalitet | Udbyder | Netværk | Datointerval | Vejrtjenester |
| `lb` | Statioun | Parameter | Dataset | Opléisung | Perioden | Qualitéit | Ubidder | Netzwierk | Datumberäich | Wiederdéngschter |

## Terms that are different things

- **Period** is a stretch of time in a station's history (the periods of missing data), and **date
  range** is what the user picks in the date picker. Both are "Zeitraum" in German (and `de-hh`),
  where the two collapse; every other locale has two words.
- **Resolution** is the interval a value stands for (10 minutes, daily), never the date range.
- **Provider** is the source of the data (DWD, NOAA) and **weather service** is the institution
  behind it: the home page counts weather services, the explorer picks a provider. The
  **operator** of a station, from the station history, is a third thing and is not translated as
  provider (`Betreiber`, `exploitant`, `gestore`, `operator`, `Bedreiwer`, `provozovatel`, ...).
- **Quality flag** is the word each locale settled on in its sixteen `quality_*` glossary entries;
  `i18n-parity.test.ts` holds a locale to it (Kennung, flag, vlag, indicateur, ...).

## Address and spelling

How each locale speaks to the reader, as the catalogs have it now. A new string follows this.

| Locale | Address | Spelling and notes |
| --- | --- | --- |
| `en` | no direct address needed | British spelling (`humanised`, `colour`), as `en-GB` in `nuxt.config.ts` |
| `de` | Sie | |
| `de-hh` | du | Hamburgisch in the glossary; see the open rows below for the UI text |
| `fr` | vous | |
| `es` | tú | `periodo`, not `período` |
| `it` | tu | |
| `nl` | je | |
| `pl` | imperative, second person singular | |
| `cs` | vy | |
| `da` | du | |
| `lb` | Dir (second person plural) | |

## Open: waits for a native speaker

Not decided here, and the text is left as it is. The review table with the proposals is in the pull
request that added this file, and the issue it belongs to is
[GH-2610](https://github.com/earthobservations/wetterdienst/issues/2610).

- `de-hh`: most of the UI text is the German text (about 85 %); the glossary is Plattdüütsch. The
  quality label is `Gööd` while its sixteen flag entries say `Gütenkennen`.
- `lb`: the explorer mode descriptions (`explorer.mode*Desc`, `*How`, `modeHowItWorks`) and the SQL
  query panel (`query.*`) are still the English text; `history.colMethod` ("Method") and
  `Dataset` (also `Datesätz` once) look borrowed.
- `lb`: the four map hints (`mapHint`, `mapHintMultiple`) address the reader with "du" ("Tipp op
  ...") where the rest of the locale uses "Dir".
- `nl`: `waarneming` (glossary, one label) and `observatie` (the UI) are both used for "observation".

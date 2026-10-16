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
| `de-hh` | Station | Parameter | Datensatz | Oplösung | Tietrüüm | Gööd | Anbeder | Nettwark | Tietruum | Wedderdeenste |
| `fr` | Station | Paramètre | Jeu de données | Résolution | Périodes | Qualité | Fournisseur | Réseau | Plage de dates | Services météorologiques |
| `es` | Estación | Parámetro | Conjunto de datos | Resolución | Periodos | Calidad | Proveedor | Red | Rango de fechas | Servicios meteorológicos |
| `it` | Stazione | Parametro | Dataset | Risoluzione | Periodi | Qualità | Fornitore | Rete | Intervallo di date | Servizi meteorologici |
| `nl` | Station | Parameter | Dataset | Resolutie | Perioden | Kwaliteit | Aanbieder | Netwerk | Datumbereik | Weerdiensten |
| `pl` | Stacja | Parametr | Zbiór danych | Rozdzielczość | Okresy | Jakość | Dostawca | Sieć | Zakres dat | Służby meteorologiczne |
| `cs` | Stanice | Parametr | Datová sada | Rozlišení | Období | Kvalita | Poskytovatel | Síť | Rozsah dat | Meteorologické služby |
| `da` | Station | Parameter | Datasæt | Opløsning | Perioder | Kvalitet | Udbyder | Netværk | Datointerval | Vejrtjenester |
| `lb` | Statioun | Parameter | Datesaz | Opléisung | Perioden | Qualitéit | Ubidder | Netzwierk | Datumberäich | Wiederdéngschter |

## Terms that are different things

- **Period** is a stretch of time in a station's history (the periods of missing data), and **date
  range** is what the user picks in the date picker. Both are "Zeitraum" in German and `Tietruum` in
  `de-hh` (the period's plural is `Tietrüüm`), where the two collapse; every other locale has two
  words.
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
| `de-hh` | du | Plattdüütsch (Low German, Hamburg), in the UI text and in the glossary alike |
| `fr` | vous | |
| `es` | tú | `periodo`, not `período` |
| `it` | tu | |
| `nl` | je | |
| `pl` | imperative, second person singular | |
| `cs` | vy | |
| `da` | du | |
| `lb` | Dir (second person plural) | |

## Counts

A message that says how many of something is written in plural forms separated by `|`: two (`{count}
value | {count} values`) in every locale but `pl` and `cs`, which have three (one, few, other:
`{count} wartość | {count} wartości | {count} wartości`). `i18n/plural-rules.ts` says which form a
count takes, from the CLDR rules of the language (French takes the first for 0 and 1, the others for
1 only). vue-i18n takes the form from the named `{count}`, so the number the noun follows is the one
called `count`: `t('dataViewer.valuesCount', { count })`, and `glossary.count` is "{shown} of
{count} parameters", the total being the `count`. `tests/unit/i18n-quality.test.ts` holds every
locale to the number of forms and to `{count}` in each of them. A count that needs no form
("Estimated values: {count}") is not written in forms.

## Review status: not natively reviewed

The text of four locales was written without a native speaker, and none has read it since. It is
meant to be understood, not to be the last word, and **a review by a native speaker is welcome**
(an issue or a pull request against the catalog is all it takes):

- `pl` and `cs`: the whole catalogs and, since GH-2968, the three plural forms of the counts.
- `lb` (Luxembourgish): the whole catalog; the explorer mode descriptions, the SQL panel (`query.*`)
  and `history.colMethod` were English until GH-2970 and are the newest text. The dataset is a
  `Datesaz` (plural `Datesätz`) and a method a `Methode`: the two words that looked borrowed, chosen
  rather than confirmed.
- `de-hh` (Plattdüütsch): the UI text, written for GH-2969 in the language the glossary is in and with
  its vocabulary (`Nedderslag`, `Daag`, `Stünn`, `Weer`/`Wedder`, `lest`, `vun`, `för`, `ünner`). The
  glossary has several spellings of the same word (`Sünnschien`, `Sünnenschien`; `Snééhööchd`,
  `Snehööch`), so there is no one orthography to follow; the UI text leans on the Sass spelling and
  is itself not uniform. The quality term is `Gööd` and its sixteen flag entries `Göödkennen`.
  `Datensatz` is kept as Low German shares the word; `Anbeder`, `Nettwark`, `Oplösung` and `Tietruum`
  are the words chosen for provider, network, resolution and date range.

Nothing here says the other locales (`en`, `de`, `fr`, `es`, `it`, `nl`, `da`) were reviewed by a
native speaker either; these four are the ones known not to have been.

## Open: waits for a native speaker

Not decided here, and the text is left as it is. The review table with the proposals is in the pull
request that added this file, and the issue it belongs to is
[GH-2610](https://github.com/earthobservations/wetterdienst/issues/2610).

- `lb`: the four map hints (`mapHint`, `mapHintMultiple`) address the reader with "du" ("Tipp op
  ...") where the rest of the locale uses "Dir".
- `nl`: `waarneming` (glossary, one label) and `observatie` (the UI) are both used for "observation".

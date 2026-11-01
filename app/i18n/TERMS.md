# Terminology

The project's own terms, and the word each locale uses for them. A translation of a new string
uses the word in this table wherever the English text says the term, so the same thing is not
called two things on two pages of one language.

The table is read back by `tests/unit/i18n-quality.test.ts`: a cell that differs from the catalog
fails, so it can only say what the catalogs say. The same test checks, for station, parameter,
dataset, resolution, provider, network and period, and for the API page's endpoint (which is not in the
table), that each locale's text contains its word wherever the English text has the term. To change a word, change it in the catalog, here and in the stem
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

Every locale speaks to the reader in the **informal singular**, as one person talks to another, and
not in the polite form, which sounds like an office. The app is a free tool made by a person for people
(see the "values" on the about page), and one register in every language means a text read in a second
language does not change tone. A new string follows this; a translation that slips back into the polite
form is a defect (GH-3157).

| Locale | Address | Quotation marks | Spelling and notes |
| --- | --- | --- | --- |
| `en` | you, your | “…” | British spelling (`humanised`, `colour`), as `en-GB` in `nuxt.config.ts`; English has no other form to choose |
| `de` | du, dein, dir | „…“ | `Wähle`, `Tippe`, `Öffne` (singular imperative, no `Sie`) |
| `de-hh` | du | „…“ | Plattdüütsch (Low German, Hamburg), in the UI text and in the glossary alike |
| `fr` | tu, ton/ta/tes, te | « … » | a no-break space before `: ; ? !` and inside the guillemets; `Choisis`, `Touche`, `Que souhaites-tu` (a verb of the first group has no `-s` in the imperative except before `y`/`en`) |
| `es` | tú | «…» | `periodo`, not `período` |
| `it` | tu | «…» | |
| `nl` | je | “…” | |
| `pl` | imperative, second person singular | „…” | |
| `cs` | ty (singular: `chceš`, `tvůj`/`tvoje`) | „…“ | the singular imperative has no `-te` (`Vyber`, `Zkus`), a text that names no one and needs no gender is preferred over `-l`/`-la` (`Našla se chyba?`, as `Našel jsi` would be masculine) |
| `da` | du | “…” | |
| `lb` | du, dir, deng/däin | „…“ | the plural `Dir`/`Är` the catalog used before GH-3157 is gone; the singular imperative is the stem (`Wiel`, `Kuck`, `Ruff … of`, `Gëff … an`) |

The apostrophe is the straight `'` in every locale, and `«…»` in the legal page's operator note is the
marker of a field to fill in, not a quotation. `tests/unit/i18n-quality.test.ts` holds the catalogs to
the quotation marks and the apostrophe, to the French spacing, and to the informal address: it looks for
the formal pronouns and possessives of every locale that has them (`Sie`/`Ihr…`/`Ihnen`,
`vous`/`votre`/`vos`, `vy`/`vás`/`váš…`, `Dir`/`Är…`, `usted`, `Lei`, `u`/`uw`, `Pan`/`Pani`, `Dem`/`Deres`)
and for the formal imperative of de, fr, cs and lb (`-ez`, `-te`, a list of Luxembourgish plural
imperatives). A place where such a word is right (a plural "you" that addresses several people, a thing
that only looks like one) is listed in that test with its reason. What it cannot find is a verb form
without such a marker (Spanish `obtiene` for `obtienes`, an `lb` plural imperative that is also a
third-person form), so a new text is read through once as a whole.

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

## Numbers, dates and coordinates

A number the app shows is written in the language of the page: `formatNumber` for text, and the
`separators` of every Plotly layout (`plotlySeparators`) for hover texts and axes. The day and month
of the Meteogram's day cards come from the language's tag (`en-GB`, `de-DE`, as `nuxt.config.ts` has
them), as the bare `en` is American. Coordinates and elevations are the exception and keep a point in
every language (`toFixed`): a position is copied into a map or a query, and the number input that
takes one reads a point. Chrome has no data for Luxembourgish, so `withData` writes `lb` as German
(`de-LU`) is written, which is the same.

## Parameter glossaries

The labels of the parameters, resolutions and datasets (`glossary/<locale>.ts`) are held by
`tests/unit/glossary-translations.test.ts` to more than being there and being translated:

- an English label that names a "Maximum", "Minimum" or "Mean" (also "Highest", "Greatest",
  "Strongest"), wherever in the label, is translated with the locale's word for it; the stems are in
  the test and a new locale adds its own;
- one English label has one translation;
- an hour after a number is `h` (`u` in nl, `t` in da), with the English number;
- a soil temperature of a cover or a texture has the word for the soil, and in fr, es and it it opens
  with the words of the plain soil temperature, so that "Maximum soil temperature under grass" is not
  "Maximum temperature under grass" (the other languages put an adjective before the noun, and a
  correct label of theirs has no fixed opening);
- French sets a no-break space before a colon, as the catalog does.

There is no list of exceptions: a label that is right and breaks one of these changes the rule.

## Review status: not natively reviewed

The text of four locales was written without a native speaker, and none has read it since. It is
meant to be understood, not to be the last word, and **a review by a native speaker is welcome**
(an issue or a pull request against the catalog is all it takes):

- `pl` and `cs`: the whole catalogs and, since GH-2968, the three plural forms of the counts; since
  GH-2971 the fallbacks `common.requestFailed` and `common.backendError*`.
- the text of the limit notice and of the note under the date range (GH-3457: `dataViewer.limit*` and
  `dateRange.defaultNote`, `dateRange.clear`) in `pl`, `cs`, `lb` and `de-hh`; the unit plurals of `pl` and `cs`
  (`dataViewer.limitUnit.*`, `limitStationsCount`, `limitParametersCount`) are the ones to look at first, and in
  `pl` the "Aktualny wybór:" of the selection's counts, which stands where English says "You have selected" to
  avoid a case; `de-hh` is German-looking where the Low German could not be told (`Reegen`, `Antwoort`, `Tietruum`).
- `lb` (Luxembourgish): the whole catalog; the explorer mode descriptions, the SQL panel (`query.*`)
  and `history.colMethod` were English until GH-2970, and the fallbacks `common.requestFailed` and
  `common.backendError*` until GH-2971; they are the newest text. The dataset is a
  `Datesaz` (plural `Datesätz`) and a method a `Methode`: the two words that looked borrowed, chosen
  rather than confirmed.
- `de-hh` (Plattdüütsch): the UI text, written for GH-2969 in the language the glossary is in and with
  its vocabulary (`Nedderslag`, `Daag`, `Stünn`, `Weer`/`Wedder`, `lest`, `vun`, `för`, `ünner`). The
  glossary has several spellings of the same word (`Sünnschien`, `Sünnenschien`; `Snééhööchd`,
  `Snehööch`), so there is no one orthography to follow; the UI text leans on the Sass spelling and
  is itself not uniform. The fallbacks of GH-2971 (`Afraag is scheefgahn`, `Backend-Fehler`) are
  new text in it. The quality term is `Gööd` and its sixteen flag entries `Göödkennen`.
  `Datensatz` is kept as Low German shares the word; `Anbeder`, `Nettwark`, `Oplösung` and `Tietruum`
  are the words chosen for provider, network, resolution and date range.

- The informal address of GH-3157, in **all four locales it changed** (`de`, `fr`, `cs`, `lb`): each
  line that spoke to the reader was rewritten by hand and read through, not by a native speaker. Least
  certain: `cs` `support.reportText` (`Našla se chyba?`, chosen to avoid a gendered `Našel jsi`);
  `lb` imperatives of verbs the catalog had not used in the singular (`Kréi` for `kréien` in
  `api.subtitle` and the `api.endpoints.*` lines, `Gëff … an` in `query.placeholder`, `Rechen … ëm` in
  `settings.convertUnitsHint`, `Fro … of` in `query.hint`) and `iwwerlee dir` in `support.donateText`;
  the `lb` and `cs` informal forms in general.

- The twelve weather words of the forecast's day cards (`meteogram.chart.weather.*`, GH-3186), in all
  four locales. Least certain: `de-hh` `Dunnerwedder`, `Niesregen`, `Newel`, `Deelwies wulkig`,
  `Stoff- oder Sandstorm`, `Sneedrieven`; `lb` `Gewitter`, `Niselreen`, `Deelweis wollekeg`,
  `Schnéigestéber`; `cs` `Polojasno` for "partly cloudy"; `pl` `Zamieć śnieżna`.

- The footer link to the third-party licences (`footer.licenses`, GH-3469), in all four locales. Least
  certain: `de-hh` `Lizenzen vun annere` and `lb` `Lizenze vun Drëtten` ("licences of others"); `cs`
  `Licence třetích stran` and `pl` `Licencje stron trzecich` are the usual forms of "third-party licences".

Nothing here says the other locales (`en`, `de`, `fr`, `es`, `it`, `nl`, `da`) were reviewed by a
native speaker either; these four are the ones known not to have been.

## Open: waits for a native speaker

Not decided here, and the text is left as it is. The review table with the proposals is in the pull
request that added this file, and the issue it belongs to is
[GH-2610](https://github.com/earthobservations/wetterdienst/issues/2610).

- `nl`: `waarneming` (glossary, one label) and `observatie` (the UI) are both used for "observation".
- `nl`: `Colofon` for the legal notice (`footer.legal`, `impressum.title`) names the publisher's
  imprint; a Dutch reader may expect `Juridische informatie`.
- `fr`: `Paramètres` is both "Settings" (`common.settings`, `settings.title`, `stripes.settingsTitle`,
  `explorer.settings`, `explorer.generalSettings`, `explorer.advancedSettings`,
  `dataViewer.chartSettings`) and "Parameters" (`glossary.parametersTitle`,
  `parameterSelection.parametersLabel`), on the same pages. `Réglages` for the settings would keep
  the two apart.

The review of GH-2610 fixed what could be shown to be wrong without a native speaker: the claim of
"no limit" in `home.dataIntro` after the rate limit, a formal address in the `es` catalog, a word
for the same thing in two forms (endpoint, station history, elevation), the quotation marks and
apostrophes that each language sets its own way, French spacing, and a few sentences that were not
grammatical. What follows it left, each with a suggestion. A suggestion is a proposal from a reader of
the language, not a decision; `pl`, `cs`, `lb` and `de-hh` are as unreviewed as before.

| Locale | Key | Now | Suggestion | Sure |
| --- | --- | --- | --- | --- |
| `lb` | `api.endpoints.coverage`, `explorer.available`, `stripes.available`, `widget.noData`, `meteogram.chart.noData`, `query.availableColumns`, `dataViewer.noChartData`, `history.about2`, `history.about3`, `history.datasetHint`, `impressum.openSourceText` | `verfügbar`, `Verfügbar` (German) | `disponibel`, which `parameterSelection.*RestrictionUnavailable` already use | high |
| `lb` | `stripes.showDataAvailability`, `stripes.plotDataAvailability` | `Datverfügbarkeet` | `Disponibilitéit vun den Daten` | medium |
| `lb` | `api.endpoints.history`, `history.about1`, `history.about3`, `history.missingDataHistory`, `history.colMissingCount` | `fehlend`, `fehlenden` | `feelend`, `feelenden` | medium |
| `lb` | `api.endpoints.history`, `history.subtitle`, `history.about3`, `history.deviceHistory`, `history.colDeviceType`, `history.colDeviceHeight` | `Gerät`, `Geräter`, `Gerätehistorique` | `Apparat`, `Apparater`, `Apparatehistorique` | medium |
| `lb` | `home.featureAnalysisTitle` | `Resumé`, where the rest of the catalog writes `Resümee` | one spelling | medium |
| `lb` | `impressum.disclaimerTitle` | `Haftungsausschloss` (German) | a Luxembourgish word for the disclaimer | low |
| `lb` | `dataViewer.rowsPerPage`, `dataViewer.copiedRows`, `query.success` | `Zeile`, `Zeil`, `Zeilen` (German) | `Rei`, `Reien` | low |
| `lb` | `meteogram.aboutText2`, `meteogram.chart.panelCloud`, `meteogram.chart.summaryAvgCloud`, `meteogram.chart.summaryMaxGust`, `meteogram.chart.seriesWindGust` | `Bewölkung`, `Bö` (German) | the Luxembourgish words for cloud cover and gust | low |
| `de-hh` | `nav.history`, `history.title`, `history.subtitle`, `history.aboutButton`, `history.stationHistoryTitle` | `Chronik`, `Stationschronik`, where the rest of the page says `Verloop` | one word, `Verloop` as `de` now has `Verlauf` | medium |
| `de-hh` | `common.backendError`, `support.reportTitle`, `history.error`, `api.endpoints.history` | `Fehler`, `fehlende` where the catalog also has `Feller` | the Low German spelling | low |
| `pl` | `support.reportText` | `Znalazłeś/-aś błąd?` (gendered) | `Czy znaleziono błąd?` | low |
| `pl` | `widget.poweredBy` | `Obsługiwane przez` ("served by") | `Działa dzięki` | low |
| `pl` | `explorer.minGain` | `Min. zysk par wartości` | `Min. przyrost par wartości` | low |
| `cs` | `glossary.noResults`, `providers.noResults` | `Hledání neodpovídá žádný parametr.` | `Hledanému výrazu neodpovídá žádný parametr.` | low |

The parameter glossaries (`glossary/<locale>.ts`) were read for GH-2610 as well (801 labels in each
of the ten languages, against `en`, this file and the weather service's own terms). What was
shown to be wrong is fixed; what follows is a proposal from a reader and waits for a native speaker.
The key is a glossary key (a family is named by its stem, `...` standing for the depths and covers).

| Locale | Key | Now | Suggestion | Sure |
| --- | --- | --- | --- | --- |
| `lb` | `annual_*`, `immediate_*` (about 100 labels) | `Jahresmelder: Rüben`, `Mais`, `Hafer`, `Weißkohl`, `frühe Reife`: the German label, 101 datasets equal to `de` | translate the prefix and the plants (`Jahresmelder`/`Sofortmelder` have no Luxembourgish word here yet) | high that it is German |
| `lb` | `cloud_cover_*`, `cloud_cover_total*`, `cloudiness` | `Bewölkungsgrad`, `Gesamtbewölkung`, `Bewölkung` (German) | the Luxembourgish word for cloud cover, as for the UI row above | low |
| `lb` | `*_manual`, `phenology_flowering_end_observation_area`, `road_surface_condition*`, `precipitation_amount_normal`, `temperature_dew_point*`, `temperature_wind_chill` | `Aebeobachtung`, `Beobachtungsgebitt`, `Fahrbunn`, `Klimanormalwäert`, `Taupunkt`, `Windchill` | a Luxembourgish word each | low |
| `lb` | `sunshine_duration`, `sunshine_duration_*` | `Sonnenscheindauer` (parameter, dataset) next to `Sonnendauer` (the other eleven) | one word, `Sonnenschäindauer` as the dataset `sun` is `Sonnenschäin` | medium |
| `de-hh` | `annual_*`, `immediate_*`, `temperature_air*`, `temperature_soil*`, `ph_value`, `turbidity` | 91 datasets and 25 parameters equal to `de` (`Jahresmelder: Mais`, `Lufttemperatur`, `Trübung`) | Low German words where there are any; `Jahresmelder`/`Sofortmelder` | low |
| `de-hh` | `cooling_degree_*`, `heating_degree*` | `Köhlgradstunnen`, `Heizgraddaag` (parameters) and `Köhlgraadstünn`, `Heizgraaddaag` (datasets) | one spelling of `grad`/`graad` | medium |
| `de-hh` | `snow_depth*`, `water_equivalent*` and the labels with `Snee`/`Snéé`/`Schnee`, `Snééhööchd`/`Snehööch`/`Neeschneehööch` | snow spelt three ways and height `hööch`/`hööchd` | one spelling, `Snee` as the UI has it | medium |
| `fr` | `*loamy_silt*` (soil moisture, evaporation, soil temperature) | `limon argileux` (argileux is clayey) | `limon` | low |
| `fr` | `pressure_vapor`, `pressure_vapor_mean` | `Pression de vapeur` | `Tension de vapeur`, the term of Météo-France | low |
| `es` | `*loamy_silt*` | `limo franco` | `franco limoso`, the name of the texture class | low |
| `es` | `count_days_glaze`, `weather_type_glaze_rime` | `Días con hielo`, `hielo o escarcha`: the same word as `count_days_ice` (`Días de hielo`) | a word for glaze ice that is not `hielo` alone | low |
| `it` | `*loamy_silt*` | `limo argilloso` (argilloso is clayey) | `franco limoso` | low |
| `pl` | `temperature_soil_max_*`, `temperature_soil_min_*` | `Maksymalna temperatura gleby ...` (about 100 labels) next to `Temperatura gruntu` for the other soil temperatures; IMGW says `temperatura gruntu` | one word, `gruntu`, with the covers rephrased (`pod gruntem odkrytym` reads badly after it) | low |
| `pl` | `frozen_ground_layer_*` | `Warstwa zmarzliny` (`zmarzlina` is permafrost) | `Przemarznięta warstwa gruntu` (IMGW: `przemarznięcie gruntu`) | low |
| `pl` | `*loamy_silt*` | `pył gliniasty` | the name from the soil texture classes of PTG | low |
| `pl` | `snow_depth*`, `snow_depth_new*` | `Grubość pokrywy śnieżnej`, `Grubość świeżego śniegu` | IMGW writes `wysokość pokrywy śnieżnej` and `wysokość świeżo spadłego śniegu` | medium |
| `cs` | `*loamy_silt*` (soil moisture, evaporation, soil temperature) | `hlinitá hlína`, `hlinitou hlínou` ("loamy loam") | `prachovitá hlína` | medium |
| `cs` | `phenology_bud_swelling` | `Nalévání pupenů` (`nalévání` is the filling of grain and fruit; it may be ČHMÚ's own name of the phase) | `Bobtnání pupenů` if it is not | low |
| `nl` | `water_equivalent_snow_depth*`, `water_equivalent` | `Sneeuwwatergehalte` next to `Waterequivalent versgevallen sneeuw` | one term | low |
| `da` | `sunshine_duration`, `sunshine_duration_*` | `Solskinstimer` (parameter, dataset) next to `Relativ solskinsvarighed` | `Solskinsvarighed` | low |
| `da` | `phenology_turning_green_beginning`, `phenology_panicle_emergence_beginning`, `phenology_tassel_tip_visible` | `Grønnes` (a verb), `Toplysskridning`, `Toppens spids synlig` | `Grønning, begyndelse`; a word for panicle emergence | low |
| `da` | `*loamy_sand`, `*loamy_silt*` | `leret sand`, `leret silt` (`leret` is clayey) | `lerblandet sand` | low |

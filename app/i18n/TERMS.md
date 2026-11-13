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

| Locale | Station | Parameter | Dataset | Resolution | Period | Provider | Network | Date range | Weather service | Settings | Legal notice |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Source key | `stripes.station` | `dataViewer.statParameter` | `parameterSelection.datasetLabel` | `parameterSelection.resolutionLabel` | `history.periods` | `parameterSelection.providerLabel` | `parameterSelection.networkLabel` | `dateRange.label` | `home.dataProvidersTitle` | `common.settings` | `footer.legal` |
| `en` | Station | Parameter | Dataset | Resolution | Periods | Provider | Network | Date Range | Weather services | Settings | Legal notice |
| `de` | Station | Parameter | Datensatz | Auflösung | Zeiträume | Anbieter | Netzwerk | Zeitraum | Wetterdienste | Einstellungen | Impressum |
| `de-hh` | Station | Parameter | Datensatz | Oplösung | Tietrüüm | Anbeder | Nettwark | Tietruum | Wedderdeenste | Instellungen | Impressum |
| `fr` | Station | Paramètre | Jeu de données | Résolution | Périodes | Fournisseur | Réseau | Plage de dates | Services météorologiques | Réglages | Mentions légales |
| `es` | Estación | Parámetro | Conjunto de datos | Resolución | Periodos | Proveedor | Red | Rango de fechas | Servicios meteorológicos | Ajustes | Aviso legal |
| `it` | Stazione | Parametro | Dataset | Risoluzione | Periodi | Fornitore | Rete | Intervallo di date | Servizi meteorologici | Impostazioni | Note legali |
| `nl` | Station | Parameter | Dataset | Resolutie | Perioden | Aanbieder | Netwerk | Datumbereik | Weerdiensten | Instellingen | Juridische informatie |
| `pl` | Stacja | Parametr | Zbiór danych | Rozdzielczość | Okresy | Dostawca | Sieć | Zakres dat | Służby meteorologiczne | Ustawienia | Nota prawna |
| `cs` | Stanice | Parametr | Datová sada | Rozlišení | Období | Poskytovatel | Síť | Rozsah dat | Meteorologické služby | Nastavení | Právní informace |
| `da` | Station | Parameter | Datasæt | Opløsning | Perioder | Udbyder | Netværk | Datointerval | Vejrtjenester | Indstillinger | Juridisk meddelelse |
| `lb` | Statioun | Parameter | Datesaz | Opléisung | Perioden | Ubidder | Netzwierk | Datumberäich | Wiederdéngschter | Astellungen | Impressum |

## Terms that are different things

- **Settings** (what the user switches in the app: units, names, an interpolation's distances) and
  **parameters** (what is measured) are two words in every locale. French used `Paramètres` for
  both until GH-2610; settings are `Réglages` now (`Réglages avancés`, `Réglages du graphique`,
  `tes réglages de l'application`) and `Paramètres` stays the measured quantity. In the browser's
  own words (`fr` `location.denied`: "les paramètres du site") the browser's name is kept.
- The **legal notice** is `Impressum` in `de`, `de-hh` and `lb` (the German name of the page),
  `Mentions légales`, `Aviso legal`, `Note legali`, `Nota prawna`, `Právní informace` and `Juridisk
  meddelelse` elsewhere; `nl` is `Juridische informatie`, not `Colofon`, which is the imprint a
  publisher prints in a book.
- **Period** is a stretch of time in a station's history (the periods of missing data), and **date
  range** is what the user picks in the date picker. Both are "Zeitraum" in German and `Tietruum` in
  `de-hh` (the period's plural is `Tietrüüm`), where the two collapse; every other locale has two
  words.
- **Resolution** is the interval a value stands for (10 minutes, daily), never the date range.
- **Provider** is the source of the data (DWD, NOAA) and **weather service** is the institution
  behind it: the home page counts weather services, the explorer picks a provider. The
  **operator** of a station, from the station history, is a third thing and is not translated as
  provider (`Betreiber`, `exploitant`, `gestore`, `operator`, `Bedreiwer`, `provozovatel`, ...).
- **Quality flag** is the word each locale settled on for a flag, as in `precipitation_type_flags`;
  `i18n-parity.test.ts` holds a locale to it (Kennung, flag, vlag, indicateur, ...). The quality marks of
  the sources (`quality`, `quality_wind`, ...) are no parameters, are not in `/api/glossary` and have no label.

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
them), as the bare `en` is American. The moment of a forecast run (the Meteogram's run list) is
written by `formatRunTime`, in the language's order ("15.10.2026, 04:00 UTC", "15/10/2026,
04:00 UTC"). The timestamps of a table of data (the history's dates, the data viewer's
`timestamp` column) stay ISO 8601 as the API gives them, since a reader copies them. A label that
is followed by its value takes the colon from `common.colon`, which French sets with a no-break
space before it (`tests/unit/i18n-source.test.ts` holds the source to it, as to a date written out
of its parts and an `Intl` call that names no language). Coordinates and elevations are the
exception to the rule for numbers and keep a point in every language (`toFixed`): a position is
copied into a map or a query, and the number input that takes one reads a point.

Every `Intl`, `toLocale*String` and luxon `setLocale` call is handed the language that
`useFormatLanguage()` answers (named `formatLanguage`), never the app's code (`lb`, `de-hh`) or a
tag read from `localeProperties`: it is the locale's tag (`en-GB`, `de-DE`) through `withData`.
Chrome has no data for Luxembourgish and writes `lb` in the system's language (an English reader
gets `en-US`: numbers "1,234.5", dates month first), so `withData` asks for German (`de-LU`) in
its place, whose order and separators Luxembourgish shares. `de-hh` is written as `de-DE`. The
helpers of `utils/format.ts` take a code or a tag and map it themselves. A time of day is written
by `formatHour` (the Meteogram's axis: "04:00" in German, "04.00" in Danish), in the station's
zone, never built from its parts (`HH:mm`); `tests/unit/i18n-source.test.ts` holds the source to
both.

## Parameter glossaries

The labels of the parameters, resolutions and datasets (`glossary/<locale>.ts`) are held by
`tests/unit/glossary-translations.test.ts` to more than being there and being translated:

- an English label that names a "Maximum", "Minimum" or "Mean" (also "Highest", "Greatest",
  "Strongest"), wherever in the label, is translated with the locale's word for it; the stems are in
  the test and a new locale adds its own;
- one English label has one translation;
- an hour after a number is `h` (`u` in nl, `t` in da), with the English number;
- a soil temperature of a cover or a texture has the word for the soil, and in fr, es and it it opens
  with the words of the plain soil temperature, so that "Maximum soil temperature, grass" is not
  "Maximum temperature, grass" (the other languages put an adjective before the noun, and a
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
  new text in it. Its word for a flag is `Göödkennen`.
  `Datensatz` is kept as Low German shares the word; `Anbeder`, `Nettwark`, `Oplösung` and `Tietruum`
  are the words chosen for provider, network, resolution and date range.

- The informal address of GH-3157, in **all four locales it changed** (`de`, `fr`, `cs`, `lb`): each
  line that spoke to the reader was rewritten by hand and read through, not by a native speaker. Least
  certain: `cs` `support.reportText` (`Našla se chyba?`, chosen to avoid a gendered `Našel jsi`);
  `lb` imperatives of verbs the catalog had not used in the singular (`Kréi` for `kréien` in
  `api.subtitle` and the `api.endpoints.*` lines, `Gëff … an` in `query.placeholder`, `Rechen … ëm` in
  `settings.convertUnitsHint`, `Fro … of` in `query.hint`) and `iwwerlee dir` in `support.donateText`;
  the `lb` and `cs` informal forms in general.

- The thirteen weather words of the forecast's day cards (`meteogram.chart.weather.*`, GH-3186), in all
  four locales. Least certain: `de-hh` `Dunnerwedder`, `Niesregen`, `Newel`, `Deelwies wulkig`,
  `Stoff- oder Sandstorm`, `Sneedrieven`; `lb` `Gewitter`, `Niselreen`, `Deelweis wollekeg`,
  `Schnéigestéber`; `cs` `Polojasno` for "partly cloudy"; `pl` `Zamieć śnieżna`.
  The funnel cloud (`meteogram.chart.weather.funnelCloud`, GH-3965), in all four locales: `de-hh`
  `Trechterwulk`, `lb` `Trechterwollek`, `cs` `Nálevkovitý oblak` (against `Trychtýřovitý oblak`), `pl`
  `Lej kondensacyjny`.

- The footer link to the third-party licences (`footer.licenses`, GH-3469), in all four locales. Least
  certain: `de-hh` `Lizenzen vun annere` and `lb` `Lizenze vun Drëtten` ("licences of others"); `cs`
  `Licence třetích stran` and `pl` `Licencje stron trzecich` are the usual forms of "third-party licences".

- **Machine-made**: the strings of the app's shell and its search (`shell.*`, GH-3518: the skip link, the
  navigation's groups, the search and its command palette, the one-line purposes of the support, legal,
  documentation, GitHub and PyPI entries) were written by a language model (Claude) in **all ten locales
  besides `en`**, `de` included, and no person has read them. Least certain: `de-hh` `Warktüüch` (tools),
  `Naslaan` (reference), `todrapen deist`; `lb` `Instrumenter` (tools), `Noschloen` (reference), `Prognos`;
  `pl` `Informacje` and `cs` `Příručka` for "Reference"; `da` `Udsigt` for a forecast, as the catalog has it.

- **Machine-made**: the strings of "Ask the weather" on the home page (`ask.*`, GH-3518: the four questions, the
  verdicts and the lines under them, the chart captions, the search of a place) were written by a language model
  (Claude) in **all ten locales besides `en`**, `de` included, and no person has read them. Least certain: `de-hh`
  `Fraag dat Weer`, `Oort ännern`; `lb` `Fro d'Wieder`, `Méintlech Mëttelwäerter`; `pl` and `cs` for the verdicts
  of the summer question (`Tak, o {anomaly} °C cieplej`), and in every language the Beaufort wording of the wind
  verdicts (calm, breezy, windy, stormy), which follows no official word list.

- **Machine-made**: the strings of the map tool (`mapTool.*`, `nav.map`, `shell.stationsMap` and `shell.stationOnMap`,
  `seo.pages.map`, GH-3650: the chips, the panel, the cards' notes and links, the about text) were written by a language
  model (Claude) in **all ten locales besides `en`**, `de` included, and no person has read them. Least certain: `de-hh`
  (`Utsicht-Stationen`, `Söök di … ut`, `opmaken`, `Pielentasten`, `Seehööch`); `lb` (`Prognosstatioune`, `Schicht`,
  `Feilen` for the arrow keys, `ewech`); `pl` and `cs` (`Wybrano: {name}` and `Vybráno: {name}` for "chosen", `n.p.m.` and
  `n. m.` for "above sea level"); and in every language the sentence of the about text that explains the keyboard.

- **Machine-made**: the strings that tell a farther station from a nearer one on the map (`mapTool.legend*`,
  `mapTool.whyFarther`, `mapTool.whyFartherNoEnd`, `mapTool.pickCloser`, `mapTool.pickedCentre`,
  `mapTool.pickedPlaceAddress`, `mapTool.pickedStationPlace`, GH-3875) were written by a language model (Claude) in
  **all ten locales besides `en`**, `de` included, and no person has read them. Least certain: `de-hh` (`Meldt nich
  mehr`, `De dichtste Station`, `Dichter bi:` for "closer", `statts`, `Oort`); `lb` (`Zeechenerklärung`,
  `Huet opgehalen`, `Méi no`); `pl` (`Przestała działać`, `Nadal działa`: a station is feminine) and `cs`
  (`Přestala hlásit`), and the case of the station's name after `Położenie stacji` and `Poloha stanice`.

- The partial last day of the forecast's day cards and rows (`meteogram.chart.partialDay`, GH-3840: "partial, {hours} h"),
  written by a language model (Claude) in **all ten locales besides `en`**, `de` included, and read by no person.
  Least certain: `de-hh` `Deeldag`, then `lb` `deelweis` and `cs` `částečně`; `de` `unvollständig` is plain German for
  "incomplete".

- **Machine-made**: the strings of the station picker's toggle and chips (`stationSelection.modeLabel`, `modeList`,
  `modeMap`, `selectedStation`, `removeStation`, `announceList`, GH-3877), written by a language model (Claude) in **all ten locales
  besides `en`**, `de` included, and read by no person. Least certain: `de-hh` `Lieste` for "list" and `wegmaken`;
  `lb` `Lëscht` and `ewechhuelen`; `cs` `Seznam` and `Odebrat {name} z výběru`; `pl` `Usuń {name} z wyboru`; `it`
  `Elenco` against `Lista`; `de-hh` `Stationssöök` and `lb` `Statiounssich` for "Station search".
- **Machine-made**: the sentences every tool shows where its result will be (`toolPlaceholder.*`, `history.noneFound`) and the
  titles of the setup cards (`cardTitle.*`, `parameterSelection.title`, GH-3850) were written by a language model (Claude)
  in **all ten locales besides `en`**, `de` included, and no person has read them. Least certain: `de-hh` `Oort un Tietruum`
  and `Chronik`; `lb` `Plaz a Period` and `Historique`; `pl` `Miejsce i okres`; `cs` `Místo a období`; and in every
  language "Place and period" (the Explorer's card, where an interpolation takes a point and not a station).

- **Machine-made**: the two strings of the "Stored" control of "Use my location" (`location.stored`, the word on the chip, and
  `location.storedLabel`, its accessible name, which opens with that word, GH-4011) were written by a language model (Claude)
  in **all ten locales besides `en`**, `de` included, and no person has read them. Least certain: `de-hh` `Bewahrt` (the note
  says `bewahrt` for "stays in this browser"); `lb` `Gespäichert`; `pl` `Zapisana` and `cs` `Uložená`; and in `fr`, `es`, `it`,
  `pl` and `cs` the feminine (`Mémorisée`, `Guardada`, `Salvata`, `Zapisana`, `Uložená`), which agrees with the language's word
  for the position (`position`, `ubicación`, `posizione`, `lokalizacja`, `poloha`), which the chip leaves out.
- **Machine-made**: the alert of "Use my location" for a browser that refuses to keep the position (`location.notKept`, GH-4014)
  was written by a language model (Claude) in **all ten locales besides `en`**, `de` included, and no person has read it.
  The second sentence names the position again (not "it"), so that it cannot read as the browser. Least certain: `de-hh`
  `verlööft` and `warrt` (the chip says `Bewahrt`, so the verb is `bewahren`; `De Standort` for the masculine article);
  `lb` `erlaabt` and `gëtt just fir`; `cs` `neumožnil` and `Poloha se použije`; `da` `tillod ikke, at`.
- **Machine-made**: the status of "Use my location" for a stored position that was deleted because the browser's permission
  was found withdrawn (`location.withdrawn`, GH-4014) was written by a language model (Claude) in **all ten locales besides
  `en`**, `de` included, and no person has read it. Least certain: `de-hh` `verlööft`, `wegmaakt worrn` and `bewahrte`
  (the chip says `Bewahrt`); `lb` `erlaabt`, `gouf déi gespäichert Positioun geläscht` and `Site`; `cs` `už ... nepovoluje`
  and `smazána`; `da` `tillader ikke længere`; `nl` `staat ... niet meer toe`.
- **Machine-made**: the banner of the provider selection for a backend that could not be reached
  (`parameterSelection.backendUnreachable`, GH-4042) was written by a language model (Claude) in **all ten locales
  besides `en`**, `de` included, and no person has read it. It says "provider" with the locale's word and names no
  one, so it needs no address. Least certain: `de-hh` `weer nich to recken` (the catalog's `utreken` and `ümreken` are "calculate", so `recken` is a guess at
  "reach") and `laat sik … wiesen`; `lb` `war net
  erreechbar` and `ugewise ginn`; `pl` `połączyć z backendem`; `cs` `Backend není dostupný`; `fr` `injoignable` and
  `listés`; and in every language whether "could not be reached" is right for a 5xx, where the backend answered.

Nothing here says the other locales (`en`, `de`, `fr`, `es`, `it`, `nl`, `da`) were reviewed by a
native speaker either; these four are the ones known not to have been.

## Open: waits for a native speaker

Not decided here, and the text is left as it is. The review table with the proposals is in the pull
request that added this file, and the issue it belongs to is
[GH-2610](https://github.com/earthobservations/wetterdienst/issues/2610).

- `nl`: `waarneming` (glossary, one label) and `observatie` (the UI) are both used for "observation".

The third pass of GH-2610 read the strings added since the second one (the `ask.*`, `mapTool.*`,
`shell.*`, `location.*` and `settings.*` texts, those of #3459 in `pl`, `cs`, `lb` and `de-hh`) and
the glossaries once more, against `en`, this file and the other texts of the same catalog. It
changed only what is wrong by the evidence of the catalog itself (a typo, a case or preposition
that is wrong, a text that drops what `en` says, a word spelt differently in the same file or the
glossary, a term of this file); the rest is in the tables below.

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
| `fr` | `ask.rain.chance` | `Plus forte probabilité de pluie sur une heure : {chance}.` ("over one hour") | `pour une heure donnée` ("in any hour") | medium |
| `fr` | `meteogram.chart.weather.blowingSnow`, glossary `weather_type_blowing_drifting_snow` | `Poudrerie` (UI, the Canadian term) next to `chasse-neige` (glossary) | one word; Météo-France writes `chasse-neige`, which alone also means a snowplough | low |
| `fr` | `meteogram.chart.weather.sleet` | `Pluie et neige` | `Pluie et neige mêlées` (Météo-France) or `Neige fondue` (the glossary) | low |
| `es` | `ask.placePlaceholder`, `ask.placeHint` | `pueblo` (village) where en says "town" | `localidad` | medium |
| `es` | `settings.bar.hint` | `la barra del pie de la pantalla` | `la barra inferior de la pantalla` | medium |
| `es` | `ask.rain.chance` | `Mayor probabilidad de lluvia en una hora` ("within one hour") | `en una hora cualquiera` | low |
| `es` | `settings.bar.hint`, `settings.bar.instructions`, `settings.bar.instructionsHeader` | `por su asa` for a drag handle | the control's usual UI term (`por el control de arrastre`) | low |
| `it` | `ask.rain.chance` | `Probabilità di pioggia più alta in un'ora` ("within one hour") | `in una singola ora` | low |
| `it` | `meteogram.chart.weather.sleet`, `meteogram.chart.weather.clear`, `ask.wind.calm` | `Nevischio` (light dry snow), `Soleggiato`, `Calmo` | `Pioggia mista a neve`, `Sereno` (Aeronautica Militare), `Calma` (the Beaufort word) | low |
| `pl` | `ask.wind.context` | `Dni wokół z silniejszymi porywami` | `Pobliskie dni z silniejszymi porywami` | low |
| `pl` | `stripes.table.note.temperature`, `stripes.table.note.precipitation` | `w piątych częściach` ("in fifths") | a clearer phrase, for example `w pięciu klasach` | low |
| `cs` | `ask.q.summer` | `Bylo poslední léto tady teplejší než obvykle?` (reads as "the final summer") | `Bylo minulé léto tady teplejší než obvykle?` | medium |
| `lb` | `seo.pages.explorer` | `liest d'Miessungen` (third person) | `lies d'Miessungen` (the singular imperative, as the other verbs of the sentence); `luet` in `home.featureExportDesc` is the same form | high that it is the third person |
| `lb` | `providers.attribution` | `Quellenangab` (German) | `Quell, déi du uginn muss` | medium |
| `lb` | `ask.placeSearching`, `ask.placeFailed`, against the other `ask.place*` and `api.endpoints.interpolate` | `Plaze` and `Uert` for "place" on the same page | one word (`Uert`, plural `Uerter`, or `Plaz`) throughout | medium |
| `lb` | `explorer.tip1` | `verständlech` ("understandable") where en says "reasonable" | `vernünfteg` | medium |
| `lb` | `meteogram.chart.weather.drizzle`, `meteogram.chart.weather.blowingSnow` | `Niselreen`, `Schnéigestéber` | `Sprëtzreen`, `Schnéidreiwen` as the glossary has them | low |
| `lb` | `meteogram.aboutText2`, `meteogram.chart.axisPrecip`, against `seo.pages.meteogram`, `seo.pages.stripes` and the glossary (about 90 labels) | `Néierschlag` and `Nidderschlag` both | one spelling | medium |
| `de` | `mapTool.about1`, `mapTool.about2` | `das Feld daneben`, `Das Feld zeigt` (reads as an input field) | `Bereich`, as `meteogram.chart.panels` has it | medium |
| `de` | `ask.placeLabel` | `Gefragt für` | `Frage zu` | medium |
| `de` | `location.note` | `... bleibt er in diesem Browser gespeichert` (`er` has no antecedent) | name the Standort in the first sentence | low |
| `de-hh` | `dataViewer.limitNarrow`, `limitNarrowPoint`, `limitStationsBody`, `mapTool.pickedCentre` | `Wähl`, `utwählt` (German forms) next to `utsöcht` | `Söök ... ut` and `utsöcht` throughout | medium |
| `de-hh` | `ask.summer.usual` | `Nich würklich: so warm as anners.` | add the "about" of en (`ungefähr`, `rund`) | medium |
| `de-hh` | `location.*`, `footer.privacy`, `location.privacyLink` | `Standort`, `ungefähr`, `Datenschutz`, `Rückt` (German words) | Low German words where there are any (`Standoort`/`Städ`, `rund`) | low |
| `de-hh` | `mapTool.count`, `shell.results`, `mapTool.results` | `Wiest Stationen: {shown}`; `Resultaten` next to `Ergebnisse` in the older texts | a participle (`Stationen wiest`); one word for "results" | low |
| `nl` | `location.denied` | `Om haar toe te staan` | `Om dit toe te staan` | medium |
| `nl` | `mapTool.legendStopped` | `Is gestopt` | `Meldt niet meer`, to pair with `Meldt nog` | medium |
| `nl` | `seo.title`, `seo.description`, `seo.noscript`, `seo.pages.providers` | `data` (the catalog says `gegevens` 51 times) | `gegevens` | low |
| `da` | `ask.wind.context` | `Dage omkring med kraftigere vindstød` | `Omkringliggende dage med kraftigere vindstød` | medium |
| `da` | `ask.placeFailed` | `Stederne kunne ikke søges.` | `Der kunne ikke søges efter steder.` | medium |
| `da` | `mapTool.legendStopped` | `Er stoppet` | `Måler ikke længere`, to pair with `Måler stadig` | medium |
| `de-hh` | `location.denied`, `location.timeout`, `location.lookupFailed`, against `stationSelection.loadError`, `map.markersNotShown` | `noch mal` (3 texts) and `noch eenmal` (3 texts), the same number in the catalog | one form | low |
| `de-hh` | `ask.rain.wettest`, `stripes.table.note.precipitation` | `Natteste` (1) and `natste` (1) | one form of the superlative | low |
| `de-hh` | `meteogram.chart.weather.drizzle` | `Meddelregen`, as the glossary has it (5 labels) | `Niesregen` was the text before the third pass; one word for drizzle | low |
| `de-hh` | `location.unsupported`, `location.unavailable` | `stattdessen` (German); `statts` is a preposition in this file (`mapTool.pickCloser`) | an adverb of Low German for "instead" | low |
| `lb` | `seo.pages.glossary`, `glossary.subtitle` | `mierkt` and `mëst` for "what a parameter measures" | the 3rd person of `miessen` is `mësst`; which form, and whether `mierkt` is right at all | low |
| `lb` | `explorer.modeSummaryDesc`, `mapTool.about1`, `history.about3` | `gemoossene`, `moossen`, `gemoosse`, `Moossmethoden`, `Moossregëster`, where the rest of the catalog writes `Miessung`, `Miesswäert` | the `Miess-` stem throughout | medium |

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
| `cs` | `*loamy_silt*` (soil moisture, evaporation, soil temperature) | `hlinitá hlína` ("loamy loam") | `prachovitá hlína` | medium |
| `cs` | `phenology_bud_swelling` | `Nalévání pupenů` (`nalévání` is the filling of grain and fruit; it may be ČHMÚ's own name of the phase) | `Bobtnání pupenů` if it is not | low |
| `nl` | `water_equivalent_snow_depth*`, `water_equivalent` | `Sneeuwwatergehalte` next to `Waterequivalent versgevallen sneeuw` | one term | low |
| `da` | `sunshine_duration`, `sunshine_duration_*` | `Solskinstimer` (parameter, dataset) next to `Relativ solskinsvarighed` | `Solskinsvarighed` | low |
| `da` | `phenology_turning_green_beginning`, `phenology_panicle_emergence_beginning`, `phenology_tassel_tip_visible` | `Grønnes` (a verb), `Toplysskridning`, `Toppens spids synlig` | `Grønning, begyndelse`; a word for panicle emergence | low |
| `da` | `*loamy_sand`, `*loamy_silt*` | `leret sand`, `leret silt` (`leret` is clayey) | `lerblandet sand` | low |
| `fr` | `weather_type_blowing_drifting_snow` | `chasse-neige` next to the UI `Poudrerie` | see the UI row | low |
| `it` | `phenology_planting_beginning` | `Trapianto, inizio` (transplanting) | `Messa a dimora, inizio` | low |
| `pl` | `weather_type_*` | `Typ pogody`, where `precipitation_form` is `Rodzaj opadu` and `cloud_type` `Rodzaj chmur` | `Rodzaj` or `Typ` throughout | low |
| `cs` | `temperature_wind_chill` | `Pocitová teplota větrem` | `Pocitová teplota (wind chill)` | low |
| `lb` | `discharge_*`, `precipitation_amount_max*`, `weather_type_heavy_fog`, `weather_type_ice_fog_freezing_fog`, `snow_depth_max`, `snow_depth_new_max`, `frozen_ground_layer_thickness_max_month` | `Maximalen Ofloss`, `Mëttleren Ofloss`, `Héchsten Nidderschlag`, `dichten Niwwel`, `Gréisste Schnéihéicht`, `Gréissten Frostschichtdicht` | the file's own pattern: masculine `-e` (`Maximale Ofloss`, `Héchste Nidderschlag`, `dichte Niwwel`), feminine no ending (`Gréisst Schnéihéicht`) | medium |
| `lb` | `tassel_tip_visible` | `Fändelschéiwen, Ufank` | `Spëtz vum Fändel ze gesinn` | low |
| `lb` | `evapotranspiration_last_24h`, `evapotranspiration_potential_*` | `Verdonstung`, `Potenziell Verdonstung` (the label of `evaporation_amount`) | a word of its own for evapotranspiration | low |
| `de` | `precipitation_amount`, `precipitation_amount_max`, `precipitation_amount_max_30min` | `Niederschlagsmenge` | `Niederschlagshöhe`, DWD's term, as the other precipitation labels | low |
| `de, nl, da` | `cloud_height_layer1` | `Wolkenuntergrenze (1. Schicht)`, `Wolkenbasis (1e laag)`, `Skybase (1. lag)`; the "(1st layer)" form of en | the form of layers 2 to 4 (`..., Schicht 1`, `..., laag 1`) | low |
| `de-hh` | `humidity_relative*`, `humidity_absolute`, `temperature_wet*`, `moisture` | `Luftfuchtigkeit`, `Fuchttemperatur`, `Fuchtigkeit` | one spelling next to `Füchtigkeit` of the other labels | low |
| `nl` | `probability_precipitation_freezing_last_*h` | `Kans op ijzel` (freezing rain only; en says freezing precipitation) | `Kans op onderkoelde neerslag` | medium |
| `nl` | `pressure_vapor`, `pressure_vapor_mean` | `Dampdruk` | `Dampspanning`, the term of KNMI | low |
| `da` | `temperature_air_mean_2m`, `temperature_air_mean_minmax_2m` | `Middellufttemperatur` next to `Gennemsnitlig` in 40 labels | one word for "mean" (`Gennemsnitlig`; `Middelvandføring` is a hydrology term and stays) | medium |
| `da` | `weather_type_blowing_spray`, `annual_autumn_crocus`, `urban_*` | `fygende havskum` (sea foam), `Høst-tidløs`, `Byens nedbør` | `fygende søsprøjt`, `Høsttidløs`, `Nedbør i byområder` | low |

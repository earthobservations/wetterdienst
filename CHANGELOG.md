# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Types of changes:

- `Added` for new features.
- `Changed` for changes in existing functionality.
- `Deprecated` for soon-to-be removed features.
- `Removed` for now removed features.
- `Fixed` for any bug fixes.
- `Security` in case of vulnerabilities.

## [Unreleased]

### Added

- DWD: new `phenology` network (`dwd/phenology`) covering the DWD phenological observation
  network -- the day of the year on which a plant reached a developmental phase, at `annual`
  resolution, reaching back to 1925. 110 datasets, one per plant and reporter group
  (`annual_common_hazel`, `immediate_winter_wheat`, ...), each carrying the phenological phases
  that plant is observed for as parameters (`phenology_flowering_beginning`,
  `phenology_leaf_unfolding_beginning`, `phenology_harvest`, ...). A value is DWD's `Jultag`, the
  day of the year, dated to the 1st of January of the reference year, so the entry date is that
  date plus the value. Both reporter groups are covered -- the ~6600-station *Jahresmelder* and
  the ~1200-station *Sofortmelder* -- with their own station catalogues

### Fixed

- Network: the fsspec listings cache silently never hit for `CacheExpiry.INFINITE`. The expiry
  reaches `FileDirCache` as `False`, which diskcache read as an expiry of `now + False == now`, so
  every entry was stored already expired and each listing was refetched. Falsy expiries now mean
  "never expire", matching what the download-side cache has always done with `INFINITE`
- Network: `FileDirCache` could not be unpickled -- its `__reduce__` passed three positional
  arguments to an `__init__` that takes one positional plus keyword-only arguments, and in the
  wrong order
- Network: a listing whose TTL lapsed between fsspec's `in dircache` probe and the following
  lookup raised a `KeyError` out of `ls()`/`find()`. The dircache is now read with a single
  lookup, which also stops a `detail=False` call from caching a name-only listing that later
  `detail=True` reads would receive
- Network: `download_file()` raised `AttributeError: 'NoneType' object has no attribute 'get'`
  when `client_kwargs` was left at its `None` default
- Network: a float timeout in `fsspec_client_kwargs` (e.g. `WD_FSSPEC_CLIENT_KWARGS='{"timeout": 30.5}'`)
  reached aiohttp unwrapped and failed every request with `ValueError: timeout parameter cannot be of
  <class 'float'> type`; only int timeouts were being wrapped in `ClientTimeout`
- Network: a disabled listings cache created (and `mkdir`-ed) a cache directory named `False`,
  `0.0` or `0.01` that nothing readable was ever written to. Those folders are no longer created,
  and any left behind by an earlier version are swept from the cache directory on the next run --
  guarded so that a folder still holding valid entries is kept
- DWD observation: the `climate_urban` URL was pinned to the `recent` directory whatever period was
  requested, so a `now` request for a 10-minute urban dataset was answered with `recent` data ending
  at the previous midnight, and `historical` -- reaching back to each station's first year, 2015 for
  Berlin-Alexanderplatz -- could not be read at all. The 10-minute urban datasets carry a directory
  per period like the non-urban ones, so the requested period now reaches the URL. The hourly urban
  datasets are unchanged: DWD publishes a single `recent` directory for them that already holds the
  full record, and every period keeps mapping onto it
- DWD observation: `describe_fields()` raised an opaque `.item()` length error for the 10-minute
  urban datasets, for which DWD publishes no description PDF at all; it now names the dataset,
  period and URL it looked at
- DWD observation: station `history` returned nothing for the 10-minute urban datasets. It looked
  for them under a `meta_data` directory that only the non-urban high resolutions have, while the
  urban zips carry their `Metadaten_*.txt` files themselves
- DWD observation: where two periods reported the same timestamp, which record survived was decided
  by neither of the two things that should decide it. The periods were read in the iteration order
  of a set, varying from one interpreter run to the next, and the deduplication then ran over a
  frame that `how="align"` had already reordered by value -- so the surviving record was the lower
  reading, or a null wherever one period was missing a measurement the other had. Values now settle
  on the quality-marked historical record, carried through the concatenation as an explicit rank,
  and stations settle on their most current description. This is visible for the first time on the
  10-minute urban datasets, whose three periods used to resolve to the same directory

## [0.134.0] - 2026-08-22

### Added

- Add the DWD climate indices as four datasets: `annual`/`climate_indices` and
  `monthly`/`climate_indices` count tropical nights and frost, summer, hot and ice days, while
  `annual`/`precipitation_indices` and `monthly`/`precipitation_indices` count the days reaching
  precipitation heights of 0.1 to 20 mm and snow depths of 1 and 5 cm. DWD derives them from the
  daily observations of the same stations and publishes them in the familiar CDC layout, so they
  arrive as metadata alone. Twelve canonical parameters are new with them, named for the index the
  literature knows (`count_days_frost`, `count_days_tropical_night`) rather than for its threshold,
  which the description carries instead
- The two interpolation search radii are settings of their own:
  `ts_geo_station_distance_homogeneous` (40 km, for a quantity that varies slowly across a region,
  such as air temperature) and `ts_geo_station_distance_heterogeneous` (20 km, for one that
  decorrelates within a few tens of kilometres, such as precipitation). They were module constants,
  so widening the search for everything meant naming all 514 parameters individually in
  `ts_geo_station_distance`, which keeps its role as the per-parameter override. The CLI takes
  them as `--interpolation_station_distance_homogeneous` and `--…_heterogeneous` (`--summary_…`
  for `summarize`) and the REST API as query parameters of the same names. A radius that is not
  given is left out rather than passed as the library default, so a server configured through
  `WD_TS_GEO_STATION_DISTANCE_*` keeps its own
- `wetterdienst summarize` reaches the settings that `interpolate` always could:
  `--summary_station_distance` and `--use_nearby_station_distance` had no command options at all,
  so the summary CLI always ran with the defaults

### Changed

- An NWS request asks the observations endpoint for its own window. The endpoint answers an
  unqualified request with its whole retention -- a rolling week of some 180 readings, close to a
  megabyte -- however little of it was wanted, and the frame was trimmed to the request only after
  it arrived. It clips a window to what it still holds rather than refusing one that reaches
  further back, so the readings are the same and a request for one day now downloads one day
- **Breaking**: `skip_empty` works through the CLI and the REST API. Neither surface ever set
  `ts_complete`, and `ts_skip_empty` was silently switched off wherever it was not, so
  `--skip_empty`, `--skip_threshold` and `--skip_criteria` -- and the three REST parameters of the
  same names -- did nothing at all, and `filter_by_rank` never skipped a station over its coverage
  the way it is documented to. The option now stands on its own: it needs neither a gridded frame
  nor `ts_drop_nulls=False`, and their log lines are gone with it. A CLI or REST request that
  passes `--skip_empty` starts skipping stations it used to return
- A station's coverage is the share of the readings the requested window can hold at the
  parameter's resolution that the station delivered, counted from the window and the resolution
  rather than by measuring a frame that had been reindexed onto a grid first. The denominator is
  the same one `ts_complete` produced, so a request that already set both settings keeps its
  answers, with two departures: a reading that does not land on the resolution's grid now counts
  as delivered rather than being dropped and counted as missing, and a request that names no
  window is measured against the span of the station's own series for the dataset in question
  instead of being called fully covered whatever it holds. Readings are counted by the grid slot
  they fall in rather than one by one, so a station reporting more often than the resolution it is
  listed under cannot cover a window twice over and read as complete while half of it holds
  nothing. `subdaily` is measured on what came back instead: it is a bucket rather than an
  interval, and its two providers disagree on one -- DWD takes three Termin readings a day where
  Meteo-France SYNOP reports every three hours -- so counting either as the interval would judge
  the other three times too harshly. A parameter is matched to its metadata case-insensitively, so
  a provider emitting its own casing -- WSV reports `w` where its metadata declares `W` -- is no
  longer read as having sent nothing
- **Breaking**: Eaufrance Hubeau reports under the interval each station transmits at, so its
  single `dynamic` resolution is replaced by `5_minutes`, `6_minutes`, `10_minutes`, `15_minutes`
  and `hourly`, and a request for `dynamic/data/...` no longer resolves. Hubeau publishes the
  interval nowhere -- not in the station referential, not on the observations, and the v2 API
  defines no field for one -- so unlike Pegelonline's declared `equidistance` it is measured from
  the timestamps a station has just published. The network does transmit on a grid: of 3018
  stations reporting over six hours, 2987 resolved to one of the five intervals (5 min for 1643 of
  them, 10 for 903, 15 for 251, 60 for 120, 6 for 33), and re-measuring a 45-station sample over
  48 hours named all 45 the same way. Two hours of the whole network are read at the station list,
  which names every station transmitting at least every fifteen minutes, and the slower and quieter
  ones are then asked about by name over a longer window. A station that has published nothing to
  measure is listed under no resolution rather than under a guessed one, and returns as soon as it
  transmits again; so is one transmitting every 20 or 30 minutes, which no resolution covers, and
  that is reported once. In exchange the interpolation search radius scales by resolution rather
  than falling back to a factor of 1.0, and a station's coverage is measured against the interval
  it actually transmits at. `Resolution.DYNAMIC` goes with it, and with it `ResolutionType`, which
  existed only to spell that one member
- **Breaking**: WSV Pegelonline reports under the interval it actually records at, so its single
  `dynamic` resolution is replaced by `1_minute`, `5_minutes`, `10_minutes`, `15_minutes` and
  `hourly`, and a request for `dynamic/data/...` no longer resolves. Pegelonline publishes an
  `equidistance` on every timeseries in the station listing the provider already downloads, so the
  interval was never something that had to be guessed -- it was simply not read. Each station is
  listed under the resolution it records the requested parameters at, and the 77 of 787 stations
  that record different parameters at different intervals (Passau reads stage every 15 minutes and
  air temperature every 60) appear under each, serving only the parameters that belong there. To
  find a station's resolution, request the parameter at every interval that could carry it and read
  the `resolution` column of the station list. In exchange the interpolation search radius scales
  by resolution like every other provider's rather than falling back to a factor of 1.0, and a
  station's coverage is measured against the interval it actually records at
- **Breaking**: the heterogeneous search radius follows the resolution of the request, so an
  interpolation or summary that already worked returns different values without anything being
  changed by hand: daily precipitation is drawn from 40 km rather than 20, `minute_10` from 15 km
  rather than 20. A quantity that decorrelates fast in space does so less the longer it is
  accumulated -- gauge studies put the correlation length of precipitation at roughly 8 km over ten
  minutes, 27 km over three hours and 33 to 94 km over a day -- and one radius cannot serve both
  ends of that. The factors are `ts_geo_station_distance_resolution_factors`: 0.75 for the minute
  resolutions, 1.0 hourly, 1.5 for `6_hour` and `subdaily`, and 2.0 from daily upwards. Resolutions
  left out keep their factor, every factor set to 1.0 turns the scaling off, and the factors
  multiply whatever `ts_geo_station_distance_heterogeneous` says, so raising that setting moves
  every resolution with it. The table stops at 2.0 rather than following the correlation length up:
  past a day what binds is terrain and not correlation, since the interpolation reads UTM x/y and
  never station height, so 40 km is as far as it may reach -- the same bound the homogeneous radius
  is held to, which is why the two meet at `daily` with the defaults. Precipitation is more
  orographically driven than temperature, not less, so it does not get to reach farther. The
  homogeneous radius does not scale at all, and a radius written out per parameter in
  `ts_geo_station_distance` is used exactly as given, at every resolution. The fine end stops short
  of the 8 km the literature gives, since interpolation needs four surrounding stations and even
  the DWD network rarely has four rain gauges that close -- in a sparse network 15 km may leave a
  request that used to answer with nothing, and raising the factor for that resolution brings it
  back. `summarize` scales too: nothing is blended there, but how far away a measurement still says
  something about the target point is the same question, and it depends on the accumulation period
- **Breaking**: the `"default"` key of `ts_geo_station_distance` is gone, in favour of the two
  radii settings above. It was undocumented and did more than it said: it rebuilt the mapping
  around the given number and so replaced the shorter radius of every heterogeneous parameter
  along with the fallback, giving `{"default": 30}` precipitation, fresh snow and visibility 30 km
  as well. Setting it now raises and names its replacements

### Removed

- **Breaking**: the `ts_complete` setting is gone. It reindexed a series onto the grid its
  resolution implies, spelling every gap out as a null row, and it cost a materialized timestamp
  per reading of the window, a station-local-to-UTC window conversion, and a three-way interlock
  with `ts_drop_nulls` and `ts_shape` that had to be spelled out in three log lines before a
  request could say what it did. The join it built was exact, so a station reporting off the grid
  -- an hourly gauge at seven minutes past, which is how a good third of Hubeau's hourly stations
  report -- came back as a column of nulls; that was worth a warning last release and is not worth
  keeping now. A caller who wants the grid can build it in a few lines of polars over the frame
  they were returned, where the phase is theirs to choose. Nothing in the CLI, the REST API or the
  app ever set it
- **Breaking**: `MetadataModel.timezone_data` is gone, and with it the `timezone_data` key all
  29 providers declared. It named the zone a provider's own `date` labels are stamped in, and
  `ts_complete` was the only thing that ever read it -- to decide which zone to build its grid in.
  The `"dynamic"` value, which meant "read the zone off the station's coordinates" and which NOAA
  GHCN and Hubeau declared, goes with the field; the lookup behind it stays, since ECCC and GHCN
  call it directly while parsing. `metadata.timezone`, the provider's civil timezone, is a
  different field and remains -- DWD reads it to work out which period a request needs. Every
  `date` a request returns is UTC either way, which is what left the field with nothing to say

### Fixed

- The NWS station list holds three American stations it used to leave out, and stops excluding
  American ground for being in the wrong hemisphere. Barking Sands on Kauai and the two US Virgin
  Islands airports are filed by MADIS under a state code rather than a country code, so the
  country column missed them; they are named one by one, because that column cannot be read as a
  state code in general -- `PR` in it is Peru and `GU` is Guatemala, and of its four `VI` rows two
  are American and two are British. All three report, returning 257, 165 and 185 observations over
  the endpoint's rolling week. The list was also narrowed to `longitude < 0 and latitude > 0` on
  top of the country column, which is not where the United States ends: the Aleutians west of
  Amchitka lie beyond the antimeridian, Pago Pago below the equator, and Tinian east of the prime
  meridian. That box is gone, since it decided nationality by hemisphere; the six rows it dropped
  are listed again, but as a correction to the filter and not as data recovered -- of the six,
  Shemya and Pago Pago are stations api.weather.gov knows and both are silent at present, and the
  other four (three duplicate Amchitka rows and Tinian) are not stations it knows at all. That is
  the character of this station list rather than of these six: it is the MADIS METAR table used as
  a proxy, and about a third of what it lists returns nothing. The box guarded nothing else --
  every station MADIS files under the United States carries a usable coordinate pair
- An NWS station of unknown elevation reads as null rather than as standing 9999 m up. MADIS
  writes a missing elevation as 9999 and it was cast to a float and passed on unread, for 31 of
  the 3120 stations -- and height is what interpolation weighs a neighbouring station by
- An NWS request no longer rewrites the settings every other request shares. It stamped its own
  headers onto `Settings.fsspec_client_kwargs` in `__post_init__`, replacing the User-Agent
  wetterdienst builds from its version with a literal `wetterdienst/0.48.0` and adding a
  `Content-Type` that no GET has a use for -- so a DWD request made after an NWS one went out under
  NWS's headers, naming a version eighty-five releases old. api.weather.gov accepts the ordinary
  User-Agent, and the override is gone rather than corrected
- Eaufrance Hubeau serves the overseas departments. Metropolitan station codes begin with the
  letter of their hydrographic basin and the codes of Guadeloupe, Martinique, Guyane, La Réunion
  and Mayotte begin with a digit, and the station list kept only the codes beginning with a letter
  -- excluding all 176 overseas gauges, 86 of them transmitting, for no reason the filter recorded.
  Every station code the referential publishes is well formed, so the filter guarded nothing
- Eaufrance Hubeau lists every station it has rather than the first thousand. The station
  referential answers with a page of 1000 of its 4150 stations and a cursor to the rest, and the
  query named no page size and followed no cursor, so three quarters of the French gauges were
  missing from the station list and unreachable through it -- including by `filter_by_station_id`,
  which filters against that list
- **Breaking**: `ts_shape="wide"` puts one timestamp of one resolution in a row, and stops filling
  rows with values that belong to another. The row used to be keyed on the dataset as well while
  the parameters were joined on the date alone, so a request spanning two datasets emitted every
  timestamp once per dataset and filled all of those rows with all of the datasets' values -- the
  `precipitation_more` row of a `climate_summary` + `precipitation_more` request reported
  `climate_summary_rsk`, and the two rows were identical but for the label. Datasets recorded at
  one resolution share their timestamps and now share a row, which is what the dataset-name column
  prefix was always for; `dataset` is null in that row, since no single name describes it, and
  still carries the name wherever a resolution holds a single dataset.
  Resolutions still get their own rows, because a 15-minute series and an hourly one do not have
  the same timestamps to begin with. The parameter joins are also outer rather than inner, so a
  parameter with no reading at a timestamp leaves a null instead of removing the timestamp from
  the frame: chained inner joins had reduced the result to the timestamps every requested
  parameter happened to share, dropping readings that were asked for and downloaded
- Values of two resolutions are sorted apart in both shapes. The row order was `dataset`,
  `parameter`, `date`, so an hourly and a 10-minute precipitation series -- one dataset name, one
  parameter name -- came back shuffled into each other, one hourly row every six 10-minute ones.
  Resolution leads the sort now, in the long shape as in the wide one
- A Zarr export names its group for what the whole frame holds rather than for whatever its first
  row happens to say: the dataset names present, or the resolutions when a wide row spanning
  several datasets carries no dataset name at all. A frame of two datasets used to be filed under
  whichever of them came first, and one merging them would have gone to the store root, where
  `mode="w"` clobbers every other group already in it
- `ts_geo_station_distance` validates what it is given. A key that is not a canonical parameter is
  rejected rather than kept and never read -- a typo silently left the parameter the user meant at
  its default radius, indistinguishable from having set nothing -- and a negative distance is
  rejected as it already is for `ts_geo_use_nearby_station_distance` next to it. A radius set for a
  parameter that is never interpolated is a warning, since the name is real but nothing reads it.
  The CLI and the REST API report the rejection as a bad parameter and a 400 rather than a
  traceback -- for `interpolate` and `summarize` that now covers every option they validate, such
  as a negative distance, which used to end in a pydantic stack trace
- Settings round-trip through `model_dump()` faithfully: `ts_geo_station_distance` serializes the
  overrides it was given rather than the mapping they were expanded into. Dumping the expansion
  made every heterogeneous parameter come back as an explicit override, which then won over a
  `ts_geo_station_distance_heterogeneous` set alongside it. The expansion is idempotent for the
  same reason -- `TimeseriesRequest` re-validates the settings it is handed, which used to take
  the already-expanded mapping for what the user had written
- Docs: `ts_geo_min_gain_of_value_pairs` is documented with its actual default of 0.1, not 1.2
- `poe docs` builds the documentation again. It ran `make html` in `docs/`, which holds no
  Makefile, so it had failed with "No rule to make target" for as long as that file has been gone.
  It runs sphinx against `docs/conf.py` now, which is what Read the Docs does, and `poe docs:clean`
  removes the build directory

## [0.133.0] - 2026-08-19

### Added

- Every parameter of every provider now carries a description, 1681 of 1681, closing the last 508
  gaps. 271 come from the source itself: MeteoSwiss publishes `ogd-smn_meta_parameters.csv` beside
  the data, MET Norway has a Frost `/elements` endpoint, KNMI writes a `long_name` on every NetCDF
  variable, FMI has an `observableProperty` metadata endpoint, and AEMET and SMHI describe their
  fields in the payloads and listings they already serve (translated here from Spanish and
  Swedish). The remaining 237 are the canonical sentence for the quantity, kept apart in
  `DERIVED_DESCRIPTIONS` so generated text is never mistaken for a source's own wording. Sibling
  prose is now borrowed only within a provider, never across: another source's specifics ("within
  the last 12 hours") need not hold for the one borrowing them
- The provider docs tables carry a `description` column for the 46 pages that had none, and 41 rows
  for parameters that were declared but never listed at all
- `GET /api/version` reports `mcp_enabled` alongside the version. The MCP endpoint sits behind the
  optional `[mcp]` extra, so whether `/mcp` exists is a property of the installation, and a client
  had no way to find out short of probing `/mcp` -- which on the streamable-HTTP transport means
  opening a session rather than asking a question. The index page has always known (it prints the
  endpoint only when mounted); this exposes the same flag over JSON
- 216 more parameters can be interpolated and summarized, 343 of 514 rather than 127. Soil
  temperature under a named cover and depth (114, NOAA GHCNd), forecast probabilities (65, MOSMIX
  and DMO), soil moisture (12, DWD's agrometeorological model), evaporation per crop and soil (6),
  concrete slab temperature (3), humidex and mean radiant temperature, cloud cover in a fixed
  height band, climatological normals, and — at the shorter radius — precipitation intensity and
  visibility. The classification was never about the data being unavailable, only about which names
  had been written into the list by hand. What stays out stays out on purpose: coded observations,
  quality flags, counts, quantities tied to one body of water, a station's own measurement errors,
  directions, which cannot be averaged linearly at all, and the 14 GHCNd soil temperatures whose
  surface cover is recorded as `unknown` — the rest of that family qualifies because the cover is
  part of the name, which is precisely what an unrecorded cover does not give you.
  One cost to know about: `interpolate()` and `summarize()` stop querying stations once *every*
  requested parameter has enough of them, so a whole-dataset request against MOSMIX or DMO now has
  65 probabilities to satisfy and will walk further down the station ranking than it used to.
  Requesting the parameters you actually want keeps it where it was
- DWD hourly solar `true_local_time_offset` (`mess_datum_woz`), a new canonical parameter holding
  how far true local solar time runs ahead of a record's timestamp -- the longitude correction plus
  the equation of time. Solar records are stamped with the UTC instant of a whole true-solar-time
  hour, so the correction sits in the minutes of that timestamp, which wetterdienst rounds to the
  hour so a solar series lines up with every other hourly series. The rounding discarded it and the
  column that also held it was dropped, so it was not reachable at all. At station 00183 it runs 40
  to 71 minutes, its monthly mean tracing the equation of time from 40.4 in February to 69.1 in
  November about a 54.7 minute longitude term
- DWD's two measurement method indicators are returned instead of dropped:
  `cloud_cover_total_measurement_method` (`v_n_i`, hourly cloud_type and cloudiness) and
  `visibility_range_measurement_method` (`v_vv_i`, hourly visibility). DWD writes them as letters
  -- `P` for a human person, `I` for an instrument -- in files that are otherwise numeric, and the
  value column is Float64, so both were declared but silently dropped and a request for them
  returned an empty frame. They are now decoded to 1 for `P` and 2 for `I`. The digits are
  wetterdienst's, not DWD's: they follow the order DWD lists the letters in, and 0 is left unused
  so "not measured" stays distinguishable from either method
- Every DWD parameter now carries a description, 717 of 717 across observation, mosmix, dmo,
  derived, road and swsmos. 25 came from correcting the docs (below), the rest are derived: where a
  source publishes no prose at all, the text is taken from the same canonical parameter at the same
  resolution elsewhere -- the same quantity over the same interval, so the wording transfers -- or
  from the canonical sentence. Those sit in `DERIVED_DESCRIPTIONS`, apart from
  `SOURCE_DESCRIPTIONS` and applied only where nothing else supplies one, so a derived sentence is
  never mistaken for a source's own wording
- Dataset and resolution descriptions on the metadata models: 88 of 148 datasets and 2 resolutions,
  lifted out of the provider docs metadata tables the same way the parameter descriptions were.
  `DatasetModel.description` and `ResolutionModel.description` had been declared but never
  populated, so `metadata["hourly"]["data"].description` returned `None` for every provider.
  `tests/test_docs.py` checks the tables still agree with the model, ignoring the trailing
  `([details](url))` pointer the pages add, which is page formatting rather than description
- Source descriptions for 1057 parameters, in `metadata.source_descriptions` and reported by
  `discover()` -- so by `GET /api/coverage`, the `coverage` MCP tool and `wetterdienst about
  coverage`. These say what a given provider's field means, as against the canonical,
  provider-independent sentence the glossary serves
- 113 DWD observation descriptions come from the English `DESCRIPTION_*_en.pdf` sheets, which are
  more specific than the text the docs carried ("The solar incoming radiation includes the direct
  and the diffuse part ..." against "hourly sum of solar incoming radiation"). DWD CDC is Creative
  Commons BY 4.0, so its wording is reproduced with attribution. A sheet's cell is used only where
  it says at least as much as the curated text: some are terse, a few truncated -- `V_S1_NS` reads
  "cloud cover of 1. laye" and `V_S2_NS` repeats it for the second layer -- and two are left
  untranslated in an otherwise English sheet
- Source descriptions for DWD observation parameters: what a given DWD field means in DWD's own
  words, alongside the canonical, provider-independent sentence the glossary already served. 133
  parameters across the 30 datasets that publish an English description sheet, transcribed into
  `provider/dwd/observation/descriptions.py` and attached to the metadata at import. DWD CDC is
  Creative Commons BY 4.0, so the wording is reproduced with attribution to the Deutscher
  Wetterdienst; the module records the source URL and licence
- `description` now appears in `discover()`, and therefore in `GET /api/coverage`, the `coverage`
  MCP tool and `wetterdienst about coverage`. `ParameterModel.description` had been a declared but
  entirely unused field -- as are `DatasetModel.description` and `ResolutionModel.description`,
  which remain unpopulated
- ECCC monthly and hourly expose the fields that were previously left undeclared, with twelve new
  canonical parameters for them. Monthly gains the day counts
  (`count_days_precipitation_height_ge_1mm` and the six `count_days_valid_*`) and the
  climatological normals (`temperature_air_mean_2m_normal`, `precipitation_height_normal`,
  `snow_depth_new_normal`, `sunshine_duration_normal`); hourly gains `temperature_humidex`. Units
  were taken from the values rather than assumed: each normal matches the range of the quantity it
  is a normal of in the same response, and humidex sits at or above the air temperature in all 233
  paired observations sampled, which is what an apparent temperature does
- CI: new `Minimum dependency versions` job that resolves every direct dependency to the lowest
  version its specifier allows (`UV_RESOLUTION=lowest-direct`) and runs the test suite against it,
  so that declared floors are actually exercised
- Canonical parameter table (`wetterdienst.metadata.parameter_table`) holding the `unit_type` of
  each of the 505 canonical parameter names in one place, plus a test that checks every provider
  declaration against it — that the name is canonical and that the declared `unit` is a unit of
  that quantity. The table is now the single source of `unit_type`; see below
- New canonical parameters `radiation_global_intensity`, `radiation_sky_long_wave_intensity` and
  `radiation_sky_short_wave_diffuse_intensity` for sources that report irradiance (power per area)
  rather than irradiation accumulated over the interval (energy per area)
- Docs: a parameter glossary on the Parameters page, built from the canonical parameter table at
  build time by the local Sphinx extension `docs/_ext/parameter_glossary.py`. Every parameter in
  every provider's metadata table now links to its glossary entry
- `wetterdienst.metadata.unit_type.UnitType`, a literal of the unit types the unit converter
  knows. `CanonicalParameter.unit_type` is typed with it, so a mistyped unit type in the parameter
  table is a type error rather than something only a test can catch. A test pins the literal to
  `UnitConverter` in both directions, since the converter builds its unit types as a runtime dict
  that no static type can be derived from
- Two unit types the audit of the canonical table turned up as missing: `mass_per_volume`
  (g/m³, kg/m³, and mg/l and g/l shared with `concentration`, which is the same quantity under a
  different convention — 1 mg/l is 1 g/m³) and `degree_hour` (°Ch, Kh, °Fh), kept apart from
  `degree_day` so that a quantity accumulated per hour is not reported per day
- New canonical parameter `cooling_degree_day`, the counterpart of `heating_degree_day`
- Parameter discovery across all three interfaces: `GET /api/glossary`, the `glossary` MCP tool and
  `wetterdienst about glossary`. `coverage` answers which parameters a given provider offers; the
  glossary answers what any of them measures and which unit it comes back in — neither of which
  `coverage` reports. Filter with `parameter=` (substring match over the 505 names), `unit_type=`
  (a closed vocabulary, so an unknown one is a 422 or a CLI usage error rather than an empty
  result) and `limit=` to cap the response. The unit reported is the one a values request would
  actually return, including any `ts_unit_targets` override. This is what puts the canonical
  descriptions in front of users rather than only in the docs. A filter matching nothing is an
  empty list over HTTP and a non-zero exit on the CLI, the latter following grep so a shell script
  can tell
- A one-sentence description for all 505 canonical parameters, so the glossary now says what each
  quantity *is* rather than only which unit it comes back in — that soil temperatures are at a
  stated depth under a stated cover, that `wind_movement_24h` is wind run, that
  `radiation_global` is accumulated energy while `radiation_global_intensity` is power. They are
  deliberately provider- and resolution-independent, describing the quantity rather than one
  source's version of it. They appear in the docs glossary today; exposing them through the REST
  API, CLI and MCP is a separate change, since `discover()` reports name, unit type and unit only

### Changed

- The backend image builds with uv 0.12.5 rather than 0.8.4, four minor versions back. 0.8.4 could
  not parse `exclude-newer = "3 days"` and responded by discarding the whole `[tool.uv]` table --
  `warning: Failed to parse pyproject.toml during settings discovery` -- taking `[tool.uv.audit]`
  with it. The build still succeeded, because `uv sync --frozen` installs from the lockfile and
  needs none of those settings, so this was a silent degradation rather than a failure. Dependabot
  will keep the pin current from here, now that it reads `docker/`
- Dependabot's `docker` entry pointed at `/`, where there is no Dockerfile -- both of them live in
  `docker/`. It has therefore never proposed a base-image update for either image; it now reads
  the directory they are actually in
- Locked dependencies refreshed to their latest compatible versions (cryptography 50, fastapi
  0.141.1, starlette 1.6, uvicorn 0.52.3, numpy 2.5.2, zarr 3.3, mcp 1.29, and others), and the dev
  toolchain with them (ruff 0.16.3, ty 0.0.72, zizmor 1.29) -- both still pass with no source
  changes needed
- `uv` now resolves with a three-day cooldown (`tool.uv.exclude-newer = "3 days"`), so a release
  has to survive its first days in the wild before it can enter the lockfile. Yanks and
  publish-day breakage are most often caught in that window. The lockfile records it as a relative
  span (`exclude-newer-span = "P3D"`), not a timestamp, so it does not churn between runs and
  `uv lock --check` stays stable
- Docs: the REST API page's "Web Frontend" section is "Web App", matching what the app has been
  called since it moved to `app/`. The stripes page and the pull-request checklist follow, as do
  the Météo-France comments that explain which caller depends on a populated `start_date`
- Docs: the README states what the project stands for, in the same four lines the app closes with,
  and opens with "Global warming is not an opinion" rather than the Fridays for Future chant -- the
  one claim a weather-data library backs up by existing. Anthropic gets a logo next to JetBrains
  under "Supported by", where it had been a mention in prose
- Docs: the README is rewritten around what a first-time reader needs. One header image rather than
  three, one badge block rather than four, and a table of all 22 providers with their country and
  what each one serves -- which the README never stated, though it is the first question anyone
  asks. The MCP endpoint and the app are named among the features. The extras list is corrected: it
  advertised a `matplotlib` extra that does not exist and omitted `eccodes`, `excel`, `knmi`,
  `radar` and `radarplus`, which do. The Raspberry Pi installation notes move to
  `docs/known_issues.md`, where the other environment-specific issues live, rather than being
  dropped -- the README is the docs landing page, so nothing written only there survives deletion
- 34 more descriptions come from the source. CHMI publishes per-element metadata beside its csv
  archive -- name, unit, sensor height and measurement schedule -- which gives all 25 of its
  parameters, translated from Czech and carrying facts the canonical sentence cannot: its daily
  temperature, humidity, pressure and wind speed are averages of the 06:00, 13:00 and 20:00
  observations, its daily extremes are read at 20:00 and its snow depth at 06:00. DWD's
  `MetElementDefinition.xml` covers nine more codes across swsmos, mosmix and dmo. 190 derived
  descriptions remain
- Resolution descriptions are written where the name underdetermines what arrives, and only there:
  Météo-France synop (SYNOP's native three-hourly interval), MET Norway's 6 hour, and the two
  `dynamic` networks, WSV and Hubeau, where the interval is a property of the station rather than
  the network -- 15 minutes at most gauges, 10 at some, measured across both. `hourly` and `daily`
  say everything about themselves, so they are left empty rather than filled with text that reads
  as information without being any. EA hydrology's resolution description is dropped: it described
  the dataset structure, not the interval, and EA's dataset description already covers that
- 84 more descriptions come from the source rather than from the canonical sentence, after finding
  that three providers document their fields after all. Météo-France publishes a
  `*_descriptif_champs*.csv` beside each resolution (43 parameters, translated from French), the
  Met Office's MIDAS tables are documented by CEDA in English (32), and LHMT lists its fields on
  api.meteo.lt (9, translated from Lithuanian). They say what the canonical sentence cannot: that
  Météo-France's daily precipitation runs 06h to 06h UTC and is attributed to the earlier day, that
  Met Office pressure is uncorrected for altitude, that LHMT returns null for cloud cover it cannot
  determine through fog. 224 derived descriptions remain, DMI (52) and RMI (42) the largest, neither
  of which documents its fields anywhere reachable
- **Breaking**: `discover()` nests its answer so that every level has a place for its description,
  which had nowhere to go before: `{resolution: {"description": ..., "datasets": {dataset:
  {"description": ..., "parameters": [...]}}}}`. The 88 dataset descriptions and 2 resolution
  descriptions were on the model but unreachable over `GET /api/coverage`, the `coverage` MCP tool
  and `wetterdienst about coverage`, which all pass this dict through as their response. Consumers
  reading `data[resolution][dataset]` as a list of parameters now read
  `data[resolution]["datasets"][dataset]["parameters"]`
- The `Parameter` enum is no longer used inside the library. The three places that hard-coded
  parameter names — `TimeseriesRequest.interpolatable_parameters`, interpolation's
  occurrence-based set and the `ts_geo_station_distance` defaults — used it purely to spell a
  lowercased string, and now spell the canonical name directly. All 186 references resolve to the
  same 126/30/30 names as before. Those three lists have since moved into the canonical parameter
  table, see below
- How a parameter behaves in space is declared once, on `CanonicalParameter`, rather than as three
  hand-maintained name lists that had to agree with each other:
  `TimeseriesRequest.interpolatable_parameters`, the `ts_geo_station_distance` defaults in
  `Settings` and `_OCCURRENCE_BASED_PARAMETERS` in `core.interpolate` are all views of the new
  `interpolation` (`"homogeneous"` at the 40 km default radius, `"heterogeneous"` at 20 km, or
  `None` for a quantity that is not interpolated) and `zero_inflated` (whether interpolated values
  are thresholded on occurrence) fields. The two are separate because they are separate facts:
  visibility decorrelates over a few kilometres without being zero-inflated, and a precipitation
  normal is as orographically variable as precipitation while never being zero.
  `_OCCURRENCE_BASED_PARAMETERS` is gone; ask the table, `PARAMETERS[name].zero_inflated`.
  The parameter glossary in the docs now states per parameter whether it can be interpolated and
  from how far away
- **Breaking**, mildly: `TimeseriesRequest.interpolatable_parameters` is a `frozenset` rather than
  a `list`. Every caller in the library only tests membership, but it is a public class attribute,
  so code that indexes or slices it, or relies on its order, needs updating
- **Breaking**: irradiance (`power_per_area`) is now returned in W/m² rather than W/cm², so
  affected values are 10⁴ times larger. W/m² is what WMO specifies and what every source in this
  library actually publishes — MeteoSwiss global radiation now reads 0–1344 W/m² where it used to
  read 0–0.1344 W/cm². Affects the 17 declarations using `power_per_area`: KNMI (10 minutes),
  MeteoSwiss, met.no Frost and RMI. Set `ts_unit_targets={"power_per_area":
  "watt_per_square_centimeter"}` to keep the old output. Irradiation (`energy_per_area`) is
  unchanged and still returned in J/cm², which is the conventional unit for it
- **Breaking**: KNMI (10 minutes), RMI, MeteoSwiss and met.no reported irradiance in W/m² under
  the `radiation_global`, `radiation_sky_long_wave` and `radiation_sky_short_wave_diffuse` names,
  which elsewhere mean irradiation in J/cm². These declarations moved to the new
  `radiation_*_intensity` names. KNMI is the clearest case: its 10-minute `qg` is W/m² while its
  hourly and daily `Q` is J/cm², so one name was covering two quantities that no unit conversion
  relates without the accumulation interval. Queries using the old names against these providers
  need to switch to the `_intensity` names; DWD and every other provider are unaffected
- **Breaking**: Geosphere 10-minute and hourly radiation is now returned as published rather than
  silently rescaled. `cglo` and `chim` are irradiance in W/m², but the parser multiplied them by
  the interval length (600/10000 and 3600/10000) to present them as irradiation in J/cm² under the
  `radiation_global` and `radiation_sky_short_wave_diffuse` names. That conversion is removed and
  the three declarations moved to `radiation_global_intensity` and
  `radiation_sky_short_wave_diffuse_intensity` in W/m². Values are correspondingly 16.67× (10
  minutes) and 2.78× (hourly) larger; multiply by 0.06 and 0.36 respectively to recover the old
  numbers. Daily and monthly are unaffected — they use `cglo_j`, a distinct upstream parameter
  genuinely accumulated over the interval, and keep `radiation_global` in J/cm². This was the only
  in-parser unit conversion left in the library
- **Breaking**: Météo-France synop `visibility_range` was the only declaration of that parameter
  using `length_long`, so it was returned in km while all 15 other declarations return m. It now
  uses `length_medium` and returns m
- Docs: provider metadata tables no longer repeat the `unit type` column. The unit type is a
  property of the canonical parameter, so it is stated once in the glossary; the `unit` column
  stays, because that really is the individual provider's own
- The provider docs tables no longer own that text. It lived only in markdown, where no interface
  could reach it and where the two copies drifted apart in both directions -- three defects found
  during the unit audit were each caught by the *other* source being right. The model is the source
  now and `tests/test_docs.py::test_docs_parameter_descriptions_match_the_model` fails if a table
  disagrees with it
- Raise several dependency floors that were declared lower than what the code actually needs:
  `aiohttp>=3.14.0` (`encode_basic_auth`), `stamina>=25.1.0` (`set_testing` as a context manager),
  `pandas>=2.2.2`, `shapely>=2.0.4` and `h5py>=3.11` (NumPy 2 support),
  `plotly>=6.1.1` with `kaleido>=1.0.0` (static image export), and `click>=8.2`
  (separately captured `stderr` in `CliRunner`)
- Raise the development tooling floors to the versions we develop against, so that the minimum
  versions job only exercises runtime dependency floors

### Removed

- **Breaking**: seven DWD observation parameters that were declared but never returned a value are
  no longer declared, so a request for one now says so instead of answering with an empty frame:
  `cloud_type_layer1..4_abbreviation` (`v_sN_csa`, hourly cloud_type), `weather_text` (`ww_text`,
  hourly weather_phenomena), `end_of_interval` and `true_local_time` (`mess_datum_woz`, hourly
  solar). Each was checked against the archive rather than assumed: `v_sN_csa` is the letter form
  of `v_sN_cs` and matches it exactly across 398,381 records; every `ww` maps to one text across
  443,827 records while two codes share a text, so the text says strictly less than the code;
  `end_of_interval` names a column that does not exist in the solar files at all; and
  `mess_datum_woz` is published as a whole hour, leaving it a fixed one hour from the returned
  timestamp at station 00183 once the solar timestamps are rounded, which is where the sub-hour
  solar correction actually lives. Their canonical entries are dropped too, since no provider can
  express text in a `Float64` value column
- `DwdObservationValues.DROPPABLE_COLUMNS`, which duplicated the parser's drop list and had already
  drifted from it. Dropping happens once, in the parser
- The `magnetic_field_intensity` and `wave_period` unit types. Each existed for exactly one
  parameter, and both of those turned out to be mis-typed: WSV `current` is a bearing in degrees and
  WSV `wave_period` is a duration in seconds, so neither unit type has anything left to describe
- **Breaking**: the `Parameter` enum, exported from the package root. It listed the canonical
  parameter names but could not be used to request them — `parameters=` accepts strings, tuples,
  `ParameterModel` and `DatasetModel`, so passing a member raised
  `AttributeError: 'Parameter' object has no attribute 'strip'`. It appeared in no example and no
  documentation page, and its last internal uses are gone (see Changed). The canonical names live
  in `wetterdienst.metadata.parameter_table`, which also carries each parameter's unit type and
  description, and are discoverable through the new glossary endpoint, MCP tool and
  `wetterdienst about glossary`. Callers who used it to spell a name should use the string directly
- The `unit_type` key from provider metadata declarations — 1575 of them across 29 files. It is a
  property of the measured quantity rather than of the provider, and restating it once per
  declaration is what let the same canonical name pick different output units in different
  providers. `ParameterModel.unit_type` now reads it from the canonical parameter table via the
  parameter's `name`, and `ParameterModel` rejects the key outright so an override cannot creep
  back in. All 1692 parameters resolve to exactly the same `unit_type` as before, so nothing
  changes for users of the library — but a **third-party or custom provider metadata dict that
  still declares `unit_type` will now fail to validate**, and should simply drop the key.
  `discover()` and the REST and CLI responses report `unit_type` exactly as before. It is no
  longer part of `ParameterModel.model_dump()`/`model_dump_json()`, since it is derived from the
  parameter's `name` and emitting it per declaration would reintroduce at the serialization layer
  the duplication this removes; look the name up in `wetterdienst.metadata.parameter_table`
  instead
- **Breaking**: five `Parameter` enum members that no provider declared, so no request could ever
  return them: `HUMIDEX`, `PRECIPITATION_FREQUENCY`, `PRECIPITATION_HEIGHT_LIQUID_MAX`,
  `TIME_WIND_GUST_MAX` and `TIME_WIND_GUST_MAX_1MILE_OR_1MIN`. The dead entries referencing two of
  them in the interpolation membership lists went with them
- Docs: `docs/data/provider/eccc/observation/annual.md`. ECCC's `annual` resolution was dropped
  when observation values moved to the api.weather.gc.ca OGC API, and the docs still described it,
  along with `humidex` under hourly. The ECCC observation overview also still described bulk CSV
  downloads and four resolutions; corrected
- Docs: the `pressure_air_sea` row from IMGW meteorology daily, a parameter that provider no
  longer exposes
- Unused `jsonschema` development dependency

### Fixed

- The whole test suite failed to collect on Python 3.10, the oldest version the project supports:
  `tests/test_citation.py` imported `tomllib`, which is stdlib only from 3.11. The import error
  aborted collection, so 3.10 has been running zero tests rather than failing loudly on one. The
  import is now guarded and falls back to `tomli`, added to the dev group under the same marker
- Fixed nine provider docs rows that named parameters renamed in the code but not in the docs
  (`*_indicator` → `*_index` for DWD, `pressure_air_sl` → `pressure_air_sea_level` for
  Geosphere/NWS, `pressure_air_sh` → `pressure_air_site` for NWS, `flow` → `discharge` for
  Eaufrance)
- Fixed `tests/test_docs.py::test_data_coverage`, which had been passing without checking anything
  because its provider path pointed at `<root>/wetterdienst/provider` instead of `<root>/src/...`
- `CITATION.cff` names the released version again, and is valid CFF 1.2.0 once more. It had lost
  `version` and `date-released`, and carried an empty `identifiers:` key, which parses as null and
  fails the schema — so the file every citation tool reads described no particular release and
  could not be converted at all. It now states 0.132.0 of 2026-08-04 and the Zenodo concept DOI,
  the one that resolves to the latest version. Because nothing generates the file, a test ties it
  to the sources it duplicates: the version in `pyproject.toml`, the release date in this changelog
  and the DOI badge in the README, so a release that forgets it fails rather than ships stale
- `summarize()` searched for stations within 20 km whatever the parameter. It bounded its search
  with `max(ts_geo_station_distance.values())`, and that mapping only holds entries for the
  parameters that get the *shorter* radius — everything else is answered by the default factory and
  so is not in `values()` at all. It now takes the widest radius among the requested parameters, as
  interpolation already did, so a summary of e.g. `temperature_air_mean_2m` reaches the full 40 km
  and finds stations it used to walk past
- **Breaking**: MET Norway's in-band codes are decoded rather than returned as measurements. Frost
  states both in the element descriptions it publishes and then writes them into the value itself:
  snow depth -1 is "no snow", which is a depth of zero rather than an absent one, and cloud cover
  -3 and 9 both mean the cover could not be estimated. Being declared in eighths those two
  converted to -0.375 and 1.125 of the sky, the second looking like a plausible reading rather than
  a code. Snow depth -1 now returns 0, cloud cover -3 and 9 return null. Frost keeps the codes out
  of its own monthly and annual means, so only the elements themselves are touched
- **Breaking**: DWD hourly cloud cover no longer reports -0.125 of the sky. `cloud_cover_total`
  (`v_n`) and `cloud_cover_layer1` to `cloud_cover_layer4` (`v_sN_ns`) carry -1 where the sky could
  not be seen at all, SYNOP's N = 9, and being declared in eighths that converted to -0.125 as a
  fraction. It is returned as null now. DWD's description documents only -999 and says nothing
  about -1, so the reading is from the data: -1 stands in 1.2% of station 00003's hourly
  observations, and fog codes (`ww` 40-49) accompany 69.1% of those against 0.8% of the rest. The
  cloud *type* codes beside them keep their -1, DWD's own value for an automated observation, which
  is dimensionless and so passes through unscaled
- Descriptions no longer leak between resolutions. `build_metadata_model` wrote them into the
  metadata dicts it was given, and providers commonly build one resolution's parameter list from
  another's by comprehension, which reuses the very same dicts: AEMET's annual parameters are its
  monthly ones minus humidity, so annual reported "Monthly mean temperature" and its own seven
  descriptions went nowhere. The dicts are copied now, and a test checks each description lands on
  the parameter it names
- **Breaking**: MET Norway `cloud_cover_total` was declared `percent` while Frost publishes it in
  octas -- its own `unit` field says so, and the values run 0 to 8. A fully overcast sky was
  reported as `8 %`. Now declared `one_eighth`, so it converts like every other cloud cover
- **Breaking**: AEMET daily `dir` is `wind_direction_gust_max`, not `wind_direction`. AEMET
  documents it as the direction of the maximum gust, and its hourly block already separates the two
  as `dmax` and `dv`
- IMGW's monthly `climate` dataset was documented under a stale `data` heading carrying the
  parameter names it had before the dataset was renamed, and DWD derived still labelled
  `count_days_cooling_degree` "Anzahl Kühltage" where the column is `Kuehltage`
- 21 docs rows named a field the provider does not use. DWD MOSMIX and DMO documented low cloud
  cover as `n1` where the element is `nl`, DWD derived used the label "Anzahl Kühltage" where the
  column is `Kuehltage`, and ECCC and IMGW carried names from before their APIs changed. Each was
  a row whose description could not reach the model, so correcting them recovered 25 descriptions
  that already existed
- DWD's layer cloud cover descriptions are correct. Its English sheet truncates `V_S1_NS` to "cloud
  cover of 1. laye" and then repeats that same string for `V_S2_NS`, so the second layer was
  described as the first. The German `Metadaten_Parameter` file inside the data ZIPs has both right
  ("Bedeckungsgrad in der ersten/zweiten Schicht"), and all four layers now read consistently.
  `end_of_interval` and `luftdruck_nn`, which DWD documents in neither language, are described
  plainly; every non-quality DWD observation parameter now has a description
- **Breaking**: DWD's `v_n_i` and `v_vv_i` are named for what they hold. Both are *measurement
  method* indicators -- P for a human observer, I for an instrument, which is why the parser lists
  them among its string parameters -- while `cloud_cover_total_index` and `visibility_range_index`
  both described a coded *value*. They are now `cloud_cover_total_measurement_method` and
  `visibility_range_measurement_method`
- **Breaking**: `visibility_range_class` is renamed `visibility_range_index`. It only existed
  because `visibility_range_index` was occupied by the method indicator above, and its description
  ("Coded indicator of the visibility range") always described DWD subdaily `vk_ter` rather than
  what it was attached to. `cloud_cover_total_index` is removed; no provider declares a coded cloud
  cover
- **Breaking**: four DWD subdaily parameters named the wrong quantity, not merely the wrong unit.
  DWD's own `Metadaten_Parameter_*.txt`, shipped inside every data ZIP, gives each field a
  description and a unit, and for these four it disagreed with what wetterdienst declared:
  - `e_tf_ter` is "Eisansatz bei der Messung der Feuchttemperatur", unit YES/NO -- whether ice had
    formed on the wet bulb thermometer. It was declared `temperature_air_mean_0_05m` in °C, and
    carries only 0 and 1 across 82901 values at station 00003. Now
    `temperature_wet_ice_formation`, dimensionless
  - `ek_ter` is "Terminwerte des Erdbodenzustand", unit CODE -- values 0-9, exactly 10 distinct. It
    was declared `temperature_soil_mean_0_05m` in °C. Now `soil_state_index`, dimensionless
  - `vk_ter` is "Terminwerte Sichtweite", unit CODE -- also 0-9. It was declared `visibility_range`
    in metres, so a request for subdaily visibility returned "5 metres" for visibility class 5. Now
    `visibility_range_class`, dimensionless
  - `tf_ter` is the wet bulb temperature and was declared `temperature_air_mean_2m`. DWD's *hourly*
    moisture dataset already maps the same quantity (`tf_std`) to `temperature_wet_mean_2m`, so the
    two resolutions disagreed with each other. Confirmed against 83994 paired observations: it sits
    a median 1.6 °C below the air temperature and never exceeds it, which is the wet bulb
    signature. Now `temperature_wet_mean_2m`
- Three new canonical parameters for the above: `temperature_wet_ice_formation`,
  `soil_state_index` and `visibility_range_class`, all dimensionless
- **Breaking**: Geosphere `cloud_cover_total` is returned as a fraction rather than a percentage
  passed off as one. It was declared `decimal` while Geosphere documents `bewm_mittel` as `1/100`
  and returns 0-100, so the raw percentage went straight through the `fraction` target unconverted
  and every value was 100x its stated meaning. Geosphere's own `humidity` and
  `sunshine_duration_relative` already declared `percent`, so this was the odd one out within the
  provider. Values now read 0-1
- **Breaking**: DWD road `visibility_range` is returned in metres rather than 1000x too large. It
  was declared `kilometer`, but BUFR `0 20 001 horizontalVisibility` is metres, nothing in the
  parser converts, and the provider's own docs page already said `m`
- **Breaking**: ECCC hourly and monthly return data at all. Both resolutions declared parameters
  the OGC API never publishes -- hourly carried a copy of the *daily* field list
  (`max_temperature`, `snow_on_ground`, the degree days), monthly carried bulk-CSV column headers
  (`"total precip (mm)"`) -- so every request came back empty. Monthly additionally crashed on
  `LOCAL_DATE`, which is `"2023-06"` for that collection against a parser expecting a full
  timestamp. Both now declare the fields ECCC actually serves; the requested field list is derived
  from those declarations rather than hand-maintained per resolution, which is what let hourly
  drift into a copy of daily in the first place. Parameter names change for both resolutions
- **Breaking**: ECCC value requests return the whole period rather than an arbitrary 500 records.
  The OGC endpoint pages at 500 features and a station-year of hourly data is ~8800, so every
  request was silently truncated to a slice of the year -- June 1972 at station 4055 returned 16
  timestamps where it holds 697. Results grow accordingly
- ECCC exposes its whole station network rather than the first 500. The OGC endpoint pages at 500
  by default and ECCC publishes ~8600 stations, so 94% of them could not be requested at all --
  including every station whose data the hourly collection actually holds
- ECCC no longer fails on the daylight-saving fall-back hour, which occurs twice in local time.
  Unreachable while a request returned only part of a year, so it surfaced with the fix above
- ECCC hourly `wind_direction` is returned in degrees rather than tens of degrees, the same source
  encoding already decoded for the daily gust direction
- ECCC stations opened before standard time no longer fail the station listing. `America/Toronto`
  is `-5:17:32` in 1895, an offset that is not a whole number of minutes and that polars rejects;
  the conversion to UTC now happens in Python. A handful of stations publish no timezone at all
  and fall back to UTC. Neither showed up while the listing stopped at 500 rows
- **Breaking**: WSV Pegelonline values are now scaled to the unit the metadata declares. The service
  publishes the unit per *timeseries*, not per parameter, and its stations disagree, so a single
  declaration was silently wrong wherever a station differed. Water level is `cm` at most gauges but
  `m+NN` at 66 of them and `m+PNP` at 2; conductivity `µS/cm` or `mS/cm`; flow speed `m/s` or
  `cm/s`; wave height `cm` or `m`; wave period `s` or `1/100s`. Significant wave height at
  MELLUMPLATE came back as 0.07–1.32 next to 12.66–280.6 at LT ALTE WESER for the same quantity,
  both labelled cm. Affected values change by the corresponding factor. A station publishing a unit
  the provider does not know is now skipped with an error rather than reported under the wrong one.
  Note that the `m+NN` gauges have no gauge zero and so measure against sea level rather than the
  gauge datum even once scaled — the `gauge_zero` station column says which
- **Breaking**: WSV `current` is renamed `flow_direction` and returned in degrees. The source gives
  it the unit `MGN`, degrees relative to magnetic north, which had been read as a magnetic quantity
  and declared as magnetic field strength in A/m; the values are compass bearings of 0–360
- **Breaking**: WSV `wave_period` is returned in seconds. It was declared with a `wave_period` unit
  whose symbol was `1/s`, a frequency rather than a duration, and carried a `TODO` questioning it
- **Breaking**: WSV `clearance_height` is returned in centimetres. It was declared in metres while
  every station publishes centimetres, so values were 100× too large
- **Breaking**: WSV parameter names are humanized like every other provider's. The parser wrote the
  source name lowercased while the humanizing map is keyed on it as declared, so the two never
  matched and values came back as `sigh`, `tp` and `r` rather than `wave_height_sign`,
  `wave_period` and `flow_direction`. Unit conversion keys case-insensitively and was unaffected,
  which is why this went unnoticed. With `ts_humanize=False` the names are now the source's own
  casing (`SIGH`) rather than lowercased (`sigh`)
- WSV `gauge_zero` is populated rather than always null. The station frame built the column as
  `gauge_datum`, which `_base_columns` then dropped, leaving `gauge_zero` null for all 738
  stations. This is the column that says which datum a water level is on, so it matters most for
  exactly the `m+NN` gauges above
- WSV turbidity is checked against the station's own unit like the other scaled parameters. The
  service publishes `TR` as `FNU` at two stations, `TE/F` at two and `NTU` at one; all three name
  the same formazin scale so no value changes, but a turbidity unit that is *not* on that scale is
  now skipped rather than passed through as NTU
- Requesting several parameters at once no longer fails when one of them has no data for the
  station. Concatenating the empty result raised `polars.exceptions.ShapeError: unable to append to
  a DataFrame of width 6 with a DataFrame of width 0`; the empty frame is skipped instead. This
  affected every provider that reports parameters separately rather than grouped. Note that a
  parameter whose *download* fails is indistinguishable from one that simply has no data at this
  point — both surface as an empty frame — so such a parameter is now omitted from the result
  rather than failing the whole request with the `ShapeError` above
- **Breaking**: conductivity conversions between per-centimetre and per-metre units were wrong, 8
  of the 12 pairs by 10²–10⁴. Conductivity is per unit *length*, so a shorter length in the
  denominator means a larger number — 1 S/cm is 100 S/m, not 1/100 of one — and the conversions
  had that inverted on top of mishandling the µ prefix. Since `siemens_per_meter` was the default
  target, every conductivity value the library returned was affected: WSV at station 71160198 read
  0.0021 S/m where the correct figure is 0.2059. Only the two pairs the tests happened to cover
  (µS/m ↔ S/m) were right. All 12 pairs are now checked against 1 µS/cm = 10⁻⁴ S/m
- **Breaking**: conductivity is returned in µS/cm rather than S/m. That is the convention in
  hydrology and water quality and what the sources publish, and S/m is a large enough unit that
  rounding to 4 decimals cost real precision — 8.481 µS/cm came back as `0.0008`, a single
  significant figure, where river values run from single digits to a few thousand µS/cm. Station
  71160198 now reads 8.481–2058.642 µS/cm. Set `ts_unit_targets={"conductivity":
  "siemens_per_meter"}` for the old unit, which now also returns the correct value
- The three new `radiation_*_intensity` parameters are now listed in
  `TimeseriesRequest.interpolatable_parameters`. Without them, `interpolate()` and `summarize()`
  silently dropped the renamed radiation parameters for the affected providers
- Fixed four more provider docs rows that named parameters renamed in the code but not in the docs:
  DWD 1-minute and 5-minute `precipitation_form` → `precipitation_index`, and the `unit` cell of
  DWD DMO hourly `visibility_range`, which repeated the unit type instead of naming the unit
- **Breaking**: ECCC daily `cooling_degree_days` and `heating_degree_days` were mapped onto the
  canonical names `count_days_cooling_degree` and `count_days_heating_degree`, which mean a number
  of days. ECCC publishes the degree day total for the single day the record covers, so the values
  were degree days labelled as a count of days — for station 2 on 1979-11-02 the mean temperature
  is 6.3 °C and the reported value is 11.7, which is `18 - 6.3` and not any count. They now use
  the canonical names `heating_degree_day` and the new `cooling_degree_day`, in °Cd. The values
  are unchanged; queries using the old names against ECCC need to switch. DWD keeps both
  quantities under their own names, and is unaffected. The same two declarations exist in the
  ECCC *hourly* block and were renamed with them, but that block declares the daily field list
  wholesale and the hourly collection publishes none of those fields, so nothing there returns
  data either way — see above
- **Breaking**: ECCC `wind_direction_gust_max` is returned in degrees rather than tens of degrees.
  ECCC publishes `DIRECTION_MAX_GUST` in tens — its own docs call the column
  `Dir of Max Gust (10s deg)` — and the declaration said `degree`, so every bearing came back 10×
  too small: 17–26 across a sample where the true directions are 170–260. Because the wrong values
  still sit inside 0–360, no range check could have caught it. Found while auditing the same file
- DWD `humidity_absolute` (`absf_std`) was declared `dimensionless`. It is a mass of water vapour
  per volume of air, published in g/m³ — station 00433 reads 1.6 to 19.1. It now uses the new
  `mass_per_volume` unit type, so it is labelled g/m³ and can be converted. The values are
  unchanged
- DWD `cooling_degree_hour` (`Kuehlgradstunden`) was declared in degree days while it accumulates
  per hour, so a monthly total of 4179.8 °Ch was reported as 4179.8 °Cd — a figure no month can
  reach. It now uses the new `degree_hour` unit type. The values are unchanged

## [0.132.0] - 2026-08-04

### Changed

- Bump the minimum supported polars version to `>=1.43.0` (from `>=1.15.0`), required by the
  `explode(empty_as_null=...)` and `concat(how="horizontal_extend")` APIs used below

### Fixed

- Resolve polars and pyarrow deprecation warnings surfaced in the test suite: pass explicit
  `empty_as_null=True` to all `explode()` calls, switch `concat(how="horizontal")` to
  `how="horizontal_extend"`, and read Feather exports via `pyarrow.ipc.open_file()` instead of the
  deprecated `pyarrow.feather.read_table`. Also vectorise two per-element `map_elements` calls
  (eaufrance/hubeau, ea/hydrology) that had native polars equivalents
- Type the station response-model `state` field as nullable so the `stations` MCP tool stops rejecting
  MOSMIX/DMO stations. These forecast stations have no state and serialise `state` as `null`, but
  `_Station.state` and `_OgcFeatureProperties.state` were typed non-null, so the derived MCP output
  schema failed validation with `Output validation error: None is not of type 'string'` for every
  `mosmix`/`dmo` station listing (the same schema drift fixed for `values`/`interpolate`/`summarize`)

## [0.131.0] - 2026-08-02

### Added

- Add a DWD SWSMOS network (`dwd`/`swsmos`) exposing the road weather forecast (Straßenwetter-MOS)
  for DWD's ~1800 road weather stations. Each model run provides an hourly forecast out to +167 hours
  (selectable via `issue`, default: the latest run): air, dew-point and road surface temperature,
  liquid precipitation, precipitation probabilities and the road surface condition. This is the
  forecast counterpart to the DWD `road` observation network
- Add the DWD `10_minutes` urban climate (Stadtklima) datasets to the `dwd`/`observation` network,
  served from DWD's `climate_urban/` path (recent period only): `urban_precipitation`,
  `urban_pressure`, `urban_solar`, `urban_temperature_air` (incl. the new
  `temperature_radiant_mean_2m` parameter), `urban_temperature_extreme`, `urban_temperature_soil`,
  `urban_wind` and `urban_wind_extreme`. These complement the existing hourly urban datasets. The
  urban station-description lists are parsed by content because they frequently leave the optional
  date and Bundesland fields blank
- Add an IPMA (Portugal) observation provider (`ipma`/`observation`) backed by the key-less
  `api.ipma.pt` open-data JSON feeds. Provides near-real-time hourly observations (temperature,
  humidity, sea-level pressure, wind speed/direction, precipitation, global radiation) from ~222
  stations. Recent-only (a rolling ~1-day window), so a date range within the last day is required.
  The `-99.0` missing sentinel becomes null and the 8-point wind-direction code is converted to
  degrees
- Add an LHMT (Lithuania) observation provider (`lhmt`/`observation`) backed by the key-less
  `api.meteo.lt` JSON REST API. Provides hourly observations (temperature, humidity, wind
  speed/gust/direction, cloud cover, sea-level pressure, precipitation, snow depth) from ~52
  stations, with historical data back to roughly 2016 fetched per station and day. Settled past days
  are cached indefinitely while the current day uses a short cache
- Add a Met Office (UK) observation provider (`metoffice`/`observation`) backed by the MIDAS Open
  archive on CEDA (UK Open Government Licence). Covers eight datasets across daily and hourly
  resolution (rain, temperature, weather, wind, radiation, soil temperature). Requires a free CEDA
  account (`WD_AUTH__CEDA=<username>:<password>`); the bearer token is minted from those credentials
  and cached in-process until shortly before it expires. Multiple report types per day are collapsed
  to one value per calendar day, multi-day rain accumulations are dropped, and native units are
  normalised (e.g. visibility from decametres to metres)

### Changed

- Sharpen the `interpolate`/`summarize` endpoint descriptions (which become the MCP tool
  descriptions) and the MCP instructions so agents stop routing plain weather questions to them.
  `stations` -> `values` is now stated as the default for weather at a named place even when a
  specific past date is given, and interpolate/summarize are called out as opt-in estimates -- used
  only on explicit request or when no station with data is near the point -- because they add
  inaccuracy

### Fixed

- Type the `interpolate`/`summarize` response-model items to match what the endpoints serialise, so
  their MCP output schemas stop rejecting valid results. `_InterpolatedValuesItemDict` and
  `_SummarizedValuesItemDict` now include the `resolution`/`dataset` keys (always present in the
  rows) and type `value`/`distance_mean`/`distance`/`taken_station_id` as nullable: interpolating or
  summarizing a point with no station in reach serialises `null` for those fields, which the previous
  non-null schema rejected (the same schema drift fixed for `values` in 0.130.0)

## [0.130.0] - 2026-07-30

### Changed

- Raise stale/incorrect dependency lower bounds to honest, still-compatible floors (no change to the
  resolved/tested versions). Most importantly `fastapi>=0.115` (was `>=0.95.1`): the REST endpoints
  use Pydantic query-parameter models, a feature added in FastAPI 0.115, so the old floor advertised
  support the code never had. Also bump `httpx>=0.27`, `uvicorn>=0.30`, `duckdb>=1` (restapi/sql/
  duckdb extras), `xarray>=2024.6`, `fsspec>=2024.6`, `python-dateutil>=2.8.2`, `tabulate>=0.9`,
  `tqdm>=4.64`, `click>=8.1`, and add a lower bound to `sqlalchemy-cratedb>=0.40` (was unbounded
  below). Dev/docs groups are unchanged
- Rewrite the `history`, `summarize` and `interpolate` endpoint descriptions (which become the MCP
  tool descriptions) so small models stop mis-routing plain weather questions to them: they now say
  what each returns and that it is not measured weather -- `history` is station *metadata* history
  (name/location/sensor changes), `summarize`/`interpolate` estimate a value for a point *between*
  stations. Add a "Choosing a tool" note to the MCP instructions pointing weather questions at the
  `stations` -> `values` workflow

### Fixed

- Match station names with `WRatio` (was `token_sort_ratio`) in `filter_by_name`, so a bare place
  name finds its stations: `name="Kiel"` now returns `Kiel-Holtenau`/`Kiel-Kronshagen` instead of
  nothing (`token_sort_ratio` scored the length gap "Kiel" vs "Kiel-Holtenau" at ~47%, below the 0.8
  threshold). `WRatio` is a partial matcher, so a query that is a common sub-token (e.g. `name="Bad"`)
  matches many stations -- set `name_threshold=1.0` (keep only score-100 matches) or use the `sql`
  filter (`sql="name = 'Aach'"`) for an exact name match
- Honor the `rank` argument in `filter_by_name` (it was silently ignored, always returning up to 5
  matches): it now returns the `rank` best matches, best score first (default 1). The `stations`
  REST/CLI listing requests several name candidates by default and passes through an explicit `rank`
- Limit the `stations` listing to the requested `rank` on the REST API (`/api/stations`) and CLI
  (`stations`). A rank filter keeps every station in the frame (the `rank` limit is applied lazily
  during value collection), so a listing that asked for the N closest returned all stations instead
  -- e.g. `rank=3` near Kiel returned all 1284 DWD stations (a ~365 KB response that overwhelmed MCP
  clients). Listings now return the `rank` closest by distance
- Return `404` for the OAuth discovery paths (`/.well-known/oauth-authorization-server`,
  `/.well-known/oauth-protected-resource`) on the REST API so MCP clients treat the open `/mcp`
  server as no-auth instead of attempting (and failing) OAuth Dynamic Client Registration
- Type `value`/`quality` as `float | None` (was `str`) in the `_ValuesItemDict` response model, so
  the `/api/values` OpenAPI schema matches the numbers actually serialised. The MCP `values` tool
  derives its output schema from that model, and the wrong `str` type made FastMCP reject valid
  results with `9.0 is not of type 'string'`. This fixes the real schema instead of the previous
  workaround (`validate_output=False`), so MCP output validation is now enabled again

## [0.129.0] - 2026-07-27

### Added

- Add an optional Model Context Protocol (MCP) endpoint at `/mcp` on the REST API, exposing the data
  endpoints as MCP tools over the streamable-HTTP transport (via [FastMCP](https://gofastmcp.com/)).
  The tools are made agent-friendly (workflow `instructions`, clean tool names, hidden noise
  endpoints, permissive output validation) so even small models can drive them. Enable it with the
  `mcp` extra (`pip install wetterdienst[mcp]`), which is included in the Docker image
- Add DWD weather alerts (CAP warnings) provider (`dwd/alerts`) with Python API, CLI `alerts`
  command and REST `/api/alerts` endpoint: all active warnings, one row per alert, with a GeoJSON
  MultiPolygon geometry, on community (Gemeinde) or district (Landkreis) granularity; a `date`
  selects a historical snapshot from DWD's rolling ~48-hour window
- Parse DWD radar site BUFR products (echo top, reflectivity) into a polars DataFrame on
  `RadarResult.df`, opt-in via the `read_bufr` setting (requires the `eccodes` and `bufr` extras)
- Add RMI (Belgium) observation provider with 10-minute, hourly and daily resolution
  from the automatic weather station (AWS) network (no authentication required)
- Add CHMI (Czechia) observation provider with 10-minute, hourly, daily, monthly and annual
  resolution (no authentication required)
- Add FMI (Finland) observation provider with hourly and daily resolution
  (no authentication required)

### Changed

- Add descriptions to every field of the REST request models (stations, values, interpolate,
  summarize, history, issues). They surface in the REST API's OpenAPI schema (`/docs`) and in the
  generated MCP tool parameters, making both surfaces self-documenting.
- REST API and CLI: the `with_metadata` and `with_stations` options now default to `false` on the
  `stations`, `values`, `interpolate`, `summarize` and `history` commands/endpoints, so output
  contains just the requested data by default. Pass `with_metadata=true` / `with_stations=true`
  (or `--with_metadata=true` / `--with_stations=true`) to include the provider-metadata and station
  blocks as before.
- Reduce DWD MOSMIX/DMO KML parsing memory by streaming the zipped KML instead of
  decompressing it fully in memory (~6.5x lower peak RSS on MOSMIX-S)
- Refresh locked dependencies to their latest compatible versions (polars 1.43.1, pyarrow 25,
  fastapi 0.140.7, uvicorn 0.51, and others). Update the dev toolchain (ruff 0.16, ty 0.0.64) and
  adopt their new checks: ignore `CPY001` (no per-file copyright headers) and `PLR0917`
  (too-many-positional-arguments, sibling of the already-ignored `PLR0913`), fix a
  `log.exception()` call outside an exception handler, wrap implicitly concatenated test URLs, and
  narrow the DWD-derived available-dates set so `min()`/`max()` no longer see `datetime | None`

### Fixed

- Parse NOAA GHCN-hourly (GHCNh) timestamps from the provided ISO date column instead of
  reconstructing them from separate year/month/day/hour/minute fields
- Fix the `about fields` CLI command, which crashed with a `TypeError` because it forwarded
  `resolution` as a separate argument to `describe_fields()`
- Report coverage cleanly for metadata-less standalone networks (`dwd/radar`, `dwd/alerts`):
  `about coverage` and `/api/coverage` now return a clear message instead of crashing with an
  `AttributeError` / HTTP 500

## [0.128.0] - 2026-07-22

### Added

- Add KNMI (Netherlands) observation provider with 10-minute, hourly and daily resolution
  (requires a free KNMI Data Platform API key)
- Add DMI (Denmark) climate data observation provider with hourly, daily, monthly and
  annual resolution (no authentication required)
- Add AEMET (Spain) observation provider with hourly (real-time), daily, monthly and
  annual resolution
- Add SMHI (Sweden) observation provider with 1-minute, hourly, daily and monthly resolution
- Add Météo-France (France) synop network (subdaily, 3-hourly)
- Add Météo-France (France) observation network (6-minute, hourly, daily, monthly)
- Add MeteoSwiss (Switzerland) observation provider with 10-minute, hourly, daily, monthly and annual resolution

### Changed

- Reduce the memory footprint of aggregated value results (`.values.all()`) by storing the
  `station_id`, `resolution`, `dataset` and `parameter` columns as polars `Enum` instead of `String`
  (roughly halves the size of tidy frames); note that the dtype of these columns is now `Enum`. To
  get plain `String` columns back (e.g. for `.str` operations or strict dtype checks), cast them via
  `df.with_columns(pl.col(pl.Enum).cast(pl.String))`

## [0.127.0] - 2026-07-07

### Added

- `[REST API]` The `/api/coverage` endpoint now reports a `date_required` flag per
  provider/network, true if any of its resolutions require a date range for value
  queries (e.g. MET Norway Frost). Lets frontends surface this before submitting a
  query rather than after the query fails.

### Changed

- `[MET Norway Frost]` Value requests now fetch all parameters of a dataset/resolution in
  a single batched request (comma-separated `elements=`) instead of one request per
  parameter, cutting the number of HTTP requests by up to 11x for multi-parameter queries.
  Falls back to the previous per-parameter behavior (including historical time-series
  discovery) if the batched request itself returns a 404.
- `[IMGW]` File listing now prunes IMGW's per-period subfolders (named `YYYY` or
  `YYYY_YYYY`, encoding the exact date range they cover) to only those overlapping the
  requested date range, instead of recursively listing the entire directory tree on every
  request. Cuts the number of HTTP requests from ~33 (meteorology) / ~74 (hydrology) down
  to the 1-2 folders that actually matter for a given query.

### Removed

- `[IMGW]` Removed the hardcoded lat/lon override for hydrology station `150190410`,
  a workaround for a corrupted upstream CSV line from ~2024-02. The station's data has
  been clean upstream for a while, so the override had become a no-op; keeping it around
  risked silently clobbering a legitimate future coordinate change for that station.

### Fixed

- `[IMGW]` Station listing for both meteorology and hydrology no longer fails: the
  upstream station CSVs gained an extra "founding year" column and switched from a
  Windows codepage to UTF-8, which broke column parsing and produced mojibake names.
  Also fixed a station-list column-index bug (hydrology latitude/longitude were reading
  the wrong columns), a missing `return_dtype` on the lat/lon DMS-to-decimal conversion,
  and station rows no longer carrying a `resolution`/`dataset` tag, which made
  `.values.all()` fail outright.
- `[IMGW]` Hydrology value downloads now honor `WD_USE_CERTIFI`/`use_certifi`, matching
  the station list fetch and the meteorology provider. Previously it was silently ignored
  for the actual data downloads.
- `[IMGW]` Hydrology daily requests touching 2023 or later no longer crash with
  `ValueError: month must be in 1..12`. IMGW switched from twelve monthly zips per year
  to one consolidated yearly zip starting 2023, which broke the date-range parsing that
  assumed a `codz_YYYY_MM.zip` filename. Also handles the two different (and, for 2024,
  outright malformed) CSV export quirks IMGW has used for these consolidated files since,
  for both daily and monthly hydrology data: semicolon-separated unquoted rows in 2023,
  and in 2024 every row wrapped in a broken extra pair of quotes with doubled inner quotes.
- `[IMGW]` Meteorology `synop` daily requests no longer crash with
  `TypeError: '<' not supported between instances of 'NoneType' and 'NoneType'`. Unlike
  every other IMGW meteorology dataset, `synop` daily has always been archived one file
  per station per period (e.g. `2024_100_s.zip` for the station whose id ends in `100`)
  rather than one file per month across all stations, going back to at least the 1966-1970
  archive — the URL selection logic never accounted for this, so `synop` daily was
  non-functional for any date range.

## [0.126.0] - 2026-07-07

### Fixed

- `[REST API]` Station listing no longer fails with `StartDateEndDateError` for providers
  with `date_required` datasets (e.g. MET Norway Frost hourly, 10-minute, 6-hour). The
  date requirement only applies to value fetching, not to listing available stations. Also
  fixed a `TypeError` when constructing requests for providers that declare multi-period
  datasets but do not accept a `periods` constructor argument.

## [0.125.0] - 2026-07-06

### Added

- `[MET Norway Frost]` Add new provider `metno/frost` for the Norwegian Meteorological
  Institute's Frost API. Supports 10-minute, hourly, 6-hour, daily, monthly and annual
  resolutions with ~2200 stations across Norway. Authentication via free API key
  (`WD_AUTH__METNO_FROST` env var). Historical synoptic 6-hourly data is retrieved
  via an `availableTimeSeries` fallback that resolves the time-series-specific query
  parameters required by the Frost API.
- `[Settings]` Load `.env` files automatically via `env_file=".env"` and support nested
  env vars via `env_nested_delimiter="__"` (e.g. `WD_TS_UNIT_TARGETS__temperature=degree_fahrenheit`).
- `[Metadata]` Add `auth: bool = False` field to `MetadataModel` so providers requiring
  an API key can declare it. Defaults to `False` for all existing providers.
- `[API]` Add `is_configured() -> bool` and `is_valid() -> bool` classmethods to
  `TimeseriesRequest`. `is_configured` checks whether credentials are present (cheap,
  offline); `is_valid` probes the API to confirm they actually work (should be cached
  by the implementation). Both default to `True` for providers that need no auth.
- `[REST API]` `GET /api/coverage` (no parameters) now returns
  `{provider: {network: {auth: bool, configured: bool, valid: bool}}}` instead of
  `{provider: [network]}`, exposing per-network auth status to API consumers.
- `[REST API]` Add `GET /api/auth?provider=&network=` endpoint that returns
  `{provider, network, auth, configured, valid}` for a specific provider/network,
  allowing clients to re-check credential validity without fetching all coverage.
  `valid` is always `false` when `configured` is `false` (probe cannot run without credentials).

## [0.124.0] - 2026-06-30

### Added

- `[DWD MOSMIX / DMO]` Add `available_issues(station_id, settings)` classmethod to
  `DwdMosmixRequest` and `DwdDmoRequest` that lists the model-run datetimes currently
  available on DWD's OpenData server for a given station (MOSMIX_L single-station KMZ
  files and ICON single-station KMZ files respectively).
- `[CLI]` Add `wetterdienst issues --provider <p> --network <n> --station <id>` command
  that prints available issue datetimes as a JSON array.
- `[REST API]` Add `GET /api/issues?provider=<p>&network=<n>&station=<id>` endpoint
  returning `{"issues": ["<UTC ISO datetime>", ...]}`. Currently supported:
  `provider=dwd, network=mosmix` and `provider=dwd, network=dmo`.

### Fixed

- `[DWD MOSMIX / DMO]` Fix `issue` (and DMO `lead_time`) parameters being silently
  ignored when calling the REST API or `_get_stations_request` directly. The guard used
  `isinstance(api, DwdMosmixRequest)` where `api` is the *class* itself (not an instance),
  so the condition was always `False` and `DwdForecastDate.LATEST` was used regardless of
  the caller's intent. Changed to `issubclass` and added a `None`-guard so that omitting
  `issue` still falls through to the dataclass default (`DwdForecastDate.LATEST`).
- `[Frontend / Meteogram]` Fix x-axis tick labels overlapping massively on narrow mobile
  screens. Tick interval is now chosen based on actual chart pixel width: a 7-day MOSMIX
  forecast on a ~360 px phone uses 24-hour ticks instead of 6-hour ones (28 → 7 labels).
  Day-name annotations above the chart also shorten to weekday-only (`Mo`) when a day
  occupies fewer than 44 px, preventing header collisions on long forecasts.

## [0.123.0] - 2026-06-18

### Fixed

- `[DWD Observation]` Skip periods where all file downloads fail (empty `filenames_and_files`)
  before passing to the parser, preventing a `polars.exceptions.InvalidOperationError` from
  `pl.concat(..., how="align")` caused by a schema-less `LazyFrame` being mixed with valid ones.
- Reduce stamina retry attempts in `download_file` from 3 to 2 to limit worst-case wait time
  per file on persistent network failures.
- Add a default `aiohttp.ClientTimeout(total=30)` to `fsspec_client_kwargs` in `Settings` so
  HTTP connections time out after 30 seconds instead of hanging indefinitely.
- Wrap bare `int` timeouts in `aiohttp.ClientTimeout` inside `HTTPFileSystem.__init__` so that
  aiohttp >= 3.9 (which rejects plain int timeouts) works correctly with `fsspec_client_kwargs`.

## [0.122.0] - 2026-06-07

### Fixed

- Fix `download_file` retry mechanism: the previous `@stamina.retry` decorator was broken
  (the `on=` predicate checked `ClientResponse` instead of an exception, and all errors were
  swallowed before stamina could see them). Replaced with `stamina.retry_context` wrapping the
  `filesystem.cat_file` call directly. Retries are now triggered on `FileNotFoundError`,
  `FSTimeoutError`, `ClientConnectorError`, `ClientResponseError` and `ClientPayloadError`; all exhausted errors are
  returned as `File` objects rather than propagated.
- `[DWD Dmo]` Convert latitude and longitude from degrees and minutes to decimal degrees using `convert_dm_to_dd`.
- Fix station history parsing and add tests

## [0.121.1] - 2026-05-26

### Fixed

- Propagate `Settings.use_certifi` through `NetworkFilesystemManager.get` and the
  download helpers (`download_file`, `download_files`, `list_remote_files_fsspec`) so
  that fsspec's HTTP clients use the certifi certificate bundle when requested. This
  ensures provider code using these helpers respects the global `use_certifi` setting.
  Fixes #1669.
  Thanks to @KonstantinWaser for reporting the issue.

## [0.121.0] - 2026-05-09

### Added

- Interpolation / summarize: greatly expanded the set of interpolatable parameters
  beyond the original six. All continuous, spatially-correlated meteorological fields
  are now supported, organised into two distance classes:
    - **~40 km** (homogeneous / large-scale): all temperature variants at 2 m and 0.05 m
      (mean, max, min, last-24 h, multiday, mean-of-extremes), dew point, wet-bulb,
      wind-chill, surface temperature, soil temperatures (0.02 m – 2 m depth),
      heating/cooling degree aggregates, all humidity variants (`humidity`,
      `humidity_absolute`, `humidity_max`, `humidity_min`, `humidex`), all wind-speed
      variants and gust-max variants, wind movement, Beaufort scale, all sunshine-duration
      variants, global / diffuse / direct / long-wave radiation, all pressure variants
      (site, sea-level, reduced, max, min, tendency, vapour), total / effective / time-
      windowed cloud cover, and evapotranspiration / evaporation fields.
    - **~20 km** (heterogeneous / locally variable): all precipitation-height variants
      (including liquid, droplet, rocker, last-1 h … last-24 h, multiday, significant-
      weather, max), precipitation duration, new-snow depth and its multiday / max
      variants, and new-snow water-equivalent variants.
    - Fixes #1651 (`sunshine_duration` was silently dropped by both `interpolate` and
      `summarize` because it was absent from `interpolatable_parameters`).
- Interpolation: occurrence-threshold zeroing (previously only applied to
  `precipitation_height`) is now applied to **all** zero-inflated accumulation
  parameters: every precipitation-height variant, precipitation duration, new-snow
  depth variants, and new-snow water-equivalent variants. This prevents spurious
  small positive values when the surrounding stations recorded no event.
- Tests: five new unit tests for the occurrence-threshold logic in
  `core/interpolate.py` (`test_occurrence_threshold_*`) and two new remote
  integration tests (`test_interpolation_sunshine_duration_daily`,
  `test_interpolation_snow_depth_new_daily`).

- CLI: `--start-date` / `--end-date` options added to the `values`, `interpolate`, and
  `summarize` commands as a user-friendly alternative to the `--date` ISO-8601 interval
  syntax. Passing only `--start-date` treats it as a single-point date; passing only
  `--end-date` likewise. `--date` and `--start-date`/`--end-date` are mutually exclusive
  and raise a `UsageError` when combined.
- CLI: comprehensive `help` text added to all options across the `values`, `stations`,
  `interpolate`, and `summarize` commands, including `--provider`, `--network`,
  `--parameters`, `--periods`, all station-filtering options, `--format`, `--target`,
  `--shape`, `--humanize`, `--convert_units`, `--unit_targets`, `--skip_empty`,
  `--skip_criteria`, `--skip_threshold`, `--drop_nulls`, `--with_metadata`,
  `--with_stations`, `--pretty`, and `--issue`.

### Fixed

- Station name filtering (`filter_by_name`, `--name`) was case-sensitive, causing
  lowercase queries like `"darmstadt"` to return no results. Fixed by adding
  `processor=fuzz_utils.default_process` to the rapidfuzz call.
- NOAA GHCN hourly: adapted to upstream format changes — the station list CSV now
  contains non-integer values in the `WMO_ID` column (e.g. `"open"`), and the
  per-station PSV files renamed the station identifier column from `Station_ID` to
  `STATION`.
- DWD observation requests no longer raise `MetaFileNotFoundError` when a period's
  station description file is absent on the server (e.g. `10_minutes/precipitation/now`).
  The missing period is skipped with a warning and remaining periods are still returned.
- No internet connection no longer raises an error; instead, an empty result is
  returned. `ClientConnectorError` (TCP/DNS failures) is caught in `download_file`
  and stored as `NoInternetError` in the `File` object. All provider call sites
  return empty `DataFrame`/`LazyFrame` values accordingly. Fixes #1624.
- `NetworkFilesystemManager` now uses `threading.local()` instead of a class-level
  `dict` so each thread in `ThreadPoolExecutor`-based parallel downloads gets its
  own `WholeFileCacheFileSystem` instance, eliminating a race condition in the
  in-memory metadata cache that caused `TypeError: cannot unpack non-iterable bool
  object` at `fsspec/implementations/cached.py:716`.
- Reverted the directory-listing cache from `shelved-cache` + `cachetools` back to
  `diskcache`. `shelved-cache` wraps Python's `dbm`/`shelve`, which is not safe for
  concurrent access; parallel pytest-xdist workers sharing the same cache directory
  caused `_dbm.error` cascades and cascading test failures. `diskcache` uses SQLite
  and is both thread- and process-safe.
- `FileDirCache` mapping semantics corrected: `__getitem__` now raises `KeyError` on a
  cache miss (previously returned `None`) and short-circuits when `use_listings_cache`
  is `False`; `__contains__` uses a proper existence check so falsy cached values (e.g.
  an empty directory listing `[]`) are no longer misreported as absent; `__len__`
  delegates to the underlying cache directly instead of materialising all keys.

### Security

- `diskcache` advisory GHSA-w8v5-vhqr-4h9v (CVE-2025-69872, pickle deserialization)
  acknowledged and suppressed in `pysentry` and `dependency-review`. Exploitation
  requires write access to the local user cache directory, which is not a realistic
  attack vector for this project.
- `lxml` upgraded to 6.1.0, resolving GHSA-vfmq-68hx-4jfw (local file read via
  `resolve_entities`).

### Changed

- Station name filtering now uses `token_sort_ratio` instead of `token_set_ratio`,
  making word-order variations (e.g. `"Koeln Bonn"` → `"Köln/Bonn"`) match correctly.
  Zero regressions across all 1281 stations; 149 stations now resolve to their correct
  match when searched by exact name.
- Default fuzzy-match threshold for `filter_by_name` lowered from `0.9` to `0.8`,
  allowing single-character typos and common shorthands to match while maintaining
  100% precision.
- `name_threshold` is now exposed in the CLI (`--name-threshold`) for the `stations`
  and `values` commands, and wired through `StationsRequest` / `ValuesRequest` models
  so the REST API `/api/stations` and `/api/values` endpoints honour it automatically.
  All previously stale `0.9` defaults in stripes endpoints updated to `0.8`.

## [0.120.0] - 2026-04-11

### Added

- Add DWD Derived data for hourly climate (duett), daily soil, and monthly soil datasets,
  including parameters for evapotranspiration, soil moisture, soil temperature, frost/thaw depth,
  radiation, sunshine duration, and heating/cooling degree days, thanks @mspils and @jb-at-bdr

### Changed

- ECCC observation: migrate data retrieval from legacy CSV bulk download to
  the `api.weather.gc.ca` OGC API. Updates parameter metadata to match new
  column naming, rewrites wide-to-long pivoting to handle `*_flag` quality
  columns, and expands timezone mapping to include daylight saving variants.

### Fixed

- DWD `describe_fields`: adapt to updated PDF location and format. Description
  PDFs moved from the period subdirectory (e.g. `daily/kl/recent/`) to the
  dataset directory (`daily/kl/`). The PDF content now uses a structured table
  format with column name and description on the same line. The German section
  header changed from `Parameter` to `CSV Inhaltsbeschreibung`.

## [0.119.0] - 2026-02-17

### Added

- New API endpoint for climate stripes data

### Changed

- Improve interpolation and summary
- DWD DMO: Remove unnecessary validation for minimum dataframe length in date extraction
- Rename API endpoint /stripes/values to /stripes/image
- Migrate from `diskcache` to `cachetools` and `shelved-cache` for caching functionality. The new
  implementation uses `shelved_cache.PersistentCache` wrapping `cachetools.TTLCache` for improved
  maintainability while preserving all existing functionality and API compatibility.

### Fixed

- Update API endpoint for geosphere data retrieval

## [0.118.0] - 2026-02-01

### Added

- Implement station history retrieval; added API and request support to query historical station
  snapshots and lifecycle events (created, updated, decommissioned) by station id and dataset.
- Add `use_certifi` setting to use certifi certificate bundle instead of system certificates for
  HTTPS connections. Default is `False` for backward compatibility. Can be enabled via
  `Settings(use_certifi=True)` or environment variable `WD_USE_CERTIFI=true`.

### Changed

- Move code to src directory
- Filter By Rank: Sort stations by distance and station id
- Soften validation for numbers and integers in UI core request models

## [0.117.0] - 2026-01-03

### Added

- Restapi: Add /api/version endpoint to get current version of wetterdienst backend (used in frontend)

## [0.116.0] - 2025-12-09

### Changed

- Improve polars code, thanks @SeeBastion524

### Fixed

- Allow concatenation of station data with varying columns, thanks @jb-at-bdr
- Adjust data type of "name" column, thanks @jb-at-bdr

## [0.115.0] - 2025-11-24

### Added

- Add classifier for python 3.14
- Add new data of DWD Derived, thanks @jb-at-bdr

### Changed

- Update docker image to use python 3.14

### Fixed

- Cast value in interpolate function to float

  @ninjeanne reported that wetterdienst lately quirks when running interpolation. This issue is related to one of the
  new polars versions > 1.33.1. A shorthand fix would be to cast the value coming from the scipy interpolate function to
  a float.

## [0.114.3] - 2025-11-07

### Fixed

- \[DWD Obs\] Fix encoding issue

## [0.114.2] - 2025-11-05

### Fixed

- \[DWD DMO\] Fix path for `icon_eu` and minor fixes

## [0.114.1] - 2025-11-01

### Fixed

- Fix global import of duckdb exception in `to_target` method

## [0.114.0] - 2025-10-31

### Added

- \[DWD Obs\] Use utf8 encoding for parsing data
- Add `if_exists` argument to `to_target`
- Use more polars-native methods

### Fixed

- \[DWD Road\]: Skip empty files

### Changed

- Bump polars minimum to 1.15.0

## [0.113.0] - 2025-09-21

### Added

- Make Mosmix and DMO a lot faster for multiple stations requests

### Changed

- Bump pypdf to <7
- Make pypdf optional

## [0.112.0] - 2025-09-06

### Changed

- Switch back to `WholeFileCacheFileSystem` for caching
- Improve more things on caching
- Update uv.lock
- Polars: Set format and timezone on datetime conversion

## [0.111.0] - 2025-08-03

### Added

- Make humidity interpolatable
- Improve interpolation configuration
- Set missing `return_dtype` in fileindex function
- Set `return_dtype` for polars functions

### Changed

- Pin zarr to `>=3.1;python_version>=3.11`
- Docker: Copy uv bin from uv image
- Pin lxml to <7

### Fixed

- Parse parameters only if any are given
- Fix export for interpolated values to csv
- Round timestamps of hourly solar data to nearest hour
- Fix several polars issues
- Docker: Install chromium to fix png export

## [0.110.0] - 2025-07-23

### Added

- Make retry of `download_file` more robust
- Overhaul docs switching to `sphinx` and `myst-parser`
- Improve exception handling in restapi
- Improve download of files

### Changed

- Drop upper version pins for fsspec and tzdata
- Introduce `wetterdienst.model`, streamline others
- Bump minimum kaleido version to `0.2.2`

### Fixed

- Export: Fix influx tags and fields
- \[NOAA GHCN hourly\] Fix metadata creation
- Include resolution column in wide format
- Disallow `polars==1.31.0` due to issues

## [0.109.0] - 2025-06-03

### Changed

- Split `coordinates` and `bbox` into separate arguments
- Bump dependencies

## [0.108.0] - 2025-04-25

### Added

- Improve restapi look and add impressum
- Add uvloop and httptools for speed via `uvicorn[standard]`

### Changed

- Use dataclass everywhere
- Refactor query method
- Adjust retry of function `download_file`

### Fixed

- Fix numerous radar tests

## [0.107.0] - 2025-03-25

### Changed

- Refactor `download_file`

### Fixed

- Fix false attribute parsing by pydantic model in cli
- Fix datetime parsing for generic radar data

## [0.106.0] - 2025-03-05

### Fixed

- Improve parameter unpacking in `ParameterSearch.parse`
- Fix docker manifest

## [0.105.0] - 2025-03-01

### Added

- Add user agent to default `fsspec_client_kwargs`
- Adjust apis to track resolution and dataset (allows querying data for different resolutions and datasets in one
  request)

### Changed

- Improve date parsing across multiple apis
- Cleanup docker image
- Improve numerous apis

### Fixed

- \[WSV Pegel\] Fix characteristic values and improve date parsing

## [0.104.0] - 2025-02-15

### Changed

- Reduce the margin of the stations plot
- Make pydantic models for uis simpler
- Migrate from `sklearn+numpy` to `pyarrow` for location querying
- Remove command from Docker file
- Improve workflow for Docker
- Get rid of columns enumeration
- \[NOAA GHCN\] Improve date parsing and other fixes

## [0.103.0] - 2025-02-02

### Added

- Stripes: Replace matplotlib by plotly
- Explorer: Add download button for plot
- Split up plotting extras into `plotting` and `matplotlib`
- Interpolation/Summary: Add dataset to DataFrame
- Add plotting capabilities

### Changed

- Update docker image extras

### Removed

- Remove unused cachetools dependency

### Fixed

- Fix benchmark code
- Make fastexcel a polars extra
- Drop click-params dependency
- Make pyarrow a polars extra

## [0.102.0] - 2025-01-17

### Added

- Add cmd to docker image

### Changed

- Use `to_list()[0]` instead of `first()`

## [0.101.0] - 2025-01-13

### Added

- Move more details into `MetadataModel`

### Changed

- \[DWD Obs\] Make the download function more flexible using threadpool
- \[DWD Obs\] Cleanup parser function
- \[DWD Obs\] Improve fileindex and metaindex

### Fixed

- \[DWD Obs\] Reduce unnecessary file index calls during retrieval of data for stations with multiple files

## [0.100.0] - 2025-01-06

### Added

- Add logo for restapi
- **Breaking:** Add dedicated unit converter

  Attention: Many units are changed to be more consistent with typical meteorological units. We now use `°C` for
  temperatures. Also, length units are now separated in `length_short`, `length_medium` and `length_long` to get more
  reasonable decimals. For more information, see the new units chapter (usage/units) in the documentation.

### Changed

- Add reasonable upper bounds for dependencies

### Fixed

- Filter out invalid underscore prefixed files

## [0.99.0] - 2024-12-30

### Added

- Add setting `ts_complete=False` that allows to prevent building a complete time series

### Changed

- Docs: Change to markdown using mkdocs
- Settings: Switch to `pydantic_settings` for settings management
- Improve wetterdienst api class
- Dissolve wetterdienst notebook into examples
- Use `duckdb.sql` and ask only for WHERE clause
- Update restapi annotations
- Use `Settings` in restapi/cli core functions
- Restapi/Cli: Use pydantic models for request parameters
- Rename `dropna` to `drop_nulls`
- Change default of `drop_nulls` to True
- Replace occurrences of `dt.timezone.utc` by `ZoneInfo("UTC")`
- Improve release workflow using `uv build` and `uv publish`
- Improve docker-publish workflow to use `uv build`

## [0.98.0] - 2024-12-09

### Added

- Add support for Python 3.13

### Changed

- **Breaking:** Add new metadata model: Requests now use `parameters` instead of `parameter` and `resolution` e.g.
  `parameters=[("daily", "kl")]` instead of `parameter="kl", resolution="daily"`

### Deprecated

- Deprecate Python 3.9

## [0.97.0] - 2024-10-06

### Fixed

- DWD Road: Use correct 15 minute resolution

## [0.96.0] - 2024-10-04

### Changed

- Bump polars to `>=1.0.0`
- Change `DWDMosmixValues` and `DWDDmoValues` to follow the core `_collect_station_parameter` method
- Allow only single issue retrieving with `DWDMosmixRequest` and `DWDDmoRequest`

## [0.95.1] - 2024-09-04

### Fixed

- Fix `state` column in station list creation for DWD Observation

## [0.95.0] - 2024-08-27

### Changed

- Make fastexcel non-optional
- Remove upper dependency bounds

## [0.94.0] - 2024-08-10

### Added

- DWD Road: Add new station groups, log warning if no data is available, especially if the station group is one of the
  temporarily unavailable ones

### Fixed

- Explorer: Fix DWD Mosmix request kwargs setup

## [0.93.0] - 2024-08-06

### Fixed

- Fix multiple Geosphere parameter and unit enums
- Explorer: Fix wrap `(parameter, dataset)` in iterator
- Adjust parameter typing of apis

## [0.92.0] - 2024-07-31

### Changed

- Rename parameters
    - units in parameter names are now directly following the number
    - temperature parameters now use meter instead of cm and also have a unit
    - e.g. TEMPERATURE_AIR_MEAN_2M, CLOUD_COVER_BETWEEN_2KM_TO_7KM, PROBABILITY_PRECIPITATION_HEIGHT_GT_0_0MM_LAST_6H

### Fixed

- Bump pyarrow version to <18
- Fix EaHydrology station list parsing
- Rename `EaHydrology` to `EAHydrology`
- Fix propagation of settings through `EAHydrology` values

## [0.91.0] - 2024-07-14

### Fixed

- Fix DWD Road api

## [0.90.0] - 2024-07-14

### Changed

- Bump `environs` to <12

### Fixed

- Explorer: Fix json export

## [0.89.0] - 2024-07-03

### Fixed

- EaHydrology: Fix date parsing
- Hubeau: Use correct frequency unit
- Fix group by unpack

## [0.88.0] - 2024-06-14

### Added

- Allow passing `--listen` when running the explorer to specify the host and port

## [0.87.0] - 2024-06-06

### Added

- Add precipitation version

### Changed

- Rename warming stripes to climate stripes
- Replace custom Settings class with pydantic model

## [0.86.0] - 2024-06-01

### Changed

- Interpolation/Summary: Require start and end date
- Enable interpolation and summarization for all services

### Fixed

- Fix multiple issues with interpolation and summarization

## [0.85.0] - 2024-05-29

### Fixed

- Fix `dropna` argument for DWD Mosmix and DMO
- Adjust DWD Mosmix and DMO kml reader to parse all parameters
- Fix `to_target(duckdb)` for stations
- Fix init of `DwdDmoRequest`

## [0.84.0] - 2024-05-15

### Fixed

- Fix DWD Obs station list parsing again

## [0.83.0] - 2024-04-26

### Added

- Allow `wide` shape with multiple datasets

## [0.82.0] - 2024-04-25

### Fixed

- Adjust column specs for DWD Observation station listing
- Maintain order during deduplication
- Change threshold in `filter_by_name` to 0.0...1.0

## [0.81.0] - 2024-04-09

### Added

- Warming stripes: Add option to enable/disable showing only active stations

## [0.80.0] - 2024-04-08

### Added

- Migrate explorer to streamlit
- UI: Add warming stripes

### Changed

- Explorer: Disable higher than daily resolutions for hosted version

## [0.79.0] - 2024-03-21

### Fixed

- Fix parsing of DWD Observation stations where name contains a comma

## [0.78.0] - 2024-03-09

### Added

- Docker: Install more extras

### Fixed

- Cli/Restapi: Return empty values if no data is available

## [0.77.1] - 2024-03-08

### Fixed

- Fix setting NOAA GHCN-h date to UTC

## [0.77.0] - 2024-03-08

### Changed

- Refactor index caching -> Remove monkeypatch for fsspec

## [0.76.1] - 2024-03-03

### Fixed

- NOAA GHCN Hourly: Fix date parsing

## [0.76.0] - 2024-03-02

### Added

- Add NOAA GHCN Hourly API (also known as ISD)

## [0.75.0] - 2024-02-25

### Changed

- Remove join outer workaround for polars and use `outer_coalesce` instead
- Allow duckdb for Python 3.12 again
- Update REST API index layout
- Bump polars to 0.20.10
- Docker: Bump to Python 3.12
- Docker: Reduce image size

## [0.74.0] - 2024-02-22

### Added

- Restapi: Add health check endpoint

## [0.73.0] - 2024-02-09

### Changed

- Set upper version bound for Python to 4.0
- Make pandas optional

### Fixed

- Add temporary workaround for bugged line in IMGW Hydrology station list
- Fix parsing of dates in NOAA GHCN api

## [0.72.0] - 2024-01-13

### Added

- Allow for passing kwargs to the `to_csv` method

### Fixed

- Fix issue when using `force_ndarray_like=True` with pint UnitRegistry

## [0.71.0] - 2024-01-03

### Added

- CI: Add support for Python 3.12

### Fixed

- Fix issue with DWD DMO api

## [0.70.0] - 2023-12-30

### Added

- Docker: Enable interpolation in wetterdienst standard image

### Changed

- Replace partial with lambda in most places
- IMGW: Use ttl of 5 minutes for caching

### Fixed

- IMGW Meteorology: Drop workaround for mixed up station list to fix issue
- WSV Hydrology: Fix issue with station list characteristic values
- DWD Observation: Remove redundant replace empty string in parser
- NWS Observation: Read json data from bytes
- EA Hydrology: Read json data from bytes

## [0.69.0] - 2023-12-18

### Added

- Restapi: Unify station parameter and add alias
- Interpolation: Make maximum station distance per parameter configurable via settings

### Fixed

- Result: Convert date to string only if dataframe is not empty
- Restapi: Move restapi from /restapi to /api

## [0.68.0] - 2023-12-01

### Added

- Add example for comparing Mosmix forecast and Observation data

### Fixed

- Fix parsing of DWD Observation 1 minute precipitation data

## [0.67.0] - 2023-11-17

### Changed

- **Breaking:** Use start_date and end_date instead of from_date and to_date
- Use artificial station id for interpolation and summarization
- Rename taken station ids columns for interpolation and summarization

## [0.66.1] - 2023-11-08

### Fixed

- Add workaround for issue with DWD Observation station lists

## [0.66.0] - 2023-11-07

### Added

- Add lead time argument - one of short, long - for DWD DMO to address two versions of icon

### Changed

- Rework dict-like export formats and tests with extensive support for typing
- Improve radar access
- Style restapi landing page
- Replace timezonefinder by tzfpy

### Fixed

- Fix DWD DMO access again

## [0.65.0] - 2023-10-24

### Changed

- Cleanup error handling
- Make cli work with DwdDmoRequest API
- Cleanup cli docs

### Fixed

- Fix DWD Observation API for 5 minute data

## [0.64.0] - 2023-10-12

### Added

- Export: Add support for InfluxDB 3.x

### Changed

- Remove direct tzdata dependency
- Replace pandas read_fwf calls by polars substitutes

## [0.63.0] - 2023-10-08

### Added

- \[Streamlit\] Add sideboard with settings
- \[Streamlit\] Add station information json
- \[Streamlit\] Add units to DataFrame view and plots
- \[Streamlit\] Add JSON download

### Fixed

- Return data correctly sorted

## [0.62.0] - 2023-10-07

### Changed

- Raise minimum version of polars to 0.19.6 due to breaking changes

### Fixed

- Fix multiple issues with DwdObservationRequest API

## [0.61.0] - 2023-10-06

### Added

- Make parameters TEMPERATURE_AIR_MAX_200 and TEMPERATURE_AIR_MIN_200 summarizable/interpolatable
- Add streamlit app for DWD climate stations
- Add sql query function to streamlit app

### Fixed

- Fix imgw meteorology station list parsing
- Improve streamlit app plotting capabilities
- Fix DWD DMO api

## [0.60.0] - 2023-09-16

### Added

- Add implementation for DWD DMO

## [0.59.3] - 2023-09-11

### Fixed

- Fix DWD solar date string correction

## [0.59.2] - 2023-09-06

### Fixed

- Fix documentation and unit conversion for Geosphere 10minute radiation data

## [0.59.1] - 2023-07-18

### Fixed

- Fix Geosphere parameter names

## [0.59.0] - 2023-07-30

### Changed

- Revise type hints for parameter and station_id

### Fixed

- Fix Geosphere Observation parsing of dates in values -> thanks to @mhuber89 who discovered the bug and delivered a fix

## [0.58.1] - 2023-07-26

### Fixed

- Fix bug with Geosphere parameter case

## [0.58.0] - 2023-07-10

### Added

- Add retry to functions
- Add IMGW Hydrology API
- Add IMGW Meteorology API

### Changed

- Rename FLOW to DISCHARGE and WATER_LEVEL to STAGE everywhere

## [0.57.1] - 2023-06-28

### Fixed

- Fix pyarrow dependency

## [0.57.0] - 2023-05-15

### Added

- Sources: Add DWD Road Weather data

### Changed

- **Breaking:** Backend: Migrate from pandas to polars

  Switching to Polars may cause breaking changes for certain user-space code heavily using pandas idioms, because
  Wetterdienst now returns a [Polars DataFrame](https://pola-rs.github.io/polars/py-polars/html/reference/dataframe/).
  If you absolutely must use a pandas DataFrame, you can cast the Polars DataFrame to pandas by using the `.to_pandas()`
  method.

## [0.56.2] - 2023-05-11

### Fixed

- Fix Unit definition for RADIATION_GLOBAL

## [0.56.1] - 2023-05-10

### Fixed

- Fix JOULE_PER_SQUARE_METER definition from kilojoule/m2 to joule/m2

## [0.56.0] - 2023-05-02

### Fixed

- Update docker images
- Fix now and now_local attributes on core class

## [0.55.2] - 2023-04-20

### Fixed

- Fix precipitation index interpolation

## [0.55.1] - 2023-04-17

### Fixed

- Fix setting empty values in DWD observation data
- Fix DWD Radar composite path

## [0.55.0] - 2023-03-19

### Changed

- Drop Python 3.8 support

### Fixed

- Explorer: Fix function calls

## [0.54.1] - 2023-03-13

### Fixed

- Fix DWD Observations 1 minute fileindex

## [0.54.0] - 2023-03-06

### Changed

- SCALAR: Improve handling skipping of empty stations, especially within .filter_by_rank function
- Make all parameter levels equal for all weather services to reduce complexity in code
- Change `tidy` option to `shape`, where `shape="long"` equals `tidy=True` and `shape="wide"` equals `tidy=False`
- Naming things: All things "Scalar" are now called "Timeseries", with settings prefix `ts_`
- Drop some unnecessary enums
- Rename Environment Agency to ea in subspace

### Fixed

- CLI: Fix cli arguments with multiple items separated by comma (,)
- Fix fileindex/metaindex for DWD Observation
- DOCS: Fix precipitation height unit
- DOCS: Fix examples with "recent" period

## [0.53.0] - 2023-02-07

### Added

- CLI: Add command line options `wetterdienst --version` and `wetterdienst -v` to display version number

### Changed

- SCALAR: Change tidy option to be set to True if multiple different entire datasets are queried (in accordance with
  exporting results to json where multiple DataFrames are concatenated)
- Further cleanups
- Change Settings to be provided via initialization instead of having a singleton

## [0.52.0] - 2023-01-19

### Added

- Add Geosphere Observation implementation for Austrian meteorological data

### Changed

- RADAR: Clean up code and merge access module into api

### Fixed

- DWD MOSMIX: Fix parsing station list
- DWD MOSMIX: Fix converting degrees minutes to decimal degrees within the stations list. The previous method did not
  produce correct results on negative lat/lon values.

## [0.51.0] - 2023-01-01

### Added

- Update wetterdienst explorer with clickable stations and slightly changed layout

### Fixed

- Improve radar tests and certain dict comparisons
- Fix problem with numeric column names in method gain_of_value_pairs

## [0.50.0] - 2022-12-03

### Added

- Interpolation/Summary: Now the queried point can be an existing station laying on the border of the polygon that it's
  being checked against
- UI: Add interpolate/summarize methods as subspaces

### Changed

- Geo: Change function signatures to use latlon tuple instead of latitude and longitude
- Geo: Enable querying station id instead of latlon within interpolate and summarize
- Geo: Allow using values of nearby stations instead of interpolated values

### Fixed

- Fix timezone related problems when creating full date range

## [0.49.0] - 2022-11-28

### Added

- Add NOAA NWS Observation API
- Add Eaufrance Hubeau API for French river data (flow, stage)

### Fixed

- Fix bug where duplicates of acquired data would be dropped regarding only the date but not the parameter
- Fix NOAA GHCN access issues with timezones and empty data

## [0.48.0] - 2022-11-11

### Added

- Add example to dump DWD climate summary observations in zarr with help of xarray

### Fixed

- Fix DWD Observation urban_pressure dataset access (again)

## [0.47.1] - 2022-10-23

### Fixed

- Fix DWD Observation urban_pressure dataset access

## [0.47.0] - 2022-10-14

### Added

- Add support for reading DWD Mosmix-L all stations files

## [0.46.0] - 2022-10-14

### Added

- Add summary of multiple weather stations for a given lat/lon point (currently only works for DWDObservationRequest)

## [0.45.2] - 2022-10-11

### Fixed

- Make DwdMosmixRequest return data according to start and end date

## [0.45.1] - 2022-10-10

### Fixed

- Fix passing an empty DataFrame through unit conversion and ensure set of columns

## [0.45.0] - 2022-09-22

### Added

- Add interpolation of multiple weather stations for a given lat/lon point (currently only works for
  DWDObservationRequest)

### Fixed

- Fix access of DWD Observation climate_urban datasets

## [0.44.0] - 2022-09-18

### Added

- Add DWD Observation climate_urban datasets

### Changed

- Slightly adapt the conversion function to satisfy linter
- Adjust Docker images to fix build problems, now use python 3.10 as base
- Adjust NOAA sources to AWS as NCEI sources currently are not available
- Make explorer work again for all services setting up Period enum classes instead of single instances of Period for
  period base

### Fixed

- Fix parameter names:
    - we now use consistently INDEX instead of INDICATOR
    - index and form got mixed up with certain parameters, where actually index was measured/given but not the form
    - global radiation was mistakenly named radiation_short_wave_direct at certain points, now it is named correctly

## [0.43.0] - 2022-09-05

### Added

- Add DWD Observation climate_urban datasets

### Changed

- Use lxml.iterparse to reduce memory consumption when parsing DWD Mosmix files
- Fix Settings object instantiation
- Change logging level for Settings.cache_disable to INFO

## [0.42.1] - 2022-08-25

### Fixed

- Fix DWD Mosmix station locations

## [0.42.0] - 2022-08-22

### Changed

- Move cache settings to core wetterdienst Settings object

### Fixed

- Fix two parameter names

## [0.41.1] - 2022-08-04

### Fixed

- Fix correct mapping of periods for solar daily data which should also have Period.HISTORICAL besides Period.RECENT

## [0.41.0] - 2022-07-24

### Fixed

- Fix passing through of empty dataframe when trying to convert units

## [0.40.0] - 2022-07-10

### Changed

- Update dependencies

## [0.39.0] - 2022-06-27

### Changed

- Update dependencies

## [0.38.0] - 2022-06-09

### Added

- Add DWD Observation 5 minute precipitation dataset
- Add test to compare actually provided DWD observation datasets with the ones we made available with wetterdienst

### Fixed

- Fix one particular dataset which was not correctly included in our DWD observations resolution-dataset-mapping

## [0.37.0] - 2022-06-06

### Fixed

- Fix EA hydrology access
- Update ECCC observation methods to acquire station listing

## [0.36.0] - 2022-05-31

### Fixed

- Fix using shared FSSPEC_CLIENT_KWARGS everywhere

## [0.35.0] - 2022-05-29

### Added

- Add option to skip empty stations (option tidy must be set)
- Add option to drop empty rows (value is NaN) (option tidy must be set)

## [0.34.0] - 2022-05-22

### Added

- Add UKs Environment Agency hydrology API

## [0.33.0] - 2022-05-14

### Fixed

- Fix acquisition of DWD weather phenomena data
- Set default encoding when reading data from DWD with pandas to 'latin1'
- Fix typo in `EcccObservationResolution`

## [0.32.4] - 2022-05-14

### Fixed

- Fix acquisition of historical DWD radolan data that comes in archives

## [0.32.3] - 2022-05-12

### Fixed

- Fix creation of empty DataFrame for missing station ids
- Fix creation of empty DataFrame for annual data

## [0.32.2] - 2022-05-10

### Fixed

- Revert ssl option

## [0.32.1] - 2022-05-09

### Fixed

- Circumvent DWD server ssl certificate problem by temporary removing ssl verification

## [0.32.0] - 2022-04-24

### Added

- Add implementation of WSV Pegelonline service

### Changed

- Clean up code at several places

### Fixed

- Fix ECCC observations access

## [0.31.1] - 2022-04-03

### Fixed

- Change integer dtypes in untidy format to float to prevent loosing information when converting units

## [0.31.0] - 2022-03-29

### Changed

- Improve integrity of dataset, parameter and unit enumerations with further tests
- Change source of hourly sunshine duration to dataset sun
- Change source of hourly total cloud cover (+indicator) to dataset cloudiness

## [0.30.1] - 2022-03-03

### Fixed

- Fix naming of sun dataset
- Fix DWD Observation monthly test

## [0.30.0] - 2022-02-27

### Fixed

- Fix monthly/annual data of DWD observations

## [0.29.0] - 2022-02-27

### Added

- Add datasets EXTREME_WIND (subdaily) and MORE_WEATHER_PHENOMENA (daily)
- Add support for Python 3.10

### Changed

- Simplify parameters using only one enumeration for flattened and detailed parameters
- Rename dataset SUNSHINE_DURATION to SUN to avoid complications with similar named parameter and dataset
- Rename parameter VISIBILITY to VISIBILITY_RANGE

### Removed

- Drop Python 3.7 support

## [0.28.0] - 2022-02-19

### Added

- Extend explorer to use all implemented APIs

### Fixed

- Fix cli/restapi: return json and use NULL instead of NaN

## [0.27.0] - 2022-02-16

### Added

- Add support for Python 3.10

### Fixed

- Fix missing station ids within values result
- Add details about time interval for NOAA GHCN stations
- Fix falsely calculated station distances

### Removed

- Drop support for Python 3.7

## [0.26.0] - 2022-02-06

### Added

- Add Wetterdienst.Settings to manage general settings like tidy, humanize,...
- Instead of "kind" use "network" attribute to differ between different data products of a provider

### Changed

- Rename DWD forecast to mosmix

### Fixed

- Change data source of NOAA GHCN after problems with timeouts when reaching the server
- Fix problem with timezone conversion when having dates that are already timezone aware

## [0.25.1] - 2022-01-30

### Fixed

- Fix cli error with upgraded click ^8.0 where default False would be converted to "False"

## [0.25.0] - 2022-01-30

### Fixed

- Fix access to ECCC stations listing using Google Drive storage
- Remove/replace caching entirely by fsspec (+monkeypatch)
- Fix bug with DWD intervals

## [0.24.0] - 2022-01-24

### Added

- Add NOAA GHCN API

### Fixed

- Fix radar index by filtering out bz2 files

## [0.23.0] - 2021-11-21

### Fixed

- Add missing positional dataset argument for _create_empty_station_parameter_df
- Timestamps of 1 minute / 10 minutes DWD data now have a gap hour at the end of year 1999 due to timezone shifts

## [0.22.0] - 2021-10-01

### Added

- Introduce core Parameter enum with fixed set of parameter names. Several parameters may have been renamed!
- Add FSSPEC_CLIENT_KWARGS variable at wetterdienst.util.cache for passing extra settings to fsspec request client

## [0.21.0] - 2021-09-10

### Changed

- Start migrating from `dogpile.cache` to `filesystem_spec`

## [0.20.4] - 2021-08-07

### Added

- Enable selecting a parameter precisely from a dataset by passing a tuple like [("precipitation_height", "kl")]
  or [("precipitation_height", "precipitation_more")], or for cli/restapi use "precipitation_height/kl"
- Rename `wetterdienst show` to `wetterdienst info`, make version accessible via CLI with `wetterdienst version`

### Fixed

- Bug when querying an entire DWD dataset for 10_minutes/1_minute resolution without providing start_date/end_date,
  which results in the interval of the request being None
- Test of restapi with recent period
- Get rid of pandas performance warning from DWD Mosmix data

## [0.20.3] - 2021-07-15

### Fixed

- Bugfix acquisition of DWD radar data
- Adjust DWD radar composite parameters to new index

## [0.20.2] - 2021-06-26

### Fixed

- Bugfix tidy method for DWD observation data

## [0.20.1] - 2021-06-26

### Changed

- Update readme on sandbox developer installation

### Fixed

- Bugfix show method

## [0.20.0] - 2021-06-23

### Added

- Change cli base to click
- Add support for wetterdienst core API in cli and restapi
- Export: Use InfluxDBClient instead of DataFrameClient and improve connection handling with InfluxDB 1.x
- Export: Add support for InfluxDB 2.x
- Add show() method with basic information on the wetterdienst instance

### Fixed

- Fix InfluxDB export by skipping empty fields

## [0.19.0] - 2021-05-14

### Changed

- Make tidy method a abstract core method of Values class

### Fixed

- Fix DWD Mosmix generator to return all contained dataframes

## [0.18.0] - 2021-05-04

### Added

- Add origin and si unit mappings to services
- Use argument "si_units" in request classes to convert origin units to si, set to default
- Improve caching behaviour by introducing optional `WD_CACHE_DIR` and `WD_CACHE_DISABLE` environment variables. Thanks,
  @meteoDaniel!
- Add baseline test for ECCC observations
- Add DWD Observation hourly moisture to catalogue

## [0.17.0] - 2021-04-08

### Added

- Add capability to export data to Zarr format
- Add Wetterdienst Explorer UI. Thanks, @meteoDaniel!
- Add MAC ARM64 support with dependency restrictions
- Add support for stations filtering via bbox and name
- Add support for units in distance filtering

### Changed

- Rename station_name to name
- Rename filter methods to .filter_by_station_id and .filter_by_name, use same convention for bbox, filter_by_rank (
  previously nearby_number), filter_by_distance (nearby_distance)

### Fixed

- Radar: Verify HDF5 responses instead of returning invalid data
- Mosmix: Use cached stations to improve performance

## [0.16.1] - 2021-03-31

### Changed

- Make .discover return lowercase parameters and datasets

## [0.16.0] - 2021-03-29

### Added

- Add capability to export to Feather- and Parquet-files to I/O subsystem
- Add `--reload` parameter to `wetterdienst restapi` for supporting development
- Add Environment and Climate Change Canada API

### Changed

- Use direct mapping to get a parameter set for a parameter
- Rename DwdObservationParameterSet to DwdObservationDataset as well as corresponding columns
- Merge metadata access into Request
- Repair CLI and I/O subsystem
- Improve spreadsheet export
- Increase I/O subsystem test coverage
- Make all DWD observation field names lowercase
- Make all DWD forecast (mosmix) field names lowercase
- Rename humanize_parameters to humanize and tidy_data to tidy

### Deprecated

- Deprecate support for Python 3.6

### Fixed

- Radar: Use OPERA as data source for improved list of radar sites

## [0.15.0] - 2021-03-07

### Added

- Add StationsResult and ValuesResult to allow for new workflow and connect stations and values request
- Add accessor .values to Stations class to get straight to values for a request
- Add top-level API

### Fixed

- Fix issue with Mosmix station location

## [0.14.1] - 2021-02-21

### Fixed

- Fix date filtering of DWD observations, where accidentally an empty dataframe was returned

## [0.14.0] - 2021-02-05

### Added

- DWD: Add missing radar site "Emden" (EMD, wmo=10204)

### Changed

- Change key STATION_HEIGHT to HEIGHT, LAT to LATITUDE, LON to LONGITUDE
- Rename "Data" classes to "Values"
- Make arguments singular

### Fixed

- Mosmix stations: fix longitudes/latitudes to be decimal degrees (before they were degrees and minutes)

## [0.13.0] - 2021-01-21

### Added

- Create general Resolution and Period enumerations that can be used anywhere
- Create a full dataframe even if no values exist at requested time
- Add further attributes to the class structure
- Make dates timezone aware
- Restrict dates to isoformat

## [0.12.1] - 2020-12-29

### Fixed

- Fix 10minutes file index interval range by adding timezone information

## [0.12.0] - 2020-12-23

### Changed

- Move more functionality into core classes
- Add more attributes to the core e.g. source and timezone
- Make dates of internal data timezone aware, set start date and end date to UTC
- Add issue date to Mosmix class that actually refers to the Mosmix run instead of start date and end date
- Use Result object for every data related return
- In accordance with typical naming conventions, DWDObservationSites is renamed to DWDObservationStations, the same is
  applied to DWDMosmixSites
- The name ELEMENT is removed and replaced by parameter while the actual parameter set e.g. CLIMATE_SUMMARY is now found
  under PARAMETER_SET

### Removed

- Remove StorageAdapter and its dependencies
- Methods self.collect_data() and self.collect_safe() are replaced by self.query() and self.all() and will deprecate at
  some point

## [0.11.1] - 2020-12-10

### Fixed

- Bump `h5py` to version 3.1.0 in order to satisfy installation on Python 3.9

## [0.11.0] - 2020-12-04

### Added

- Upgrade Docker images to Python 3.8.6
- Radar data: Add non-RADOLAN data acquisition

### Changed

- Change wherever possible column type to category
- Increase efficiency by downloading only historical files with overlapping dates if start_date and end_date are given
- Use periods dynamically depending on start and end date

### Fixed

- InfluxDB export: Fix export in non-tidy format (#230). Thanks, @wetterfrosch!
- InfluxDB export: Use "quality" column as tag (#234). Thanks, @wetterfrosch!
- InfluxDB export: Use a batch size of 50000 to handle larger amounts of data (#235). Thanks, @wetterfrosch!
- Update radar examples to use `wradlib>=1.9.0`. Thanks, @kmuehlbauer!
- Fix inconsistency within 1 minute precipitation data where historical files have more columns
- Improve DWD PDF parser to extract quality information and select language. Also, add an example at
  `example/dwd_describe_fields.py` as well as respective documentation.
- Move intermediate storage of HDF out of data collection
- Fix bug with date filtering for empty/no station data for a given parameter

## [0.10.1] - 2020-11-14

### Fixed

- Upgrade to dateparser-1.0.0. Thanks, @steffen746, @noviluni and @Gallaecio! This fixes a problem with timezones on
  Windows. The reason is that Windows has no zoneinfo database and `tzlocal` switched from `pytz` to
  `tzinfo`. https://github.com/earthobservations/wetterdienst/issues/222

## [0.10.0] - 2020-10-26

### Added

- CLI: Obtain "--tidy" argument from command line
- Extend MOSMIX support to equal the API of observations
- DWDObservationData now also takes an individual parameter independent of the pre-configured DWD datasets by using
  DWDObservationParameter or similar names e.g. "precipitation_height"
- Newly introduced coexistence of DWDObservationParameter and DWDObservationParameterSet to address parameter sets as
  well as individual parameters

### Changed

- DWDObservationSites now filters for those stations which have a file on the server
- Imports are changed to submodule thus now one has to import everything from wetterdienst.dwd
- Renaming of time_resolution to resolution, period_type to period, several other relabels

## [0.9.0] - 2020-10-09

### Added

- Rename `DWDStationRequest` to `DWDObservationData`
- Add `DWDObservationSites` API wrapper to acquire station information
- Move `discover_climate_observations` to `DWDObservationMetadata.discover_parameters`
- Add PDF-based `DWDObservationMetadata.describe_fields()`

### Changed

- Large refactoring
- Make period type in DWDObservationData and cli optional
- Activate SQL querying again by using DuckDB 0.2.2.dev254. Thanks, @Mytherin!

### Fixed

- Fix coercion of integers with nans
- Fix problem with storing IntegerArrays in HDF

## [0.8.0] - 2020-09-25

### Added

- Add TTL-based persistent caching using dogpile.cache
- Add `example/radolan.py` and adjust documentation
- Export dataframe to different data sinks like SQLite, DuckDB, InfluxDB and CrateDB
- Query results with SQL, based on in-memory DuckDB
- Split get_nearby_stations into two functions, get_nearby_stations_by_number and get_nearby_stations_by_distance
- Add MOSMIX client and parser. Thanks, @jlewis91!
- Add basic HTTP API

## [0.7.0] - 2020-09-16

### Added

- Add test for Jupyter notebook
- Add function to discover available climate observations (time resolution, parameter, period type)
- Make the CLI work again and add software tests to prevent future havocs
- Use Sphinx Material theme for documentation

### Fixed

- Fix typo in enumeration for TimeResolution.MINUTES_10

## [0.6.0] - 2020-09-07

### Changed

- Enhance usage of get_nearby_stations to check for availability
- Output of get_nearby_stations is now a slice of meta_data DataFrame output

## [0.5.0] - 2020-08-27

### Added

- Add RADOLAN support
- Change module and function naming in accordance with RADOLAN

## [0.4.0] - 2020-08-03

### Added

- Extend DWDObservationData to take multiple parameters as request
- Add documentation at readthedocs.io
- \[cli\] Adjust methods to work with multiple parameters

## [0.3.0] - 2020-07-26

### Added

- Add option for data collection to tidy the DataFrame (properly reshape) with the "tidy_data" keyword and set it to be
  used as default

### Changed

- Establish code style black
- Setup nox session that can be used to run black via nox -s black for one of the supported Python versions

### Fixed

- Fix integer type casting for cases with nans in the column/series
- Fix humanizing of column names for tidy data

## [0.2.0] - 2020-07-23

### Added

- \[cli\] Add geospatial filtering by distance.
- \[cli\] Filter stations by station identifiers.
- \[cli\] Add GeoJSON output format for station data.
- Improvements to parsing high resolution data by setting specific datetime formats and changing to concurrent.futures

### Changed

- Change column name mapping to more explicit one with columns being individually addressable
- Add full column names for every individual parameter
- More specific type casting for integer fields and string fields

### Fixed

- Fix na value detection for cases where cells have leading and trailing whitespace

## [0.1.1] - 2020-07-05

### Added

- \[cli\] Add geospatial filtering by number of nearby stations.
- Simplify release pipeline
- Small updates to readme

### Changed

- Parameter, time resolution and period type can now also be passed as strings of the enumerations e.g. "
  climate_summary" or "CLIMATE_SUMMARY" for Parameter.CLIMATE_SUMMARY
- Enable selecting nearby stations by distance rather than by number of stations

### Fixed

- Change updating "parallel" argument to be done after parameter parsing to prevent mistakenly not found parameter
- Remove find_all_match_strings function and extract functionality to individual operations

## [0.1.0] - 2020-07-02

### Added

- Initial release
- Update README.md
- Update example notebook
- Add Gh Action for release
- Rename library

[Unreleased]: https://github.com/earthobservations/wetterdienst/compare/v0.134.0...HEAD
[0.134.0]: https://github.com/earthobservations/wetterdienst/compare/v0.133.0...v0.134.0
[0.133.0]: https://github.com/earthobservations/wetterdienst/compare/v0.132.0...v0.133.0
[0.132.0]: https://github.com/earthobservations/wetterdienst/compare/v0.131.0...v0.132.0
[0.131.0]: https://github.com/earthobservations/wetterdienst/compare/v0.130.0...v0.131.0
[0.130.0]: https://github.com/earthobservations/wetterdienst/compare/v0.129.0...v0.130.0
[0.129.0]: https://github.com/earthobservations/wetterdienst/compare/v0.128.0...v0.129.0
[0.128.0]: https://github.com/earthobservations/wetterdienst/compare/v0.127.0...v0.128.0
[0.127.0]: https://github.com/earthobservations/wetterdienst/compare/v0.126.0...v0.127.0
[0.126.0]: https://github.com/earthobservations/wetterdienst/compare/v0.125.0...v0.126.0
[0.125.0]: https://github.com/earthobservations/wetterdienst/compare/v0.124.0...v0.125.0
[0.124.0]: https://github.com/earthobservations/wetterdienst/compare/v0.123.0...v0.124.0
[0.123.0]: https://github.com/earthobservations/wetterdienst/compare/v0.122.0...v0.123.0
[0.122.0]: https://github.com/earthobservations/wetterdienst/compare/v0.121.1...v0.122.0
[0.121.1]: https://github.com/earthobservations/wetterdienst/compare/v0.121.0...v0.121.1
[0.121.0]: https://github.com/earthobservations/wetterdienst/compare/v0.120.0...v0.121.0
[0.120.0]: https://github.com/earthobservations/wetterdienst/compare/v0.119.0...v0.120.0
[0.119.0]: https://github.com/earthobservations/wetterdienst/compare/v0.118.0...v0.119.0
[0.118.0]: https://github.com/earthobservations/wetterdienst/compare/v0.117.0...v0.118.0
[0.117.0]: https://github.com/earthobservations/wetterdienst/compare/v0.116.0...v0.117.0
[0.116.0]: https://github.com/earthobservations/wetterdienst/compare/v0.115.0...v0.116.0
[0.115.0]: https://github.com/earthobservations/wetterdienst/compare/v0.114.3...v0.115.0
[0.114.3]: https://github.com/earthobservations/wetterdienst/compare/v0.114.2...v0.114.3
[0.114.2]: https://github.com/earthobservations/wetterdienst/compare/v0.114.1...v0.114.2
[0.114.1]: https://github.com/earthobservations/wetterdienst/compare/v0.114.0...v0.114.1
[0.114.0]: https://github.com/earthobservations/wetterdienst/compare/v0.113.0...v0.114.0
[0.113.0]: https://github.com/earthobservations/wetterdienst/compare/v0.112.0...v0.113.0
[0.112.0]: https://github.com/earthobservations/wetterdienst/compare/v0.111.0...v0.112.0
[0.111.0]: https://github.com/earthobservations/wetterdienst/compare/v0.110.0...v0.111.0
[0.110.0]: https://github.com/earthobservations/wetterdienst/compare/v0.109.0...v0.110.0
[0.109.0]: https://github.com/earthobservations/wetterdienst/compare/v0.108.0...v0.109.0
[0.108.0]: https://github.com/earthobservations/wetterdienst/compare/v0.107.0...v0.108.0
[0.107.0]: https://github.com/earthobservations/wetterdienst/compare/v0.106.0...v0.107.0
[0.106.0]: https://github.com/earthobservations/wetterdienst/compare/v0.105.0...v0.106.0
[0.105.0]: https://github.com/earthobservations/wetterdienst/compare/v0.104.0...v0.105.0
[0.104.0]: https://github.com/earthobservations/wetterdienst/compare/v0.103.0...v0.104.0
[0.103.0]: https://github.com/earthobservations/wetterdienst/compare/v0.102.0...v0.103.0
[0.102.0]: https://github.com/earthobservations/wetterdienst/compare/v0.101.0...v0.102.0
[0.101.0]: https://github.com/earthobservations/wetterdienst/compare/v0.100.0...v0.101.0
[0.100.0]: https://github.com/earthobservations/wetterdienst/compare/v0.99.0...v0.100.0
[0.99.0]: https://github.com/earthobservations/wetterdienst/compare/v0.98.0...v0.99.0
[0.98.0]: https://github.com/earthobservations/wetterdienst/compare/v0.97.0...v0.98.0
[0.97.0]: https://github.com/earthobservations/wetterdienst/compare/v0.96.0...v0.97.0
[0.96.0]: https://github.com/earthobservations/wetterdienst/compare/v0.95.1...v0.96.0
[0.95.1]: https://github.com/earthobservations/wetterdienst/compare/v0.95.0...v0.95.1
[0.95.0]: https://github.com/earthobservations/wetterdienst/compare/v0.94.0...v0.95.0
[0.94.0]: https://github.com/earthobservations/wetterdienst/compare/v0.93.0...v0.94.0
[0.93.0]: https://github.com/earthobservations/wetterdienst/compare/v0.92.0...v0.93.0
[0.92.0]: https://github.com/earthobservations/wetterdienst/compare/v0.91.0...v0.92.0
[0.91.0]: https://github.com/earthobservations/wetterdienst/compare/v0.90.0...v0.91.0
[0.90.0]: https://github.com/earthobservations/wetterdienst/compare/v0.89.0...v0.90.0
[0.89.0]: https://github.com/earthobservations/wetterdienst/compare/v0.88.0...v0.89.0
[0.88.0]: https://github.com/earthobservations/wetterdienst/compare/v0.87.0...v0.88.0
[0.87.0]: https://github.com/earthobservations/wetterdienst/compare/v0.86.0...v0.87.0
[0.86.0]: https://github.com/earthobservations/wetterdienst/compare/v0.85.0...v0.86.0
[0.85.0]: https://github.com/earthobservations/wetterdienst/compare/v0.84.0...v0.85.0
[0.84.0]: https://github.com/earthobservations/wetterdienst/compare/v0.83.0...v0.84.0
[0.83.0]: https://github.com/earthobservations/wetterdienst/compare/v0.82.0...v0.83.0
[0.82.0]: https://github.com/earthobservations/wetterdienst/compare/v0.81.0...v0.82.0
[0.81.0]: https://github.com/earthobservations/wetterdienst/compare/v0.80.0...v0.81.0
[0.80.0]: https://github.com/earthobservations/wetterdienst/compare/v0.79.0...v0.80.0
[0.79.0]: https://github.com/earthobservations/wetterdienst/compare/v0.78.0...v0.79.0
[0.78.0]: https://github.com/earthobservations/wetterdienst/compare/v0.77.1...v0.78.0
[0.77.1]: https://github.com/earthobservations/wetterdienst/compare/v0.77.0...v0.77.1
[0.77.0]: https://github.com/earthobservations/wetterdienst/compare/v0.76.1...v0.77.0
[0.76.1]: https://github.com/earthobservations/wetterdienst/compare/v0.76.0...v0.76.1
[0.76.0]: https://github.com/earthobservations/wetterdienst/compare/v0.75.0...v0.76.0
[0.75.0]: https://github.com/earthobservations/wetterdienst/compare/v0.74.0...v0.75.0
[0.74.0]: https://github.com/earthobservations/wetterdienst/compare/v0.73.0...v0.74.0
[0.73.0]: https://github.com/earthobservations/wetterdienst/compare/v0.72.0...v0.73.0
[0.72.0]: https://github.com/earthobservations/wetterdienst/compare/v0.71.0...v0.72.0
[0.71.0]: https://github.com/earthobservations/wetterdienst/compare/v0.70.0...v0.71.0
[0.70.0]: https://github.com/earthobservations/wetterdienst/compare/v0.69.0...v0.70.0
[0.69.0]: https://github.com/earthobservations/wetterdienst/compare/v0.68.0...v0.69.0
[0.68.0]: https://github.com/earthobservations/wetterdienst/compare/v0.67.0...v0.68.0
[0.67.0]: https://github.com/earthobservations/wetterdienst/compare/v0.66.1...v0.67.0
[0.66.1]: https://github.com/earthobservations/wetterdienst/compare/v0.66.0...v0.66.1
[0.66.0]: https://github.com/earthobservations/wetterdienst/compare/v0.65.0...v0.66.0
[0.65.0]: https://github.com/earthobservations/wetterdienst/compare/v0.64.0...v0.65.0
[0.64.0]: https://github.com/earthobservations/wetterdienst/compare/v0.63.0...v0.64.0
[0.63.0]: https://github.com/earthobservations/wetterdienst/compare/v0.62.0...v0.63.0
[0.62.0]: https://github.com/earthobservations/wetterdienst/compare/v0.61.0...v0.62.0
[0.61.0]: https://github.com/earthobservations/wetterdienst/compare/v0.60.0...v0.61.0
[0.60.0]: https://github.com/earthobservations/wetterdienst/compare/v0.59.3...v0.60.0
[0.59.3]: https://github.com/earthobservations/wetterdienst/compare/v0.59.2...v0.59.3
[0.59.2]: https://github.com/earthobservations/wetterdienst/compare/v0.59.1...v0.59.2
[0.59.1]: https://github.com/earthobservations/wetterdienst/compare/v0.59.0...v0.59.1
[0.59.0]: https://github.com/earthobservations/wetterdienst/compare/v0.58.1...v0.59.0
[0.58.1]: https://github.com/earthobservations/wetterdienst/compare/v0.58.0...v0.58.1
[0.58.0]: https://github.com/earthobservations/wetterdienst/compare/v0.57.1...v0.58.0
[0.57.1]: https://github.com/earthobservations/wetterdienst/compare/v0.57.0...v0.57.1
[0.57.0]: https://github.com/earthobservations/wetterdienst/compare/v0.56.2...v0.57.0
[0.56.2]: https://github.com/earthobservations/wetterdienst/compare/v0.56.1...v0.56.2
[0.56.1]: https://github.com/earthobservations/wetterdienst/compare/v0.56.0...v0.56.1
[0.56.0]: https://github.com/earthobservations/wetterdienst/compare/v0.55.2...v0.56.0
[0.55.2]: https://github.com/earthobservations/wetterdienst/compare/v0.55.1...v0.55.2
[0.55.1]: https://github.com/earthobservations/wetterdienst/compare/v0.55.0...v0.55.1
[0.55.0]: https://github.com/earthobservations/wetterdienst/compare/v0.54.1...v0.55.0
[0.54.1]: https://github.com/earthobservations/wetterdienst/compare/v0.54.0...v0.54.1
[0.54.0]: https://github.com/earthobservations/wetterdienst/compare/v0.53.0...v0.54.0
[0.53.0]: https://github.com/earthobservations/wetterdienst/compare/v0.52.0...v0.53.0
[0.52.0]: https://github.com/earthobservations/wetterdienst/compare/v0.51.0...v0.52.0
[0.51.0]: https://github.com/earthobservations/wetterdienst/compare/v0.50.0...v0.51.0
[0.50.0]: https://github.com/earthobservations/wetterdienst/compare/v0.49.0...v0.50.0
[0.49.0]: https://github.com/earthobservations/wetterdienst/compare/v0.48.0...v0.49.0
[0.48.0]: https://github.com/earthobservations/wetterdienst/compare/v0.47.1...v0.48.0
[0.47.1]: https://github.com/earthobservations/wetterdienst/compare/v0.47.0...v0.47.1
[0.47.0]: https://github.com/earthobservations/wetterdienst/compare/v0.46.0...v0.47.0
[0.46.0]: https://github.com/earthobservations/wetterdienst/compare/v0.45.2...v0.46.0
[0.45.2]: https://github.com/earthobservations/wetterdienst/compare/v0.45.1...v0.45.2
[0.45.1]: https://github.com/earthobservations/wetterdienst/compare/v0.45.0...v0.45.1
[0.45.0]: https://github.com/earthobservations/wetterdienst/compare/v0.44.0...v0.45.0
[0.44.0]: https://github.com/earthobservations/wetterdienst/compare/v0.43.0...v0.44.0
[0.43.0]: https://github.com/earthobservations/wetterdienst/compare/v0.42.1...v0.43.0
[0.42.1]: https://github.com/earthobservations/wetterdienst/compare/v0.42.0...v0.42.1
[0.42.0]: https://github.com/earthobservations/wetterdienst/compare/v0.41.1...v0.42.0
[0.41.1]: https://github.com/earthobservations/wetterdienst/compare/v0.41.0...v0.41.1
[0.41.0]: https://github.com/earthobservations/wetterdienst/compare/v0.40.0...v0.41.0
[0.40.0]: https://github.com/earthobservations/wetterdienst/compare/v0.39.0...v0.40.0
[0.39.0]: https://github.com/earthobservations/wetterdienst/compare/v0.38.0...v0.39.0
[0.38.0]: https://github.com/earthobservations/wetterdienst/compare/v0.37.0...v0.38.0
[0.37.0]: https://github.com/earthobservations/wetterdienst/compare/v0.36.0...v0.37.0
[0.36.0]: https://github.com/earthobservations/wetterdienst/compare/v0.35.0...v0.36.0
[0.35.0]: https://github.com/earthobservations/wetterdienst/compare/v0.34.0...v0.35.0
[0.34.0]: https://github.com/earthobservations/wetterdienst/compare/v0.33.0...v0.34.0
[0.33.0]: https://github.com/earthobservations/wetterdienst/compare/v0.32.4...v0.33.0
[0.32.4]: https://github.com/earthobservations/wetterdienst/compare/v0.32.3...v0.32.4
[0.32.3]: https://github.com/earthobservations/wetterdienst/compare/v0.32.2...v0.32.3
[0.32.2]: https://github.com/earthobservations/wetterdienst/compare/v0.32.1...v0.32.2
[0.32.1]: https://github.com/earthobservations/wetterdienst/compare/v0.32.0...v0.32.1
[0.32.0]: https://github.com/earthobservations/wetterdienst/compare/v0.31.1...v0.32.0
[0.31.1]: https://github.com/earthobservations/wetterdienst/compare/v0.31.0...v0.31.1
[0.31.0]: https://github.com/earthobservations/wetterdienst/compare/v0.30.1...v0.31.0
[0.30.1]: https://github.com/earthobservations/wetterdienst/compare/v0.30.0...v0.30.1
[0.30.0]: https://github.com/earthobservations/wetterdienst/compare/v0.29.0...v0.30.0
[0.29.0]: https://github.com/earthobservations/wetterdienst/compare/v0.28.0...v0.29.0
[0.28.0]: https://github.com/earthobservations/wetterdienst/compare/v0.27.0...v0.28.0
[0.27.0]: https://github.com/earthobservations/wetterdienst/compare/v0.26.0...v0.27.0
[0.26.0]: https://github.com/earthobservations/wetterdienst/compare/v0.25.1...v0.26.0
[0.25.1]: https://github.com/earthobservations/wetterdienst/compare/v0.25.0...v0.25.1
[0.25.0]: https://github.com/earthobservations/wetterdienst/compare/v0.24.0...v0.25.0
[0.24.0]: https://github.com/earthobservations/wetterdienst/compare/v0.23.0...v0.24.0
[0.23.0]: https://github.com/earthobservations/wetterdienst/compare/v0.22.0...v0.23.0
[0.22.0]: https://github.com/earthobservations/wetterdienst/compare/v0.21.0...v0.22.0
[0.21.0]: https://github.com/earthobservations/wetterdienst/compare/v0.20.4...v0.21.0
[0.20.4]: https://github.com/earthobservations/wetterdienst/compare/v0.20.3...v0.20.4
[0.20.3]: https://github.com/earthobservations/wetterdienst/compare/v0.20.2...v0.20.3
[0.20.2]: https://github.com/earthobservations/wetterdienst/compare/v0.20.1...v0.20.2
[0.20.1]: https://github.com/earthobservations/wetterdienst/compare/v0.20.0...v0.20.1
[0.20.0]: https://github.com/earthobservations/wetterdienst/compare/v0.19.0...v0.20.0
[0.19.0]: https://github.com/earthobservations/wetterdienst/compare/v0.18.0...v0.19.0
[0.18.0]: https://github.com/earthobservations/wetterdienst/compare/v0.17.0...v0.18.0
[0.17.0]: https://github.com/earthobservations/wetterdienst/compare/v0.16.1...v0.17.0
[0.16.1]: https://github.com/earthobservations/wetterdienst/compare/v0.16.0...v0.16.1
[0.16.0]: https://github.com/earthobservations/wetterdienst/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/earthobservations/wetterdienst/compare/v0.14.1...v0.15.0
[0.14.1]: https://github.com/earthobservations/wetterdienst/compare/v0.14.0...v0.14.1
[0.14.0]: https://github.com/earthobservations/wetterdienst/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/earthobservations/wetterdienst/compare/v0.12.1...v0.13.0
[0.12.1]: https://github.com/earthobservations/wetterdienst/compare/v0.12.0...v0.12.1
[0.12.0]: https://github.com/earthobservations/wetterdienst/compare/v0.11.1...v0.12.0
[0.11.1]: https://github.com/earthobservations/wetterdienst/compare/v0.11.0...v0.11.1
[0.11.0]: https://github.com/earthobservations/wetterdienst/compare/v0.10.1...v0.11.0
[0.10.1]: https://github.com/earthobservations/wetterdienst/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/earthobservations/wetterdienst/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/earthobservations/wetterdienst/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/earthobservations/wetterdienst/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/earthobservations/wetterdienst/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/earthobservations/wetterdienst/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/earthobservations/wetterdienst/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/earthobservations/wetterdienst/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/earthobservations/wetterdienst/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/earthobservations/wetterdienst/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/earthobservations/wetterdienst/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/earthobservations/wetterdienst/releases/tag/v0.1.0

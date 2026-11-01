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

- A Parquet file, a NetCDF file and a Zarr group written by `to_target` carry the licence, the credit
  line and the date of the data: the `metadata` block of the REST API, as JSON under
  `wetterdienst_metadata` and as `license`, `attribution`, `retrieved_at` and more, in Parquet's
  key-value metadata and in the attributes of the group. CSV, spreadsheets, JSON, JSON Lines,
  GeoJSON and Feather files stay bare; `to_target(..., with_metadata=True)` and `to_csv(file=...,
  with_metadata=True)` write the block beside them as `<file>.metadata.json`, and add the units and
  the quality legend to the three that carry it. A database target refuses `with_metadata` (GH-3449)
- `dmi/observation` now serves five more DMI parameters under new names: `snow_cover` (daily,
  2011-01-01 to 2015-11-21 only; percent, returned as a decimal), `leaf_wetness_duration` (minutes,
  returned in seconds), `temperature_air_mean_grass_height` (5 to 20 cm above ground) and
  `vapor_pressure_deficit_mean` (kPa, returned in hPa), hourly and daily, and
  `temperature_soil_mean_0_3m`, daily only. The daily leaf wetness is the minutes of the day (0 to
  1440), not the average of the hourly values the source's table names. The library holds none of
  the five to a range, so the impossible values DMI writes for some days and hours are kept
  (Part of GH-3622)
- `FormattableResult` (`wetterdienst.model.result`) is a `typing.Protocol` of `to_dict`,
  `to_json` and `to_format` that the five results and the alerts result satisfy, so one function
  can write them all. `HistoryResult` gets `to_format`, for JSON only: any other format, CSV
  included, is an `UnknownFormatError` naming `json`. The alerts result of `dwd/alerts` takes the
  format in any case (`to_format("JSON")`, refused before), `indent` as a number or a flag in
  `to_json`, `to_geojson` and `to_format` (`indent=0` now breaks lines without indenting, as on
  the others), and `with_metadata` (the block of the others); its default stays one line. It is
  outside the frozen results (GH-3449)
- `wetterdienst stations`, `values`, `interpolate` and `summarize` pass `--with-metadata` to
  `--target`, as `to_target(..., with_metadata=True)` takes it: a file `<file>.metadata.json`
  beside a CSV, spreadsheet, JSON, JSON Lines, GeoJSON or Feather file, and the units and the
  quality legend in the block of a Parquet, NetCDF or Zarr file. With a database target it is now
  refused with the library's message and exit code 1, before anything is written, where the flag
  was ignored and the table written: leave it out for a database target (GH-3704)

### Changed

- **Breaking**: 5 more `noaa/ghcn` hourly stations are placed west of Greenwich, no longer east
  of it, where `ghcnh-station-list.csv` has lost the sign of their longitude: Freetown in Sierra
  Leone (CMU55-00161), Surtsey (ICM00004102), Buhta Providenja (RSU025594-5), Calanda
  (SPM00008166) and Kilo Nalu off Oahu (USL000KNOH1). They were 40 to 4,571 km off, so a
  nearest-station search or a distance filter near them picked the wrong stations; a filter on
  the old position needs the new one. A row is turned only while it lists the position that was
  checked, so a list NOAA corrects is read as it is (GH-2886)

### Fixed

- `to_json`, `to_geojson`, the `.geojson` file target and the JSON, GeoJSON and NDJSON answers of
  the REST API, the command line and MCP write a `NaN` or an infinity as `null`, as polars does
  for `to_ndjson` and the `.json`, `.jsonl` and `.ndjson` files. They wrote the bare tokens `NaN`,
  `Infinity` and `-Infinity`, which are not JSON and which `JSON.parse` and other strict parsers
  refuse. A station whose longitude or latitude is not finite has no position in GeoJSON, and one
  whose elevation is not finite no z. `to_dict` still returns the float (GH-3679)
- Writing a frame with a `pl.Categorical` column to a `.zarr` or `.nc` target no longer fails with
  `Cannot interpret 'CategoricalDtype(...)' as a data type`; the column is written as text, as a
  `pl.Enum` column was (GH-3679)
- A `file://` target is matched to its file type by the path it names, decoded. A query string
  was never ignored: everything after `file://` is the path, so `file:///x.csv?a=1` names a file
  `x.csv?a=1` and is refused as an unknown file type, which the message now explains and names
  `%3F` as the way to write a `?` that belongs to the file name (GH-3679)
- The `missing-value-marker` warning no longer counts the values a hard plausibility check
  rejected (`rejected:<check>,raw:<number>`): the source wrote a number there, not a marker.
  They are told by a new warning `rejected-by-plausibility`, with the count per check; a value
  that several checks rejected is counted under each. A client that summed the old count to
  find the rejected values reads the new warning instead (GH-3682)
- `wetterdienst history --target` accepts a file name ending in `.JSON` or any other case of
  `.json`, as `values` and `stations` do; it refused all but the lowercase one (GH-3693)
- The CrateDB and SQL (SQLAlchemy) targets hand the database a `pl.Categorical` column as text, as
  they did a `pl.Enum` column, not as a pandas Categorical. SQLite and DuckDB wrote the text
  either way; the dialects that could not be tried are no longer left to read a Categorical
  (GH-3694)

## [0.180.0] - 2026-11-01

### Added

- The option `plausibility` sets what each plausibility check (`range`, `elevation`, `stuck`,
  `consistency`, `floor`) does to a number it finds implausible: `hard` nulls it and keeps the
  number as `rejected:<check>,raw:<number>` in `quality_flags`, `soft` keeps it and flags it
  `suspect:<check>`. Set it with `Options(plausibility={"range": "soft"})`,
  `WD_TS_PLAUSIBILITY__RANGE`, `--plausibility-range` or `plausibility_range` (REST, MCP), or
  `plausibility="soft"`, `WD_TS_PLAUSIBILITY=soft`, `--plausibility soft` and `plausibility=soft`
  for every check at once (a check named beside it wins). Interpolation, summary and climate
  stripes always leave out a suspect value, and `skip_empty` counts the unflagged values alone
  (GH-3676)
- `dmi/observation` now serves the highest and lowest pressure at sea level of the day, month and
  year (new `pressure_air_sea_level_max`/`_min`; 45 stations, 38 in Greenland), the monthly and
  annual summer days and tropical nights (`count_days_summer`, `count_days_tropical_night`) and
  the heating degree days of Greenland, as `heating_degree_day` beside Denmark's: the base is 17 °C
  in Denmark and 19 °C in Greenland. DMI counts the days above 25 and 20 °C, so a day at exactly
  25.0 or 20.0 °C is not counted, where the names count from the threshold (Part of GH-3622)
- `wetterdienst.exceptions.UnknownFormatError` is what `to_format`, the charts' `to_image` and the
  alerts result's `to_format` raise for a format they do not render, naming it and listing the
  supported ones. It is a `RequestError`, and a `KeyError` as `to_format` raised and a `ValueError`
  as the alerts result did, so an `except KeyError` or `except ValueError` still catches it; the
  REST API and the command line never reach it, as their `format` is a choice (GH-3449)
- `dmi/observation` now serves the global radiation of the day, month and year as `radiation_global`
  (DMI publishes MJ/m²; it comes back in J/cm² by default), eight counts of days with DMI's own
  thresholds (new `count_days_temperature_air_min_2m_lt_minus_10c`,
  `count_days_wind_speed_rolling_mean_max_ge_10_8mps` and `_20_8`, `_24_5`, `_28_5`,
  `count_days_cloud_cover_total_mean_lt_20pct`/`_gt_80pct`, `count_days_snow_cover_gt_50pct`, 2011
  to 2015 only), the mean vapour pressure, the greatest snow depth, the 12 and 24 hour extremes and
  precipitation (stamped at the end of their window) and the soil temperature at 10 cm. A greatest
  snow depth of 999.0 is null (`raw:999`) and the trace code −0.1 of the 12 and 24 hour
  precipitation is 0.0 with `raw:-0.1` (Part of GH-3622)
- `ndjson` is a format of `to_format`, with a new `to_ndjson()` on the results: the rows, one JSON
  object per line, no envelope, what the `.jsonl` file holds and the records of the lines the REST
  API and the command line send between their `metadata` and `end` lines (which stay as they are;
  a number may be written `0.00005` here and `5e-05` there). `.ndjson` is a second extension of
  that file target, and `.geojson` a new one that writes the feature collection of `to_geojson`,
  without the `{"data": ...}` it wraps it in (GH-3449)

### Changed

- **Breaking**: `quality_flags` gain the tokens `suspect:<check>` and `rejected:<check>` before
  `raw:`. A number a check rejected is `rejected:range,raw:4021` where it was `raw:4021`, so `raw:`
  alone is now a code of the source; `str.replace(r"rejected:[a-z+]+,", "")` gives the old string
  (GH-3676)
- **Breaking**: the `stuck` check is soft by default: `rmi/observation` (the sunshine of station
  6477 in its dead periods), which was null, keeps its values as `suspect:stuck`, and so does
  `dwd/road` (a stopped sensor, once quality `1`) beside DWD's own flag; as that is a suspect
  value, `skip_empty` no longer counts it, so a road station with long stuck runs can be skipped
  where it was kept. For the null again, set `stuck` to hard: `plausibility={"stuck": "hard"}`,
  `WD_TS_PLAUSIBILITY__STUCK=hard`, `--plausibility-stuck hard` or `plausibility_stuck=hard`
  (GH-3676)
- **Breaking**: the constant pressure of `dwd/observation` is a run of identical readings, not a
  file of at most three values, and soft like the other `stuck` verdicts (`suspect:stuck`, null
  with `stuck` hard): 72 hourly readings, 5 days or 36 readings at 10 minutes of one
  `pressure_air_site` or `pressure_air_site_mean` (HadISD, ECA&D; the 36 is derived, not
  published), in the series of the periods read, a gap of more than four times the interval ending
  a run. A constant stretch below the run is no longer flagged, and the check now also covers the
  hourly `pressure` and `urban_pressure`, the 10-minute `temperature_air` and `urban_pressure` and
  the daily `climate_summary` (GH-3676)
- **Breaking**: a Zarr file (`file://x.zarr`) holds a gap as `NaN`, and a missing time as `NaT`,
  where it held -999 (an integer column with a gap is now a float one). It read as a measurement:
  an air temperature of -999 degrees, a station 999 m below the sea. A reader that tested for -999
  tests for `NaN` (`np.isnan`, or `xarray`'s `.isnull()`), as for NetCDF; with pandas 3 a frame
  with a missing time, such as stations that have not ended, could not be written to Zarr and now
  can (GH-3449)
- **Breaking**: 7 `noaa/ghcn` stations are placed south of the equator, no longer north of it,
  where the lists have lost the sign of their latitude: Lambarene and Lastoursville in Gabon
  (GB000004551, GB000004560) in `ghcnd-stations.txt`; Adelaide (ASU34-00001), Halley in
  Antarctica (GLUHALLEY-2, -3, -4) and Nuku'alofa (TNU55-00239) in `ghcnh-station-list.csv`.
  They were 160 to 16,800 km off, so a nearest-station search or a distance filter near them
  picked the wrong stations; a filter on the old position needs the new one. A row is turned only
  while it lists the position that was checked, so a list NOAA corrects is read as it is
  (GH-3662)
- **Breaking**: `to_format` refuses an argument that no format takes, with a `TypeError` listing
  the ones that are (`with_metadata`, `with_stations`, `indent`, `width`, `height`, `scale`,
  `max_side`), where it dropped it: `to_format("csv", separator=";")` wrote a comma CSV and said
  nothing. An argument that another format takes is still dropped, so the one set the command line,
  the REST API and MCP build is unaffected; pass `to_csv(separator=";")` to give polars an argument
  (GH-3449)
- **Breaking**: `dwd/road` returns null, with the number DWD wrote as the last token of
  `quality_flags` (`rejected:range,raw:0.1`), for a `humidity_relative` below 1 % and for a
  `temperature_surface` more than 20 K above the `temperature_air` of the same minute with the sun
  more than 6 degrees below the horizon (`rejected:consistency,raw:338.75`, in K); both came back as
  published, among them a surface of 61 to 75 °C at night. Read the old number from `raw:`. The
  other road readings stay raw data apart from the values outside their range, as the docs now say
  (GH-3624)
- **Breaking**: 5 `noaa/ghcn` hourly stations are placed west of Greenwich, no longer east of it,
  where `ghcnh-station-list.csv` has lost the sign of their longitude: Nemours/Ghazaouet
  (AGUG0060517), Khouribga military airport (MOI0000GMMK), Alcaniz, Bujaraloz and Oliva
  (SPM00008164, -8165, -8282). They were 16 to 1,299 km off, so a nearest-station search or a
  distance filter near them picked the wrong stations; a filter on the old position needs the new
  one (GH-2886)
- **Breaking**: `dwd/observation` `pressure_air_site` and `pressure_air_site_mean` (the hourly
  `P0` and `P_STD`, the subdaily and 10 minute station pressure, the urban station pressure
  `LUFTDRUCK_STATIONSHOEHE` and `P0_ST_10`, the daily mean `PM`) and `meteofrance/synop` `pres` are
  null, with the number the source wrote as `rejected:elevation,raw:` in `quality_flags`, where
  they are more than 75 hPa (7,500 Pa) from the pressure the standard atmosphere expects at the
  station's elevation:
  909.5 hPa at Berlin-Tempelhof (48 m) and 968.6 hPa at the Zugspitze (2,956 m, where 705 hPa are
  expected) came back as readings. The old number is the `raw:` token; a station without an
  elevation in the list is held to the world-wide bounds as before (500 to 1090 hPa, 1100 for
  synop) (GH-3627)
- **Breaking**: `meteofrance/observation` (hourly `U`) and `meteofrance/synop` (`u`): at the
  stations without frost, the relative humidity of a row with a dew point below 0 °C is null too,
  with its number as `rejected:consistency,raw:`, where it came back as 1 to 20 % beside a dew point
  of -20 C, the same failed hygrometer. A humidity beside a dew point that is a reading stays, low
  as it is. The old number is the `raw:` token (GH-3629)
- **Breaking**: `dwd/dmo` `radiation_global` (`rad1h`) and `radiation_short_wave_net_last_3h`
  (`rads3`) are 0.0 where ICON writes a little below 0 at night (to -0.77 and -0.46 J/cm2), with
  the number kept as `rejected:floor,raw:-0.16` in `quality_flags`; they were negative, and a
  `-0.00` was `-0.0`. `rr1` and `rr3` already did this. Nothing to change in a caller; filter on
  `raw:` for the old numbers (GH-3263)

### Fixed

- File extensions of `to_target` are read in any case: `file://x.CSV` was refused as an unknown
  file type, the path is kept as written (GH-3449)
- `to_target("influxdb://…")` of a frame with no `timestamp`, `station_id`, `resolution` or
  `dataset`, such as the stations, is refused with an `ExportRefusedError` naming what is missing,
  before the client is built, where it failed with a bare `KeyError('timestamp')` (GH-3449)
- `ImageTooLargeError` pickles: it failed with a `TypeError` on unpickling, which broke it for
  a caller that passes it across processes (multiprocessing, `ProcessPoolExecutor`). Its size, its limit and any notes now
  come through the copy (GH-3673)
- `noaa/ghcn` daily: a direction of the fastest or peak wind of 0 beside a speed of exactly 0
  (`wind_direction_gust_max` and its `_1min`, `_2min`, `_5sec`, `_instant`, `_1mile`) is null, with
  `raw:0` in `quality_flags`, where it came back as north. The files write that 0 for a day
  without a direction (1,798 of 1,799 in `wind_direction_gust_max` of 9 stations); a 0 beside a
  wind that blows stays (GH-3648)
- `noaa/ghcn` daily: `wind_gust_max` of 0 with source flag `C` (Environment Canada) is null, with
  `raw:0` in `quality_flags`, where it came back as a peak gust of 0.0 m/s. Environment Canada
  does not report a gust below 31 km/h and the files write 0 for it; a 0 of another source stays
  (GH-3655)
- `dwd/phenology`: 304 of the 404 parameter descriptions now carry DWD's definition of the phase,
  where they gave its name only: the share of the flowers, ears, stems or plants that decides the
  date, pollen release as the flowering of hazel, birch, spruce and others.
  `phenology_heading_beginning` was "the first ears" (DWD: about half of the stems),
  `phenology_harvest_by_hand` begins with a scythe or simple machine, and
  `phenology_emergence_beginning` no longer says "first seedlings" (GH-3136)
- Dataset and resolution descriptions that stated a wrong fact now follow their source:
  `dwd/observation` `annual/climate_summary` no longer lists air pressure (it has none), the
  `subdaily` datasets are no longer "recent" only (they have a historical period), the `subdaily`
  resolution gives DWD's observation hours by date (07, 14, 21 until March 2001, 06, 12, 18 UTC
  from April 2001, not "7am, 2pm, 9pm"), and `ea/hydrology` covers England, not the UK
  (GH-3136)

## [0.179.0] - 2026-10-30

### Added

- A response warning `file-skipped` (REST, MCP, command line and, as a log line at WARNING,
  Python) names the stations whose file the provider let go (a refused download, a file withdrawn
  since the listing, a maintenance page answered with HTTP 200, a file that would not parse), so
  that a partial answer can be told from a whole one: one warning for the request, with
  `stations` and the datasets read at them. Try again later. Not told for `interpolate` and
  `summarize` (GH-3552)
- A response warning `parameter-without-rows` (REST, MCP, command line and, as a log line at
  WARNING, Python) names a requested parameter the source has no values for, with `parameter`
  and `stations`, where the answer used to be an empty header that read like a failed request
  (`TX`/`TN` of `dwd/mosmix` for Los Angeles, `tx24` of `meteofrance/synop` for Paris). Told for
  a parameter asked for by name when no station has a row of it, and for a dataset asked for
  whole only when none has a row of any of its parameters. It names the `periods`, run or lead
  time it is limited to, and leaves out a station whose file the provider let go (GH-3539)
- `meteofrance/synop` now offers the 12 h maximum and minimum temperature
  (`temperature_air_max_2m_last_12h`, `temperature_air_min_2m_last_12h`; `tx12`, `tn12`), given
  at 06 and 18 UTC by 158 of the 190 stations (2026), where `tx24`/`tn24` are given by 35 and
  by none for Paris-Montsouris. Where `tn12` repeats the `tx12` of its own row (three overseas
  stations at some hours: Cayenne-Matoury, Le Raizet, Lamentin) it is null, with the number kept as
  `raw:` in `quality_flags` (GH-3540)
- `imgw/hydrology` stations now list the river the gauge is on (`river`, with IMGW's hydrographic
  code, `Odra (1)`), its position along it in kilometres from the mouth (`river_kilometer`) and
  the altitude of the gauge's zero in metres (`gauge_zero`), under the names `wsv/pegel` uses; null
  where IMGW's list is empty. `river_kilometer` is not comparable with `wsv/pegel`'s waterway
  kilometre, which grows downstream. `gauge_zero_datum` is null, as the list states no datum
  (GH-3599)
- `dmi/observation` now offers the sunshine duration (`sunshine_duration`), the cloud cover
  (`cloud_cover_total` at minute 0 of the hour, `cloud_cover_total_mean` from the day), the hourly
  global radiation (`radiation_global_intensity_mean`), the highest and lowest relative humidity of
  the day and of the year (`humidity_relative_max`/`_min`; the annual ones were left out as not
  published, but are), the manual snow depth of the day (`snow_depth_manual`) and the monthly and
  annual counts of ice days, frost days and days with 0.1, 1 and 10 mm (`count_days_*`). A cloud
  cover above 100 is null, with the number as `raw:` in `quality_flags`. Not offered yet: the
  radiation of a day and longer, the pressure extremes and the other counts (Part of GH-3622)
- `noaa/ghcn` daily now offers the average dew point (`temperature_dew_point_mean_2m`, ADPT),
  sea level and station pressure (`pressure_air_sea_level_mean`, `pressure_air_site_mean`; ASLP,
  ASTP), wet bulb temperature (`temperature_wet_mean_2m`, AWBT), wind direction
  (`wind_direction_mean`, AWDR) and relative humidity (`humidity_relative_mean`/`_min`/`_max`;
  RHAV, RHMN, RHMX), at the US stations that report them. A direction of 0 beside an average wind
  speed of 0 is null, with `raw:0` in `quality_flags`. TAXN is listed for no station (Part of GH-3622)

### Changed

- **Breaking**: asking the Python API for the values of a `date_required` dataset without `start`
  and `end` raises `DateRequiredError` (a `ValueError`) naming the dataset, from
  `stations.values()` on, as REST, CLI and MCP already refused it. `noaa/ghcn`, `meteoswiss`,
  `meteofrance`, `geosphere`, `eccc`, `imgw`, `dwd/road` and `ea` used to answer the whole record,
  `wsv`, `nws`, `ipma` and `eaufrance/hubeau` a recent slice; `aemet` (daily to annual), `chmi`
  (sub-daily), `dmi`, `fmi`, `knmi`, `lhmt`, `rmi` and `metno/frost` an empty frame. Pass `start`
  and `end`; listing stations needs no window (GH-3562)
- **Breaking**: the REST API, CLI and MCP refuse a `metno/frost` request for `daily`, `monthly` or
  `annual` values without a start and end date, as for the other resolutions (REST: 400,
  `timestamp` is required). Such a request was answered with no rows and no reason, as the source
  is only asked within a window. Pass a window instead (GH-3560, GH-3562)
- **Breaking**: `coverage` (`/api/coverage`, the MCP tool, `about coverage`,
  `TimeseriesRequest.discover()`) gives a parameter the unit its values come back in as `unit`
  (`degree_celsius`, `decimal` for a percentage: what `glossary` gives, following the server's
  `WD_TS_UNIT_TARGETS` and `WD_TS_CONVERT_UNITS`), where it gave the unit the provider publishes
  (`degree_kelvin`, `percent`) for 362 of the 2048 parameters, and a model told a user "Kelvin".
  That unit is the new `unit_source`, there only where it differs from `unit` (absent: the same).
  Read `unit_source` where you used `unit` to know what the source holds or what
  `convert_units=false` returns. `coverage` takes no options: a `unit_targets` of a `values`
  request changes the values, not `unit` (GH-3537)
- **Breaking**: `nws/observation` fills a gap of the observation it keeps for an hour from the
  nearest other observation of that hour (a verified 5-minute row for a METAR whose temperature
  is not controlled yet), with that row's `quality_flags`. These come back where they were null:
  temperature, dew point, humidity, both pressures, visibility, wind speed and the three
  precipitation sums (the temperature in 1.8 % of the hours measured, the wind speed in 5.2 %).
  The wind direction comes only together with a filled speed, from the same row; a report that
  has a speed keeps its own direction (null for a variable wind). The running total since the
  last routine report is taken from an earlier report only. Gust and wind chill stay as the
  report has them. A value the kept observation has is never replaced. Nothing needs to be done
  (GH-3480)
- A read of many stations of `smhi/observation` fetches the per-parameter files of the next 4
  stations into the cache while one is parsed, as `dwd/observation`, `chmi` and the others
  already do (not with `cache_disable`, nor for `interpolate` and `summarize`). Answers, their
  order and errors are unchanged; the connection limits and `Settings(fetch_ahead=...)` /
  `WD_FETCH_AHEAD` (0 switches it off) are those of GH-3454 (GH-3507)
- The description of the `large` dataset of `dwd/mosmix`, which `coverage` reports and the docs
  page carries, says that which elements a station gets, and at which hours, depend on the station:
  `tx` and `tn` at 06 and 18 UTC for Berlin, 12 and 00 UTC for Tokyo, none for Los Angeles, and
  that an element without a value for it is an answer with no rows (GH-3539)

### Fixed

- `eccc/observation` monthly values carry `I` in `quality_flags` for a month with missing days,
  following the archive's rule (Technical Documentation, Notes 25 and 26) applied to the
  collection's counts `count_days_valid_*`: any missing day for the extremes, precipitation and
  snowfall, more than 5 for the mean temperature (the "3 in a row" half is not published, so the
  mean is under-flagged). It is derived, not ECCC's own flag, and set for months before 1994 too,
  from which the documentation dates the archive's flag (GH-3621)
- `dmi/observation` reads DMI's -0.1 in `precipitation_amount` (and the maxima of a day or 30
  minutes) as a trace of precipitation: 0.0 with `raw:-0.1` in `quality_flags`, where it was
  null as out of range, as the trace of KNMI, AEMET and `meteofrance/synop` is (GH-3621)
- On Windows, two processes that share a cache directory no longer lose the date a cached file
  arrived with (the `updated` column and `data_updated_at` came back null) nor download the file
  once more, when one reads or replaces its date at the moment the other does: that is asked again
  for under a second (GH-3632)
- On any system, two processes that share a cache directory no longer overwrite each other's
  date of a cached file, which made the `updated` column and `data_updated_at` come back null
  when one wrote the date at the moment the other replaced the file. The date is now written
  under the same lock as the file and its entry in the cache; where another process keeps that
  lock too long, it is written without it, as before (GH-3634)
- The `noaa/ghcn` parameter descriptions no longer offer a choice of units. 30 daily rows read
  "mm or inches as per user preference" or "Fahrenheit or Celsius", the wording of NCEI's
  ordering form; the files hold one unit, which the values already came in (mm, °C, m/s, km,
  cm), and the descriptions now say so. The hourly `relative_humidity` no longer says it is
  always calculated from air temperature and dew point (GHCNh: "Depending on the source,
  relative humidity is either measured directly or calculated") (GH-3136)
- The `eccc/observation` hourly dataset no longer claims a wind gust and weather: it holds air
  temperature, dew point, humidity, precipitation, station pressure, visibility, wind direction
  and speed, wind chill and humidex. Its parameter descriptions now say what ECCC's glossary and
  technical documentation say (the climatological day, the degree-day base of 18 °C, the
  gust published above 30 km/h only, the humidex and wind chill ranges) (GH-3136)
- `chmi/observation` lists, for `10_minutes` and `hourly`, only the stations that can have files
  there: 767 of the 1,603 (read 2026-10-30), those whose period ends in 2018 or later, when these
  files begin, and that have a daily file. The 836 left out answered every request with an empty
  frame (795 closed before 2018, 41 more with no daily file); no station with a 10 minute or hourly
  file is among them. `daily`, `monthly` and `annual` are unchanged. The daily directories are
  read for a sub-daily stations request now (GH-3623)
- Two processes that share a cache directory no longer fail a download on Windows with
  `PermissionError` when one opens a cached file while the other replaces it: the open is asked
  again for under a second, and a file that stays unreadable still raises (GH-3630)
- A request that asks several resolutions or datasets of one provider no longer returns some
  readings under another parameter's name. The humanized name is now looked up per resolution
  and dataset, where a name the source gives two parameters took the last one's: chmi (`T`, `H`,
  `P`, `F`, `TMA`, `TMI`), geosphere (`p`, `sh`, `tsmin`, `tl_mittel`), meteofrance/observation
  (`TN`, `TX`) and aemet (`hr`). The 10 minute `T` of chmi, asked with the daily one, came back
  as `temperature_air_mean_2m` (GH-3605)
- `chmi/observation` lists stations that `meta1.csv` (read 2026-10-30, 1,603 stations) has since
  been given rows for: the 29 monthly and 22 annual ids with files but no row (e.g.
  `0-203-0-10101019002`), and 14 more, 43 in all, none with a `daily` file. `monthly` lists 1,567
  stations (was 1,538), `annual` 1,555 (was 1,533). `10_minutes` and `hourly` list them too (1,603,
  was 1,560), though none of the 43 has a file there in any year (2018-2025) (GH-3259, #3623)
- `/api/stripes/image` now sends the licence, the credit line and the warnings in the headers
  `X-Wetterdienst-License`, `Link`, `X-Wetterdienst-Attribution` and `X-Wetterdienst-Warnings`,
  so a client or the MCP tool `stripes_image` can tell that the image is DWD data under CC BY 4.0;
  the image itself is unchanged. `/api/stripes/values` never recorded the warnings of its read, so
  its `metadata.warnings` and `X-Wetterdienst-Warnings` (and the MCP tool `stripes_values`) were
  always empty; they now tell them (GH-3581)
- A reading no sensor can have produced is now null, with the number the file wrote kept as
  `raw:` in `quality_flags`. `dwd/observation`: a wind speed below 0 or above 115 m/s (the hourly
  urban wind read -0.80 m/s at Berlin-Alexanderplatz) and a pressure outside 500 to 1090 hPa in
  `pressure_air_site`, `pressure_air_site_mean` (daily `PM`) and `pressure_air_sea_level` (the
  hourly `P0` read 1093.3 hPa at 00433); the vapour pressures are not bound. `meteofrance/synop`:
  `pres` outside 500 to 1100 hPa (31 rows of 108.6 to 420.6 hPa in the files of 1996, 2000, 2005,
  2010 and 2015), `pmer` outside 850 to 1100 hPa, temperatures and dew point outside -90 to
  60 C, `rr1` outside 0 to 600 mm, `rr3`, `rr6`, `rr12` outside 0 to 1200 mm, `rr24` outside
  0 to 2000 mm (GH-3135)
- `meteofrance/observation` and `meteofrance/synop`: a temperature below 0 C (air at 2 m, its
  extremes, the dew point) at a station of Guadeloupe (971), Martinique (972), Guyane (973),
  Mayotte (985), Wallis-et-Futuna (986), French Polynesia (987) or the Iles Eparses (Glorieuses,
  Juan de Nova, Europa, Tromelin) is null, with the number kept as `raw:`: there is no frost
  there, and the files hold -20.0 C at 441 m in Martinique, dew points of -39.5 C at 1,141 m
  in Guadeloupe, -32.6 C at Hao (French Polynesia) and -21.6 C at Tromelin. Synop names its 24
  stations. La Reunion, Saint-Pierre-et-Miquelon, the southern territories and New Caledonia
  are not (GH-3135)
- `chmi/observation` no longer lists the two stations abroad of CHMI's catalogue, Reykjavik
  (`0-20000-0-04030`) and Marambio Base (`0-20000-0-89055`), in the `10_minutes` and `hourly`
  station lists: the portal has no file for them in any resolution, so they never had a value
  (GH-3589)
- The row-limit refusal and the 504 timeout of `interpolate` and `summarize` (REST and the MCP
  tools) no longer advise fewer stations, which a point request does not name, nor
  `format=ndjson` or `format=csv`: they say to ask for a shorter `timestamp` window or fewer
  `parameters`. The problem keeps `limit`, `maximum` and `requested` (GH-3576, GH-3590)
- The MCP tools answer every `format` they offer, where `csv`, `ndjson`, `html` and `svg` of the
  tools with an output schema failed ("has an output schema but did not return structured
  content") and so did `png`, `jpg`, `webp` and `pdf` of every tool (a decoding error). A text
  body is the text content of the result, an image its image content and a PDF an embedded
  resource; the structured content is one sentence about it that also gives the licence, the
  attribution and the warnings, which REST sends in headers for these formats. An `html` chart
  loads plotly.js from the CDN (9 KB, not 4.8 MB). A tool answers one body in every format, held
  to the `rows` limit (`csv` and `ndjson` get no `stream_rows`), and its refusals (row limit,
  timeout) no longer advise `format=ndjson` or `format=csv`: they name a shorter `timestamp`
  window, fewer `parameters` or fewer stations (the point tools: a window or fewer parameters,
  GH-3576). REST and the command line are unchanged (GH-3464)
- A download, post or listing whose TLS handshake the peer answers wrongly (a non-TLS answer,
  `WRONG_VERSION_NUMBER`; an invalid session, `INVALID_SESSION_ID`) is retried like any other
  transient network error, where the first one failed the answer: `www.dwd.de` throws them now
  and then. A certificate that does not verify still fails at once (GH-3533)
- A `dwd/dmo` request for a lead time its product does not publish (`lead_time=long` for
  `icon_eu`, which has the short run alone) is refused as a 400 naming what the product
  publishes, where it ended in a 500 (`Unable to find a 168 h forecast`) (GH-3539)
- The stations come in one order from one request to the next, where they changed with every
  request or process: by station id for `dwd/observation` and `dwd/derived`, in the order of the
  catalogue for `smhi`, `dmi`, `chmi` and `hubeau`, and the datasets of a station in the
  order the request names them (`eccc`, `dwd/dmo`, `knmi` followed the hash seed of the process).
  So do the `stations` of a values, interpolate or summarize answer, the features of its OGC form
  and `filter_by_rank` / `filter_by_distance`. The values rows of a station were not affected
  (GH-3551)
- The `missing-value-marker` warning of an answer counts the readings that are a marker for a
  missing value inside the window the request asked for, where it counted those of every file read
  (12,663 for a 3-day request at DWD station 00011, the whole archive) (GH-3550)
- The `missing-value-marker` warning counts the readings of the stations that are in the answer,
  with `drop_nulls` on (the default) or off: not those of a station `skip_empty` leaves out, nor of
  one a `rank` walk passes over for having no reading. `interpolate` and `summarize`, whose answer
  is an estimate, carry no such warning now (GH-3554)
- Processes that share a cache directory take turns on it, through a lock file beside each
  directory (new dependency: `filelock` 3.30 or later). The metadata read-merge-write no longer
  loses a row another process saved in between (its file was then fetched again), the save no
  longer fails with `PermissionError` on Windows while another process has the metadata open, and a
  sweep no longer deletes a file another process has just fetched again. A process waits for the
  lock as long as it moves between processes (60 s at most) and 10 s behind one holder; a holder
  stuck that long costs that wait once, in which the process's other cache misses wait too, and
  then the loads, saves and sweeps of the directory for a minute, which are skipped with a warning:
  a skipped load reads nothing and a skipped save fetches again. No request fails. A killed process
  leaves no stale lock, and a file system without `flock` goes without the lock. The metadata file
  is written in one go, about four times faster for a directory of tens of thousands of entries,
  with the same content (GH-3485)
- The `station-skipped` warning is told for a station `skip_empty` leaves out whatever `drop_nulls`
  is: with the nulls dropped (the default) a station that held nothing but missing values was left
  out unsaid, and with them kept it was told. The warning is the same for both, and so is
  `parameter-without-rows`: a parameter or dataset that held only missing values at a station left
  out (wholly or with some readings) is no longer named there. The rows of an answer are unchanged
  (GH-3567)
- `skip_empty` judges a station by the same span whether `drop_nulls` is on or off. For a request
  that names no window the coverage is measured against the span of the station's own series, and
  that was read after the empty readings had been dropped: a station whose first or last readings
  were nulls looked complete (and was kept) with `drop_nulls=True`, the default, and sparse (and
  was skipped) with `drop_nulls=False`. The span now includes the empty readings, so with the
  default setting such stations are skipped, and the answer has fewer stations than before. The
  same holds for a resolution with no fixed interval (`subdaily`), where the share of readings
  with a value was taken of the rows left, always all of them, so nothing was skipped. A request
  with a window and a fixed interval is unchanged (GH-3578)

### Security

- `uv.lock` pins `joserfc` 1.7.7 (was 1.7.5), which closes GHSA-9pg5-8c7x-5hfx (CVE-2026-119284,
  fixed in 1.7.6) and the `vulnerable` check that failed on it. It comes in only through the `mcp`
  extra (`fastmcp`, `authlib`), and wetterdienst neither imports it nor serves an authenticated
  MCP endpoint, so its own code did not reach the affected path; a source install with the extra
  and the Docker image (built from the lock) now carry the fixed version (GH-3653)

## [0.178.0] - 2026-10-28

### Security

- `uv.lock` pins `authlib` 1.9.1 (was 1.8.0) and `dnspython` 2.9.0 (was 2.8.0), which close the
  open Dependabot alerts for both. They come in only through the `mcp` extra (`fastmcp`), and
  wetterdienst neither imports them nor serves an authenticated MCP endpoint, so its own code
  did not reach the affected paths; a source install with the extra and the Docker image
  (built from the lock) now carry the fixed versions (GH-3514)

## [0.177.0] - 2026-10-27

### Changed

- A read of many stations of `dwd/observation`, `dwd/derived`, `chmi` or the daily synop of
  `imgw/meteorology` fetches the files of the next 4 stations into the cache while one is parsed
  (not with `cache_disable`, nor for `interpolate` and `summarize`): 100 stations of one small file
  took 17.5 s and now take 4.3 s against a local upstream of 120 ms latency. Answers, their order
  and errors are unchanged. That is up to 4 more connections to the host beside the station's own
  download, and 8 per host at most for all reads of a process together (a station's own downloads
  are not counted); a missing or failed file is asked twice, ahead and at its turn, so an outage
  can show up later, by up to twice the client timeout. `Settings(fetch_ahead=...)` or
  `WD_FETCH_AHEAD` sets the 4 (at most 8), 0 switches it off (GH-3454)

### Fixed

- `dwd/observation`: a read of the historical period of a 1-, 5- or 10-minute dataset for a window
  that no file of the station covers (the gap between two files, a window past the last one) no
  longer downloads and parses every historical file of the station only for the rows to be
  dropped. The answer is the same, the read is faster and makes fewer requests (GH-3505)
- `eaufrance/hubeau` declares its `extent.bbox` up to 51.1 N, not 51.0: France reaches 51.09 N
  (Bray-Dunes), so a correctly placed station there is no longer reported as outside the country
  by the catalogue rules and a swapped one is corrected. The box of metropolitan France that
  swaps a misplaced position moves with it (GH-3481)

## [0.176.0] - 2026-10-27

### Added

- Every MCP tool has a `title` ("Find stations") and the annotations `readOnlyHint` true,
  `destructiveHint` false and `idempotentHint` true, which the Claude connectors directory
  requires and clients use to skip a confirmation. `openWorldHint` is false for `coverage`,
  `glossary` and `providers`, which answer from wetterdienst's own metadata, and true for the
  tools that reach a provider's service. Names, arguments and descriptions are unchanged (GH-3482)
- Each network of `GET /api/providers` has an `extent`, where its stations are, which the `country`
  of its provider does not say: `scope` (`global`, `national`, `regional`), `continents`, `bbox`
  `[west, south, east, north]` and, for a regional one, `country_codes`. A dataset narrower than its
  network has its own (`dwd/dmo` `icon_eu`). `GET /api/coverage` (and the CLI, the MCP tools and
  `Wetterdienst.discover()`) lists the `scope` of each network, and the coverage of one network
  gives each dataset its extent. `dwd/mosmix`, `dwd/dmo` and `noaa/ghcn` are global (GH-3456)
- The `metadata` block of every data answer has `data_updated_at`, when the source says its data
  was last updated (UTC; `null` where it states none), with the `X-Wetterdienst-Data-Updated-At`
  header where it is set. The values, interpolation and summary results have `data_updated_at`, and
  so does the `metadata` of their `to_dict`, `to_json` and `to_ogc_feature_collection` with
  `with_metadata=True`. `meteofrance/observation` fills it from the files whose rows the answer
  keeps (the newest `last_modified` of data.gouv.fr, as Etalab 2.0 asks), and downloads a cached
  file again when the listing dates it later than the copy, serving an archive's copy and its own
  date if the file host does not answer (a current-period file whose copy expired still fails with
  the download error); a network whose source states none, a list of stations, a history and a
  streamed answer (NDJSON, CSV of `values`) say `null`. A result cut by `filtered_by_sql` keeps
  the date of the result it was cut from. `schema_version` stays `"1"` (GH-2567)
- `data_updated_at` is also filled from the `Last-Modified` of the files an answer is read from, when
  the source last wrote them (the newest of the files whose rows the answer keeps), for `dwd`
  `observation`, `derived`, `phenology`, `poi` and `road`, `chmi`, `imgw`, `ipma`, `meteoswiss`,
  `noaa/ghcn` and `meteofrance/synop`; for the forecasts `dwd/mosmix`, `dmo` and `swsmos` it is the
  model run (`retrieved_at` less it is the age of the forecast), for `dwd/alerts` the newest `sent`,
  and a `RadarResult` and a `DwdWeatherAlertResult` have it as well. A cached answer has the date of
  its cached copy; one cached before this has none until it expires (12 hours at most) or the cache
  is cleared, and `meteofrance/synop` downloads each finished year it holds once more for it, once.
  FMI and SMHI send the time of the request as `Last-Modified` and stay `null` (GH-2567)

### Changed

- **Breaking**: where a provider hands over several rows for one reading (the same station,
  parameter and timestamp), the answer has the first row that has a value, with that row's
  `quality_flags`; it kept the first row even when it had none, and the value of the later row was
  lost. A reading that was missing, or was dropped as null, is now filled where another row had a
  value; two different values still keep the first. `data_updated_at` can now date such an answer
  by the newer file whose row is kept. Nothing needs to be done (GH-3450)
- The MCP `instructions` say that the same `stations` then `values` steps serve a network of any
  `kind`, for a place given by `latitude`, `longitude` and `rank`, and that a provider's `country`
  is its operator's, not the extent of its data, so a model does not refuse a place because of it
  (it had refused a forecast for Los Angeles because DWD is German). `Provider.country` and
  `country_code` are described the same way in the OpenAPI schema and the `providers` tool; the
  answers are unchanged (GH-3456)
- The `attribution` that `meteoswiss/observation` and `metoffice/observation` report with every
  answer is the credit line their providers state: "Source: MeteoSwiss" (was "© MeteoSwiss
  (Federal Office of Meteorology and Climatology)") and the citation of the CEDA record of MIDAS
  Open (was "© Crown Copyright, Met Office, MIDAS Open"). The licences are unchanged; a caller
  that shows the credit shows the new text (GH-2567)
- `metno/frost` reports its licence as `CC-BY-4.0 AND NLOD-2.0` (was `CC-BY-4.0 OR NLOD-2.0`), with
  the name "Creative Commons Attribution 4.0 International and Norwegian Licence for Open
  Government Data 2.0": MET Norway states that the data are licensed under both, not under one of
  them. A caller that reads `provider.license.spdx_id` or the `X-Wetterdienst-License` header sees
  the new expression, and the conditions of both licences apply to its use of the data; the credit
  to give is the same, `attribution` is still "Data from MET Norway" (GH-2567)
- `/api/auth` and the MCP `auth` tool probe the provider at most once a minute per network and
  server process, and say so in their description. `metno/frost` and `aemet/observation` already
  kept an accepted answer for a minute on disk; now a rejection is kept for up to 60 s too, a
  `valid: null` for 5 s, and simultaneous calls share one probe. A changed or corrected credential
  shows within a minute, a revoked one within two. The answer has the same shape (GH-2607)
- **Breaking**: the positions of 54 `eaufrance/hubeau` stations change: the referential lists them
  with latitude and longitude swapped (Anor at 4.10 N, 49.99 E, a point near Somalia), and they
  now come back where they are (50.0 N, 4.1 E). A position is swapped when it lies in none of
  metropolitan France, Guadeloupe and Martinique, Guyane, Reunion and Mayotte and the swapped one
  lies in one; no station overseas is moved. `J543211003` (the Blavet), listed in Algeria, is not
  moved. Nothing needs to be done; a filter on a station's old position needs the new one (GH-3468)

### Fixed

- `dwd/swsmos` lists a station once when DWD's catalogue repeats its line (Q311, 2026-10-26): the
  `stations` answer had it twice (GH-3474)
- Four pages stated what the code does not do. Interpolation said a negative search distance is a
  400 on the REST API: it is a 422, and only a name that is no canonical parameter is a 400.
  Python Examples said `RADOLAN_CDC` takes an hourly or daily resolution: `5_minutes` too.
  Development said `poe test -k ...` selects tests: a task that is a sequence drops what follows
  it and runs the whole suite, so the page now calls pytest. Web app called the app a Nuxt 3
  one: it is Nuxt 4, and the page names no major version now (GH-2621)
- `meteofrance/synop` reads the yearly files data.gouv.fr lists (`data/OBS/SYNOP/`), not the
  `synchro_ftp` copy of them, which stopped being refreshed on 2026-09-09: values of the current
  year now run to the day before today instead of ending on 2026-09-08 (GH-3447)
- A file that one call had cached was fetched again by a later call made in another thread, with
  `File.from_cache` false: `download_files` (whose threads are new for every call), the main thread
  and the workers of the REST server each read the cache metadata when they start and only again
  after 10 s, so they did not see what another thread cached in between. A thread that finds no
  copy now reads the metadata again before it fetches; a hit reads nothing more (GH-3452)
- Several processes starting together on an empty cache directory (workers of a server, parallel
  CLI runs, a CI matrix) no longer remove it under each other: the first sweep of a process took
  the directory and the copies the others had just written, which raised `FileExistsError` or
  `OSError` in some of them and sent others to a temporary cache directory. The sweep now removes
  only the expired entries and the files no entry names that are older than the expiry and an
  hour. On Windows, processes sharing a cache directory can still fail saving the metadata file
  (`PermissionError`, GH-3485) (GH-3467)

## [0.175.0] - 2026-10-25

### Added

- `[Docker]` The backend image has a `HEALTHCHECK`: it asks `/health` on the port the server
  listens on (a server on all interfaces or on loopback), every 30 s, and `docker ps` shows the
  container as `healthy` or `unhealthy`. A platform without a health check of its own (Coolify's
  default) now routes through a proxy such as Traefik on this one, which sends traffic only to
  containers that are healthy or have no health state. `docker run --no-healthcheck` switches it
  off (GH-3346)
- `chmi/observation` hourly has `pressure_air_sea_level` (CHMI's `P_hm`, the pressure reduced to
  sea level, published for 2018 to 2025): another quantity than the station-level
  `pressure_air_site`, not a rename of it. The pressure tendency `ppp` is not read (GH-3413)

### Changed

- **Breaking**: the `ipma/observation` wind direction returns north as 360 degrees, no longer 0.0,
  as every other provider does (DWD subdaily included). IPMA's codes 1 and 9 (north) were read as
  0.0, 586 of 4,283 direction values in the feed, all beside a wind that blows; 0 now stands for
  a calm only, and the code 0 stays null. A filter or a compass rose that expects 0 for north now
  gets 360 (GH-3135)
- `compose.yml` publishes the ports of the backend (7890) and the app (4000) on `127.0.0.1`, no
  longer on every interface of the host, so `docker compose up` is not reachable from the network.
  To reach it from another machine, set `WETTERDIENST_BIND_HOST=0.0.0.0` (or a host address) in
  the shell or in `.env`; a `compose.override.yml` that maps ports gives the address itself
  (GH-3096)
- **Breaking**: the `noaa/ghcn` hourly stations Chelveston (UKW00015015) and Huntington
  (Alconbury, UKW00015033) are placed west of Greenwich, no longer 73 and 29 km east of it, where
  `ghcnh-station-list.csv` has lost the sign of their longitude; a filter on the old position
  needs the new one. The hourly elevation of UKW00015033 now follows the daily one (47.9 to 49.1 m)
  when both resolutions are requested. One table serves both lists and turns a row only while it
  lists the position that was checked, so a list NOAA corrects is read as it is (GH-3384)

### Fixed

- `chmi/observation` hourly `pressure_air_site` returned no rows from 2025 on without a word:
  CHMI publishes that station pressure (`P`) for 2018 to 2024 only. A window that reaches past 2024
  now answers with the warning `parameter-ended` saying so (and pointing to `pressure_air_sea_level`
  and the `10_minutes` resolution, which still publishes it), and the files that do not exist are
  no longer asked for (GH-3413)
- `wetterdienst restapi --reload` now writes the `INFO` lines of the package and, with `--debug`,
  its debug lines: the worker that uvicorn spawns configured no logging, so the log held uvicorn's
  access lines only (GH-3390)
- The debug line of a file that `chmi/observation` or `metoffice/observation` does not find names
  its URL without the query, as the other providers do, where it named the URL as requested
  (GH-3394)

### Security

- The wheel and sdist of a release carry a PEP 740 attestation on PyPI, which
  `pypi-attestations verify pypi` checks (GH-3346)
- `[Docker]` The backend image carries a build provenance signed with the GitHub Actions identity
  of the workflow through Sigstore, which
  `gh attestation verify oci://ghcr.io/earthobservations/wetterdienst:<version> --repo
  earthobservations/wetterdienst` checks, and an unsigned BuildKit provenance and SBOM per
  platform (the registry lists them as `unknown/unknown` manifests). Releases before this one have
  none; see "Release provenance" in `.github/SECURITY.md` (GH-3346)
- A redirect from `https` down to `http` is refused for every session again; 0.174.0 let a session
  without a credential follow it. Nothing needs to change: no provider needs the hop, which was
  data.gouv.fr's maintenance page. A request that data.gouv.fr redirects to
  `http://sorry.data.gouv.fr` is now a `DownloadError` saying that data.gouv.fr is in maintenance
  (HTTP 502 in the REST API), and `meteofrance/observation` does not ask it twice (GH-3400)
- Follow-up and redirect URLs are limited to the provider's own hosts: a redirect, and a link an
  answer names (next page, `datos`, asset, measure), is followed only to a host that the provider
  lists (its API and the store of its files). A link is fetched over `https` only. Any other
  host, one under the provider's own domain included, is refused with a `DownloadError` that
  names the host and the provider; 0.174.0 held them to the provider's registered domain (GH-3339)

## [0.174.0] - 2026-10-24

### Changed

- **Breaking**: 6 more `noaa/ghcn` daily stations are placed west of Greenwich, no longer east of
  it, where `ghcnd-stations.txt` has lost the sign of their longitude: Torrevieja (SP000007038),
  Alice Holt Lodge (UKE00105927) and the RAF stations Molesworth, Chelveston, Bassingbourn and
  Huntington (Alconbury) (UKW00015014, -15015, -15018, -15033). They were 7 to 125 km off, so a
  nearest-station search, a distance filter or an interpolation near them picked the wrong
  stations. Their `longitude` is now negative; a filter on the old position needs the new one
  (GH-2886)

### Removed

- **Breaking**: the `debug` parameter is removed from every REST endpoint and MCP tool that had
  it (all but `version`, `settings` and `health`). It set the log level of the whole server
  process for every caller, so one anonymous request switched the server's log to debug. A request
  that still sends it is refused (REST 422 of type `removed`, an MCP tool error) with `debug was
  removed` and what to do instead: drop it. The level is the operator's, set as for any Python
  logger (`logging.getLogger("wetterdienst")`); the `--debug` option of the command line is
  unchanged (GH-3336)

### Fixed

- `--debug` of the command line, and of `wetterdienst restapi`, now shows the debug lines of the
  whole package: those of the models and the providers (downloads, dropped columns, skipped
  files), where it showed those of one internal module only and so none. The level is set on the
  logger `wetterdienst`; the loggers of other libraries, `fsspec` and `aiohttp` among them, stay
  at `INFO`. The hint of a removed `debug` parameter now names `wetterdienst restapi --debug`
  (GH-3388)

### Security

- The REST API and MCP server now write the text a request sent into their log on one line:
  control characters (a newline, an escape) in a refused value, a parameter, a station name or a
  path are logged as escape sequences such as `\n`. This holds for the messages of the loggers of
  `wetterdienst.ui` and `wetterdienst.model.request`; the logger of the CLI is unchanged
  (GH-3336)
- The query of a download URL (a pre-signed link of KNMI or AEMET carries its signature there) is
  no longer shown by the errors a failed download returns (`repr()` and the retry records of
  `stamina` included), and the download, listing and post lines of the log name the file without
  its query, as do the warnings of KNMI and AEMET for a file they skip. Other log lines of a
  provider are unchanged, and so is the debug line of `fsspec` that names the URL in full when an
  application enables DEBUG for it (GH-3341)
- **Breaking**: a redirect to another registered domain is no longer followed, and neither is one
  from `https` down to `http` for a session that holds a credential (a credential header, `auth`,
  cookies, `trust_env`, a proxy or middleware among its `fsspec_client_kwargs`): the download
  fails with a `DownloadError`. A session without any still follows an `http` hop inside the
  provider's domain, as data.gouv.fr answers for the stations of `meteofrance/observation`.
  Nothing to change for the providers; read that one without those keys. A key in a header other
  than `Authorization` (AEMET's `api_key`) is dropped where a redirect changes the origin. The
  links that AEMET, KNMI, NWS, Hub'Eau, MeteoSwiss, Météo-France and EA take from an answer (next
  page, `datos`, asset, measure) are fetched only at the provider's own domain, over `https` (KNMI
  and Météo-France also at their object store) (GH-3338, GH-3339, GH-3398)
- A KNMI NetCDF file with a variable whose data is kept outside the file (HDF5 external storage or
  a virtual dataset) is refused with an `UpstreamError` (HTTP 502 in the REST API), for the
  values and for the station list; KNMI's own files keep every variable in the file (GH-3337)
- **Breaking**: an `influxdbs://` or `influxdb1s://` export (library `to_target`, CLI `--target`)
  now verifies the server's TLS certificate; the InfluxDB 1 client used to accept any, so the
  credentials and the data could be read on the path. A server with a self-signed or private-CA
  certificate now fails with an SSL error: set `REQUESTS_CA_BUNDLE` to a CA bundle that includes
  that certificate (or its CA) instead (GH-3342)
- `diskcache` is no longer a dependency. The directory listings of the file indexes are kept as
  JSON in a SQLite file (`listings-v1.sqlite3`, in a folder of the cache directory) of the standard
  library, where `diskcache` unpickled them: write access to the cache directory no longer runs
  code in the process (GHSA-w8v5-vhqr-4h9v, which had no fixed version). The old cache is ignored
  and the listings are fetched once more; its files are removed once idle for an hour. A cache
  directory that wetterdienst makes now has mode 0o700 and the database 0o600; an existing one
  keeps its mode. The floor of `fsspec` is now 2026.6.0, the first release whose download-cache
  metadata file is JSON only (earlier ones fell back to `pickle`): upgrade it as well.
  `FileDirCache` has a new method, `close()`, which closes the database connections (GH-3326)
- A single download is now limited to 2 GiB and to one hour in all (`download_file(max_bytes=...)`
  sets the size per call), and an archive that unpacks to more than a ceiling is refused: 1 GiB
  for most providers, 256 MiB for DWD SWSMOS and alerts, 2 GiB for DWD radar, 4 GiB for the KML of
  MOSMIX and DMO, 8 GiB for Météo-France climate files. They fail with a `DownloadError` (REST
  502), which is not retried, where the body used to be read into memory whatever its size. A zip
  archive that is not stored or deflated, and a tar archive with links, are refused. A file whose
  name does not say it is compressed but that arrives as gzip, zlib or zstd is refused too, as
  `polars.read_csv` unpacks those on its own. The files served today are below these figures
  (GH-3340)

## [0.173.0] - 2026-10-24

### Added

- `dwd/radar` `DwdRadarValues` takes `polarization=` (`DwdRadarPolarization.HORIZONTAL` or
  `VERTICAL`, or `"th"` / `"tv"`) to read only the `TH` or only the `TV` files of the unfiltered
  reflectivity sweeps (`subset=DwdRadarDataSubset.UNFILTERED` of `SWEEP_PCP_REFLECTIVITY_H` and
  `SWEEP_VOL_REFLECTIVITY_H`); without it both are answered, as before. Naming one for any other
  product or folder raises a `RequestError` (GH-3288)
- `wsv/pegel` serves the two series it did not map: `SW` (SICHTWEITE, one station, every minute) as
  `visibility`, in m, and `V` (VOLUMEN, one station, every 15 minutes) as the new
  `volume_reservoir`, in m³. `volume_reservoir` has the new unit type `volume` (`cubic_meter`, the
  default, and `cubic_hectometer`), which the `unit_targets` option and the glossary's `unit_type`
  filter accept (GH-3242)

### Changed

- **Breaking**: the direct radiation of `metoffice/observation` (`direct_irad`, hourly `radiation`)
  is `radiation_sky_short_wave_direct_perpendicular`, no longer `radiation_sky_short_wave_direct`:
  it is the energy of the hour on a plane perpendicular to the sun's rays, not on a horizontal
  surface, so it can exceed the global radiation. The old name is refused with the new one named;
  values and units are unchanged. Request, filter and key by the new name; for the horizontal
  component multiply by the cosine of the solar zenith angle (roughly, at the middle of the hour).
  MIDAS holds no direct radiation past December 1997. Release the app after this backend (GH-3316)

### Removed

- **Breaking**: `Wetterdienst(provider, network)`, the constructor form that returned a class
  (deprecated in 0.156.0), is removed in 0.173.0, earlier than announced for 1.0.0, and raises a
  `TypeError` that names the replacement. Write `Wetterdienst.resolve(provider, network)`, or
  `Wetterdienst.resolve_standalone(provider, network)` for `dwd/radar` and `dwd/alerts` (GH-3128)
- **Breaking**: `wetterdienst stripes values`, the old name of `stripes image` (deprecated in
  0.159.0), is removed in 0.173.0, earlier than announced for 1.0.0: it fails as "No such command
  'values'" with exit 2. Write `wetterdienst stripes image`, which takes the same options and
  writes the same image. The name is not reused. `/api/stripes/values` and the MCP tool
  `stripes_values` are unchanged (GH-3128)

### Fixed

- The station map (`StationsResult.to_plot`, and `to_image` and `format=png` of the station
  endpoints) zoomed in beyond the stations of any region under about 6 degrees: the picture of 5
  stations around Berlin or 16 around Munich showed none of them. The zoom now fits the stations'
  longitudes to the width and their latitudes to the height, at most 10 for one station, and a
  `width` or `height` given to `to_image` is fitted too. Stations across the antimeridian are not
  handled (GH-3373)

### Security

- The Docker image, and an environment synced from `uv.lock`, now hold fastmcp 4.1.3, and pypdf
  6.21.2 where the `pdf` extra is installed (the image has none); the floors are `fastmcp>=4.1.2`
  (`mcp` extra) and `pypdf>=6.21.2` (`pdf` extra).
  fastmcp 4.0.0 to 4.1.1 have GHSA-vqqp-x5qm-5qp4 (OAuth client-credentials providers) and
  GHSA-7xgj-8392-5q4r (authorization of transformed components); the MCP server of
  `wetterdienst restapi` is open and uses neither, so neither reaches it. pypdf before 6.21.2 has
  three advisories of long runtimes on a crafted PDF (GHSA-6c7f-9265-g8fw, GHSA-gmh7-3g9r-mjh5,
  GHSA-jr96-gvgh-j3r4); wetterdienst reads PDFs only in `describe_fields` and
  `wetterdienst about fields` (DWD's description files), not in the REST API or MCP. An
  installation from PyPI resolves its own versions: upgrade them there (GH-3376)

## [0.172.0] - 2026-10-23

### Fixed

- The threat model (`.github/SECURITY.md`) and the REST API page were inexact, and the MCP page
  lacked a section. They now say that the cache directory holds the downloaded bodies it caches,
  not only the listings; that seven providers fetch URLs an upstream's answer names, so a
  compromised upstream can make the server fetch from another http(s) host (GH-3339); and that the
  provider text the MCP tools return, such as DWD alert text, is unfiltered and untrusted for an
  agent (GH-3347)
- Three pages stated what the code does not do. Scheduling said an unwritable cache directory fails
  the run: it warns once and caches in a temporary directory for that run, so every run downloads
  again. Climate Stripes put the `unit` of `/api/stripes/values` in `metadata`; it is in `series`
  since 0.158.0. Interpolation gave celsius values and a Frankfurt elevation span that neither the
  code nor DWD's files give (GH-2621)

### Security

- The floors of four dependencies now exclude releases with published advisories: `aiohttp>=3.14.4`
  (was `>=3.14.0`; every download), `duckdb>=1.1.0` (was `>=1`; the `sql` and `duckdb` extras:
  GHSA-w2gf-jxc9-pf2q, where `sniff_csv` read files with external access off, which the REST SQL
  filter relies on), `pypdf>=6.21.1` (was `>=3.12.1`; the `pdf` extra) and `influxdb>=5.3.1` (was
  `>=5.3`), with `msgpack>=1.2.1` in the `influxdb` extra (5.3.0 pinned `msgpack==0.6.1`,
  GHSA-6v7p-g79w-8964). An installation that holds an older release keeps it when wetterdienst is
  upgraded: upgrade these packages as well
  (`pip install --upgrade aiohttp duckdb pypdf influxdb msgpack`) (GH-3343)
- **Breaking**: the REST API and the MCP tools bound the inputs of `interpolate` and `summarize`, so
  that one request cannot ask for an unbounded amount of work: a station distance given is at most
  200 km, `num_additional_stations` at most 20 and `min_gain_of_value_pairs` above 0 (a 422 past
  them), and a request whose radius reaches more stations with a record in the window than
  `WD_RESTAPI_MAX_STATIONS` (100) is refused as `limit-exceeded` before any download. A caller who
  needs more uses the Python API or the command line, which take any value. Everywhere, the search
  for a group of four stations to interpolate from looks at the 30 nearest stations of a parameter
  at most, and falls back to one group around the point where none of them surrounds it. The
  explorer of the app holds its inputs to the bounds (GH-2606)
- The REST API sends `X-Content-Type-Options: nosniff` on every answer, errors and streams
  included, and a `Content-Security-Policy` that allows no script or request on the index page and
  the `svg` answers, so that a browser does not take a body for another media type or run script in
  an SVG opened as a document. `/docs`, `/redoc` and `format=html` carry no policy, as they run
  scripts (GH-3349)

## [0.171.0] - 2026-10-23

### Changed

- The `radarplus` extra needs `wradlib>=2.6.0` (was `>=2.0.1`): the first release whose `radolan`
  backend opens the ODIM HDF5 file DWD serves as the RADOLAN RW, where older ones raise a
  `UnicodeDecodeError`. A host that pins an older wradlib upgrades it (GH-3329)
- `chmi/observation` stations of `daily`, `monthly` and `annual` are the ones with a file of a
  requested parameter, not of any element of the resolution (0.169.0):
  `daily/data/sunshine_duration` lists 312 of the 1,537 stations, the other 1,225 answered it with
  no values (read 2026-10-23).
  A dataset lists the stations with a file of any of its parameters, from the directories of the
  requested elements only; `10_minutes` and `hourly` still list all stations (GH-3295)

### Security

- wetterdienst now requires certifi 2026.10.19 or later (was 2024.2.2): older certifi releases still
  trust the `emSign ECC Root CA - G3`, whose intermediate CA keys are compromised
  (GHSA-6q48-6c7w-9gw2), and `use_certifi` (`WD_USE_CERTIFI`) hands that bundle to every download.
  The Docker image is built on a python base image (3.15.1) with pip 26.2.2 and Debian's
  `ca-certificates` update. An installation from PyPI resolves its own certifi: upgrade it there,
  and the system trust store through the operating system, see `.github/SECURITY.md` (GH-3331)

## [0.170.0] - 2026-10-23

### Changed

- **Breaking**: `dwd/observation` `hourly/temperature_soil` `historical`: the stamps of the periods
  whose source is the eMD archive (up to 1991, 74 East German stations, the terms 01, 04, ..., 22)
  are MEZ, not UTC, and come back one hour earlier (00, 03, ..., 21), per depth, with `zone:mez` in
  `quality_flags`. The same holds for `hourly/temperature_air` of Diepholz from 1995-02-01 00 to
  1996-05-31 23, which its plain MEZ label does not mark.
  Add an hour to flagged stamps to get the old ones; the Diepholz stamp 1995-02-01 00 is the row of
  1995-01-31 23 and is dropped. The hourly wind of Bückeburg and Celle is right as written (ISD is
  the one an hour off there), and Regensburg-Oberhub and Stötten stay as written (GH-3029)

### Fixed

- The migration guide named no release for the `dwd/observation` hourly air temperature of the MEZ
  periods (0.155.0, GH-2709), and its "Verified" section counted 361 parameters of 0.139.0 that are
  gone where there are 403, with two removals (WSV Pegel, NWS) missing from its list (GH-3321)
- `dwd/radar` `DwdRadarValues` with `start=DwdRadarDate.LATEST` of a product that is no sweep: a
  folder with no file named latest (warns `No radar file found`, as the sweeps do) or a latest
  `.tar` with no member (warns `No radar data found in <url>`) now answers no result instead of
  raising a polars `ValueError` or a `RuntimeError`. Two files named latest are both answered, the
  first result of each, in the order of their names. A connection failure is still raised (GH-3311)

## [0.169.0] - 2026-10-23

### Added

- `dwd/radar` reads the folder `unfiltered` of the reflectivity sweeps, which holds the total
  reflectivity `TH` and `TV` (`subset=DwdRadarDataSubset.UNFILTERED` of `SWEEP_PCP_REFLECTIVITY_H`
  and `SWEEP_VOL_REFLECTIVITY_H`): both files of each sweep are answered, told apart by
  `result.url`. `start=DwdRadarDate.LATEST` of the precipitation sweep is its `-LATEST-` files, TH
  and TV. That of the volume sweeps stays refused, as DWD replaces the ten files one by one and
  they come from two volumes for minutes; ask for a time (GH-3288)

### Changed

- **Breaking**: `dwd/dmo` `precipitation_amount_last_1h` (`rr1`) and `precipitation_amount_last_3h`
  (`rr3`) are 0.0 where ICON writes a little below 0 (to -0.10 and -0.04 mm; 2769 of 459,732 `RR1`
  values of the icon run of 2026-10-22 12Z), with the number kept as `raw:-0.1` in `quality_flags`;
  they were negative, and a `-0.00` was `-0.0`. Nothing to change in a caller; filter on `raw:` for
  the old numbers.
  `radiation_global` (`rad1h`) and `radiation_short_wave_net_last_3h` (`rads3`) stay as written, a
  little negative at night (mostly above -0.2 J/cm2, at a few stations to about -0.8), and their
  descriptions say so (GH-3263)
- **Breaking**: the direct radiation of `dwd/poi` (`direct_solar_radiation_last_hour`) is
  `radiation_sky_short_wave_direct_perpendicular_intensity`, no longer
  `radiation_sky_short_wave_direct_intensity`: it is the irradiance on a plane perpendicular to the
  sun's rays, not the component on a horizontal surface, so it can exceed the global radiation. The
  old name is refused with the new one named; values and units are unchanged. Request, filter and
  key by the new name; multiply by the cosine of the solar zenith angle for the horizontal
  component. Release the app after this backend (GH-3263)
- `chmi/observation` lists, for `daily`, `monthly` and `annual`, only the stations that have a file
  in the resolution: 25, 24 and 29 of the 1,562 stations of `meta1.csv` (closed ones such as
  Sadská) answered every request with an empty frame (read 2026-10-22). `10_minutes` and `hourly`
  still list all 1,562. A stations request for the three now lists the element directories (7, 2
  and 2), and a failed listing raises `NoInternetError` or `DownloadError`. The monthly and annual
  files of 29 and 22 ids that `meta1.csv` does not carry, with no position anywhere, stay unlisted
  (Part of GH-3259)
- `noaa/ghcn` `daily` no longer lists the 147 stations of `ghcnd-stations.txt` that have no line
  in `ghcnd-inventory.txt` (133,039 listed, read 2026-10-22): 83 Canadian `CAN030...`, 58 US
  `USC...`, 5 Swedish and 1 `GMM`. 146 have no data file (`access/<id>.csv` is a 404); `USC00144840`
  has one, PRCP of 2013 flagged `Z`. They had null `start_timestamp` and `end_timestamp` and the
  nearest-station search could pick them. Looking one up by id now warns that there is no such
  station and answers an empty frame (GH-3260)

### Fixed

- `dwd/radar`: `start=DwdRadarDate.LATEST` answers `RadarResult.timestamp` for the latest files
  whose name has no time, which was `None`: the `-latest-` files of the site products, the
  `-LATEST-` sweeps of the precipitation scan, HX, DMAX, VII, HymecNG and the RADOLAN products.
  It is `date` and `time` of the `/what` group of the ODIM HDF5 file (needs h5py, the `radar`
  extra; without it `None` and one warning), the header of a `DX` file, or the event time of
  `meso_latest.xml`, which stays `None` for a run with no event (GH-3299)
- `dwd/radar`: `DwdRadarDate.MOST_RECENT` of the volume sweeps (`SWEEP_VOL_*`) is the 5 minute slot
  10 minutes before now, no longer 5: their last sweeps are listed up to 485 s after the slot
  starts, so 0.6 % of the answers lacked sweeps (0.1 % had fewer than four) (GH-3302)
- The example `dwd_radar_composite_rw.py` plots `ACRR`, the variable wradlib reads from a RADOLAN RW
  file (it asked for `RW` and failed). The radar docs say what an RW file holds and that it is ODIM
  HDF5, which `wrl.io.read_radolan_header` cannot read: use h5py or
  `xr.open_dataset(..., engine="radolan")` (GH-3298)
- `eaufrance/hubeau` descriptions of `stage` and `discharge` no longer say the source states no
  statistic and, for the height, no reference level. The swagger dates a value by the instant it
  occurred, with no interval, and the height is relative to the zero of the station's gauge, so
  stations share no level; the station's `gauge_zero` (metres, in `gauge_zero_datum`, not given for
  every station) is that zero. No value or name changed (Part of GH-3264)
- `wsv/pegel` docs no longer constrain `stage` to `>=0`: a stage is read against the gauge's own
  datum, and on 2026-10-22 nine gauges stood below it (Schillig -250 cm, Rotterdam -35 cm). The
  values were never clipped; only the constraints column of the five resolution pages said so.
  The `ipma/observation` page no longer calls `radiacao` global radiation: the source says only
  "radiação solar (kJ/m2)" (Part of GH-3242)
- `dwd/radar`: `DwdRadarDate.MOST_RECENT` of `LMAX_VOLUME_SCAN`, `PE_ECHO_TOP`, `PR_VELOCITY` and
  `PZ_CAPPI` is the 5 minute slot 10 minutes before now, no longer 5: DWD publishes them more than
  5 minutes after the run in 18 of 577 runs (up to 8 minutes), and the 5 minute slot was empty
  then (GH-3288)
- `dwd/observation` and `dwd/derived` log a warning, once a process, that names the stations that
  have data files and no line in the station description of any period, when all periods of a
  dataset are read (01018, 02996 and 05047 in `daily/climate_summary`, nine in `derived` soil, read
  2026-10-22). They were dropped without a word and still are not listed, as DWD gives no name or
  position for them; the docs pages say so (Part of GH-3258)
- A parameter name renamed before 0.139.0 whose new name a dataset renamed again is refused with
  "It was renamed to <current name>", not a "Did you mean" guess or no hint: `humidity` in 26
  datasets (now `humidity_relative_mean`), `visibility_range`, `precipitation_height*` in NWS,
  NOAA GHCNh, SWSMOS and DMI, and `soil_moisture_gras_*`, `soil_moisture_winterwheat_*` and
  `soil_moisture_corn_loamysilt_*` in `dwd/derived` `monthly/soil` (GH-3276)
- `metadata.provider.license.url` of Météo-France and Eaufrance answers
  `https://www.data.gouv.fr/pages/legal/licences/etalab-2.0`, the Etalab 2.0 text; the old
  etalab.gouv.fr address redirected to the data.gouv.fr home page. `metadata.provider.url` of
  SMHI is now `https://www.smhi.se/data/sok-oppna-data-i-utforskaren`, where the old one
  redirected (GH-3255)

### Security

- The Docker image, and an environment synced from `uv.lock`, now hold opentelemetry-api 1.45.1,
  which bounds the parsing of the `tracestate` header (GHSA-xcq7-p3pf-p88h). It reaches
  wetterdienst through FastAPI and the MCP server (`restapi` and `mcp` extras). An installation
  from PyPI resolves its own version: upgrade it there (GH-3280)

## [0.168.0] - 2026-10-22

### Added

- `dwd/radar` offers the products DWD publishes and it did not (read 2026-10-22), all in
  `DwdRadarParameter`: the composites `RS_PRECIPITATION_SUM` (a `.tar` a run as `RV_`, the
  precipitation of the hour), `HX_REFLECTIVITY` and `DMAX_REFLECTIVITY`, `VII_INTEGRATED_ICE` and
  `HYMECNG_PRECIPITATION_TYPE`, each ODIM HDF5; the RADOLAN `YW_REFLECTIVITY`; the unfiltered
  `SWEEP_VOL_` and `SWEEP_PCP_` `ZDR`, `RHOHV` and `PHIDP` (`DwdRadarDataSubset.UNFILTERED`, which
  `subset` need not name); and the XML of `KONRAD3D_CONVECTIVE_CELLS` and
  `MESOCYCLONE_DETECTION` (`DwdRadarDataFormat.XML`, handed over unparsed in `result.data`). The
  radar docs page says what each is (GH-3283)

### Removed

- **Breaking**: the radar BUFR reader is removed: `read_radar_bufr`, `DwdRadarDataFormat.BUFR`,
  `RadarResult.df` and the `read_bufr` setting (`WD_READ_BUFR`, now ignored). DWD's index of
  weather/radar (1.03 million files, read 2026-10-22) holds no BUFR file, nor does any other
  directory of weather/ hold a radar one. `fmt="bufr"` is an `InvalidEnumerationError` and
  `Settings(read_bufr=...)` a `ValueError`, each with the reason; read the ODIM HDF5 `result.data`.
  The `bufr` and `eccodes` extras and the BUFR of `dwd/road` are unchanged. `radarplus` no longer
  installs `pybufrkit` and `bitstring`, which nothing imported (GH-3287)

## [0.167.0] - 2026-10-22

### Security

- The Docker image, and an environment synced from `uv.lock`, now hold certifi 2026.10.19 and
  Pillow 13.0.0 (30 vulnerabilities in `uv audit`), and pypdf 6.21.1 where the `pdf` extra is
  installed (the image has none). certifi drops the `emSign ECC Root CA - G3`, under which eight
  intermediate CA keys are compromised (GHSA-6q48-6c7w-9gw2): a host whose certificate chains to
  it fails the TLS check wherever certifi is the trust store (`WD_USE_CERTIFI`). Pillow reaches
  wetterdienst only through matplotlib. An installation from PyPI resolves its own versions:
  upgrade these there (GH-3280)

### Changed

- **Breaking**: `dwd/radar` reads the layout DWD publishes now (read 2026-10-22). The composites
  `RV_REFLECTIVITY` and `WN_REFLECTIVITY` are one `.tar` a run of ODIM HDF5 files, one for the
  analysis and each lead time (`composite_rv_20261022_1130_005-hd5`), no longer RADOLAN binary
  files packed as `.tar.bz2` or `.bz2`: decode `result.data` with h5py or wradlib's ODIM reader.
  `LATEST` of `RV_REFLECTIVITY` failed with `can only call '.item()'` and that of
  `WN_REFLECTIVITY` handed over the whole tar as one result; both answer the first file of the
  latest run, the analysis, now. `LMAX_VOLUME_SCAN`, `PE_ECHO_TOP`, `PR_VELOCITY`,
  `PX250_REFLECTIVITY` and `PZ_CAPPI` are ODIM HDF5 only, no longer binary or BUFR: leave `fmt`
  out, as a format a product is not served in is a `RequestError` naming the one it is, no longer
  an empty answer (GH-3279)

### Removed

- **Breaking**: `DwdRadarParameter` no longer has `HG_REFLECTIVITY`, `PG_REFLECTIVITY`,
  `PX_REFLECTIVITY`, `PF_REFLECTIVITY`, `RE_REFLECTIVITY` and `RQ_REFLECTIVITY`: `composite/hg`,
  `composite/pg`, `sites/pf`, `radvor/re` and `radvor/rq` hold no file and `sites/px` only stale
  files of a single site (found 2026-10-22), so no request could return a value. A request for
  one is an `InvalidEnumerationError` that says so; use `RV_` or `WN_REFLECTIVITY` for a composite
  or a forecast, `PX250_REFLECTIVITY` for a site. `RADAR_PARAMETERS_RADVOR` is gone with them.
  DWD publishes no radar product as BUFR any more, so `read_bufr` has no effect (GH-3279, GH-3282)

## [0.166.0] - 2026-10-22

### Changed

- **Breaking**: the air temperature of `wsv/pegel` (`LT`, `LUFTTEMPERATUR`) is `temperature_air`,
  no longer `temperature_air_2m`: PEGELONLINE states no height for it. The old name, and
  `temperature_air_mean_2m` of 0.139.0, are refused with the new one named; values and units are
  unchanged. Request, filter and key by the new name (GH-3242)
- **Breaking**: parameters of `dwd/swsmos` and `dwd/derived` are named for what DWD's sheets state.
  `dwd/swsmos`: `temperature_air_2m` (`TL`) is `temperature_air` and `temperature_dew_point_2m`
  (`TD`) is `temperature_dew_point` (no height is stated; the 0.139.0 `..._mean_2m` names too);
  `road_surface_condition` (`RC`) is `road_surface_condition_forecast`, its codes (1 dry, 2 moist,
  3 snow, ...) are not the BUFR ones of `dwd/road` (0 dry, 1 moist, 2 wet, ...), which keeps the
  name. `dwd/derived`: `soil_moisture_winter_wheat_*`, `soil_moisture_mean_winter_wheat_*` and
  `evaporation_amount_winter_wheat_*` are `..._winter_cereals_...` ("Wintergetreide"). The old name
  is refused with the new one named; values and units are unchanged: request, filter and key by the
  new name. Release the app after this backend (GH-3263)
- **Breaking**: the daily maximum wind of `chmi/observation` (`Fmax`) is `wind_speed_max`, no longer
  `wind_gust_max`: CHMI calls it "Max rychlost", the maximum speed, and states no gust. The old name
  is refused with the new one named; values and units are unchanged. Request, filter and key by the
  new name (GH-3264)

### Removed

- **Breaking**: `wsv/pegel` no longer has `chloride_concentration` (`CL`), `precipitation_amount`
  (`NIEDERSCHLAG`) and `precipitation_intensity` (`NIEDERSCHLAGSINTENSITÄT`):
  `stations.json?timeseries=` answers 0 stations for each shortname (786 stations read on
  2026-10-21), so no request could return a value. A request for them is an unknown parameter.
  `chloride_concentration` is no parameter of any provider now, so `chlorid_concentration`, its old
  misspelling, is unknown too; the other providers keep `precipitation_amount` and
  `precipitation_intensity` (GH-3242)
- The `nightly` tag of `ghcr.io/earthobservations/wetterdienst` and `-app` is no longer published:
  the images are built on release tags only. An image pulled by `:nightly` stays at its last
  build, so pull a release tag (`:0.165.0` of the backend, `:0.29.0` of the app) instead (GH-2477)

### Fixed

- The `wsv/pegel` descriptions called every series "a reading"; PEGELONLINE states "ungeprüfte
  Rohdaten", one value per recording interval of the series, and no statistic, so they now say that
  and name the units the series are published in (e.g. `m+NN` stage, `MGN` flow direction)
  (GH-3136)
- The `ipma/observation` wind, precipitation and radiation descriptions were the canonical
  sentences: they now give the source's 10 m (wind) and 1.5 m (precipitation, accumulated over the
  hour) heights, the 8-point wind direction class, and say the radiation's period and kind
  ("global", "horizontal") are not stated by the source (the old text said global, horizontal and
  per interval; the daily course only suggests an hourly sum) (GH-3136)
- `dwd/derived` `daily/soil` and `monthly/soil` listed 479 of the 484 stations of DWD's list: the
  soil files of the stations 44, 73, 78, 91 and 96 (`..._v2_44.txt.gz`, the index is not padded)
  were not found, so those stations were missing and a request for one answered "No station". They
  are listed now and return their values (GH-3257)
- The REST API's row limit estimated a `values` request with `periods=recent` from the whole
  record of each station, so the first documented sample (`daily/kl`, stations 1048 and 4411, 12,319
  rows) was refused on a default server as "about 714,308 rows". The estimate now counts only what
  the requested periods hold (about two years for `recent`, longer for the 1 and 5 minute and the
  annual data, the whole record for datasets with no `recent` release of their own, as hourly
  solar has); a request for the whole record is still refused when it is over the limit (GH-3249)
- DWD descriptions that stated what the source does not: the `dwd/swsmos` liquid precipitation
  (`RRL1c`) read MOSMIX's "consistent with significant weather", and `TL` and `TD` said 2 m (the
  sheet gives no height); the `dwd/poi` new snow was "since the previous observation" (it is in the
  06 UTC report only, with no period stated); the `dwd/derived` soil rows said "winter wheat" for
  DWD's winter cereals; the `dwd/mosmix` `ww3` read as plain `ww`. They now say what the
  sources say (GH-3136)
- The REST API's row limit estimated a DWD `values` request with `periods=now` from the whole
  record of each station, so `10_minutes/temperature_air` at a station recording since 1993 came
  out at about 8.7 million rows against a few hundred read, and the caller was told to stream. The
  estimate now counts the days the `now` files hold, measured on the real files with a margin of
  two (five days for the 1 and 5 minute data, four for the 10 minute data); a request for the
  whole record is still refused when it is over the limit (GH-3271)
- The `chmi/observation` descriptions called the daily mean temperature the average of the 06:00,
  13:00 and 20:00 observations; it is (T06 + T13 + 2 T20) / 4, while humidity, pressure and wind
  speed are the plain average. The monthly and annual rows said "read at 06:00 each day"
  (precipitation) or described a daily value (temperature) and now say they are the month's or
  year's total or mean; the precipitation of a day is the 24 hours from 06:00 UTC of that day, not
  those before it (GH-3136)

## [0.165.0] - 2026-10-21

### Added

- The option `station_window_end_buffer` (`WD_TS_STATION_WINDOW_END_BUFFER`, the command line's
  `--station-window-end-buffer`, a query parameter of `stations` and `values`) sets how many days
  after the end its catalogue publishes a station is still kept for a request window: `0` compares
  the end exactly, and the default (`None`) is the buffer by resolution that applied before: two
  days, 62 for monthly, 732 for annual. `filter_by_name` and the `stations` listing of every
  surface apply it by one rule, the start being compared exactly. `values` reports it in its
  `settings` block (GH-3220)

### Changed

- **Breaking**: nine `geosphere/observation` parameters whose source states a mean are named as
  means (GH-2614): the 10-minute `radiation_global_intensity` (`cglo`),
  `radiation_sky_short_wave_diffuse_intensity` (`chim`), `wind_direction` (`dd`), `wind_speed`
  (`ff`) and `snow_depth` (`sh`), the hourly `radiation_global_intensity`, `wind_direction` and
  `wind_speed`, and the monthly `pressure_air_site` (`p`) are now `<name>_mean`. The old name is
  refused in those datasets with the new one named, values and units are unchanged: request,
  filter and key by the new name. The same fields that state no mean keep their name. Release the
  app after this backend
- **Breaking**: `nws/observation` no longer has `temperature_air_max_2m_last_24h` and
  `temperature_air_min_2m_last_24h` (`maxTemperatureLast24Hours`, `minTemperatureLast24Hours`):
  api.weather.gov answered null in all 49,688 observations of 108 stations read, so no request
  could return a value. A request for them is an unknown parameter; the METAR's 24 hour group
  exists only in its raw message. `meteofrance/synop` still has both names (GH-2614)

### Fixed

- The description of the Geosphere datasets said they hold observations "for Germany" (they are
  Austrian) and, for three of them, only 2 m air temperature and humidity; the `glossary`, the
  `coverage` answers and the docs now say what the source's titles say. The Météo-France daily
  precipitation and new snow windows start at 06h FU, not 06h UTC, overseas (GH-3136)
- The IMGW descriptions of `temperature_air_min_0_05m` say "at the ground (przy gruncie)" and that
  the source states no height, never 5 cm, and the `_2m` air temperatures say the file states no
  height (the shelter convention); the name `temperature_air_min_0_05m` is unchanged (GH-3136)
- The app's forecast chart (also the embeddable widget) was missing its wind barbs at first paint
  and showed them only once something made Plotly draw again, such as a resize of the browser
  window. They are drawn with the chart. App only, no backend release needed (GH-3240)

## [0.164.0] - 2026-10-21

### Changed

- A station `name` is matched without regard to diacritics, on the command line, the REST API,
  MCP and in `filter_by_name`: `Köln`, `Koln` and `koeln` all find `Köln`, `Dusseldorf` and
  `Düsseldorf` find the same stations, `ß` is `ss`, `ł` is `l`. A search that found one
  spelling now finds the others, and a `threshold` of 1 finds a name that differs only in its
  diacritics (GH-2625)
- **Breaking**: the Python `filter_by_name` matches the name among the stations that have a
  record in the `start` and `end` of the request, as `stations` and `values` with a `timestamp`
  already do, a `df_all` you pass included: a station that closed before the window or began
  after it is no match. Build the request without `start` and `end` to match all stations as
  before (GH-2625)
- **Breaking**: five parameters of `dwd/road` and `ipma/observation` are named for what their
  source's value is (GH-2614). `dwd/road`: `temperature_air_2m` (`airTemperature`) is
  `temperature_air` and `temperature_dew_point_2m` is `temperature_dew_point`, the sensors stand
  4 to 5 m above ground and never at 2 m; `humidity_relative_mean` is `humidity_relative`, a
  reading and no mean. `ipma/observation`: `humidity_relative` is `humidity_relative_mean` and
  `pressure_air_sea_level` is `pressure_air_sea_level_mean`, IPMA's hourly means. The old name is
  refused with the new one named, values and units are unchanged: request, filter and key by the
  new name. Release the app after this backend
- **Breaking**: a wind direction of 0 is null, with `raw:0` in `quality_flags`, only beside a speed
  of 0 of the same reading, a calm, in every provider; a 0 beside a wind that blows is 0 degrees,
  where it was null in `dwd/observation` hourly `wind` and subdaily `wind` (beside a force of 0),
  `dwd/poi`, `eccc` daily gust, `fmi`, `meteofrance/observation` (`DD`, `DXI`),
  `meteofrance/synop`, `noaa/ghcn` hourly and `smhi`. SMHI reads the speed with the direction, one
  more download when only the direction is asked for. Tell a calm by `raw:0` in `quality_flags` or
  by the speed beside the direction, and filter on it for the old nulls; the rules of every special
  value are on the new docs page `data/special_values` (GH-3222)
- **Breaking**: `meteoswiss/observation` `wind_direction_mean` (10 minutes, hourly, daily) is null,
  with `raw:0` in `quality_flags`, where the file holds a 0 beside a speed of 0, a calm (912 of the
  1,169 zeros of BER, SMA and JUN in 2024): it was 0 degrees, north. A 0 beside a wind that blows
  stays. Filter on `raw:0` or on the speed for the old calms (GH-3222)
- **Breaking**: a value cell that is the text `nan` or `inf` is null and counted in the core's debug
  line, as a text that is no number is; a cast made it a NaN or an infinity. Test for null, not for
  NaN. A number padded with blanks is read, where it was null (GH-3222)

### Fixed

- `stations` with a point and a `rank` (command line, REST API, MCP) lists `rank` stations, each
  with a row per requested dataset; with two datasets it counted rows and `rank=2` listed one
  station twice (GH-2625)
- **Breaking**: `dwd/road` returns a value outside the physical range of its quantity as null, with
  the number DWD wrote as `raw:<number>` in `quality_flags`, as `dmi` and `rmi` do: the -75 °C of a
  stopped sensor (`raw:198.15`, in kelvin) and any temperature below -60 °C. It was returned as
  published, marked `1`. Read the `raw:` token, with `drop_nulls=False`, for the number (GH-3222)
- `ipma/observation` and `lhmt/observation` read a value that is a text and no number, or a JSON
  `NaN`, as null and count it in the core's debug line: such a cell raised and failed the request,
  and LHMT returned a `NaN` as a value (GH-3222)

## [0.163.0] - 2026-10-20

### Changed

- **Breaking**: five parameters are named for what their source's value is (GH-2614).
  `dwd/dmo` `icon`: `radiation_global_last_3h` (`rads3`) is `radiation_short_wave_net_last_3h` and
  `radiation_sky_long_wave_last_3h` (`radl3`) is `radiation_long_wave_net_last_3h`, DWD's radiation
  balances, positive downward. `dwd/observation` monthly and annual: `snow_depth` (`mo_sh_s`,
  `ja_sh_s`) is `snow_depth_sum`. `geosphere` daily: `temperature_air_min_0_05m` is
  `temperature_air_min_0_05m_night`. `dmi` daily: `precipitation_amount_max` is
  `precipitation_amount_max_30min`. The old name is refused with the new one named, values and
  units are unchanged: request, filter and key by the new name. Release the app after this backend
- **Breaking**: 19 canonical names that no dataset of any provider declares are gone from the
  parameter table, so the glossary of the docs, the API and the app no longer lists them and
  `geo_station_distance` no longer takes them as a key (GH-2614). No dataset could be asked for
  them. A request for `radiation_global_last_3h` or `radiation_sky_long_wave_last_3h` is refused
  with the name to use, `radiation_short_wave_net_last_3h` or `radiation_long_wave_net_last_3h`;
  for `groundwater_level_max`, `groundwater_level_min` and the two
  `evapotranspiration_potential_grass_*_last_24h` as before, in their dataset. The rest, among
  them `cloud_base_convective`, `temperature_radiant_mean_2m` and eleven `quality_*` flags, is an
  unknown parameter, and so is `quality_precipitation_height` (and `_liquid`): its rename to
  `quality_precipitation_amount`, which no dataset declared either, is gone with it

## [0.162.0] - 2026-10-20

### Changed

- The dependency is now `polars[calamine]>=1.43.2,<3` (it was `>=1.43.0`): 1.43.0 and 1.43.1 are
  yanked on PyPI, so no installer resolved them by default and 1.43.2 is the oldest polars a caller
  can get. Pinned environments that still hold 1.43.0 or 1.43.1 upgrade polars (GH-3138)
- AEMET: the `Ip` (inapreciable) of a precipitation below what the gauge reads is 0.0, with
  `raw:Ip` as the last token of `quality_flags`, in `precipitation_amount` (daily, monthly,
  annual) and `precipitation_amount_max` (monthly, annual); it was null. A day of trace now
  counts in a sum, as in KNMI (`-1`) and Météo-France synop (`-0.1`), which already read a
  trace as 0.0. Every other text that is no number stays null with its text (GH-3188)
- IMGW: the `attribution` in the `metadata` block of its answers carries both statements the
  terms prescribe, the source of the data (§ 5 ust. 3) and that the data were processed (§ 5
  ust. 4), and `license.url` links the terms' PDF, not the portal. The docs say that the data
  are free for private use only, since IMGW has declared none high-value, and that a business
  use needs an agreement with IMGW (GH-2567)
- The app's climate stripes and forecast chart (also the embeddable widget) have a text
  alternative: the chart is described by a sentence, and "Show as table" below it lists what it
  draws, every year with its value and class for the stripes, every time with the values of the
  shown panels for the forecast, so a screen reader or a keyboard reads the data that colour and
  shape carry. Plotly's modebar buttons were found keyboard-operable already and are now held so
  by a test (GH-3145)

### Fixed

- DMI, RMI, MET Norway Frost and DWD (`dmo`, `mosmix`, `poi`): a station list the source answers
  with no station is the empty stations frame now. DMI and RMI answered one station with every
  column null, Frost and the fixed-width lists of DWD (a header and no row) raised (GH-3203)
- NOAA GHCN (`hourly`, `daily`), IMGW (`hydrology`, `meteorology`) and WSV (a stage or another
  parameter that is scaled to its unit): a value cell that is a text and no number is null now,
  as in every other provider, where it raised and lost the whole station. The rows around it
  are returned (GH-2627)
- ECCC `monthly` stations have no `end_timestamp` any more: the station list's `MLY_LAST_DATE` stops
  at 2018-02 for every station while the monthly rows run to 2026-09, so a `timestamp` after 2018
  left out every station with monthly values, and with it `stations` and `values` with a `name`
  found none. The daily and hourly ends are unchanged (GH-3026)
- `dwd/observation` `hourly/moisture`: `pressure_air_site` (`P_STD`) is also null in a file of at
  least 500 readings that holds two or three distinct values, the pressure of a station without a
  barometer whose constant changed (55 files, e.g. 953.1 then 954.8 at 00142, 977.1 then 977.6 at
  00091); no other file holds fewer than 47. Each value stays as the last
  `quality_flags` token (`raw:954.8`). Take the pressure of another source for such a station
  (GH-3139)
- `metno/frost` daily and monthly `sunshine_duration` is in hours, as Frost's `unit` of every
  observation says, and comes back as the seconds of those hours: it was read as seconds, so the
  values were 3,600 times too small (10.4 hours of sunshine came back as 10.4 s) (GH-3137)
- `knmi/observation` 10-minute `cloud_cover_total` is null, with `raw:9` in `quality_flags`, where
  the file holds a 9, the sky obscured by fog (128 of 11,293 readings in two weeks of October
  mornings): it was 1.125, as the hourly and daily cloud cover were before (GH-3135)
- `aemet/observation` hourly `wind_direction_mean_last_10min` is null, with `raw:0` in
  `quality_flags`, where the feed writes a 0 beside a mean speed of 0, a calm (112 of its 114 zeros;
  north is 360): it was 0 degrees. A 0 beside a speed above 0 stays (GH-3135)
- `metoffice/observation` hourly `wind_direction_mean_last_10min`, `wind_direction_mean` and
  `wind_direction_gust_max` are null, with `raw:0`, where the file holds a 0 beside a speed of 0 (the
  gust direction beside the gust speed), a calm: the table says zero direction and speed mean no
  wind, and north is 360. A 0 beside a speed above 0 stays. `cloud_cover_total` is null where the
  file holds a 9, the sky obscured. They were 0 degrees and 1.125 (GH-3135)
- `metoffice/observation` hourly `rain`, `wind` and `radiation` keep only the readings of one hour
  (`ob_hour_count` 1): the 12 hour rain totals ending 09:00 and 21:00 and the 24 hour radiation
  totals, which are in the same files, replaced the reading of their hour with the maximum (GH-3137)
- The `wsv/pegel` parameter descriptions no longer say "average ... during time scale": the values
  are the raw readings PEGELONLINE publishes (`... ROHDATEN`) at the recording interval of each
  series. The data are those of the last 31 days, not 30 (GH-3136)
- The `metoffice/observation` docs and the descriptions of the daily temperatures say that a day is
  the date of `ob_end_time` (the source's 09Z day) and that 24-hour 09-09Z rows (2,962 of 14,334)
  fall on the day after most of their coverage, where the docs said the true daily extreme was
  recovered (GH-3137)

## [0.161.0] - 2026-10-19

### Changed

- **Breaking**: the stations of a `name` come back best match first, not in the order of the station
  list, and `rank` counts stations: `filter_by_name(name, rank=3)` is at most three stations, with
  all their rows, where a station with several datasets used up the rank with its own rows and two
  stations of the same name both came back. Equal scores are ordered by `station_id`. Callers that
  relied on the order of the list sort the result themselves (GH-3025)
- `values` with a `name` and a `timestamp` (command line, REST API, MCP) matches the name among the
  stations that have a record in the window, as `stations` does, so the best match is no station that
  closed before it while one of the same name is open. A window that no station of the name covers is
  an empty result. The Python `filter_by_name` still matches all stations: pass the stations of the
  window as `df_all` (GH-3026)

### Deprecated

- `Wetterdienst(provider, network)` and the CLI command `wetterdienst stripes values` are removed in
  1.0.0, as the `DeprecationWarning` and the command's notice now say: use
  `Wetterdienst.resolve(provider, network)` (`resolve_standalone` for `dwd/radar` and
  `dwd/alerts`) and `wetterdienst stripes image`. Both work unchanged until then (GH-3128)

### Fixed

- `ea/hydrology` daily `groundwater_level_max` and `groundwater_level_min`, which became `stage_max`
  and `stage_min` (GH-2632), are refused with the new names, as `dwd/derived` monthly
  `evapotranspiration_potential_grass_fao_last_24h` and `..._haude_last_24h` are now with
  `evapotranspiration_potential_grass_fao` and `..._haude`; they said only "not found" (GH-3168)
- A `filter_by_sql` on a wide frame names the new column for a parameter that was renamed in one
  dataset only (`wind_speed` for `wind_speed_mean_last_10min`) when the frame has it, as it does
  for the other renames. A key of `geo_station_distance` for such a name is still accepted, as the
  name is a parameter of the datasets that keep it; key the new name for the renamed one (GH-3008)
- The CLI no longer answers an unknown option with a refused one: `wetterdienst stations
  --lead-time=long` suggested `--end-date`, which is itself refused in favour of `--end`. Refused
  options are left out of "Did you mean", and a renamed option still names the new one (GH-3167)
- **Breaking**: reading a `dwd/mosmix` or `dwd/dmo` run that fails raises the `DownloadError` of
  every other download, or the `NoInternetError` where no connection could be made, with the failure
  as `__cause__`, where a TLS failure was a bare `ssl.SSLError`, a reset, timeout, 5xx or cut-short
  body the aiohttp or fsspec error, and a missing run (or any failure with the cache disabled) a
  `FileNotFoundError`. The REST API answers 502, 503 or 504 for them, not 500. Catch `DownloadError`
  and `NoInternetError` instead of those (GH-3120)

## [0.160.0] - 2026-10-18

### Added

- `start` and `end` of a request take a month and a year as strings, `"2020-05"` and `"2020"`, as
  the whole span they name, as the REST, CLI and MCP `timestamp` always read them: `start="2020-05"`
  begins at the first instant of May and `end="2020-05"` ends at 23:59:59.999999 UTC of the 31st. A
  bound given alone is the span. A `datetime` and a string with a time stay exact. A string that is
  none of day, month, year or time is refused with the forms listed (GH-3155)

### Changed

- **Breaking**: the mean of the irradiances, the soil moisture, the snow depth, the precipitation
  intensity and the Beaufort wind force carries its statistic in the name (GH-3151, last of three
  families): where the source states a mean of the row's interval they are
  `radiation_global_intensity_mean`, `radiation_sky_long_wave_intensity_mean`,
  `radiation_sky_short_wave_diffuse_intensity_mean`, `precipitation_intensity_mean`,
  `snow_depth_mean`, `wind_force_beaufort_mean` and `soil_moisture_mean_<cover>_<soil>_<depth>`
  (35 rows, 6 networks: MeteoSwiss, KNMI, MET Norway, RMI, DWD derived and observation). The old
  name is refused with the new one named; `wsv/pegel` stays as it was until WSV confirms its
  "average". All rows are in the parameters page of the docs. Release the app after this backend
- **Breaking**: the mean of humidity, pressure, cloud cover and visibility carries its statistic in
  the name (GH-3151, second of three families): where the source states a mean of the row's interval
  `humidity_relative`, `pressure_air_site`, `pressure_air_sea_level`, `pressure_vapor`,
  `cloud_cover_total` and `visibility` are `<name>_mean` (81 rows, 14 networks, e.g. DWD daily and
  monthly, MeteoSwiss, DMI, IMGW, MET Norway), and NOAA GHCN's average cloudiness is
  `cloud_cover_total_mean_midnight_to_midnight` etc. Rows whose source states no statistic or a
  reading at one moment keep the plain name. The old name is refused with the new one named: change
  the `parameter` you request and filter on, wide column names, SQL filters and
  `geo_station_distance` keys. All rows are in the parameters page of the docs. Release the app
  after this backend
- **Breaking**: the mean wind carries its statistic in the name, as `temperature_air_mean_2m` does
  (GH-3151, first of three families): where the source states a mean of the row's interval the name
  is `wind_speed_mean` / `wind_direction_mean` (46 rows, 13 networks), and a mean of a shorter
  window is `wind_speed_mean_last_10min` etc. (were `wind_speed_last_10min`; the Met Office hourly
  `weather` rows were `wind_speed`, GH-2838). Rows whose source states no statistic keep
  `wind_speed` / `wind_direction`. The old name is refused with the new one named: change the
  `parameter` you request and filter on, wide column names, SQL filters and `geo_station_distance`
  keys. All rows are in "The statistic in a name" of the docs' parameters page. Release the app
  after this backend
- **Breaking**: `knmi/observation` `hourly` values are stamped with the end of their hour, KNMI's own
  timestamp, where they were stamped with its start: the air temperature KNMI gives for 12:00 UTC
  was returned as 11:00, the hourly sums and means as the hour that begins at the stamp. Every
  hourly `timestamp` moves 1 hour later, and a request for `start`..`end` returns the hours that
  end in it, so `start` = `end` = 12:00 returns the hour 11-12. `10_minutes` (the file name is its
  end) and `daily` are unchanged (GH-2824)
- **Breaking**: a remote listing (`list_remote_files_fsspec`, `list_remote_directory_fsspec`, so
  every provider that lists) that fails on TLS, a certificate that does not verify or a handshake
  that fails, raises a `DownloadError` naming the URL, with the `ssl.SSLError` as its `__cause__`,
  as a download does, not the bare `ssl.SSLError` (REST: 500, now 502). Code that caught
  `ssl.SSLError` around a listing catches `DownloadError` and reads `__cause__` now; a TLS failure
  is still asked for once (GH-3099)
- The OpenAPI document of the REST API is complete: `info` names Wetterdienst with its version,
  licence and contact (it was FastAPI's "FastAPI 0.1.0"), and `info.x-api-version` is the API
  version, `1`. There are `servers` and described `tags`. `/health` and `/version` have response
  schemas, the index, `robots.txt` and the stripes image their media types, and each route declares
  the problems it can answer (400, 403, 404, 500, 501, 502, 503, 504) as references to
  `components.responses`, where the 400 and 502-504 of the data routes were inline. 13 parameters
  have descriptions. A client that reads `responses` of the document has to resolve `$ref` in them
  (GH-3129)
- **Breaking**: `Settings(ts_shape=...)` and the other `ts_*` settings are gone, with reading or
  assigning `settings.ts_*` and a `settings={"ts_...": ...}` dict, which warned since 0.148.0; they
  are a `ValidationError` that names the option to pass instead: `options=Options(shape=...)` (or
  `options={"shape": ...}`) on the request. The `WD_TS_*` variables are unchanged (GH-3128)
- **Breaking**: the fields `df_all`, `stations_filter` and `rank` of `StationsResult`, which say how
  `df` was selected, are private: `_df_all`, `_stations_filter` and `_rank`, also as the keywords of
  its constructor. A caller that read them reads `df`; the frozen public surface leaves them out
  (GH-3128)
- **Breaking**: a `start` or `end` of a request that is a date without a time (`"2026-01-31"`, a
  `datetime.date`) is the whole day, as the REST `timestamp` always read it: `end="2026-01-31"`
  includes the 31st to 23:59:59.999999, where it ended at midnight and left out the day. A date
  alone is the whole day too. A `datetime` or a string with a time stays that exact instant; end a
  window at midnight with `end="2026-01-31T00:00:00"`. A `date` is accepted as a bound (GH-3133)

### Fixed

- `knmi/observation`: the sunshine duration `SQ` of KNMI's `-1` ("less than 0.05 hour") is 0.0, with
  `raw:-1` in `quality_flags`, where the `-1` came back as -3600 s, and the `9` of the hourly cloud
  cover `N` and the daily `NG`, a sky that is invisible, is null, where it came back as a cloud
  cover of 1.125 (GH-3123)
- `smhi/observation` hourly `cloud_cover_total`: SMHI's 113 is null, with `raw:113` as the last
  token of `quality_flags`, no longer returned as a cloud cover of 1.13. It is the 9 of the oktas
  scale, a sky that cannot be observed (fog, snow drift), written as a percentage: station 182910
  writes it in 427 of 3,140 hours (GH-3122)

## [0.159.0] - 2026-10-18


### Added

- `wetterdienst stripes image` writes the climate stripes image, named as `/api/stripes/image` and
  the MCP tool `stripes_image` are. `stripes values`, which wrote the image while REST's
  `stripes/values` answers the yearly data, still writes it, with a deprecation notice on stderr
  (stdout stays the image alone); use `stripes image` for the image (GH-3035)
- `/api/providers` counts the different parameters its networks declare in
  `metadata.counts.parameters`, beside `providers` and `networks`; the app's home page
  states that number instead of one it was written with (GH-3105)

### Changed

- **Breaking**: the Docker image listens on 7890 by default (`EXPOSE` and the `CMD` of both stages),
  as `wetterdienst restapi` does outside Docker, and `compose.yml` publishes 7890 and reaches the
  backend there; it was 3000. A deployment that maps `3000:3000` or asks the container for port 3000
  maps `3000:7890` (or `7890:7890`) now, or starts it with `--listen 0.0.0.0:3000` (GH-3106)
- **Breaking**: `aemet/observation`: a rate limit that outlasts the retries (an HTTP 429 or an
  `estado` of 429 in the envelope) raises a `DownloadError` naming the file, the 429 as its
  `__cause__`; the REST API answers a 502. It was logged and the chunk skipped, so a rate-limited
  request returned a partial or empty result as if AEMET had no data. Catch `DownloadError` (or
  `UpstreamError`) to keep going, and retry later (GH-2989)
- **Breaking**: a remote listing (`list_remote_files_fsspec`, `list_remote_directory_fsspec`, so
  every provider that lists) whose connection is reset or dropped, whose body stops arriving, that
  times out or that is refused with an HTTP status raises a `DownloadError` naming the URL, with
  the aiohttp error as its `__cause__`, not the raw aiohttp error (REST: 500, now 502 or 504). A
  code that caught `aiohttp.ClientError`, `OSError` or `TimeoutError` around a listing catches
  `DownloadError` (or `UpstreamError`) now; a connection that cannot be made stays the
  `NoInternetError` (GH-3004)
- **Breaking**: the MCP endpoint (`/mcp/v1`, `/mcp`) is stateless. It creates no session, sends no
  `mcp-session-id` and needs no `initialize` before `tools/list` or `tools/call`; `DELETE` and the
  `GET` that opens a server stream answer 405. A client that sends a session id is served as one
  without. The tools held no session state, so nothing else changes; a client that depended on
  being given a session id has to stop (GH-3088)
- **Breaking**: the rows of `values` are estimated for a station whose record the provider does not
  publish too, so that `WD_RESTAPI_MAX_ROWS` holds for a request without a `timestamp`: from 1950
  for a dataset with historical data, two years back for recent data and two days for current data.
  Such a request used to be counted as no rows and can be a 400 `limit-exceeded` now: give a
  `timestamp` or use `format=ndjson` or `csv`. Forecasts are not counted (GH-3089)
- A request that has not been answered within `WD_RESTAPI_TIMEOUT` is no longer
  cancelled but left to end with its answer dropped, and it counts as being served until it has
  (see `WD_RESTAPI_MAX_CONCURRENT`). `GET /api/version` reports `limits.max_concurrent` (GH-3089)

### Fixed

- `nws/observation` follows the pages of the endpoint (`pagination.next`) until the window has been
  read: a window of more than 500 observations, about 40 hours at a station's 12 an hour, came
  back as its newest 500 with no warning. The last 5 days of KBOS are 121 hourly rows now, not
  about 40. A window costs one request per 500 observations (a week is five), a request without
  dates reads the endpoint's whole week (GH-2994)
- The warning for a parameter a dataset does not have no longer offers the direction of the mean wind
  for the direction of a gust, nor the reverse: `meteofrance/observation` `hourly/core`
  `wind_direction_gust_max`, no longer served (GH-2836), no longer suggests
  `wind_direction_last_10min` (GH-3009)
- `eccc/observation` lists a station for `monthly` only if the station list flags a monthly
  summary (`HAS_MONTHLY_SUMMARY` is `Y`), no longer all 8435 stations: the 108 whose flag is `N` or
  empty have no monthly row, so `filter_by_rank`, `filter_by_distance`, `interpolate` and
  `summarize` for monthly no longer pick them. Hourly and daily are unchanged (GH-3006)
- `dwd/observation` `hourly/urban_wind` `wind_direction`: a 0 is null, with `raw:0` as the last
  token of `quality_flags`, no longer returned as a bearing. The 1,288 zeros come at 0.1 to
  1.6 m/s, never 0, and in the 410 of those hours with the six 10-minute values at hand the
  directions are spread over the compass (1 of the 2,460 is 0), so it is neither a calm nor
  north, which the file writes as 360. DWD has not been asked (GH-2809)
- `dwd/observation`: of a stamp that a file lists twice, a row with a value in some parameter wins
  over one with none, where the first row was kept: `10_minutes/precipitation` of station 03086
  lists 1002 stamps of 1999-08-04 to 1999-12-31 twice, a reading and a `-999` placeholder, and 74
  readings were lost (about 1000 when a second period is requested, which orders the rows by their
  values first). Two rows with a value, or two without, are settled as before (GH-2996)
- A query value that JSON has no number for (`distance=1e999`, `skip_threshold=nan`) or a JSON
  mapping nested thousands of levels deep (`unit_targets`, the station distances) is a 422 problem,
  as any malformed value is, instead of a 500. What an `errors` entry repeats as `input` is cut off
  below 16 levels of nesting (GH-3085)
- `dwd/mosmix` and `dwd/dmo` no longer send an HTTP HEAD for a run the cache holds: the size
  for the progress bar is read from the cached file, so a cached run is read with no request
  at all (GH-3003)
- A `rank` or `num_additional_stations` that no integer holds (`rank=99999999999999999999`) was a
  500 `OverflowError`; it is a 422 now, as one above 1,000,000 is (GH-3101)
- Docs that stated something the code does not do are corrected: the metadata example of the
  contribution guide named none of the provider fields (`name_short`, `country_code`, `license`,
  ...) that `build_metadata_model` requires, so it raised; the `limit-exceeded` problem of the REST
  API page lacked the `instance` and `request_id` every problem has; the interpolation example
  gave kelvin where the default is °C; the DWD alerts page started the API on port 3000, not the
  default 7890. The pages' code samples are now run by tests (GH-2621)
- More docs that stated what the code does not do: the station history page promised snapshots at a
  date and lifecycle events (a history has five sections, `name`, `parameter`, `device`,
  `geography` and `missing_data`, and only DWD observation has one, the others raise
  `NotImplementedError` or answer 501), the data overview and DWD pages gave station counts that
  have drifted ("more than 5000" now) and left out the DWD networks `poi`, `derived` and `alerts`,
  and the README said the rest is tuned through `Settings`, which is `Options` for a request.
  The Python API page lists the keywords of every formatter (GH-2621)

### Security

- `wetterdienst restapi` started on a loopback `--listen` (`127.0.0.1`, `::1`, `localhost`, the
  default `127.0.0.1:7890`) answers to the loopback names only: another `Host` is a 400 problem of
  the kind `host-not-allowed`, and an MCP request with another `Origin` is `origin-not-allowed`, so
  a web page cannot reach a local server by DNS rebinding. A local server that is reached by another
  name sets `WD_RESTAPI_ALLOWED_HOSTS` (comma-separated names, a port optional, `*.example.org`) to
  its names; a server on any other address, or started otherwise, answers to every host unless it
  is set (GH-3087)
- At most `WD_RESTAPI_MAX_CONCURRENT` requests under `/api` (32 by default, 0 for no limit) are
  served at once; one past it is a 503 problem of the kind `server-busy` with `Retry-After`. A
  request keeps its place until its handler is done, also after the 504 of the timeout, so the cap
  bounds the threads that requests leave running. Raise it for a host that is meant to serve more
  (GH-3089)
- `/api/issues`, the MCP tool `issues` and `wetterdienst issues` refuse a `station` that is not an
  id (letters, digits, `_`, `-` and, after the first character, `.`, up to 32 characters) with a
  422 problem, or a usage error on the command line. It was put into the path of the directory DWD
  is asked to list as it came, so `..` listed other directories of `opendata.dwd.de` (GH-3084)
- `/api/providers` no longer puts the text of an `ImportError` into the `warnings` of its answer,
  which could name a path of the server: it names the network and, for a missing module, the module.
  The text is in the server log (GH-3086)

## [0.158.0] - 2026-10-17

### Added

- The MCP endpoint is versioned like the REST API: `/mcp/v1` is the endpoint to configure, and
  `/mcp` stays as an alias of the current version, the same endpoint with the same tools and
  sessions. A breaking change of a tool will come with `/mcp/v2`, and `/mcp/v1` keeps serving for
  at least two minor releases. `GET /api/version` reports `mcp_path` (`/mcp/v1`) and
  `mcp_alias_path` (`/mcp`), `null` without the `[mcp]` extra; the index page lists `/mcp/v1`.
  Nothing a client has configured at `/mcp` changes (GH-3074)
- `Settings(...)` is checked by `ty`, mypy and pyright field by field: a misspelt setting
  (`Settings(cache_dsable=True)`) or a value of the wrong type is reported where it is written, not
  as a `ValidationError` at run time. Nothing changes at run time (GH-3042)
- The dictionaries that the results return have public names to annotate a function with:
  `StationsDict`, `StationsOgcFeatureCollection`, `ValuesDict`, `ValuesOgcFeatureCollection`,
  `InterpolatedValuesDict`, `InterpolatedValuesOgcFeatureCollection`, `SummarizedValuesDict`,
  `SummarizedValuesOgcFeatureCollection`, `HistoryDict` and `ResultMetadata`, importable from
  `wetterdienst.model.result` instead of the underscored classes they are aliases of (GH-3046)
- `GET /api/providers`, `wetterdienst about providers` and the MCP tool `providers` say what each
  provider is: names (`name_short`, English, local), country (`country_code`, ISO 3166-1 alpha-2),
  `license`, `attribution`, and its networks with their kind, source URL, whether they need credentials and the resolutions and
  datasets they offer. Nothing is downloaded or probed. A network declaration has to give
  `country_code` now, null for a provider of several countries (GH-2565)
- With `with_metadata=true`, `metadata.quality.legend` says what each kind of `quality_flags` token
  means for the network read (`zone:`, `validity:`, `raw:`, ...), with the codes where the source
  documents a closed set (GH-3060)
- The REST API and the MCP tools refuse a request that would return more than the server allows,
  with a 400 problem of the kind `limit-exceeded` before anything is downloaded: it names the
  `limit`, its `maximum` and what the request comes to (`requested`), and how to narrow it. The
  limits are the stations of one `values` or `history` request (100), the estimated rows of an
  answer sent as one body (500,000) and of a streamed one (10,000,000), set with
  `WD_RESTAPI_MAX_STATIONS`, `WD_RESTAPI_MAX_ROWS` and `WD_RESTAPI_MAX_STREAM_ROWS`; 0 is no limit
  (GH-3065)
- `stations` and `values` answer `format=ndjson`, and their `format=csv` is streamed too, station
  by station instead of held in memory. NDJSON is the `metadata` block, a line for each row and an
  `end` line with the counts and every warning, or an `error` line if a later station fails; the
  CSV carries the block in its headers. `wetterdienst stations` and `values` take
  `--format=ndjson` and write the same lines (GH-3065)
- A request is held to one timeout, `WD_RESTAPI_TIMEOUT` (60 seconds, 0 for none): the 504 problem
  `request-timeout` with `Retry-After` if it is not answered by then. A stream is held to it
  between two chunks. What was fetched is cached for the retry (GH-3065)
- Every problem has a `type` of its own, `urn:wetterdienst:problem:<kind>` (listed in the REST API
  docs), an `instance` and a `request_id`, and every response an `X-Request-ID` header, the
  client's own if it sends a plain one. A 502, 503 or 504 carries `Retry-After`. A response to a
  request that uses something deprecated carries `Deprecation`, `Sunset` and `Link`; the policy is
  in the docs (GH-3065)
- `GET /api/version` reports the `limits` of the instance: `max_stations`, `max_rows`,
  `max_stream_rows` and the `timeout` in seconds, 0 for none, so a client can size its requests
  before one is refused (GH-3078)

### Changed

- The answers of `issues`, `alerts` and the three `stripes` endpoints carry the `metadata` block
  too, over REST, on the command line and in the MCP tools. `stripes/stations` keeps the `provider`
  and `producer` it had, and the GeoJSON of `alerts` has it as a foreign member. These and `history`
  are in the OpenAPI document with a response model now; the MCP tools `alerts` and `stripes_*`,
  whose model is a union with text for CSV, answer `{"result": ...}` as `stations` does; read
  the answer from `result` (GH-3059)

- Results compare by what they hold: `result == other` is true for two results of the same class
  whose frames have the same columns, dtypes and values in the same order and whose other fields
  (the request, the point of an interpolation) are equal. It raised polars' "truth value of a
  DataFrame is ambiguous" before. A result stays unhashable (GH-3037)
- AEMET asks again once when it answers a 401 (or an `estado` of 401) to the key, which it
  accepts on the next request, and raises `CredentialRejectedError` only when it refuses it twice
  (GH-3022)
- **Breaking**: a `metoffice/observation` token exchange with CEDA that does not answer (a timeout,
  a dropped connection, a 5xx, a TLS failure) raises `DownloadError`, where it was a warning and
  an empty result. Catch `DownloadError` (or `UpstreamError`) where you relied on the empty frame
  (GH-3022)
- **Breaking**: `noaa/ghcn` `hourly` returns one reading for each parameter and full hour, the one
  nearest to the hour (a parameter a SPECI lacks is read from the report that has it), stamped with
  the hour: the METAR of 14:53 is 15:00. It returned every report of the file under its own minute,
  up to seven an hour at Denver, which `interpolate`, `summarize` and `skip_empty` could not find on
  the full-hour grid. The minute of a report is not returned; read the GHCNh file for it. The
  precipitation of source 412 (`FM94_1`) stays, marked `source:412`; it does not agree with the
  station's gauge, see the provider page (GH-3000, GH-3016)
- `rmi/observation` `sun_duration` of station 6477 is null, with the source's value as `raw:<value>`
  in `quality_flags`, from 2016-04-30 to 2017-05-31 (a stuck sensor, 13 days of exactly 1,440
  minutes among them) and in two summers of zeros (2015-04-25 to 2015-08-19, 2017-06-02 to
  2017-09-19), in all three resolutions; they were returned as readings. See the provider page
  (GH-3031)
- **Breaking**: the answer of `stripes/values` has the `station`, `resolution`, `dataset`,
  `parameter` and `unit` of its values in a `series` member, no longer in `metadata`, which is only
  the metadata block, as for every other endpoint. Read `answer["series"]["unit"]` where you read
  `answer["metadata"]["unit"]`; the same for the other four, in the MCP tool `stripes_values` too
  (GH-3076)
- **Breaking**: `values` refuses more than 100 stations (`all=true` on a network of more), and any
  answer over the row limits above, with the 400 `limit-exceeded`. Request fewer stations or a
  shorter `timestamp`, use `format=ndjson` or `csv` for a long answer, or raise the limits on your
  own server with the settings above (GH-3065)
- **Breaking**: the `type` of a problem was always `about:blank`; it names the kind of error now,
  `urn:wetterdienst:problem:<kind>`. Branch on it instead of on the text of `detail` (GH-3065)
- **Breaking**: a network without station history (`/api/history`) and an `/api/issues` for a
  network that lists none answer 501, where they answered 404 and 400: a `NotImplementedError` is
  now decided by `failure_status` like every other failure (GH-3065)
- The CSV of `stations` and `values` is sent in chunks, the same bytes as before, and without the
  `X-Wetterdienst-Rows` header, which the rows are not known for as the headers go out (GH-3065)

### Removed

- **Breaking**: `summarize` no longer takes `use_nearby_station_distance` (deprecated since 0.140.0,
  it was read by nothing): `--use-nearby-station-distance` of `wetterdienst summarize` is an unknown
  option, and the REST API (a 422) and the MCP tool refuse the parameter. Leave it out; a summary
  takes the nearest station with data. `interpolate` keeps its own (GH-3077)
- **Breaking**: `StationsResult.get_metadata()` is gone: it was the `metadata` block of the REST,
  CLI and MCP formats, which a result writes under `with_metadata=True` in `to_dict`, `to_json` and
  `to_geojson`. Read those, or `request.metadata` (a `MetadataModel`, with the licence at
  `request.metadata.license`) for the provider and `Info().to_dict()` for the library (GH-3047)
- **Breaking**: `TimeseriesValues` no longer has the attributes `stations_counter` and
  `stations_collected`, nor takes them as constructor arguments. `query()` kept them for nobody; the
  stations a query returned are in the `station_id` column of the results (GH-3037)

## [0.157.0] - 2026-10-17

### Added

- Every JSON and GeoJSON answer of `stations`, `values`, `interpolate`, `summarize` and `history`,
  over REST, on the command line and in the MCP tools, carries a `metadata` block, with or without
  `with_metadata`: the provider's `license` (SPDX identifier, name, URL; null where it states none)
  and `attribution`, the request as resolved, `retrieved_at`, `counts`, `crs`, `warnings` (each with
  a stable `code`: an unknown station id, a skipped station, ...), `api_version` and
  `schema_version`. `with_metadata=true` adds the unit of each parameter and what `quality_flags`
  holds. The library has the licence at `request.metadata.license` (GH-2561)
- Those answers, CSV and images included, carry the same in the headers `X-Wetterdienst-API-Version`,
  `-Schema-Version`, `-Retrieved-At`, `-Provider`, `-License`, `-Attribution`, `-Stations`, `-Rows`
  and `-Warnings`, and a `Link: <licence>; rel="license"` (GH-2561)
- The `metadata` block says the licences as the providers state them: CHMI is CC BY 4.0 and NOAA
  GHCN CC0 1.0, IMGW and IPMA have terms of their own (`license.spdx_id` null, with the name and
  the link of the terms; IMGW's credit line is the Polish sentence its terms prescribe), and DMI
  links its terms of use, as its documentation host answers 404. `request.stations` has a `count`
  and lists `ids` for up to 100 stations, else `ids` is null; read the ids from the body (GH-3061)

### Changed

- `wetterdienst stations` no longer takes `--lead-time` and `--issue`, which 0.156.0 added, and
  the MCP `stations` tool no longer takes `lead_time` and `issue`: they never changed the list, the
  run being chosen for `values`. Drop the flag or argument, or pass it to `values`; `wetterdienst
  stations --lead-time=...` now fails with click's `No such option`, and a tool call with either
  with a tool error (GH-3056)
- **Breaking**: `/api/stations` no longer takes `lead_time` and `issue`: a request with either is
  a 422, as for any parameter the endpoint does not know. They never changed the list. Leave them
  out of the request, or send them to `/api/values`, where the run is chosen (GH-3056, GH-3061)
- **Breaking**: a download that did not answer is a `DownloadError`, where it was logged and read as
  no data, in the `metno/frost` values and the AEMET and KNMI station lists: a timeout, a dropped
  connection, a body cut short and a 5xx. A TLS failure (a certificate that does not verify) is one
  too, in those and in the AEMET, KNMI and `smhi/observation` values. A 404, a 412 and any other
  4xx but a refused credential stay the empty result. The REST API answers 502 (504 after a
  timeout) and the command line exits 1; catch `DownloadError` (or `UpstreamError`) where you
  relied on the empty frame (GH-3022)
- **Breaking**: a credential that the provider rejects (HTTP 401 or 403) raises
  `CredentialRejectedError` in the `metno/frost`, `aemet/observation`, `knmi/observation` and
  `metoffice/observation` values and in the AEMET, KNMI and Met Office station lists, as it does in
  the `metno/frost` stations. It was an empty result with a warning, for Met Office also a
  `DownloadError`. The REST API and the MCP tools answer 501, the command line prints one line.
  A refused pre-signed link, which takes no credential, stays what it was; catch
  `CredentialRejectedError` (a `PermissionError`) where you relied on the empty result (GH-3018)
- The OpenAPI document requires `metadata` in the answers of `stations`, `values`, `interpolate`
  and `summarize`, and the component schemas of the stations answer are
  `_StationsWithMetadataDict` and `_StationsWithMetadataOgcFeatureCollection`, no longer
  `_StationsDict` and `_StationsOgcFeatureCollection`; a client generated from the document names its
  types after them. A provider's metadata declaration has to give `license` and `attribution`
  (`None` where the provider states none), or `MetadataModel` refuses it (GH-2561)

## [0.156.0] - 2026-10-16

### Added

- `wetterdienst stations` takes `--lead-time` and `--issue`, as `values` does and `/api/stations`
  already did; `interpolate` and `summarize` take `--min-gain-of-value-pairs` and
  `--num-additional-stations`, which their endpoints took as `min_gain_of_value_pairs` and
  `num_additional_stations`; `stations`, `values`, `interpolate` and `summarize` take `--width`,
  `--height` and `--scale` for a chart, and `stripes stations` takes `--debug`. A request has the
  same parameters on the command line, over REST and in the MCP tools (GH-2561)
- The REST API is served under `/api/v1/...`, and the OpenAPI document describes that prefix.
  `/api/...` stays, an alias of the current version with the same handlers and not deprecated, so a
  client of `/api` changes nothing. `/api/version` reports `api_version` (`"1"`). The operation ids
  and the MCP tool names do not change (GH-2561)

### Changed

- **Breaking**: the siblings of `eccc/observation` monthly `mean_temperature`, which ECCC builds
  from the daily (max + min) / 2: `days_with_valid_mean_temp` is
  `count_days_valid_temperature_air_mean_minmax_2m`, no longer
  `count_days_valid_temperature_air_mean_2m`, and `normal_mean_temperature` is
  `temperature_air_mean_minmax_2m_normal`, no longer `temperature_air_mean_2m_normal`. Request the
  new names; the old ones are not found and say what they are called now (GH-3017)
- **Breaking**: `dwd/observation` `hourly/precipitation` `precipitation_form` (`wrtr`) 9, DWD's
  "Missing value, Type of precipitation unascertainable", is no longer returned as the code 9: the
  value is null and the 9 is the last token of `quality_flags` (`3,raw:9`). Read the null as an
  unknown form, and `raw:9` where the code matters; the form codes left are 0, 1, 2, 3, 4, 6, 7
  and 8 (GH-2703)
- **Breaking**: a parameter that takes a list is plural on the REST API, the MCP tools and the
  command line. `station` of `stations`, `values` and `history` is `stations` (`--stations`); the
  other lists (`parameters`, `periods`, `resolutions`, `datasets`) were plural already, and their
  singulars are now refused with an error naming the plural, as `station` is (`station was renamed
  to stations`). Rename `station` in your requests; the one reference `station` of `interpolate`
  and `summarize`, and that of `issues` and `stripes`, stay (GH-2561)
- **Breaking**: the options of the command line are spelled with hyphens, as the parameters of the
  REST API and the MCP tools are spelled with underscores: `--convert-units`, `--unit-targets`,
  `--sql-values`, `--skip-empty`, `--skip-criteria`, `--skip-threshold`, `--drop-nulls`,
  `--if-exists`, `--with-metadata`, `--with-stations`, `--lead-time`, `--start-year`, `--end-year`,
  `--name-threshold`, `--show-title`, `--show-years`, `--show-data-availability`, `--wmo-code`,
  `--country-name`, `--use-nearby-station-distance` and `--interpolation-station-distance*` and
  `--summary-station-distance*`. The underscored name is refused with an error naming the
  hyphenated one; replace the underscores in your scripts (GH-2561)
- Every boolean option of the command line is one option: bare it is on, and it takes `=true` or
  `=false` in the spellings REST accepts (`true`, `1`, `yes`, `on`, `t`, `y` and their opposites).
  `--all`, `--debug`, `--dwd` and `--reload` were flags that took no value, and now take one, and
  `--with-metadata` and the other options that wanted a value can be given bare (GH-2561)
- A station selection made twice, or not at all, names the alternatives in the refusal on every
  surface: `Cannot be combined with name, give exactly one of all, stations, name, (latitude and
  longitude), (left, bottom, right and top) or sql` in the 422 and the tool error, and the same in
  the options' names in the usage error of the command line (GH-2561)
- The OpenAPI document describes a list query parameter as one comma-separated value
  (`?stations=01048,04411`, `explode: false`), which is how the endpoints and the tools take it.
  The key given more than once is still read, and no longer documented (GH-2561)
- **Breaking**: the precipitation group of a METAR, `noaa/ghcn` hourly `precipitation` and
  `nws/observation` `precipitationLastHour`, is `precipitation_amount_since_last_routine_report`
  (new), no longer `precipitation_amount`: a running total since the last routine report, which a
  routine report holds for the whole hour and a SPECI for the part that had fallen. Request the new
  name; the old one raises `InvalidParameterError` in those datasets, which says what it is called
  now. `noaa/ghcn` hourly returns this precipitation for one report of each UTC hour, the one at
  the station's routine minute (`:53` at LAX), else the last that is no SPECI, no longer for every
  report; its other elements keep every report (GH-2841)
- **Breaking**: `StationsResult.stations`, which held the request and not stations, is
  `StationsResult.request`, and the `stations=` argument of `StationsResult(...)` is `request=`;
  the stations were and are in `.df`. The old name raises an error that names the new one. Write
  `stations.request.settings`, not `stations.stations.settings`, and `values.stations.request` for
  the request behind a values result (GH-2626)
- **Breaking**: `StationsResult.values` and `.history`, which built a new reader on every access,
  are methods. Write `stations.values().all()`, `stations.values().query()`,
  `stations.values().to_target(...)` and `stations.history().query()` where you wrote
  `stations.values.all()` and so on; reading either as an attribute raises an error that names the
  call (GH-2626)
- **Breaking**: the results are frozen, so assigning to `result.df` raises `FrozenInstanceError`.
  `filter_by_date` and `filter_by_sql` on a result, which replaced its frame and returned the frame,
  are `filtered_by_date` and `filtered_by_sql`, which return a new result and leave the old one
  as it was; the old names raise an error that names the new. Write `values =
  values.filtered_by_sql(sql)`, and `.df` where you used the returned frame (GH-2626)
- **Breaking**: `ValuesResult` no longer holds the reader that produced it, so `result.values` and
  the `values=` argument are gone, and a result you keep no longer keeps its reader, with whatever
  it cached, alive. Get a reader from `stations.values()`. `df_stations` of a `ValuesResult` now names
  the stations with a row in the frame, so it follows `filtered_by_sql`, and
  `InterpolatedValuesResult` and `SummarizedValuesResult` have it too (GH-2626)
- The return types of `Wetterdienst.discover()`, `TimeseriesRequest.discover()` and `Info.to_dict()`
  are typed dicts, no longer `dict[str, Any]`, so a type checker follows
  `discover()["dwd"]["observation"]["kind"]` and `request.discover()["daily"]["datasets"]`. The
  `Coverage*` types of the REST API (`CoverageNetwork`, `CoverageResolution`, `CoverageDataset` and
  `CoverageParameter`) moved to `wetterdienst.model.metadata`; import them from there.
  `StationsResult.request` is typed `TimeseriesRequest`, no longer a union with the two forecast
  requests. `Settings.fsspec_client_kwargs` and the `settings` and `options` of a request are
  `dict[str, Any]`, so the keys of `fsspec_client_kwargs` must be strings (GH-2622)
- **Breaking**: `to_geojson`, `to_ogc_feature_collection` and `to_plot` of the results take the
  arguments they declare and no others. They accepted any keyword and dropped it, so
  `to_geojson(with_metdata=True)` wrote a document without metadata; it is a `TypeError` now, and a
  type checker reports it. `to_image` takes `fmt`, `width`, `height`, `scale` and `max_side` and no
  others. Fix the name or drop the argument. `to_format(fmt, **kwargs)` still takes one set of
  arguments for any format and gives each format those it takes, so the command line, REST and MCP
  are unchanged; `to_csv` still passes its keywords to polars (GH-3043)
- **Breaking**: the results (`StationsResult`, `ValuesResult`, `InterpolatedValuesResult`,
  `SummarizedValuesResult` and `HistoryResult`) are built by keyword only.
  `ValuesResult(df, stations)` is a `TypeError`: write
  `ValuesResult(stations=..., df=...)`. The library builds them, so only code that constructs one
  by hand is affected (GH-3044)
- **Breaking**: `Wetterdienst.resolve` is for the timeseries networks and is typed so. `dwd/radar`
  and `dwd/alerts`, whose classes are no `TimeseriesRequest`, are refused with an `ApiNotFoundError`
  that names their own entry point, `Wetterdienst.resolve_standalone("dwd", "radar")`, which is
  typed to the exact class for literal names; or import the class. `Wetterdienst.standalone` lists
  them and `Wetterdienst.is_standalone(provider, network)` tells (GH-3045)

### Deprecated

- `Wetterdienst(provider, network)` warns with a `DeprecationWarning` and still returns the class
  of either kind of network. Use `Wetterdienst.resolve(provider, network)`, or `resolve_standalone`
  for `dwd/radar` and `dwd/alerts` (GH-3045)

### Fixed

- mypy read `DwdObservationMetadata` and the other `<Provider>Metadata` of the provider modules as
  a dict, and `DwdObservationRequest.metadata` with it, so `DwdObservationMetadata.daily.kl` was an
  error in a type-checked program (pyright and ty were not affected); the dict a provider declares
  has a private name of its own now, and the public name is the model (GH-2622)
- **Breaking**: a data provider that failed is no longer a 500. An `UpstreamError` is a 502 (a
  download that was refused or cut short, a file the parser does not expect) or, after a timeout, a
  504; `NoInternetError` stays a 503. The body is a fixed sentence that says the request was
  valid. Retry a 502, 503 or 504, and read a 500 as a defect of the server. `/api/alerts`
  decides as every endpoint does, by the exception's class, so a `NotFoundError` or a
  `ConfigurationError` raised there is a 404 or a 501, and a plain `ValueError` out of the provider
  is no longer taken for the caller's mistake (GH-2561, GH-2985)
- **Breaking**: `DwdWeatherAlertRequest` raises `DownloadError` for a snapshot that did not download
  or is no zip archive, where it raised `OSError`: catch `DownloadError` (or `UpstreamError`). A
  granularity, language or timestamp it cannot read is a `RequestError`, still a `ValueError`
  (GH-2985)
- An exception that no endpoint handled reaches an MCP tool as the 500 the REST API answers, the
  fixed sentence naming its type, and no longer as the tool error carrying the exception's own
  text, which could name a path of the server (GH-2984)
- **Breaking**: `/api/stations` and the MCP `stations` tool no longer take `with_stations`, which
  they accepted and ignored: a listing of stations is the stations. A request that still sends it
  is a 422; drop it. `history` and the value endpoints keep it (GH-3034)
- A client ID that Frost rejects (HTTP 401 or 403) raises `CredentialRejectedError`, a
  `ConfigurationError` that is still a `PermissionError`. The REST API and the MCP tools answer 501
  "The provider rejected the credential of this server for metno/frost" and log the setting, no
  longer a 500 that names `WD_AUTH__METNO_FROST`; the command line prints one line and exits 1,
  without a traceback (GH-2665)
- `Wetterdienst.discover()`, `/api/coverage` and `wetterdienst about coverage` leave out a network
  that cannot be imported (a broken install) and a provider with no network left,
  and log why; they listed it as needing no credentials. Asking for that network by name still
  tells the import error (GH-2800, GH-2801)

## [0.155.0] - 2026-10-16

### Added

- `WetterdienstError` is the root of every class of `wetterdienst.exceptions`, so
  `except WetterdienstError` catches them all. Below it `RequestError` (a `ValueError`),
  `NotFoundError` (a `LookupError`), `ConfigurationError`, `UpstreamError` and `ExportRefusedError`
  say what kind of failure it is; all six are importable from `wetterdienst`. Every class keeps the
  built-in classes it had (`ValueError`, `OSError`, `FileNotFoundError`, `IndexError`,
  `ImportError`), so an existing `except` still catches it. New: `StartDateEndDateError` and
  `ImageTooLargeError` are also `ValueError`s, and `ProviderNotFoundError`, `StationNotFoundError`
  and `ApiNotFoundError` are also `LookupError`s (GH-2634)
- `Wetterdienst.discover()`, `/api/coverage` and `wetterdienst about coverage` without arguments
  give every network a `name_short`, `country`, `url` and `kind`. `kind` is `observation`,
  `forecast` or `derived` for a timeseries network, which has stations and values, and `radar` or
  `alerts` for `dwd/radar` and `dwd/alerts`, the standalone networks that `stations`, `values` and
  the other timeseries endpoints refuse (GH-2641)
  the other timeseries endpoints refuse. The four are null for a network that cannot be imported
  (GH-2641)
- `stations` (`/api/stations`, the MCP tool and `wetterdienst stations`) takes the window `values`
  takes, as `timestamp` or, on the command line, `--start`/`--end`, and lists only the stations
  whose record overlaps it, so the nearest three are no longer ones that closed a century ago. A
  station is left out when it started after the window or ended before it by more than two readings
  of its resolution (two days up to daily, as the end an index states lags a station still
  reporting); one whose start or end is not published is kept. Without a window nothing changes
  (GH-2635)

### Changed

- **Breaking**: the REST API answers every error, a 400, 404, 422 or 500, as an RFC 9457 problem
  (`application/problem+json`): `type`, `title`, `status` and `detail`, which is always text. A 422
  put pydantic's list under `detail`; the list is now `errors`, and `detail` is its lines as text.
  Read `errors` for the invalid parameters, and `detail` for a sentence. The MCP tools show the
  text of `detail` in their errors, no longer a Python dict (GH-2634, GH-2561)
- **Breaking**: the REST API answers a `NotFoundError` with a 404: a station
  `/api/stripes/values` and `/api/stripes/image` do not know, and a forecast run (`issue`) the
  source does not list on `/api/values`, `/api/interpolate` and `/api/summarize`, were a 400. Which
  answer a failure gets, here and in the command line, follows from its class (`RequestError` 400,
  `NotFoundError` 404, `ConfigurationError` 501, any other 500), so a `WetterdienstError` of a new
  class is a server error until it is given a kind (GH-2634)
- `wetterdienst.model.schema` exports the schema of every public frame as an object to assert
  against: `STATIONS_SCHEMA`, `LONG_SCHEMA`, `WIDE_SCHEMA` (with `wide_schema(names)` for the
  parameters' columns), `INTERPOLATED_SCHEMA` and `SUMMARIZED_SCHEMA`. `HistoryResult` and
  `TimeseriesHistory` have `to_dict` and `to_json`, the body that `/api/history` and the `history`
  command answer with (GH-2633)
- **Breaking**: `station_id`, `resolution`, `dataset` and `parameter` of `.values.all().df` are
  `String`, as they already were in an empty, an interpolated and a summarized result, and in
  `query()`; they were polars `Enum` with the categories of each result, which did not join a
  stations frame, concatenate across requests or take `is_in` with an absent name. Drop the casts
  back to `String`; code that read the `Enum`'s categories takes them from the data (GH-2633)
- **Breaking**: every timestamp in a JSON, GeoJSON or CSV body is written the way values wrote it,
  ISO 8601 in UTC to the microsecond, `2026-09-01T00:00:00.000000+00:00`. History (`valid_from`,
  `valid_to`), alerts, issue lists and climate stripes wrote `1926-05-01T00:00:00+00:00`, and the
  CSV of alerts and stripes `1926-05-01T00:00:00.000000+0000`. Read them with a parser that takes a
  fraction, as `datetime.fromisoformat` does (GH-2633)
- The parameter columns of a wide values frame are in the order the request names its parameters,
  as an empty frame has them, not in the order the source delivered its rows in. A parameter no
  station delivered has no column in a populated frame (GH-2633)
- **Breaking**: `nws/observation` `hourly` returns one observation for each station-hour, stamped
  with the full hour, no longer the 12 an hour the endpoint serves (5-minute ASOS rows, METAR,
  SPECI). The kept one is the METAR or SPECI report nearest to the full hour, normally the METAR at
  :51 to :54; an hour with no report keeps its nearest 5-minute row. The 5-minute rows and the
  minute of a report are no longer available; read `api.weather.gov` for them. Precipitation is a
  running total since the last routine METAR and the winds are 2-minute means; a SPECI nearer the
  full hour than a synoptic METAR takes its 3- and 6-hour amounts with it, see the provider page
  (GH-2857)
- `meteofrance/observation` stations have a `region`, the code of their département as the registry
  lists it, with two digits (`09`) or three overseas (`972`); it was null. Corsica's two
  départements are both `20`, as in the registry (GH-2019)
- **Breaking**: the listing of every network (`Wetterdienst.discover()`, `/api/coverage` and
  `wetterdienst about coverage` without arguments, the MCP `coverage` tool) no longer has `valid`.
  It was `true` for a network without credentials, `false` for missing ones and null for present
  ones, never checked. Read `configured`, and ask `/api/auth`, `wetterdienst about auth` or
  `Wetterdienst.is_valid(api)` whether a provider accepts the credentials of one network (GH-2641)
- **Breaking**: the resolution `6_hour` is `6_hours` (`Resolution.HOUR_6.value`, `metno/frost`), as
  `10_minutes` is. The old value is not accepted: a `6_hour/data` parameter raises
  `InvalidParameterError` (which says it was renamed), and
  `geo_station_distance_resolution_factors={"6_hour": ...}` is refused with the new one named.
  Write `6_hours/data` for Frost and `{"6_hours": 1.5}` for the factors (GH-2641, GH-2561)
- `dwd/observation` `hourly/sun` `quality_flags` carry `zone:woz` (`10,zone:woz`) for a stamp of a
  period that DWD's `Metadaten_Parameter` calls "Stundenwerte in WOZ": the station's local true
  solar time, not UTC, at 528 of 636 stations, at 172 of them past 2001-03-31 (to 2006). Stamps
  and values are unchanged, as the offset is no whole hour; filter the flagged rows out, or shift
  them by the longitude and the equation of time yourself (GH-2816, GH-2617)
- **Breaking**: `dwd/poi` `wind_speed_rolling_mean_max_yesterday` is named
  `wind_speed_rolling_mean_max_last_6h`: DWD's "previous day" column is carried at 00, 06, 12 and
  18 UTC and is the maximum of the 6 hourly values up to the stamp, not a value of the previous
  day. Request the new name; the old one raises `InvalidParameterError`, which says what it is
  called now (GH-2817)
- `dwd/observation` `hourly/urban_wind` `wind_direction`: the description says that its 0, which
  comes with 0.1 to 0.8 m/s and never with 0, is returned as 0 because DWD does not state whether
  it is a calm or north, unlike the calm of `10_minutes/urban_wind` that is null (GH-2809)
- **Breaking**: the strongest gust of the last 10 minutes is `wind_gust_max_last_10min` (new), no
  longer `wind_gust_max`, which is the strongest gust of the row's interval: `fmi/observation`
  hourly `wg_10min`, `meteofrance/synop` subdaily `raf10`, `metoffice/observation` hourly weather
  `q10mnt_mxgst_spd` and `nws/observation` `windgust`. Request the new name; the old one raises
  `InvalidParameterError` in those datasets, which says what it is called now.
  `meteofrance/observation` hourly `DXY` (`wind_direction_gust_max`), the direction of the hour's
  highest 10-minute mean and of no gust, is no longer served. `wind_gust_max` stays for every gust
  of an interval (GH-2836)
- **Breaking**: the 2-minute averages of the wind are `wind_speed_last_2min` and
  `wind_direction_last_2min` (new), no longer `wind_speed` and `wind_direction`: `nws/observation`
  (the ASOS's 2-minute averages) and `eccc/observation` hourly direction (ECCC: "the average
  direction during the two minute period"). Request the new names; NWS's old ones are not found,
  and ECCC's `wind_direction` still selects its row, which comes back named
  `wind_direction_last_2min`. ECCC's speed (one-, two- or ten-minute), `dwd/road` (10 minutes in
  some station groups, 15 or none in others) and `noaa/ghcn` (GHCNh states no window) keep their
  names (GH-2837, GH-2838)
- **Breaking**: `dwd/mosmix` (small, large) and `dwd/dmo` (icon, icon_eu) `pppp`, DWD's "Surface
  pressure, reduced", is `pressure_air_sea_level`, no longer `pressure_air_site_reduced`: it is
  reduced to sea level (Hamburg and Munich-Flughafen agree with the sea-level pressure of their
  reports within 1 hPa). `nws/observation` `barometricpressure`, the METAR altimeter setting
  (A#### x 33.86389 Pa, KATL at 315 m reads 101.8 kPa), is `pressure_air_site_reduced`, now
  described as reduced to sea level with the standard atmosphere, no longer `pressure_air_site`
  (the station's pressure). Request the new names; the old ones are not found in those datasets
  (GH-2840, GH-2842)
- **Breaking**: `dwd/mosmix` large `rrad1` is `radiation_global_relative_last_1h` (new), the global
  radiation of the last hour relative to that at the top of the atmosphere, no longer
  `probability_radiation_global_last_1h`. `dwd/poi` `past_weather_1` and `past_weather_2` are
  `weather_past` and `weather_secondary_past` (new): their window is 6 hours in the reports of
  00, 06, 12 and 18 UTC and 3 hours in the others, not `weather_last_3h` and
  `weather_secondary_last_3h`. `dwd/swsmos` `RR6`, DWD's liquid precipitation of the last 6 hours,
  is `precipitation_amount_liquid_last_6h` (new), no longer `precipitation_amount_last_6h`. The
  retired names answer with the one to use (GH-2843, GH-2844, GH-2845)
- **Breaking**: `rmi/observation` `temp_grass_pt100_avg`, RMI's "average temperature measured on
  the grass" (10 minutes, hourly, daily), is `temperature_surface_mean`, a surface temperature,
  no longer `temperature_air_mean_0_05m`. Request the new name (GH-2846)
- **Breaking**: the daily totals of potential evapotranspiration, `meteoswiss/observation` daily
  `erefaod0` and `dwd/derived` daily `vpgfao` and `vpgh`, are
  `evapotranspiration_potential_grass_fao` and `evapotranspiration_potential_grass_haude`, as the
  monthly ones are, no longer the `_last_24h` names, which no source serves now and which stay for
  one that publishes a trailing 24 hours at a sub-daily timestamp. Request the plain names
  (GH-2847)
- The `restapi` extra needs `starlette>=1.3` (was `>=0.46`): the first release whose test client
  takes `httpx2`. A host that pins an older starlette upgrades it (GH-3013)
- **Breaking**: `aemet/observation`, `knmi/observation` and `smhi/observation` values raise a
  `DownloadError` for a download that timed out, was dropped, was cut short or came back as a 5xx
  (for AEMET also an `estado` of 500 or more), as every other provider does, where they logged a
  warning and answered an empty frame that read as a station without data. A 404 stays the empty
  result, as does a 429 or another 4xx. The REST API answers 500 and the command line exits 1.
  Catch `DownloadError` (or `WetterdienstError`) where the empty frame was relied on (GH-2965)
- **Breaking**: the mean that a source computes as (maximum + minimum) / 2 is
  `temperature_air_mean_minmax_2m` (new), no longer `temperature_air_mean_2m`:
  `eccc/observation` daily and monthly `mean_temperature` and `geosphere/observation` daily
  `tl_mittel`. Request the new name; the old one raises `InvalidParameterError` in those datasets,
  which says what it is called now. Geosphere monthly `tl_mittel` keeps `temperature_air_mean_2m`
  (GH-2839)
- **Breaking**: an empty result is exit 0 on the command line, as it is a 200 on the REST API: a
  window without readings, a selection that finds no station, a glossary filter that matches
  nothing. The sentence goes to stderr and stdout holds what the REST API answers (`{"values": []}`,
  the CSV header); a `--target` is left as it is. It exited 1, as a failure does. A script that told
  "no data" by exit 1 tests the output, or the sentence on stderr; exit 1 now only means failure
  (GH-2635)
- **Breaking**: a `name` selects its one best match in `values` on the command line, the REST API
  and MCP, as `filter_by_name` does; it selected the best five, and read the values of all five.
  `stations` still lists the best five. Pass `--rank` or `rank` for another number, `rank=5` to
  `filter_by_name` for the listing's (GH-2635)
- A list of station ids (`filter_by_station_id`, `--station`, `station=`) leaves out an id the
  network has no station for as before, and now names it in a warning; where none exists the result
  is empty on every surface. The one reference station of `interpolate` and `summarize` keeps its
  404 and exit 2 (GH-2635)
- The command line renders a result through the function the REST API does: with
  `--with_metadata=true` its JSON and GeoJSON carry the `settings` block next to `metadata`, as the
  REST API's did. `--pretty` is one option on every command, bare or as `--pretty=true`;
  `interpolate` and `summarize` took it only bare, the others only with a value (GH-2635)

### Removed

- **Breaking**: `dwd/mosmix` `large` no longer declares `h_bsc`, `rr1`, `rr3`, `rr6`, `rrh`, `rrd`,
  `rads3` and `radl3`, which MOSMIX-L never delivers (none of the 114 elements of its 5648
  stations); a request that named one got an empty frame and is now logged and dropped, or raises
  `NoParametersFoundError` when no other parameter is requested. Drop them from the request;
  MOSMIX-L's precipitation totals are `rr1c`, `rr3c`, `rr6c`, `rrhc` and `rrdc`. The description of
  `sund3` says it is not a sliding 3 hour total (GH-2851)

### Fixed

- `noaa/ghcn` daily: 9 more stations, in the UK (Hull, Rothamsted, Wisley, ...), Algeria (Oran,
  Sidi Bel Abbes) and France (Espoey), are placed west of Greenwich, no longer east of it, where
  `ghcnd-stations.txt` has lost the sign of their longitude. They were 25 to 144 km off, so a
  nearest-station search or an interpolation near them picked the wrong stations (GH-2886)
- `eccc/observation` lists a station for `hourly` (`daily`) only if the station list gives it a
  `HLY_FIRST_DATE` (`DLY_FIRST_DATE`): 1685 of 8435 stations for hourly, 8340 for daily, no longer
  all of them, as the others have no row there. `stations`, `filter_by_rank` and
  `filter_by_distance` hold only listed stations, and `interpolate_by_station_id` and
  `summarize_by_station_id` raise `StationNotFoundError` for an unlisted one: pass its coordinates
  instead. The hourly rows of 27490 (2008, after its `LAST_DATE`) are no longer returned, not even
  for a request with dates (GH-2867)
- **Breaking**: a request made without a network connection raises `NoInternetError`, naming the URL
  with the connection error as its `__cause__`, for every provider, for station catalogues and
  file listings as for values. It was an empty frame, or for `dwd/observation` a bare
  `FileNotFoundError: ... does not have a list of files`, which a scheduled job could not tell
  from a source with no data; `knmi`, `aemet`, `lhmt` and `dmi` returned the values read before the
  connection dropped, and now raise. A source that answers badly is still a `DownloadError`. Catch
  `NoInternetError` where an empty result is wanted offline. The REST API answers 503 (retryable),
  the command line exits 1 with one line (GH-2640)
- **Breaking**: a parameter the provider does not have, or one not shaped like a parameter, raises
  `InvalidParameterError` (a `RequestError`, a 400 over REST) naming each with its close match; it
  was logged and skipped, so the result held fewer parameters than asked for without saying so.
  Fix the name, or pass `on_unknown="warn"` to the request for the old behaviour. A request where
  none resolves raises it as well, no longer `NoParametersFoundError`; catch `RequestError` for
  both (GH-2636)
- **Breaking**: bad inputs are refused where they were answered with less or with an unrelated
  error. `discover()` raises `MetadataNotFoundError` for a resolution or dataset the network does
  not have (a 404 on `/api/coverage`, a usage error on `about coverage`), not `{}`;
  `Wetterdienst.get_network_names("foo")` raises `ApiNotFoundError`, not `KeyError`; a date that is
  neither a `str` nor a `datetime` (`start=2020`) raises `TypeError`, not `AttributeError`. Catch
  `NotFoundError` or `LookupError` instead of `KeyError`. Also, an `InvalidEnumerationError` lists
  the valid values, `(Resolution.DAILY, "kl")` works as `("daily", "kl")`, and `end` without `start`
  stays one instant, as `start` alone is, now documented (GH-2636)
- `dwd/observation` `hourly/moisture`: `pressure_air_site` (`P_STD`) is null in a file that holds
  one value in each of at least 500 readings, which is the pressure of a station without a
  barometer and no reading (761 of the 1314 files hold one value, e.g. 997.3 for station 14072);
  the value stays as the last `quality_flags` token, `raw:997.3`. A constant that changed once in
  a file is not caught. Take the pressure of another source for such a station (GH-2699)
- A value outside the physical range of its parameter, which no sensor can have produced, is null,
  with the source's number (`raw:4021`) as the last token of `quality_flags`, no longer a reading:
  `rmi/observation` (a daily `temp_max` of 4021 degrees, a `temp_avg` of 110, a humidity of -6999 %,
  a gust over 60 m/s such as the 81.5 of 6414 on 2003-10-09, 13,851 minutes of sunshine in a day)
  and `dmi/observation` (rain over 500 mm in a day, such as 1978 and 989 mm at 04339, over 1,500 mm
  in a month, over 4,000 mm in a year, the largest amounts of a day over 500 mm). The bounds are
  generous and rain and sunshine have one per resolution, so a merely odd value stays: a year of
  3,253.4 mm of DMI is below its bound, and its `validity:false` tells; the long shape drops the
  null rows unless `drop_nulls=False` (Part of GH-2797)
- `dwd/observation` `5_minutes/precipitation` `historical`: the row stamped 200001010000 that every
  December 1999 file holds as its first row is dropped. It is not the missing 23:55 MEZ reading
  but an incomplete copy of the 00:00 UTC row, which the January file has whole, and it was
  returned at 23:00 UTC, where no reading is (GH-2827)
- `dwd/observation` `10_minutes` `historical`: of the stamps 1999-12-31 23:00 to 23:50 MEZ that the
  file of 1999 lists twice (precipitation, extreme_temperature, extreme_wind), the row kept at
  22:00 to 22:50 UTC is the one that is not a copy of a row of the 2000 file; the copy of 00:00 to
  00:50 MEZ of 2000-01-01 was kept in 201 of 226 differing cases. A request that touches 22:00 UTC
  on that day now also reads the 2000 file (GH-2829)
- A failed lookup of a parameter by attribute (`dataset.klx`) listed the dataset's `quality_*`
  flags under "Available parameters", which iterating the dataset and `coverage` leave out; they
  are left out of the list too (GH-2641)
- The explorer no longer offers `dwd/radar` and `dwd/alerts` as networks to choose, which answer
  its coverage request with a 404 (GH-2641)
- The description of `noaa/ghcn` daily `tavg` said it was (max + min) / 2. It is GHCN's own
  average daily temperature, an average of hourly readings (UTC day) from source 'S', and that is
  what the description now says; `temperature_air_mean_2m` stays (GH-2839)
- **Breaking**: `dwd/observation` `hourly/temperature_air` `historical`: the stamps of periods that
  DWD's `Metadaten_Parameter` calls "Stundenwerte in MEZ (MD)", up to 1991 at 80 East German
  stations, are MEZ, not UTC, and are returned one hour earlier than before, per parameter
  (`temperature_air_2m`, `humidity_relative`), with `zone:mez` in `quality_flags` (`3,zone:mez`).
  Plain MEZ and UTC periods are unchanged. A change inside a shared day (36 stations on 1991-11-01)
  is taken to be after its stamp 00. Add an hour to flagged stamps to get the old ones; 30 rows
  that the shift puts on a stamp that is there are dropped (GH-2709)
- `wetterdienst stations|values|interpolate|summarize --format=png|jpg|webp|svg|pdf` wrote the
  `repr` of the image (`b'\x89PNG...'`) to stdout; it writes the image as the REST API sends it
  (GH-2635)

## [0.154.0] - 2026-10-15

### Changed

- The Docker images run on Python 3.15 (was 3.14). Packages without a 3.15 wheel are built from
  source when the image is built, so a local or compose build takes longer (GH-2568)

### Fixed

- Docs that stated a wrong fact are corrected: `wetterdienst.info()` is `wetterdienst cache`; the
  DMO `periods==recent` REST example is refused (DMO has `future` only); interpolation and summary
  work for any provider, not DWD alone; stripes read annual, not daily, observations; DMI needs no
  API key; the Docker image has the `export`, `knmi` and `mcp` extras and no `explorer`; the image
  is built from `docker/Dockerfile` without a wheel (GH-2621)
- `Info().authors`, and so `wetterdienst info` and the REST index, are read from the installed
  package's `[project] authors` instead of a copy that named another address for the first author
  (`benjamin@eobs.org`, not `gutzemann@gmail.com`). An author without a known GitHub account has
  an empty `github_handle` and no GitHub link on the index; a never-installed checkout has no
  authors (GH-2954)

## [0.153.0] - 2026-10-15

### Added

- Python 3.15 is supported (tested on 3.15.0rc1) and declared as a classifier. The `mcp` extra needs
  beartype 0.23 or newer there (0.22 does not import on 3.15; fastmcp brings it in without a
  floor). h5py, duckdb, numcodecs and pyyaml, installed by the `knmi`/`radar`, `sql`, `export` and
  `restapi` extras, have no 3.15 wheel yet and are built from source: h5py needs the HDF5
  headers (`libhdf5-dev`) (GH-2568)

### Changed

- `noaa/ghcn` hourly `quality_flags` also carry the file's `<element>_Measurement_Code` and
  `<element>_Source_Code`, as `measurement:<code>` and `source:<code>` after the quality code and
  before `raw:` (`5,measurement:T,source:335`), as daily does. The source says which list a
  quality code is read in (`4` is "passed gross limits" for source 335, "calculated" for 223); the
  measurement code marks, by element, a trace of precipitation, a calm wind and the tendency of the
  3-hour pressure change. The text `Null`, which sources 245 and 367 write for "no code", is left
  out of the quality code too (it was returned as the flag `Null`) (GH-2925)
- **Breaking**: `ea/hydrology` `quality_flags` carries the reading's `completeness` after its
  quality, `Good,completeness:Complete` or `Good,completeness:Incomplete`, whether the value is
  based on complete data. Daily readings carry it (not all of them); a reading without one, and
  every 15 minute reading, keeps the quality alone (`Good`). A filter `quality_flags == 'Good'` no
  longer holds for daily readings: use `str.starts_with('Good')` (GH-2762)

### Fixed

- `wetterdienst restapi` on an install with `fastapi` and without `uvicorn` now prints that
  `uvicorn` is missing and to `pip install wetterdienst[restapi]`, in one line with exit status 1,
  no longer a `ModuleNotFoundError` traceback (GH-2928)
- `knmi/observation`, `aemet/observation` and `lhmt/observation` values requests that go offline
  end at the first download answered with no connection, as the loop over files of one station
  already did: the stations and datasets after it are no longer tried, each waiting for the
  connection to fail, and so return nothing even where their files were already downloaded. What
  the station that found out had read is returned (GH-2620)
- `knmi/observation` hourly `wind_direction_last_10min` is null, no longer 990 or 0, where KNMI
  writes the code for a variable wind (990) or a calm (0); the code stays in `quality_flags` as
  `raw:990` or `raw:0`. Only bearings (360 is north) are left as values (GH-2850)
- **Breaking**: `ea/hydrology` returned the level of a river as `groundwater_level`. The Environment
  Agency's `level-*` measures are river levels (2638 stations), so `daily/groundwater_level_max`
  and `_min` had no groundwater behind them, and `15_minutes/groundwater_level` held rivers and no
  borehole. The river level is now `15_minutes/stage` and `daily/stage_max` and `stage_min`, in
  centimetres, no longer metres: request the new names (the old daily ones are not found) and
  multiply stored values by 100. `15_minutes/groundwater_level` now holds the 1074 borehole
  loggers, in metres above ordnance datum, every 15 minutes to hourly per station (GH-2632)
- `interpolate` and `summarize` no longer return a timestamp outside the requested window when
  `start` or `end` is not on the resolution's grid (`start` 12:30 and `end` 12:30 two days later at
  daily gave the next day's 00:00 after `end`; `start` 10:29 at hourly gave 10:00 before it). The
  rows are the timestamps within `start` and `end`, both included, the ones `values` returns for
  the same window, and a window holding none returns no rows (GH-2814)
- `dwd/radar` converts an aware `start` or `end` to UTC, as a naive one already was taken to be, so
  one instant selects one file: `2020-01-01T01:00+01:00` read January's `RW202001.tar.gz` where
  the same instant as `00:00Z` reads December's, losing the hour before midnight, and a `+05:30`
  bound matched no file; a bound in a named zone (`Europe/Berlin`) raised a polars `SchemaError`
  on the recent and composite files. A historical RADOLAN_CDC request spanning months now reads
  every month's archive, not only the one it opens in (GH-2818)
- `ea/hydrology` lists every station of the Environment Agency, not the first 100 of 9537 that
  the API answers with unless asked for more: 2638 stations for `stage` and 1074 for
  `groundwater_level` (it listed 1 borehole), 1103 for 15 minute `discharge`. A station the
  listing gives two names is listed under the first, and one it gives two dates of closing
  (Udford) ends on the later. The listing is cached for 12 hours, not 5 minutes (GH-2933)
- The warning for a parameter a dataset does not have no longer offers a near spelling whose
  leading words name another quantity: `temperature_dew_point_mean_2m` in `dwd/observation`
  `daily/kl` no longer suggests `temperature_air_mean_2m`, nor
  `error_absolute_temperature_air_mean_2m` in `dwd/mosmix` `hourly/small` `temperature_air_2m`.
  A misspelling of a name the dataset has is still answered; otherwise the message lists the
  available names (GH-2924)
- The descriptions of `dwd/observation` `tx5_10` (`10_minutes/temperature_extreme`) and `v_te002`
  (`hourly/temperature_soil`) in the REST API, the MCP tools and the docs say that only the
  historical files carry a value (up to 2009 and 2019): `recent` (and `now` at 10 minutes) hold
  `-999` at every station, so those periods never have a value for these two (GH-2852)
- The description of `dwd/observation` `hourly/weather_phenomena` `weather` in the REST API, the
  MCP tools and the docs says that its code is one of two tables with disjoint numbers (0-99,
  WMO table 4677 `ww`; 100-199, WMO table 4680 `wawa` plus 100), that a station's historical file
  can hold both, and that the code's text is in DWD's `Wetter_Beschreibung.txt`. The code is
  returned as written, neither table translated into the other (GH-2718)
- A `dwd/radar` HDF5 request without `h5py` warns once, naming `pip install wetterdienst[radar]`,
  and returns the files unverified, where it logged a traceback for every file (GH-2928)
- `eccc/observation` stations are placed at the position ECCC's list gives in decimal degrees, no
  longer at its packed degrees, minutes and seconds read as degrees: 8431 of 8435 stations move,
  4904 by more than 0.25 degrees on an axis and up to 53 km. `CARWAY` (2219) on the Alberta border
  was at 48.5959 N, now 48.9997 N. Distance searches, interpolation and summaries pick stations by
  it (GH-2942)
- `dmi/observation` lists a station with the name, country, position and elevation of its
  current record (`validTo` null), no longer of its oldest: 696 of the 967 stations with several
  records change, by up to 1.75 degrees; 52 gain an elevation and one loses it. `04205` is now
  `Mittarfik Qaanaaq` at 77.4853 N with 16.0 m, no longer `Qaanaaq` at 77.4833 N without one
  (GH-2946)

### Security

- The REST API answers a failure of the server's own with a 500 whose `detail` is `Internal
  server error (<ExceptionType>). The cause is in the server log.`, no longer the exception's
  text, which names server paths (a cache directory, a file an `OSError` met) and upstream URLs.
  The body is still `{"detail": "<string>"}` and the status is unchanged, as are the 4xx and 501
  bodies; the text and traceback are in the server log, at error level as before (GH-2767)

## [0.152.0] - 2026-10-15

### Changed

- **Breaking**: `dwd/mosmix` `hourly/large` `e_ttt` and `e_td`, the absolute error of `ttt` and
  `td`, are named `error_absolute_temperature_air_2m` and `error_absolute_temperature_dew_point_2m`,
  no longer `error_absolute_temperature_air_mean_2m` and
  `error_absolute_temperature_dew_point_mean_2m`, so that a value and its error share a name.
  Request the new names; the old ones are not found (logged and dropped, or
  `NoParametersFoundError` when no other parameter is requested), values frames carry the new
  names, and a `geo_station_distance` key by an old name is refused, naming the new one (GH-2659)
- `geosphere/observation` station lists have a `wmo_id` column, the station's five-digit WMO number
  (`11021` for Litschau) from the list's `Synopstationsnummer`, null for the stations without one
  and for the 19 whose number has seven digits (`8989106`), which is no WMO number. It appears in
  the frames, JSON and GeoJSON properties. The composite series (`zusammengesetzt` `ja`, e.g. `1`
  Aflenz) have none; the number is on their part series, which can share it (GH-2751, GH-2019)
- The retry of `list_remote_files_fsspec` and `list_remote_directory_fsspec` no longer puts the
  `Settings` of a keyword call (`settings=settings`) into stamina's log record as
  `stamina.kwargs`, where a handler that serialises pydantic objects by their fields (logfire,
  rich) would print a proxy password. The record now carries no arguments and names the retried
  block `<context block>`, as `download_file`'s does, no longer the listing function. The retry
  policy and the answers are unchanged (GH-2904, GH-2623)

### Fixed

- `wetterdienst[radarplus]` installs `bitstring` below 5, because `pybufrkit` 0.2.25 calls
  `bitstring.BitStream`, which 5.0.0 removed: with it, decoding a BUFR file with `pybufrkit`
  raised `AttributeError`. (GH-2930)
- A TLS failure (a certificate that does not verify, a failed handshake) is no longer retried: a
  listing asked for it three times and a download or a post twice, each with a retry warning and
  the same error at the end. The listings (`list_remote_files_fsspec`,
  `list_remote_directory_fsspec`) also retry only a failed connection, a timeout, a broken body
  or a 5xx, no longer every exception, so a 4xx or a missing directory (which
  `list_remote_directory_fsspec` raises) is not asked for three times (GH-2618)
- `dwd/phenology` parameter descriptions (glossary in the CLI, REST API, MCP tools and docs) no
  longer say the value is "the day of the year". It is DWD's `Jultag`, which is the day of the
  year only for a date in the reference year and, in a leap year since about 1952, only before
  29 February; the descriptions now say so. Only the text changed, not the values (GH-2833,
  GH-2914)
- `repr(settings)` and `str(settings)` no longer raise for `fsspec_client_kwargs` that aiohttp takes
  but JSON cannot hold, such as `ClientTimeout(total=5)` or a `yarl.URL` as `proxy`. Such a value
  is masked like the rest of the client kwargs, so a failed file listing is retried and raises its
  own error instead of the serialization error from stamina's retry log. The settings' fields as
  pydantic and `rich` print them mask the client kwargs too (GH-2623)
- `wetterdienst about coverage --provider ... --network ...` and `wetterdienst radar` refuse a
  malformed `WD_*` setting, naming the variable and exiting 1, as `about coverage` without
  arguments and every other command already do. They ran and exited 0, so the same environment
  gave `about coverage` two different exit codes (GH-2619)
- `aemet/observation` no longer keeps a good envelope when the fetch of its `datos` link fails, and
  no longer keeps a `datos` body that is no JSON array (a maintenance page, an error object sent
  with HTTP 200). Both were read back for 5 minutes, the station list for 12 hours, so an expired
  link kept every request failing. A request that gets such a body now logs a warning and returns
  no data, not an exception, and the next one asks AEMET again (GH-2887)
- `dwd/dmo` station P0563 (London Luton) is at longitude -0.37, no longer +0.37 (50 km east),
  where the DMO station list loses its minus. Waddington (03377), Farnborough (03768) and
  Castellon de la Plana (08286) are west of Greenwich and Bauru (F9424) south of the equator, no
  longer east and north, where DWD publishes them in every file; they are in `dwd/mosmix` too.
  A position is corrected only while DWD still publishes the wrong one (GH-2897)
- The `dwd/phenology` overviews (the DWD index and the phenology page of the docs, the module
  docstrings) no longer open by calling the value "the day of the year". It is DWD's `Jultag`,
  which is that only for a date in the reference year and not for every date of a leap year
  since about 1952; the openings now say so. Only the text changed, not the values (GH-2902)
- The `dwd/observation` docs list the code sets DWD publishes: `hourly/precipitation` `wrtr` as
  0, 1, 4, 6, 7, 8, 9, plus 2 and 3, which the files hold and the sheet does not define, and the
  precipitation indicators `rs_ind_01`, `rs_ind_05`, `rws_ind_10` as 0 to 3 with their meaning by
  QN, no longer 0, 1, 3. Only the docs change; the values returned do not (GH-2703)
- `eccc/observation` `start_timestamp` and `end_timestamp` of a station are those of the
  resolution's own collection (`HLY_`/`DLY_`/`MLY_` dates of the station list), no longer the
  station's overall `FIRST_DATE`/`LAST_DATE` for all three. A station with no date for a
  resolution has null, not the overall dates, so test for null, not for a date; such stations are
  still listed for the resolution (GH-2747)
- `eccc/observation` values requested without `start` and `end` ask for the years from the first
  row of the collection (one `limit=1` request per station and collection; for hourly and monthly
  also the last), no longer from the station's `FIRST_DATE` to `LAST_DATE`. Rows before
  `FIRST_DATE` are returned now (1765: 1321 hourly values of 1955), and no request is made for the
  65 empty years of a station such as White Rock whose hourly record is shorter than the
  station's. A request with `start` and `end` is unchanged (GH-2820, GH-2864)
- `GET /api/auth` and `GET /api/coverage?provider&network` answer a listed network whose module
  fails to import (an `ImportError` that is no missing optional extra, such as a broken `lxml`
  install) with a 500, as the data routes do, no longer a 404 "Choose provider and network from
  /api/coverage"; the MCP tools raise the import error. The `/` index leaves out a provider whose
  first network does not import, no longer answering 500 for the whole page. The listing of every
  provider (`/api/coverage`, `wetterdienst about coverage`) logs a warning for a network it cannot
  import (GH-2800, GH-2801)
- The `noaa/ghcn` hourly docs page no longer constrains `pressure_air_site_delta_last_3h` (the
  3-hour pressure change) to `>=0`: it is negative when the pressure falls (-6.8 to 7.4 hPa at
  Anchorage in 2023). Only the docs change, the values returned do not (GH-2874)
- `noaa/ghcn` hourly values carry the file's `<element>_Quality_Code` in `quality_flags` (`2`
  suspect, `3` erroneous, `c` climatological outlier, ...; the meaning depends on the element's
  source, see the quality flags table of the Python API docs), where they were null apart from
  `raw:`. A suspect value is still returned, e.g. 50.0 °C at Antigua with `2`. The text of a
  sentinel follows the code (`1,raw:999`) (GH-2754)
- A missing optional package now raises `MissingDependencyError` naming the extra, where it
  leaked the package's own error: for a `to_target` to a SQL database whose driver is not
  installed, to CrateDB (`cratedb`), InfluxDB 1, 2 and 3 (`influxdb`), `.xlsx` and `.zarr`, and
  for a `.nc` without an engine (a plain `ImportError` before); for the image of a result or of
  warming stripes without Kaleido; for `describe_fields` without pypdf. The command line prints
  one line and exits 1, the REST API answers 501; so does
  `wetterdienst restapi` without the extra, no longer a traceback. Where plotly raised a
  `RuntimeError` (images) or SQLAlchemy a `NoSuchModuleError` (CrateDB), catch
  `MissingDependencyError` instead. The radar HDF5 download logs the install line (GH-2663, GH-2667)
- The `dwd/observation` daily docs list the precipitation form `rskf` and `rsf` as the codes 0 to 9
  (the 2021 sheet defines 0, 1, 4, 6, 7, 8, 9; the files also hold 2, 3, 5), no longer as `>=0`.
  Only the docs change; the values returned do not (GH-2911)
- A request for a parameter name that a dataset renamed (logged and dropped, or
  `NoParametersFoundError`) now says what it is called there: "It was renamed to
  'temperature_air_max_2m_last_12h' in this dataset" for MOSMIX `temperature_air_max_2m`, AEMET
  monthly `temperature_air_max_2m_multiday` and the `wind_*_last_10min` renames; "It is named
  'temperature_air_2m' here" for a sub-daily `temperature_air_mean_2m`, `temperature_soil_mean_2m`
  and the like. It named the closest spelling before, which was another quantity: the mean of the
  daily maxima for AEMET, `temperature_air_min_2m` for Geosphere 10-minute `temperature_air_mean_2m`
  and the 10 cm grass temperature for KNMI's. The old names still are not accepted (GH-2644,
  GH-2673)

### Security

- The release workflow builds the distributions in a job without the PyPI trusted-publishing token
  and publishes them from a second job that runs no project or dependency code, so a compromised
  build dependency can no longer obtain a PyPI token to upload files of its own. The CI provider
  keys (`WD_AUTH__*`) are given to the test steps alone, no longer to `uv sync` or the Codecov
  action (GH-2768)

## [0.151.0] - 2026-10-14

### Fixed

- Station names of `aemet/observation`, `metoffice/observation` and `metno/frost` no longer carry
  the blanks the catalogues pad some with (`PORTOCOLOM  `, `PORTLAND `, `KVANNDALEN `), so an exact
  comparison of the name, such as `name = 'PORTLAND'` in an SQL filter, matches them (GH-2654)
- **Breaking**: `dwd/observation` `10_minutes/urban_solar` `sunshine_duration` (`SD_ST_10`) is
  declared in hours, no longer minutes. DWD's parameter sheet says "Minute", but the values are
  fractions of an hour (0.17 is a full-sun interval of 10 minutes). With the default unit targets
  a full-sun interval comes back as 612 s, not 10.2 s, so values you stored from before are 60
  times too small in seconds; multiply them by 60. With `convert_units=False` the numbers are
  unchanged, and their unit is `h`, not `min` (GH-2698)
- The `radar` extra no longer installs `tabula`, an unrelated package ("Ascii table") that has no
  `read_pdf`; nothing at runtime imported it. Only the maintainers' radar-sites generator
  (`provider/dwd/radar/sites.py`) reads a PDF with `tabula`, and needs `pip install tabula-py` and
  a Java runtime itself. `uv sync --extra radar` drops `tabula` and, with it, `setuptools` (GH-2764)
- `noaa/ghcn` daily stations FR000007510 (Bordeaux-Merignac), FRE00104044 (Caen-Carpiquet) and
  SP000008416 (Valencia) are listed west of Greenwich, at -0.6914, -0.4558 and -0.3664, no longer
  east of it. `ghcnd-stations.txt` has lost the sign of their longitude, which put them 63 to 109
  km off, so a nearest-station search or an interpolation near them picked the wrong stations
  (GH-2645)
- **Breaking**: `dwd/observation` `daily/temperature_soil/temperature_soil_mean_1m` (`v_te100m`) is
  gone. DWD does not publish a 100 cm column (the files and the dataset sheet stop at 50 cm), so a
  request for it returned no rows and no warning, and the docs and coverage listed it as available.
  A request that names it now warns that it is not a known parameter and drops it, and fails if it
  names nothing else; remove it from the request. The hourly `temperature_soil_1m` (`v_te100`) is
  unchanged (GH-2700)
- `aemet/observation` no longer serves an error of AEMET's back from the cache. AEMET reports
  the rate limit (`estado` 429) and its own faults (500) in the body of an HTTP 200, which was
  kept for 5 minutes (12 hours for the station list) and read back by every request after it.
  Such an answer, a maintenance page and an envelope without a link to the data are now dropped,
  so the next request asks AEMET again (GH-2750)
- `aemet/observation` and `metno/frost` keep an accepted credential check for one minute, not one
  hour, so `is_valid()` and the credential check of the REST API and app stop reporting `True`
  for a revoked key within a minute. A refused or failed AEMET check is no longer kept at all
  (GH-2750)
- `imgw/meteorology` returns the first station of the list, `249170080` Dzierżkowice, which the
  reader took for the header: the list gave 799 of 800 stations and a request for that station
  found nothing (GH-2650, GH-2752)
- `noaa/ghcn` daily: 20 more stations, in the UK (Heathrow, Waddington, Cranwell, ...), Spain
  (Alicante, Murcia/San Javier, Valencia airport, ...), France (Mont-de-Marsan) and Burkina Faso
  (Ouagadougou, Dedougou), are placed west of Greenwich, no longer east of it, where
  `ghcnd-stations.txt` has lost the sign of their longitude. They were 6 to 756 km off, so a
  nearest-station search or an interpolation near them picked the wrong stations (GH-2886)
- `dwd/mosmix` and `dwd/dmo` station 08370 (Javea) is at longitude +0.17, no longer -0.17, and
  `dwd/dmo` station 40103 (Tripoli, Lebanon) at latitude 34.45, no longer 33.45. DWD publishes both
  at the wrong place, 30 and 111 km off, so a nearest-station search near them picked the wrong
  stations. A position is corrected only while DWD still publishes the wrong one (GH-2646)
- `meteofrance/observation` daily `wind_direction_gust_max` (`DXI`) and `meteofrance/synop`
  `wind_direction_last_10min` (`dd`) no longer return a direction of 400 degrees, which lies
  outside the compass and which neither source defines: the daily 2007-09-05 of 31299001 and 14
  rows of the 1996 SYNOP file (89642, 61972). The value is null with `raw:400` as the last token
  of `quality_flags` (GH-2728, GH-2873)
- `noaa/ghcn` daily stations that report in the current year have no `end_timestamp` (null) in the
  station list, as for `chmi/observation`; it was 31 December of this year, a date not reached
  yet, for 38,505 of 133,039 stations. The inventory gives only the year of the last observation,
  so null reads as still reporting; a filter for such stations tests for null (GH-2643)

## [0.150.0] - 2026-10-13

### Fixed

- `eccc/observation` makes no requests for hourly or daily values of a station that the station
  list gives no `HLY_`/`DLY_` first date (6750 of 8435 stations for hourly) when a request names
  no `start` and `end`. It asked for every year of the station and got empty answers, one request
  per year. Such a station has no values in the years asked for; a null-valued row (flag `M`) of
  one is no longer returned with `drop_nulls` off. Requests with dates are unchanged (GH-2820)
- `metno/frost` sends the end of a request one second later, and for `daily` as 00:00 UTC of the
  date after it, because Frost's intervals exclude their end. The value stamped at the end of a
  window (the 00:00 hourly reading, the month or year that starts there) and the daily `snow_depth`
  of the end date, read at 06:00 UTC, are returned now; results are still cut to the window asked
  for. Taken from Frost's documentation, not checked against the live API (GH-2729, GH-2746)
- **Breaking**: `dwd/dmo` `radiation_global` (`Rad1h`, both products) and `radiation_global_last_3h`
  (`RadS3`) are ten times larger than before. DWD writes them in J/cm2, not the kJ/m2 of the MOSMIX
  element table that was assumed (142.09 in the file is 142.09 J/cm2, 1421 kJ/m2, not 14.2 J/cm2).
  Values stored from earlier versions are a tenth of the true ones: multiply them by 10 (GH-2821)
- **Breaking**: `noaa/ghcn` hourly `snow_depth` is declared in millimeters, as GHCNh publishes it
  ("depth of snowpack on the ground (millimeters)"), no longer in centimeters. The numbers in the
  files are unchanged, but they were taken for centimeters, so values came back ten times too
  large (Anchorage: 910 cm where the GHCN-daily `SNWD` gives 910 mm). With the default unit
  targets the value is still in centimeters but a tenth of what it was (91.0 for 910 mm);
  `unit_targets` for `length_short` picks another unit. Values you stored from before are ten
  times too large in whatever unit they carry; divide them by 10 (GH-2848)
- `meteofrance/synop` `wind_direction_last_10min` (`dd`) is null where the file writes 0, with
  `raw:0` in `quality_flags`, no longer 0 degrees (north). 0 is the WMO code of a calm wind (all
  3495 zeros of the 2024 file have `ff` 0) and north is 360. `wind_speed_last_10min` is unchanged
  (GH-2856)

## [0.149.0] - 2026-10-13

### Changed

- **Breaking**: `meteofrance/synop` `subdaily/data` `dd` and `ff`, Météo-France's direction and
  speed of the wind averaged over 10 minutes, are named `wind_direction_last_10min` and
  `wind_speed_last_10min`, no longer `wind_direction` and `wind_speed`. Request the new names; the
  old ones are not found in `subdaily/data` (logged and dropped, or `NoParametersFoundError` when
  no other parameter is requested). `ff` is the 10-minute mean cut to whole m/s (2.4 m/s in the
  hourly `meteofrance/observation` `FF` is 2 in `ff`), so it reads up to 0.9 m/s below it
  (GH-2733)
- **Breaking**: `knmi/observation` hourly `DD`, KNMI's mean wind direction over the last 10 minutes
  of the hour ("Past 10 minute mean wind direction"), is named `wind_direction_last_10min`, no
  longer `wind_direction`, which is the mean over the row's interval. Request the new name; the old
  one is not found in `hourly/data` (logged and dropped, or `NoParametersFoundError` when no other
  parameter is requested; GH-2644). The 10-minute `wind_direction` is unchanged (GH-2835)
- **Breaking**: `meteofrance/observation` hourly `FXY`, the hour's highest 10-minute mean wind
  ("valeur maximale de FF dans l'heure"), is named `wind_speed_rolling_mean_max`, no longer
  `wind_gust_max`: it is no gust (department 31 since 2020: mean 3.7 m/s, between `FF` 2.9 and
  the gust `FXI` 6.0). Request the new name; `wind_gust_max` is not found in `hourly/core`
  (logged and dropped, or `NoParametersFoundError` when no other parameter is requested; its
  "Did you mean" names `wind_direction_gust_max`, wrongly). The hourly gusts `FXI` and `FXI3S`
  stay unmapped; the daily `wind_gust_max` (`FXI`) is unchanged (GH-2834)

### Fixed

- `dwd/phenology`: `Jultag` is documented as what it is. It is the value DWD writes, not the day
  of the year as the docs said: in leap years since about 1952 it counts 365 days (1 March is 60)
  and a date before the reference year is a negative number of days. The timestamp plus `Jultag`
  does not always give the entry date; the values are unchanged (GH-2822)
- `rmi/observation` returns the stamp of a request with `start == end` (the one-day form) at all
  three resolutions. It raised `DownloadError` (HTTP 400): the GeoServer rejects a zero-length
  `DURING` period. The filter is now `timestamp >= start AND timestamp <= end`, the same window
  otherwise (GH-2823)
- `dwd/observation` `10_minutes/urban_wind` `wind_direction`: a 0 beside a wind speed of 0 (a
  calm wind) is null, with `raw:0` in `quality_flags`, no longer 0 degrees (north), as for
  `10_minutes/wind`. The hourly `urban_wind` direction is unchanged (GH-2809)
- A cache directory that cannot be written no longer fails every request. A Docker volume that an
  image before 0.148.0 filled as root made them fail with `sqlite3.OperationalError: attempt to
  write a readonly database`. The process now logs one warning naming the directory and the reason
  and keeps its cache in a temporary directory, removed at exit. Chown the volume to
  `10001:10001` once to keep the cache across runs, see the Docker page (GH-2860)
- `nws/observation` keeps the fractions of wind gust, air and sea-level pressure, visibility,
  the 24-hour temperature extremes and precipitation (1, 3 and 6 hours). They were truncated to
  whole numbers on the read, so 0.8 mm of rain was returned as 0 and 28.4 mm as 28; the values
  now come back as the endpoint gives them (GH-2849)

## [0.148.0] - 2026-10-13

### Added

- `wetterdienst about auth --provider=... --network=...` and the MCP tool `auth` check one
  network's credentials, as `GET /api/auth` does and with the same answer: `valid` is `true`,
  `false` (rejected, or not configured) or `null` when the probe (one attempt, given up after a
  few seconds) could not tell. `coverage` does not probe, so this is the check from the command
  line and from an MCP client. The command exits 0 whatever `valid` is; read the JSON (GH-2773)

### Changed

- **Breaking**: the Docker image runs as the user `wetterdienst` (uid 10001), no longer as root,
  with `/home/wetterdienst` as its working directory and
  `/home/wetterdienst/.cache/wetterdienst` as its cache. Mount a cache volume there, or anywhere
  with `WD_CACHE_DIR` pointing to it, and make a volume or host directory that root filled (the
  cache, a file `--target`) writable by uid 10001 once: `docker run --rm --user 0 -v <volume>:/c
  ghcr.io/earthobservations/wetterdienst chown -R 10001:10001 /c` (GH-2770)
- `chmi/observation`: the monthly and annual values carry the files' `FLAG_INTERRUPTED` in
  `quality_flags` (null before) as `interrupted:I`: the value is computed although daily values of
  the period are missing. A filter on a null `quality_flags` as "no flag" no longer holds for these
  rows. `FLAG_REPEAT` is carried as `repeat:*` too, but only `MAX`/`MIN` rows have it and none of
  the parameters is one (GH-2763)
- `Settings` no longer holds the 15 `ts_*` settings: they are gone from `model_fields`,
  `model_dump()` (so `Settings(**s.model_dump())` carries none) and the repr, and a malformed
  `WD_TS_*` is refused when `Options` is built, not by `Settings()`. `Settings(_env_file=...)` no
  longer sets options: use `Options(_env_file=...)`. `SkipThreshold` is imported from
  `wetterdienst.options`, where `resolve_options` and `options_from_settings` of 0.147.0 are gone;
  `resolve_options` is in `wetterdienst.settings` (GH-2639)
- `dmi/observation`: `quality_flags` (null before) carries DMI's `qcStatus` and `validity`, as
  `manual,validity:true`. DMI sets `validity` to `false` for values its climatologists consider
  invalid ("generally not correct"), mostly Greenland: 1978 mm of precipitation in a day at
  04339, 17,802 mm in a month. The values are still returned; filter `quality_flags` for
  `validity:false` to leave them out. A filter on a null `quality_flags` no longer holds (Part of
  GH-2797)

### Deprecated

- `Settings(ts_shape=...)` and the other `ts_*` settings, reading or assigning `settings.ts_*`
  (`ts_tidy` and the other derived members too), and a `settings={"ts_...": ...}` dict now warn
  with a `DeprecationWarning` and are forwarded to the options of a request given no `options=`.
  Use `options=Options(shape=...)` and read `request.options`. A request keeps the options it was
  built with, and `options=` beside `ts_*` settings that differ from the environment's options is a
  `ValueError`. `Settings.model_construct(ts_...)` is not forwarded. Assigning
  `settings.ts_geo_station_distance` takes effect now (it was checked and then discarded). The
  `WD_TS_*` variables stay and do not warn (GH-2639)

### Fixed

- `dwd/poi` `cloud_cover_total` is null, with `raw:113` or `raw:126` in `quality_flags`, where DWD
  writes those numbers in the percent column (113 is an obscured sky, 126 comes with fog). They
  came back as a cloud cover of 1.13 and 1.26: 58 of 8744 reports in a day of 960 stations (GH-2615)
- `dwd/observation` wind direction: a 0 that DWD writes for a calm or variable wind is null, with
  `raw:0` in `quality_flags`, no longer 0 degrees (north, which a wind rose or a mean direction
  counted). Every 0 of `hourly/wind`, `hourly/wind_synoptic` (DWD: "windstill DD=00") and
  `subdaily/wind`; in `10_minutes/wind` and `10_minutes/wind_extreme` only a 0 beside a wind speed
  (a gust) of 0, as some stations write north as 0 there and a 0 beside a wind that blows stays
  (GH-2805)
- `dwd/derived` and `eccc/observation` values collect with the in-memory engine, as on polars 1,
  not with the streaming engine polars 2 uses by default: it took 6 times as long for the hourly
  radiation of one station and 4 times for 60 years of daily rows of one ECCC station, for the
  same rows (GH-2781)
- A wind direction of 0 that is no bearing (a calm wind) is null, with the source's text (`raw:0`)
  in `quality_flags`, no longer 0 degrees (north, which a wind rose or a mean direction counted):
  `noaa/ghcn` hourly `wind_direction` (the documentation's "000"), `geosphere/observation`
  `wind_direction` (`dd`) of the 10 minute and hourly data, and `dwd/poi`
  `wind_direction_last_10min`, where the 0 is a calm or a variable wind (it comes with speeds up to
  22 km/h). North is 360 in these sources. The gust direction of Geosphere has no 0 and is
  unchanged (GH-2794)
- A wind direction of 0 that means a calm wind is null, with the source's text (`raw:0`, `raw:0.0`)
  in `quality_flags`, no longer 0 degrees (north, which a wind rose or a mean direction counted):
  `nws/observation` (METAR `00000KT`), `smhi/observation` (both directions), `fmi/observation`
  `wd_10min`, and `dmi/observation` `mean_wind_dir` where the mean wind speed of the same hour,
  day, month or year is 0. North is 360 in these sources. A DMI 0 beside a wind that blows stays
  (GH-2794)
- `GET /api/auth` and `GET /api/coverage?provider=...&network=...`, and so the MCP tools `auth`
  and `coverage`, answer a network whose optional extra is not installed with the 501 the data
  routes answer, not the 404 "Choose provider and network from /api/coverage" for an unknown one.
  The install line is in the server log (GH-2788)
- `eccc/observation` daily `wind_gust_max` and `wind_direction_gust_max` are null, with `raw:0` in
  `quality_flags`, where ECCC writes 0: the gust is not reported below 31 km/h, and a direction of 0
  is no bearing (north is 36 tens of degrees). They were 0 m/s and 0 degrees on over a third of the
  days with a gust value. Use the gust only where it is not null (GH-2615)
- `eccc/observation` `start_timestamp` and `end_timestamp` of a station with hourly values were one
  hour early when the station's first or last date fell in the daylight-saving season (Toronto Intl
  A started 2013-06-11 13:00 UTC, not 14:00). The dates are Local Standard Time, so they are now
  converted with the fixed offset of the `TIMEZONE` code (no more 17 min 32 s from the local mean
  time of a station that began before 1895), and an unknown code raises (GH-2693)
- `dwd/observation` 1-, 5- and 10-minute `historical` values: a request for the last hour (two in
  summer time) of the last day of a file, such as 22:00 to 23:50 UTC on 31 July, came back without
  those hours, because the file's end was read as Berlin midnight; its stamps are UTC (MEZ, a fixed
  UTC+1, before 2000). A request ending on a file's first stamp now gets that file too (GH-2811)
- `eccc/observation` hourly `wind_direction` is null, with `raw:0` in `quality_flags`, where ECCC
  writes 0: ECCC's glossary says "A value of zero (0) denotes a calm wind", and north is 36 tens of
  degrees. A calm hour was 0 degrees, north, before: 1824 of 43,469 hours with a direction at
  five stations, all with a wind speed of 0 (GH-2794)
- `dwd/observation` `10_minutes` `historical`: the six values 1999-12-31 23:00 to 23:50 UTC were
  missing for every station and dataset that spans the year 2000 (a 70 minute hole), because the
  file of 1999 (MEZ) and the file of 2000 (UTC) carry the same digits for different instants. The
  wind file of 1999 also reaches into 2000-01-01 00:00 to 00:50 MEZ, which now lands on 23:00 to
  23:50 UTC and no longer competes with the real values of 00:00 to 00:50 UTC. The same holds for
  the stamps past MEZ midnight in the December 1999 files of `1_minute` (23:00 to 23:59 UTC) and
  `5_minutes` (one row, 23:00 UTC; whether it is a misstamped 23:55 is open, GH-2827). A request
  for that hour returns these values (GH-2815)
- `dwd/observation` `subdaily/wind` `wind_direction` (`DK_TER`) is in degrees. The file holds the
  point of a 32-point wind rose (DWD: "32-teilige Windrose"), and 24 was returned as 24 degrees for
  a west wind. A value is now multiplied by 11.25: 8 is 90 degrees, 16 is 180, 24 is 270, 32 is 360
  (GH-2808)
- `dwd/derived` settles a timestamp that two periods report (historical and recent) on the
  historical record, in every run. It kept whichever row it had read first, in the order of an
  unordered set, so the value (or a missing reading) could differ from one run to the next (GH-2792)
- `imgw/meteorology` `daily/climate` (from May 2024) and `daily/synop` (from July 2024) no longer
  raise `AttributeError`: IMGW stopped writing `k_d_t` and `s_d_t` into the zips then. The
  parameters of `k_d`/`s_d` are returned; those only the missing file carries (`cloud_cover_total`,
  `humidity_relative`, `wind_speed` and, in synop, the vapour and air pressures and the day and
  night precipitation) have no rows after the month the file ends (GH-2819)

## [0.147.0] - 2026-10-12

### Added

- polars 2 is supported: the dependency is now `polars[calamine]>=1.43.0,<3` (it was `<2`), so
  wetterdienst installs next to packages that need polars 2. `dwd/observation` collects with the
  in-memory engine, as on polars 1, not with the streaming engine polars 2 uses by default
  (GH-2570)
- `wetterdienst.Options`: the per-request options (`shape`, `humanize`, `convert_units`,
  `unit_targets`, `skip_*`, `drop_nulls` and the `geo_*` distances), the request half of what
  `Settings` holds as `ts_*`, as a frozen class of their own. They read the same `WD_TS_*`
  variables and `.env`, so no host configuration changes; `replace(**changes)` makes a validated
  copy. `Settings` is unchanged; `check_settings()` now checks them too (GH-2639)
- Every timeseries request takes the keyword `options=` (an `Options`, or a dict naming some of
  them), and `StationsResult.options` carries them to the values, `interpolate` and `summarize`.
  Given none, a request takes the `ts_*` settings of its `Settings` as before, so nothing changes
  for a caller who passes none -- except that assigning `settings.ts_*` after the request is built
  no longer reaches it. Passing `options=` beside settings that carry a non-default `ts_*` raises
  a `ValueError`: set the options in `options=` alone (GH-2639)

### Changed

- **Breaking**: the `quality` number of every values frame is replaced by one nullable string
  column `quality_flags` (wide: `<parameter>_quality` by `<parameter>_quality_flags`) holding every
  flag the source publishes, comma-separated: the quality flag plain (`T`, `Good`, `3`), further
  kinds as `kind:code` (`noaa/ghcn` daily `G,measurement:T,source:7`, `chmi/observation`
  `3,element:E`); null where there is none. It fills what `eccc`, `ea`, `meteofrance`, `noaa/ghcn`,
  `chmi`, `nws` and `smhi` dropped, and `imgw/meteorology` keeps `Z` where it wrote 10. Where you
  used the number, cast it, `pl.col("quality_flags").cast(pl.Int64, strict=False)` (`Z` is no
  number); select by name, as columns move; SQL tables need the new column. Interpolated and
  summarized frames have no flags column (GH-2018, GH-2755, GH-2757, GH-2758)
- **Breaking**: `metno/frost` `daily` `snow_depth` is stamped at 00:00 UTC of the date of its
  reading, no longer at the time of the reading (usually 06:00 UTC), like the other daily
  parameters. Join stored snow depth on the date (GH-2729)
- **Breaking**: `metno/frost` and `aemet/observation` `is_valid()` is `False` only when the provider
  rejects the credential (HTTP 401/403, for AEMET also an `estado` of 401/403), `True` when it
  accepts it, and `None` when the probe could not tell (no network, a TLS failure, a timeout, a 429,
  a 5xx), which used to read as `False`. `valid` in `/api/auth` is `true`,
  `false` or `null` with it: treat `null` as unknown, not as invalid, and do not hide the provider
  for it. The app lists such a network. `Wetterdienst.is_valid(api)` is the guarded call
  (GH-2550, GH-2562)
- The REST API and the MCP tools refuse a chart image with a side over 8192 px, `scale` (or the
  stripes `dpi`) applied, with a 400 naming the limit; a larger one held a Chromium for tens of
  seconds and could come back empty. Ask for a smaller `width`, `height`, `scale` or `dpi`. The
  library and the CLI are not limited (GH-2765)
- **Breaking**: `Wetterdienst.discover()`, `GET /api/coverage` (and the MCP `coverage` tool) and
  `wetterdienst about coverage` download nothing, so they answer at once. `valid` is `null` for a
  network whose credentials are configured, where it was `true` or `false` after a probe; it stays
  `false` where they are missing. Ask `GET /api/auth` per network, or `Wetterdienst.is_valid(api)`,
  whether they are accepted. That probe is one attempt that takes at most 5 s, and AEMET's probe
  reads only the envelope: an `estado` of 200 is accepted, whatever follows. The app lists the
  networks at once and hides one when `/api/auth` says its credentials are rejected (GH-2564)
- The package ships `py.typed` (PEP 561): mypy and pyright now read the annotations of the public
  API instead of taking all of it for `Any`, so code they passed before may report errors. For
  that the annotations were made true: every provider package lists its classes in `__all__`
  (strict mode refuses `from wetterdienst.provider.dwd.observation import DwdObservationRequest`
  otherwise), `to_plot(**kwargs)` takes any values (it said `dict`), `discover()` is
  `dict[str, Any]`, and `TimeseriesValues` is generic over the model a provider collects by (a bare
  `TimeseriesValues` still means any). A request's `metadata`, `_values` and `_history` are class
  variables, no longer in `dataclasses.fields()` (GH-2622)
- **Breaking**: a `.env` file is read as UTF-8 on every Python, where the encoding was the locale's
  (the ANSI code page on Windows) until Python 3.15 made UTF-8 the default. A `.env` saved in a
  Windows code page with a non-ASCII value now raises `UnicodeDecodeError` on `Settings()`:
  re-save it as UTF-8 (GH-2568)
- A value a provider maps from a missing-value sentinel is no longer a null with no trace: the text
  the source wrote is the last token of `quality_flags`, `raw:<text>` (`3,raw:-999`, `raw:-99.0`,
  `raw:NaN`), for the `dwd` networks that read one, `aemet`, `fmi`, `geosphere`, `imgw/hydrology`,
  `ipma`, `knmi`, `meteofrance`, `metoffice`, `metno/frost` and `noaa/ghcn` hourly. Where the source
  documents the code (FMI's `-1.0`), the value is what it stands for (`0.0`) and the token stays.
  The long frame drops null rows by default, so read the token with `ts_drop_nulls=False` or in the
  wide shape, where a null `quality_flags` no longer means "no flag" for these rows.
  `metoffice/observation` returns a day whose reports are all `NA` as a null row, and
  `imgw/hydrology` nulls `9999` in the stage, `99999.999` in the discharge and `99.9`, `9999` in
  the water temperature, no longer all three in every column (GH-2759)

### Removed

- The `tzfpy` dependency and `TimeseriesValues._get_timezone_from_station`, which looked up a
  station's time zone from its position. Since GH-2683 no provider stamps a row with the station's
  zone, so nothing called it; installs are one compiled package smaller. A subclass that called the
  private method must resolve the zone itself (GH-2725)

### Fixed

- `eccc/observation` a `daily` request for the first day of a station, or a `monthly` one for its
  first month, no longer skips the station: its `start_timestamp` and `end_timestamp` in the station
  list are now 00:00 UTC of the first and last date (of the month for `monthly`), like the values,
  where they were the local time moved to UTC (13:00 UTC for 09:00 in Toronto). `hourly` is
  unchanged (GH-2730)
- `ea/hydrology` daily requests no longer cut the newest reading of a window: the readings request
  carried a `_limit` of one reading per day, but a window holds more readings than days (the
  maximum and minimum are dated at their instant, and the endpoint answers some days twice), so
  the last requested day could be missing. No `_limit` is sent for daily now (GH-2732)
- Station lists keep columns the readers built and `all()` dropped: `wsv/pegel` has `river` (as
  published, `ELBE`) and `river_kilometer`, `noaa/ghcn` has `wmo_id` (daily and hourly, five digits),
  `knmi/observation` has `wigos_id`, the full WIGOS identifier whose trailing number is
  `station_id`, and `metoffice/observation` fills `region` with the MIDAS historic county
  (`shetland`), which was null. The columns appear in the frames, JSON and GeoJSON properties of
  those providers (GH-2019)
- **Breaking**: `dmi/observation` `region` held DMI's country code (`DNK`, `GRL`, `FRO`) and is
  null now, DMI giving no region; the code is in the new `country` column. Filter or group by
  `country` where you used `region` (GH-2019)
- **Breaking**: `imgw/meteorology` `region` held the river catchment with its hydrographic code
  (`Odra (1)`) and is null now, the station list giving no region; the catchment is in the new
  `river` column. Use `river` where you used `region` (GH-2019)
- `knmi/observation` without the `knmi` extra raises `MissingDependencyError` naming
  `pip install wetterdienst[knmi]`, no longer a bare `ModuleNotFoundError` (an `ImportError` either
  way); the CLI prints that line, and `/api/stations`, `/api/values`, `/api/interpolate` and
  `/api/summarize` answer 501 with the line in the server log, no longer a 500 with a traceback
  (GH-2545)
- `noaa/ghcn` reads its daily station list and inventory over https, no longer plain http
  (GH-2766)

## [0.146.0] - 2026-10-11

### Changed

- **Breaking**: `fmi/observation` hourly `ws_10min` and `wd_10min`, FMI's mean wind speed and
  direction over 10 minutes, are named `wind_speed_last_10min` and `wind_direction_last_10min`, no
  longer `wind_speed` and `wind_direction`, which are the mean over the row's interval. Request
  the new names; the old ones are not found in `hourly/data` (logged and dropped, or
  `NoParametersFoundError` when no other parameter is requested; GH-2644) (GH-2707)
- **Breaking**: `metno/frost` hourly `wind_speed` and `wind_from_direction`, Frost's mean over the
  last ten minutes before the observation time, are named `wind_speed_last_10min` and
  `wind_direction_last_10min`, no longer `wind_speed` and `wind_direction`. Request the new names;
  `wind_direction` is not found in `hourly/data` (logged and dropped, or `NoParametersFoundError`
  when no other parameter is requested), and `wind_speed`, which is also Frost's own element name,
  still selects the row but comes back named `wind_speed_last_10min`. Daily and monthly
  `wind_speed` are unchanged (GH-2707)
- **Breaking**: `smhi/observation` hourly parameters `4` and `3`, SMHI's mean wind speed and
  direction over 10 minutes taken once per hour, are named `wind_speed_last_10min` and
  `wind_direction_last_10min`, no longer `wind_speed` and `wind_direction`. Request the new names;
  the old ones are not found in `hourly/data` (logged and dropped, or `NoParametersFoundError`
  when no other parameter is requested). The 1-minute `wind_speed` and `wind_direction` are
  unchanged (GH-2707)
- **Breaking**: `meteofrance/observation` hourly `FF` and `DD`, Météo-France's wind force averaged
  over 10 minutes and its direction, are named `wind_speed_last_10min` and
  `wind_direction_last_10min`, no longer `wind_speed` and `wind_direction`. Request the new names;
  the old ones are not found in `hourly/core` (logged and dropped, or `NoParametersFoundError` when
  no other parameter is requested). The daily and monthly `wind_speed` (`FFM`) are unchanged
  (GH-2707)
- **Breaking**: `noaa/ghcn` `daily` values are stamped at 00:00 UTC of their date, no longer at the
  station's local standard midnight in UTC (Tokyo 15:00 UTC of the day before, New York 05:00 UTC),
  so a request for one day (`start` and `end` the same date) returns that day for every station.
  Stamps move by up to 14 hours: join stored series on the date, no longer on the instant, and
  shift series stored with the old stamps (GH-2683)
- **Breaking**: `eccc/observation` `daily` and `monthly` values are stamped at 00:00 UTC of their
  date or of the first of the month, no longer at the station's civil midnight in UTC (Toronto
  05:00 UTC in winter, 04:00 UTC in summer), so a request for one day or month returns it. Join
  stored series on the date, no longer on the instant (GH-2683)
- **Breaking**: `smhi/observation` `daily` `snow_depth` is stamped at 00:00 UTC of the date of its
  reading, no longer at 06:00 UTC, like the other daily parameters, so a request for one day
  returns it with them, where it used to be dropped. Join stored snow depth on the date (GH-2683)
- **Breaking**: `ea/hydrology` `daily` values are stamped at 00:00 UTC of the day they name (the
  24 hours from 09:00 of that day), no longer at 09:00 UTC for the mean and at the instant of the
  extreme for the maximum and minimum, so a request for one day returns it. Where the endpoint
  answers one day twice, the reading with a value is kept, then the complete one, then the good
  one. Join stored series on the date, no longer on the instant (GH-2683)

### Fixed

- `meteofrance/synop` `subdaily/data` returns `0.0`, no longer `-0.1`, for
  `precipitation_amount_last_1h`, `_3h`, `_6h`, `_12h` and `_24h` in hours with a trace of rain, so
  a sum over a period is no longer short by a tenth of a millimetre per trace, and null, no longer
  `1.01`, for `cloud_cover_total` when the sky was obscured (`n = 101`) (GH-2674)
- `meteofrance/observation` `hourly/others` `cloud_cover_total` is null, no longer `1.125`, in the
  hours in which the sky was invisible (`N = 9`), so a mean or a maximum over a period is no longer
  pulled past a whole sky; null values are dropped by default (GH-2687)
- `metno/frost` sends the bounds of a request to Frost as UTC. They went out as the wall clock of
  whatever zone they were held in, which Frost reads as UTC, so a request in `Europe/Oslo` asked
  for a window one or two hours off and lost rows at one end (GH-2681)
- `dwd/observation` `hourly/weather_phenomena` returns null, no longer `-1`, for `weather` in the
  hours in which DWD did not report the present weather (`WW_Text`: "Wetter wurde nicht gemeldet"),
  so counting hours by weather code, or taking its maximum or mean, no longer includes them
  (GH-2670)
- **Breaking**: `dmi/observation` daily `precipitation_amount_max` (`max_precip_30m`) is dated by
  the day it ends on, as DMI defines it ("23:31 local time to the previous day to 24.00 local time
  of the respective day"), not by the day before; its series moves one day later. Shift stored
  series of it by one day. The other daily parameters are unchanged (GH-2676)
- `dwd/derived` monthly values (`heating_degreedays`, `cooling_degreehours_*` and
  `climate_correction_factor`) are stamped with the first day of their month at 00:00 UTC, no
  longer with the request's start including its time of day and offset (`start` of
  `2025-01-01T00:00+01:00` stamped January as 2025-01-31 23:00 UTC). The UTC months of `start` and
  `end` are fetched, and a month is returned only if its first day at 00:00 UTC lies within
  `start` and `end`, so a `start` of `2025-01-01T06:30` no longer returns January (GH-2679)
- `meteoswiss/observation` picks the decade files of the 10-minute and hourly historical data by
  the UTC year of the request bounds, as the time stamps are in UTC, where it took the year as
  written: a request in a local zone near New Year, such as `2010-01-01T00:30:00+02:00`, returned
  no rows (GH-2680)
- `meteofrance/observation` `hourly/core` `wind_direction_last_10min` and
  `wind_direction_gust_max` and `daily/core` `wind_direction_gust_max` are null, no longer `0` or
  `999`: the files write `0` where there is no direction, mostly in a calm wind (5 % of the hourly
  `wind_direction_last_10min` values since 2020), and `999`, probably for a variable one, which a
  wind rose or a mean direction counted as north or as 999 degrees. `360` is north and stays
  (GH-2720)
- A request whose `start` and `end` carry a named time zone (`ZoneInfo("Europe/Vilnius")`) no
  longer raises a polars `SchemaError` once its values are cut to the window. The bounds, and so
  `request.start`/`end` and the result's, are converted to UTC when the request is made: the same
  instants as before, now with a UTC zone, where an aware bound kept the zone it was given. The
  providers that read a bound's year or date, or format it for the upstream, now do so in UTC
  (GH-2682)
- The "Time zones and reference times" page (`docs/data/time_reference.md`) no longer lists the
  `dwd/derived` monthly stamp, the `meteoswiss/observation` decade files and the `metno/frost`
  request bounds as deviations from their sources: they were fixed (GH-2679, GH-2680, GH-2681) and
  the notes of their rows state what the code does now (GH-2734)
- The "Time zones and reference times" page (`docs/data/time_reference.md`) no longer calls the
  `metno/frost` hourly wind an instant: `wind_speed_last_10min` and `wind_direction_last_10min`
  are Frost's mean over the ten minutes before the stamp, so the stamp ends their window
  (GH-2736)
- The "Time zones and reference times" page (`docs/data/time_reference.md`) no longer files the
  10-minute wind mean as an instant: `dwd/poi` hourly wind is "end for wind: the mean of the last
  10 minutes before the stamp", as AEMET's already was, and `meteofrance` hourly and synop wind say
  that their source does not state which end of the 10 minutes the stamp is (GH-2738)

## [0.145.0] - 2026-10-11

### Changed

- **Breaking**: Python 3.10 is no longer supported; `wetterdienst` requires Python 3.11 or newer.
  Install on 3.11 or newer; pip on an older Python keeps resolving the last release that supports
  it. The `backports-datetime-fromisoformat` dependency, which only Python 3.10 installed, is
  dropped. The `export` extra requires `xarray>=2025.6.0`; with the `zarr>=3.1` the extra
  installs, 2024.6 cannot write Zarr and earlier releases cannot read it back, so upgrade xarray.
  The `radarplus` extra requires `xradar>=0.8`, as older releases need the `datatree` package that
  xarray 2025.1 and later no longer work with (GH-2568, GH-2704)
- **Breaking**: `chmi/observation` monthly and annual `TMA` and `TMI` are named
  `temperature_air_max_2m_mean` and `temperature_air_min_2m_mean`, no longer
  `temperature_air_max_2m` and `temperature_air_min_2m`: the files hold the mean of the daily
  maxima and minima, not the extremes of the period. Request the new names; the old ones are not
  found in these datasets (logged and dropped, or `NoParametersFoundError` when no other
  parameter is requested). The daily names are unchanged (GH-2614)
- **Breaking**: `aemet/observation` monthly and annual `ta_max` and `ta_min`, the absolute maximum
  and minimum of the month or year, are named `temperature_air_max_2m` and
  `temperature_air_min_2m`, no longer the `_multiday` names. Request the plain names; the old ones
  are not found in these datasets (logged and dropped, or `NoParametersFoundError` when no other
  parameter is requested) (GH-2614)
- **Breaking**: `dwd/mosmix` (`small`, `large`) and `dwd/dmo` (`icon`, `icon_eu`) `tx` and `tn`,
  the maximum and minimum temperature within the last 12 hours, are named
  `temperature_air_max_2m_last_12h` and `temperature_air_min_2m_last_12h`, no longer
  `temperature_air_max_2m` and `temperature_air_min_2m`. Request the new names; the old ones are
  not found in these datasets (logged and dropped, or `NoParametersFoundError` when no other
  parameter is requested) (GH-2614)
- **Breaking**: `dwd/observation` 10-minute `tt_10` and `tm5_10`, which DWD describes as the
  instant air temperature at 2 m and 5 cm, are named `temperature_air_2m` and
  `temperature_air_0_05m`, no longer `temperature_air_mean_2m` and `temperature_air_mean_0_05m`,
  which name the mean over the interval. Request the new names; the old ones are not found in
  `10_minutes/temperature_air` (logged and dropped, or `NoParametersFoundError` when no other
  parameter is requested) (GH-2651)
- **Breaking**: `meteoswiss/observation` 10-minute `tre200s0`, `tre005s0`, `tso005s0`, `tso010s0`,
  `tso020s0`, `tde200s0` and hourly `tso005hs`, `tso010hs`, `tso020hs`, which MeteoSwiss calls
  the current value, are named `temperature_air_2m`, `temperature_air_0_05m`,
  `temperature_soil_0_05m`, `_0_1m`, `_0_2m` and `temperature_dew_point_2m`, no longer the
  `_mean_` names. Request the new names; the old ones are not found in these datasets (logged and
  dropped, or `NoParametersFoundError` when no other parameter is requested). The hourly means
  `tre200h0`, `tre005h0` and `tde200h0` keep their `_mean_` names (GH-2651)
- **Breaking**: `smhi/observation` 1-minute `45` and hourly `1` and `39`, which SMHI calls
  instantaneous values, are named `temperature_air_2m` and `temperature_dew_point_2m`, no longer
  `temperature_air_mean_2m` and `temperature_dew_point_mean_2m`. Request the new names; the old
  ones are not found in these datasets (logged and dropped, or `NoParametersFoundError` when no
  other parameter is requested). The daily and monthly means keep theirs (GH-2651)
- **Breaking**: `aemet/observation` hourly `ta` and `tpr`, `meteofrance/observation` hourly `T`
  and `metno/frost` hourly `air_temperature`, which their sources describe as an instantaneous,
  present or observation-time value, are named `temperature_air_2m` and, for `tpr`,
  `temperature_dew_point_2m`, no longer the `_mean_` names. Request the new names; the old ones
  are not found in these datasets (logged and dropped, or `NoParametersFoundError` when no other
  parameter is requested). Where a source says a mean, the `_mean_` name stays (GH-2651)
- **Breaking**: DWD temperatures below daily resolution whose source states no statistic are named
  for a reading at one moment, no longer the mean: `dwd/observation` 10-minute `td_10` and
  `urban_temperature_air`/`_soil`, hourly `dew_point`, `moisture`, `temperature_air`,
  `temperature_soil` and `urban_temperature_air`/`_soil`, subdaily `moisture` and `temperature_air`;
  `dwd/mosmix`, `dwd/dmo` `ttt`, `t5cm`, `td`; `dwd/swsmos` `TL`, `TD`; `dwd/poi`; `dwd/road`
  `roadSurfaceTemperature`. Request `temperature_air_2m`, `temperature_air_0_05m`,
  `temperature_dew_point_2m`, `temperature_wet_2m`, `temperature_radiant_2m`, `temperature_surface`
  or `temperature_soil_0_02m` to `_1m`; the old names are not found (logged and dropped, or
  `NoParametersFoundError` when no other parameter is requested). Windowed names keep theirs; road
  `airTemperature` and `dewpointTemperature` and SWSMOS `TS` follow below (GH-2657)
- **Breaking**: the same for the sub-daily temperatures of `chmi`, `eccc`, `knmi` hourly, `lhmt`,
  `metoffice`, `noaa/ghcn` hourly, `meteofrance/observation` hourly `TD`, `meteofrance/synop` `td`
  and `metno/frost` hourly dew point, whose sources say nothing about the statistic. Request the
  spot names; the old ones are not found (logged and dropped, or `NoParametersFoundError` when no
  other parameter is requested). Rows whose source says a mean or average of the row's interval
  (IPMA, MeteoSwiss hourly, KNMI 10-minute `tg` and `tb`; DMI and RMI in the field name) keep
  their `_mean_` names (GH-2657, GH-2660)
- **Breaking**: `dwd/road` `airTemperature` and `dewpointTemperature` and `dwd/swsmos` `TS`, which
  DWD gives without a statistic, are named `temperature_air_2m`,
  `temperature_dew_point_2m` and `temperature_surface`, no longer `temperature_air_mean_2m`,
  `temperature_dew_point_mean_2m` and `temperature_surface_mean`. Request the new names; the old
  ones are not found in these datasets (logged and dropped, or `NoParametersFoundError` when no
  other parameter is requested). `dwd/road` `roadSurfaceTemperature` was already
  `temperature_surface` (GH-2660)
- **Breaking**: sub-daily temperatures whose "mean" was not the source's are named for a reading at
  one moment, no longer `temperature_air_mean_2m`, `temperature_dew_point_mean_2m` or the
  `_mean_` soil and 0.05 m names: `geosphere/observation` 10-minute `tl`, `ts`, `tb10` to `tb50`
  and hourly `tl`, `tb10` to `tb200`, `wsv/pegel` `LT`, `meteofrance/synop` `t`,
  `nws/observation` `temperature` and `dewpoint`, `fmi/observation` hourly `t2m` and `td` and
  `knmi/observation` 10-minute `ta` and `td`. Request `temperature_air_2m`, `temperature_air_0_05m`,
  `temperature_dew_point_2m` or `temperature_soil_0_1m` to `_2m` (`_2m` is new); the old names are
  not found in these datasets (logged and dropped, or `NoParametersFoundError` when no other
  parameter is requested). KNMI `tg` and `tb` keep their `_mean_` names (GH-2660)
- **Breaking**: a `ts_geo_station_distance` override keyed by an old `_mean_` name no longer
  applies to a row moved to a spot name by the entries above: the row takes the default radius.
  Key the override by the new name (GH-2651, GH-2657, GH-2660)
- `GET /api/coverage` declares its response in the OpenAPI document: the list of every provider
  and its networks, and the resolutions, datasets and parameters of one (`CoverageNetwork`,
  `CoverageResolution`, `CoverageDataset`, `CoverageParameter`), so a client can be generated from
  or checked against it. The JSON sent is unchanged; the MCP `coverage` tool takes it as its
  output schema and returns the same result (GH-2090)
- **Breaking**: `dwd/observation` hourly `wind_synoptic` `ff`, which DWD gives as the 10-minute
  mean of the wind speed ("10-Min-Mittel der Windgeschwindigkeit"), is named
  `wind_speed_last_10min` (new), no longer `wind_speed`, which is the mean over the row's
  interval. Request `wind_speed_last_10min`; `wind_speed` is not found in `hourly/wind_synoptic`
  (logged and dropped, or `NoParametersFoundError` when no other parameter is requested). `dd`
  stays `wind_direction`, as DWD states no window for it, and hourly `wind` `f` and `d`, DWD's
  hourly means, keep theirs (GH-2697)
- **Breaking**: `dwd/poi` hourly mean wind speed and direction over the last 10 minutes are named
  `wind_speed_last_10min` and `wind_direction_last_10min` (new), no longer `wind_speed` and
  `wind_direction`. Request the new names; the old ones are not found in `hourly/data` (logged and
  dropped, or `NoParametersFoundError` when no other parameter is requested) (GH-2697)
- **Breaking**: `aemet/observation` hourly `vv` and `dv`, AEMET's mean wind speed and direction over
  the 10 minutes preceding `fint`, are named `wind_speed_last_10min` and
  `wind_direction_last_10min` (new), no longer `wind_speed` and `wind_direction`. Request the new
  names; the old ones are not found in `hourly/data` (logged and dropped, or
  `NoParametersFoundError` when no other parameter is requested; the hint for `wind_direction`
  names `wind_direction_gust_max`, see GH-2644). The daily `velmedia` keeps `wind_speed` (GH-2697)
- **Breaking**: `meteofrance/observation` 6-minute and hourly timestamps of the overseas departments
  (971-975, 984-988) are UTC. The files stamp them in a fixed offset per territory ("FU", not always
  its legal time), which the library labelled UTC: Réunion's (UTC+4) came back 4 h late,
  Saint-Pierre-et-Miquelon's (UTC-4) 4 h early. Offsets: Guadeloupe, Martinique -4 h, Guyane -3 h,
  Mayotte +3 h, Wallis-et-Futuna +12 h, Polynésie -10 h, Nouvelle-Calédonie +11 h, TAAF per station.
  Drop a shift you applied yourself; a window for these stations now holds other readings. Daily and
  monthly dates, metropolitan France and Port Martin (offset unknown) are unchanged (GH-2677)
- **Breaking**: `count_weather_type_sleet` is `count_weather_type_graupel`. It was DWD's graupel
  columns (`graupel`, `rr_graupel`, `mo_graupel`, `ja_graupel`) in the `weather_phenomena` datasets
  of `dwd/observation` daily, monthly and annual and in `daily/weather_phenomena_more`. Request the
  new name; the old one in a request or as a `ts_geo_station_distance` key (now an error, it was a
  warning) is reported with its replacement. A table `to_target` wrote before holds the old name,
  as a wide column or in `parameter`: write it anew (GH-2696)

### Fixed

- `dwd/observation` `hourly/moisture` returns null, no longer `-99.9` (`-0.999` for
  `humidity_relative`), for `humidity_absolute`, `pressure_vapor`, `temperature_wet_2m`,
  `humidity_relative` and `temperature_dew_point_2m` in the hours DWD has no reading for, so means
  and minima over these series are no longer pulled down (GH-2669)
- **Breaking**: `eccc/observation` hourly values are stamped at the instant ECCC gives in
  `UTC_DATE` (Local Standard Time plus the station's standard offset, all year). Stations on
  daylight saving were stamped one hour early from March to November, the standard-time hour that
  does not exist on the civil clock in spring got no timestamp, and the UTC hour after the autumn
  change was missing, and a station whose ECCC zone differs from the zone of its position (for
  example 50837, PST) was off all year. Summer stamps move one hour later, those stations by the
  difference in either direction, and the two lost hours are returned; a comparison or join made
  on the old stamps has to be redone. Daily and monthly are unchanged (GH-2675)
- `noaa/ghcn` hourly `wind_direction` no longer returns 999 for hours in which the older reports
  give no direction (mostly marked calm): the value is null, and dropped by default, so a mean or
  a wind rose over the series is no longer pulled to 999 degrees. The documented missing value of
  the hourly `precipitation` column, -9999, is nulled too (GH-2672)
- Writing a NetCDF file no longer fails with `ValueError: unrecognized engine for to_netcdf:
  'netCDF4'` where `netCDF4` is installed and `h5netcdf` is not: the engine is named as xarray
  names it, `netcdf4` (GH-2666)
- Listing a directory (`list_remote_files_fsspec`, `list_remote_directory_fsspec`) through a proxy
  that answers with an error status no longer raises or logs the proxy's `Proxy-Authorization`
  header: the `ClientResponseError` is redacted like a download's is, retry warning included
  (GH-2603)
- `dwd/derived` hourly `sunshine_duration_uncertainty` is returned: it was declared with the global
  radiation's column `fg_un_duett`, which the sunshine duration file does not have, and so never
  came back; it is read from `sd_un_duett` (GH-2614)
- Station names of `dwd/swsmos` and `dwd/road` no longer carry the trailing blank the catalogue
  pads some with (`Darup `, `AD Südost `: 38 and 33 stations), so an exact comparison of the name,
  such as `name = 'Darup'` in an SQL filter, matches them (GH-2616)
- Station names of `imgw/meteorology` and `imgw/hydrology` no longer carry the trailing blank the
  lists pad some with (`RADZIECHOWY `, `Tuliszków `, `LUDŹMIERZ `) (GH-2616)
- The station name of `chmi/observation` `Třinec  Oldřichovice  Javorový` no longer ends in the
  blank the catalogue gives it (GH-2616)
- `geosphere/observation` stations that still report have no `end_timestamp` (null), as for
  `chmi/observation`; it was 2100-12-31, the date the list gives them, for about 470 stations. A
  filter for the stations still reporting tests for null instead of for a date in the future
  (GH-2616)
- `geosphere/observation` daily `precipitation_amount`, `snow_depth`, `snow_depth_manual` and
  `snow_depth_new` are 0.0 on a day without precipitation or snow, no longer -1.0: the source's
  `-1=kein Niederschlag` / `-1=kein Schnee`. A sum of precipitation over a month was short by one
  millimetre for every dry day. The other resolutions are unchanged (GH-2671)
- `noaa/ghcn` hourly stations `RUU71-00102` (CHABAROWKA) and `RUU71-00113` (IRKUTSK) have no
  position, where the list puts them at latitudes of 135.117 and 104.367, off the globe, with
  latitude and longitude swapped; the hourly list drops any position outside latitude +-90 or
  longitude +-180, as it does for the `BOGUS` placeholders (GH-2616)
- `to_target` with a protocol nothing here writes (`ftp://x/y.csv`) raises `ExportRefusedError`, as
  documented, no longer SQLAlchemy's `NoSuchModuleError`, and the command line prints one line. An
  optional package that is not installed (DuckDB for `sql` and `duckdb://`, SQLAlchemy for
  database targets, xarray, plotly, scipy, h5py) raises `MissingDependencyError`, an
  `ImportError` naming the extra to install, no longer a bare `ModuleNotFoundError`; the command
  line prints it as one line, and the REST API answers 501 (GH-2637)
- A request to `knmi/observation`, `aemet/observation` or `metno/frost` without a credential raises
  `CredentialMissingError`, a `ValueError` as before, with the same message. The REST API and the
  MCP tools answer it with a 501 and a fixed sentence, no longer a 500 that tells the caller to set
  an environment variable on the server (the message goes to the server log), and the command line
  prints it in one line and exits 1, no longer with a traceback (GH-2638)
- `dwd/observation` parameter descriptions say what DWD publishes, where they said more or other
  (REST API, MCP, CLI, docs tables): the daily weather phenomena are the day's occurrence, not "days
  with ripe/sleet" (`reif` is hoar frost, `graupel` is graupel); 10-minute `fx_10` and `fnx_10` no
  longer carry sampling details DWD does not state; 1-minute `rth_01` is the droplet gauge, not the
  tipping bucket; hourly gust `fx_911` is not "10 m above ground"; urban hourly values name the
  window DWD gives (temperatures and humidity: a 1-minute mean ending 10 minutes before the hour;
  precipitation, sunshine and wind: the six 10-minute values of the previous hour); daily `tmk` and
  the other term-based means say how DWD computes them; the datasets `subdaily/moisture` and
  `subdaily/soil` no longer claim mean temperatures and a soil temperature they do not hold
  (GH-2688)

- `dwd/observation` `hourly/wind` and `10_minutes/wind` return no `wind_direction` of 990 any more:
  the files write 990 where there is no direction (542,296 hourly rows in 314 stations, 17 of the
  10 minute ones, historical files from 1952 on), which came back as 990 degrees and spoiled a
  wind rose or a vector mean. It is null now, as -999 is (GH-2686)

## [0.144.0] - 2026-10-10

### Fixed

- Writing to a `mssql://` target creates text columns as `NVARCHAR(max)` instead of
  `VARCHAR(max)` (`TEXT` before SQL Server 2012), so a character outside the column's code page,
  such as the `Ł` of `Łódź` or the `ř` of `Třeboň` under `SQL_Latin1_General_CP1_CI_AS`, is
  stored as it is and no longer as a `?`. A table that is appended to keeps its column types;
  alter them, or write to a new table (GH-2273)
- The station catalogues of `fmi`, `chmi`, `ipma`, `lhmt`, `metoffice`, `dwd/swsmos` and
  `dwd/phenology`, and the `metoffice` release listing, raise `DownloadError` for a download that
  failed -- a timeout, a 5xx, a 404 -- where they logged it and returned no stations: the REST API
  answers a 500 and the CLI fails, where a station request had an empty result with a success
  status. A connection that cannot be made at all still gives no stations; the catalogues log
  it at debug now, where they warned (GH-2519)
- The station catalogues of `smhi/observation` and `metno/frost` raise `DownloadError` for a
  download that failed -- a timeout, a 5xx, a 404 -- where they logged it and returned no
  stations (for `smhi/observation`, the stations of the other parameters only): the REST API
  answers a 500 and the CLI fails. A connection that cannot be made at all still gives no
  stations, logged at debug (for `smhi/observation`, when it fails for every list; for some
  only, it raises); Frost's 401 and 403 stay a `PermissionError` (GH-2599)
- `Wetterdienst.discover()`, `GET /api/coverage` and `GET /api/auth` list `metoffice/observation`
  as needing a credential (`auth: true`), so it is not configured, with `valid` false, until
  `WD_AUTH__CEDA` is set; it was listed as needing none and as configured and valid whether that
  variable was set, missing or malformed. The Explorer app hides it while it is not configured
  (GH-2594)
- `Wetterdienst.discover()`, `GET /api/coverage` and `GET /api/auth` list a provider that needs a
  credential as not configured when a `WD_*` variable is invalid, such as `WD_AUTH__CEDA` that is
  no `username:password`, and log the problem once; one malformed credential raised for the whole
  listing and, where the REST API's start-up check is off, answered 500.
  `Wetterdienst.is_configured(api)` is that check for a single provider (GH-2580)
- Listing a directory of files on a host whose certificate does not verify, or that fails a TLS
  handshake, raises that failure (an `ssl.SSLError`) after the retries, where it returned no
  files as if offline: providers that list first returned an empty result with no hint of why
  (GH-2581)
- Listing the contents of one directory (the DWD DMO and alerts indexes, IMGW) on a host whose
  certificate does not verify, or that fails a TLS handshake, raises an `ssl.SSLError` after the
  retries instead of the aiohttp error, whose repr rendered the password of a proxy named in
  `HTTPS_PROXY` into the retry log and into messages that format it. Both are `OSError`s, so
  `except OSError` keeps catching it; `except aiohttp.ClientError` no longer does (GH-2590)
- Listing the contents of one directory (the DWD DMO and alerts indexes, IMGW) no longer leaves
  the password of a proxy named in `HTTPS_PROXY` on the error when connecting fails some way other
  than TLS (a proxy that refuses the connection, a DNS failure, a reset during the connect): it is
  still a `ClientConnectorError`, retried as before, but its repr no longer renders the password,
  and its traceback (whose frames held it), that of its `os_error` and its `__cause__` are dropped
  (GH-2602)
- A retried download or post that fails TLS through a proxy no longer logs the proxy's password:
  stamina's retry warning rendered the aiohttp error's connection key, which holds `proxy_auth`
  and the `user:secret@` of a proxy URL, whether the proxy came from `HTTPS_PROXY` or from
  `client_kwargs`. The key is logged with both removed (GH-2582)
- A download or post refused by a proxy (the proxy answered CONNECT with an error status, or
  an `http://` target behind it failed) no longer logs the proxy's `Proxy-Authorization` header, nor
  stores it in `File.content`: it and the `user:secret@` of the proxy URL are redacted from the
  error's request info, as is an `Authorization` header added by `auth=`; only a caller's own
  `headers` were before (GH-2592)
- Exporting a frame of 7 or more columns to a `sqlite://` target no longer fails with "too many
  SQL variables" once it has more than 32766 / columns rows (from 4681 rows for 7 columns) on
  SQLite 3.32 and later: the rows per insert now follow the 32766 variables a statement may
  carry, where only the older limit of 999 was honoured (GH-2579)
- Exporting a wide frame to a SQLite target that names its driver, such as
  `sqlite+pysqlite:///a.sqlite?table=t`, no longer fails with "too many SQL variables": the cap on
  the rows per insert was applied only to targets starting `sqlite://` and is now applied to every
  SQLite target (GH-2589)
- `wsv/pegel` values, the DWD field descriptions read from PDFs and the script that regenerates the
  packaged OPERA radar sites raise `DownloadError` for a failed download, as
  `File.raise_if_exception` does elsewhere, where they raised the stored error itself: a timeout
  there had an empty message and answered the REST API with `{"detail": ""}`. Catch
  `DownloadError` and read `__cause__` for the original (GH-2507)
- A `WD_*` value in the environment or `.env` that is nested too deeply to decode as JSON, such
  as `WD_AUTH__CEDA` set to 100000 opening brackets, is treated as text that is not JSON is:
  `check_settings()` names the variable and `Settings()` raises a `ValidationError` or
  `SettingsError`; text for a key of a dict setting is kept as it is. All three raised a
  `RecursionError` before: `check_settings()`, `Settings()` and so a provider's `is_configured()`,
  which now raises the `ValidationError` (GH-2543)
- KNMI and AEMET values requested with no network stop at the first download that finds none, per
  station, and return what was read before it (an empty frame if nothing), logged at debug as
  elsewhere. Every KNMI moment (720 for an hourly month) and every AEMET chunk was requested
  again before, and each skip logged a warning (GH-2558)
- LHMT values requested with no network stop at the first day whose download finds none (a missing
  day is still skipped), per station, and return the days read before it (an empty frame if
  nothing), where every day of the range was requested again (GH-2591)
- `repr()` and `str()` of `Settings` mask the credentials in `fsspec_client_kwargs`: every value
  but the timeout, the User-Agent header and booleans is masked, a `proxy` URL included. stamina's
  retry warning for a failed file listing rendered the settings, proxy password and
  `Authorization` header included. `model_dump()` still returns the values as given (GH-2593)

## [0.143.0] - 2026-10-08

### Changed

- **Breaking**: the path of a `duckdb://` target is read as the path of a URI, as a `file://` one
  is: `duckdb:////home/me/my%20data/obs.duckdb` opens `/home/me/my data/obs.duckdb`, where it
  opened `obs.duckdb` in a directory named `my%20data` and failed if there was none. A path
  holding a literal `%` followed by two hex digits, such as `%20`, must now write that `%` as
  `%25` (`%2520`); a `%` not followed by two hex digits is read as before (GH-2515)

### Fixed

- A download or post that fails on a certificate that does not verify, or on a TLS protocol
  error, is reported as that failure (status 500) and no longer as being offline (503): callers
  that return an empty result for no internet now warn about it or raise instead (GH-2553)
- An `mssql://` export writes in inserts within SQL Server's limits of 2100 parameters and 1000
  rows, about 299 rows of a 7-column values frame. It sent 5000 rows at a time, so any export of
  more than a few hundred rows failed with "too many parameters" (GH-2268)
- A file the cache downloads is written beside its blob and renamed onto it once whole, so a
  concurrent request for the same URL, from another thread or process, no longer truncates a copy
  another reader is serving, and a body cut short leaves no partial file in the cache directory.
  Where Windows refuses the rename because the blob is open, that read is served from the file
  just fetched, the blob is kept and the next read fetches again (GH-2493)
- `metno/frost` values read a failed download's status before treating it as empty. A 404 now
  reaches the fallbacks written for it (each parameter alone, then its time series discovered),
  where the request returned no data; a 401, 403 or 500 is logged as `Failed to download <url>`
  where it passed as "no data" without a word (GH-2494)
- `metno/frost` values, when the request for a whole dataset 404s, resolve only the parameters
  asked for, not every parameter of the dataset: one hourly parameter cost up to 11 requests alone
  and 11 time series discoveries per station. A dataset of one parameter (`6_hour`) goes straight
  to the discovery instead of repeating the request that 404'd (GH-2554)
- KNMI and AEMET stations and values requested with no network, or with a connection that cannot
  be made (refused, DNS or TLS handshake failure), no longer wait through two more attempts per
  URL, 2 s and more apart, before returning empty: `download_file`'s own two attempts are all
  there are. The retries for an HTTP 503 and for a 429 are unchanged (GH-2499)
- `dwd/road` raises a `DownloadError` when every file of a station group fails with an error
  response or a timeout (403, 5xx); the request used to return an empty frame. When only some
  files fail, the readings of the others are returned and a warning names how many of how many
  failed; the same warning accompanies an empty result when all are 404 (withdrawn since the
  listing). A failure to connect, a refused certificate included, still gives an empty result,
  now with that warning (GH-2495, GH-2553)
- `interpolate`, `summarize` and their `_by_station_id` variants build a provider's station list
  once, not two or three times: on a cold cache that is a round of upstream requests fewer, for
  DWD observation the station description files and the file index per period. `filter_by_rank`
  and `filter_by_distance` take the station list as an optional `df_all` (GH-2506)
- `/api/stations`, `/api/values`, `/api/interpolate`, `/api/summarize`, `/api/history` and
  `/api/issues` log an unknown provider or network as one info line, as do the first five for a
  network without stations or values (`dwd/radar`, `dwd/alerts`), and `/api/history` one without
  station history. They logged an error with its traceback; the 404 is unchanged (GH-2532)
- `WD_AUTH__CEDA` written as a pair that is not valid JSON (`[user, pa:ss]`) is refused by
  `check_settings()` and `Settings()`; with a colon in it, it was split there into a username and
  password still holding the brackets, and failed at CEDA. A pair given in Python as valid JSON
  text (`'["user", "pa:ss"]'`) is read as the pair. A `username:password` whose username starts
  with `[` is read as a pair too, and refused; write it as `["username", "password"]` (GH-2483)
- `wetterdienst about coverage --resolutions=...` or `--datasets=...` without `--provider` and
  `--network` printed the catalogue of every provider with the filter dropped; it is now a usage
  error (exit 2) naming the options it needs, as `/api/coverage` and the MCP `coverage` tool already
  answer it with a 400. Add both options, or drop the filter (GH-2527)
- `Settings` logs its `Wetterdienst cache is ...` line, and the `ts_drop_nulls` notice for a wide
  shape, once when built, no longer again on every field assignment or
  `Settings.model_validate(settings)`. A `ts_shape` assigned later logs nothing (GH-2504)
- `WD_AUTH__METNO_FROST` (and `Settings(auth={"metno_frost": ...})`) written as `id:secret`,
  `id,secret`, `id secret` or the text `("id", "secret")` is refused, as is any other lone text
  holding a character but an ASCII letter, digit or `-`, with a message naming the form
  `["client_id", "secret"]`; it was taken whole as the client id, secret included, and Frost
  refused the credential later. `check_settings()` reports it too (GH-2487)
- `dmi/observation` values for a long range, such as hourly data of station 06180 over six years,
  are read in windows (a year for hourly, ten for daily) that stay below DMI's offset cap of
  500000: a request reaching offset 600000 was cut off there, and failed with a 400 since failed
  downloads are raised. No offset above the cap is asked for any more (GH-2520)
- A lone `WD_AUTH__METNO_FROST` client id is kept without the whitespace around it, such as a
  newline in a `.env` value, the `\r` of a CRLF file, an NBSP or U+2028; it was sent to Frost with
  the padding and refused there. Text of nothing but whitespace, or `""` given in Python, reads as
  unset, as an empty value in the environment does, where it counted as a configured client id
  (GH-2542)
- `WD_AUTH__KNMI`, `WD_AUTH__AEMET`, both halves of `WD_AUTH__CEDA`, and each element of a
  `WD_AUTH__METNO_FROST` pair are kept without the whitespace around them (a newline from a `.env`
  value, a CRLF); they were sent to the provider with it and refused there. A key of nothing but
  whitespace, and a CEDA or Frost pair whose username or client id is blank, now read as unset, as
  a lone Frost client id does; they counted as configured and sent empty credentials. A password
  or secret with whitespace at its edges loses it too (GH-2557)

## [0.142.0] - 2026-10-08

### Changed

- **Breaking**: a station history's records -- station and operator names, parameters, devices,
  geography, missing data -- give their span as `valid_from` and `valid_to`, where they gave
  `start_date` and `end_date`: in Python's `History`, `/api/history`, the MCP `history` tool and
  the CLI `history` command. Read the new names (GH-2440)
- **Breaking**: the single date or interval a request names is `timestamp`, no longer `date`:
  `/api/values`, `/api/interpolate`, `/api/summarize`, `/api/alerts` and their MCP tools,
  `--timestamp` of the CLI's `values`, `interpolate`, `summarize` and `alerts`, and
  `DwdWeatherAlertRequest(timestamp=...)` with its attribute `.timestamp`. Write
  `timestamp=2020-05-01` where you wrote `date=2020-05-01`; the old name is refused with an error
  naming the new one. The app sends `timestamp` from its next release; 0.18.1 and older send
  `date`, so upgrade the app with the backend (GH-2438)
- **Breaking**: the request window is `start` / `end`, no longer `start_date` / `end_date`: write
  `DwdObservationRequest(..., start=..., end=...)` for every provider's request and
  `DwdRadarValues`, read `.start` / `.end` off a request or a `StationsResult`, and pass
  `--start` / `--end` on the CLI. The old keywords and options fail with an error naming the new
  one; reading the old attributes, or passing them by keyword to
  `TimeseriesRequest.convert_timestamps`, is a plain Python error. Error messages that named the
  pair name `start` / `end` (GH-2437)
- **Breaking**: the span a station has records for is `start_timestamp` / `end_timestamp`, no
  longer `start_date` / `end_date`: in every provider's stations frame and its exports, and wherever
  a station is returned -- `/api/stations` and the MCP `stations` tool, the OGC feature properties,
  values with stations, interpolate, summarize, `/api/stripes/stations` and the station in the
  `/api/stripes/values` metadata. Read and filter the new names, and rename the columns of a
  database table you append stations to; a `sql` filter on a station's old name fails naming the
  new one. The app reads the new names from its next release, so upgrade the app with the backend
  (GH-2439)
- **Breaking**: `/api/auth`, `/api/coverage`, `/api/glossary`, `/api/stripes/stations` and
  `/api/alerts` refuse a query parameter they do not take with a 422, as `/api/stations` and
  `/api/values` do, and every MCP tool refuses an argument it does not take, naming the ones it
  does. Both used to answer as if it had not been given, so a misspelt `limit` returned every
  match. Drop parameters an endpoint or tool does not take, such as a cache buster (GH-2479)
- CLI: `stations` reports a request the caller can rephrase -- an unknown parameter, a bad
  bounding box, a `--sql` DuckDB refuses -- as a one-line usage error with exit code 2, where it
  printed a traceback. `history` on a network whose stations have no history, such as
  `dwd/mosmix`, and `about coverage` on a standalone network such as `dwd/radar` are usage errors
  too, where they exited 1. Scripts checking for exit 1 on these now see 2; an upstream failure
  still exits 1 with its traceback (GH-2465)
- **Breaking**: in a DWD observation station's history, the current position in `geography` has a
  null `valid_to`, where it was the time the history was read and changed on every call. A name or
  operator still in use was null already. Read a null `valid_to` as a position that still applies
  (GH-2474)
- **Breaking**: a download that failed raises `wetterdienst.exceptions.DownloadError` through
  `File.raise_if_exception`, which most providers use, where it raised the stored error itself
  (`FSTimeoutError`, `ClientResponseError`, `FileNotFoundError`, aiohttp's connection errors). Its
  message is `Failed to download <url>: <reason>` with the URL stripped of query, fragment and user
  information, so the REST API's `detail` and the CLI name the file. Catch `DownloadError` and read
  `__cause__` for the original error (GH-2460)
- **Breaking**: a station the provider gives no end has a null `end_timestamp` in the station list
  of `eaufrance/hubeau` (every station it lists) and of `dwd/observation` 1-minute precipitation
  from the historical period, where it was the time of the call or the day before. Read a null
  `end_timestamp` there as a station the provider has not closed (GH-2482)
- Values of `dwd/phenology`, `dwd/poi`, `dwd/swsmos`, `chmi`, `fmi`, `ipma`, `dmi`, `rmi`,
  `metoffice`, `lhmt`, `meteofrance/synop` and `meteofrance/observation` raise a data download that
  failed -- a timeout, a 5xx -- as `DownloadError`, where they logged it and returned no data for
  the station, or went on to the next file: the REST API answers a 500 and the CLI fails, and so
  do interpolate and summarize where a station they read fails. A 404 still gives no data at
  `dwd/poi`, `dwd/swsmos`, `chmi`, `lhmt`, `metoffice`, `meteofrance/observation` and, for the
  current year, `meteofrance/synop`, and raises at the others. `fmi` gives no data for a 400, which
  it answers for a station it does not know. A connection that cannot be made at all still gives
  no data (GH-2461)

### Fixed

- `stations`, `values`, `interpolate`, `summarize` and `history` on `dwd/radar` or `dwd/alerts`,
  which have no stations or parameters to select, are refused with a 404 naming `/api/coverage` in
  the REST API and a usage error (exit 2) in the CLI, where they failed with an AttributeError: a
  500 and a traceback. `history` on a network without station history (`dwd/mosmix`) is refused
  before its station catalogue is downloaded, so an upstream failure no longer hides it (GH-2492)
- The CLI's `about coverage` refuses `--provider` without `--network`, and `--network` without
  `--provider`, with a usage error (exit 2) naming the missing option. It printed every provider
  with exit 0, as if neither had been given; with neither it still lists them (GH-2498)
- `/api/glossary` and the MCP `glossary` tool refuse a `limit` below 1 with a 422, as the CLI's
  `--limit` already does; a limit of 0 or below answered one entry with a 200 (GH-2497)
- `geosphere/observation` values without dates, at 10 minutes or hourly, and long windows no
  longer fail: the API refused a slice of more than 1,000,000 data points (the 10-minute record is
  1.8 million), and answered one of more than about 6 years at 10 minutes too slowly for the read
  timeout. A window is fetched in several requests, two years each at 10 minutes and ten years
  each hourly for one parameter (GH-2466)
- `geosphere/observation` values ask the API for all the requested parameters of a dataset in one
  request, not one request per parameter. A whole dataset of a station without dates took 285 to
  414 requests at 10 minutes or hourly and stopped at the API's 240 requests an hour with an HTTP
  429; it takes about 105 (10 minutes), 62 (hourly), 4 (daily) and 1 (monthly). The windows get
  shorter with more parameters, as the API counts timestamps times parameters towards its limit of
  1,000,000 data points, and a whole daily dataset is now fetched in windows too (GH-2517)
- A `file://` target of `to_target` and of the CLI's `stations`, `values`, `interpolate`,
  `summarize`, `history` and `alerts` is read as the path the URI names: `%20` and other
  percent-encoding is decoded, and on Windows `file:///C:/data/obs.csv` is `C:/data/obs.csv`.
  Both wrote to the wrong path. A path with a literal `%20` in a `file://` target is now written
  `%2520`; a plain path is read as given (GH-2454)
- `/api/values` and the MCP `values` tool log a request they refuse with a 400 -- an unparseable
  timestamp, an unknown parameter or period -- as one info line, as `/api/interpolate` and
  `/api/summarize` do. Each was logged as an error with its traceback; the status is unchanged
  (GH-2459)
- `/api/stations`, `/api/issues`, `/api/history`, `/api/stripes/values` and `/api/stripes/image`
  log a request they refuse with a 400 as one info line, as `/api/values` does, where they logged
  an error with its traceback; the status is unchanged. `/api/issues` on a network without issue
  listing is a 400 that was never logged and still is not (GH-2512)
- `WD_USE_CERTIFI=true` now reaches every download of `geosphere/observation` values,
  `ea/hydrology` values, `metno/frost` stations, values and credential check, and `dwd/road`
  values. They went out with the system CA store, so where that store cannot verify the upstream
  they failed SSL verification even with the setting on (GH-2463)
- A `WD_AUTH__METNO_FROST` pair that is not valid JSON, such as `[myid, mysecret]` with its
  elements unquoted, is refused, and `check_settings()` names it. It was taken whole as the client
  id, secret included, and sent to Frost, which refused it. Quote each element:
  `["myid", "mysecret"]`. A pair given in Python as that text is read as the pair (GH-2464)
- A download through the cache (any TTL but `CacheExpiry.NO_CACHE`, cache not disabled) reports
  the failure it met, as one without the cache does: an HTTP error other than 404 comes back with
  its own status -- a 401, 403 or 429 too, which `download_file` no longer asks again -- and a
  refused connection as 503 with `NoInternetError`, where all were `File(status=404)` with
  `FileNotFoundError`, as a missing file is, and a provider that skips a missing file, such as DWD
  derived's months, skipped them too. KNMI's and AEMET's own retry of a 429 or 5xx now
  applies through the cache too. A cache miss is one GET instead of two, and a body that ends
  before its `Content-Length` is no longer read back from the cache by the retry (GH-2467)
- `filter_by_name`, `filter_by_rank` and `filter_by_bbox` build the station list once, where they
  built it twice, `filter_by_distance` once instead of four times, and `interpolate` and
  `summarize` twice instead of six times: that much less parsing, and with `WD_CACHE_DISABLE` or a
  provider that does not cache its station list, that many fewer downloads. `filter_by_distance`
  on a request with no stations finds none, where it raised "'rank' has to be at least 1."
  (GH-2475)
- A request built from a `Settings` object, as the CLI builds its requests, uses it as it is rather
  than validating it again, so the cache line and the `ts_drop_nulls` notice of a wide shape are
  logged once, when the settings are built, rather than twice. Settings given as a dict are
  validated as before (GH-2476)
- DWD road values and radar BUFR reads import `pyproj`, where it is installed, before they load
  `eccodes`. On Linux, with the `eckitlib` wheel pip installs beside `eccodes`, a process that used
  `pyproj` or wradlib after such a read aborted at exit with status 134 or 139 (ecmwf/eckit#354);
  it now exits cleanly, unless something imported `eccodes` before wetterdienst did (GH-2468)
- `/api/values`, `/api/interpolate`, `/api/summarize` and their MCP tools word a `timestamp` that
  ends before it starts, or is missing for an interpolation or a summary, in terms of `timestamp`
  ("the interval in timestamp ends before it starts"), where they named the request's `start`
  and `end`, which their callers cannot pass. Python callers keep the request's message, and
  `ReversedTimeIntervalError` and `MissingTimeIntervalError` are subclasses of the exceptions
  they raised (GH-2478)
- `wetterdienst values`, `interpolate` and `summarize` word a window that ends before it starts in
  terms of the options ("the interval in --timestamp or --start / --end ends before it starts"),
  where they printed `Error: Error: 'start' must be smaller or equal to 'end'.`. Python callers
  get the request's message without the stray `Error: ` prefix (GH-2513)
- `/api/values` and its MCP tool answer a dataset that is queried by a window (ECCC, DMI,
  Geosphere, NOAA GHCN and others), requested without a `timestamp`, with "timestamp is required
  for this dataset", where they said "Start and end date required for single period datasets";
  `/api/interpolate` and `/api/summarize` do the same for an empty `timestamp`. The CLI's `values`
  says "--timestamp or --start / --end is required for this dataset". Python callers keep the old
  message; the new `DateRequiredError` is a subclass of `StartDateEndDateError` and also of
  `MissingTimeIntervalError`, so `except InvalidTimeIntervalError` and `except ValueError` now
  catch it too (GH-2514)
- `wetterdienst stripes values` refuses a `--target` that is a URI (`s3://...`, `file://...`)
  before it fetches and renders, as a usage error (exit 2) naming `--target`; the write to the
  path read off the URI (`s3:/bucket/...`) failed only afterwards. A `--target` whose extension
  does not match `--format` is a usage error too, exit 2 where it was 1. Pass a local path
  (GH-2450)
- `/api/coverage` and the MCP `coverage` tool answer 404 for an unknown provider or network,
  pointing at `/api/coverage`, where they answered a bare 500. With no provider and network the
  list of every provider honours `pretty`, so it comes back compact by default, not indented as
  before; pass `pretty=true` for the indented form. `resolutions` or `datasets` without `provider`
  and `network` is refused with a 400, where the full list came back unfiltered; pass both with
  them, or drop the filter (GH-2496)

## [0.141.0] - 2026-10-06

### Added

- The JSON of `/api/stripes/values` and the MCP `stripes_values` tool name the unit of their
  values in a new metadata field `unit`: `degree_fahrenheit` where the server's
  `WD_TS_UNIT_TARGETS` converts temperatures to it, the source's unit with
  `WD_TS_CONVERT_UNITS=false`, and `degree_celsius` or `millimeter` by default (GH-2372)

### Changed

- The `restapi` extra now needs `fastapi>=0.142` (was `>=0.115`), which brings `opentelemetry-api`;
  upgrade fastapi where it is pinned lower. The REST API turns off fastapi's OpenTelemetry export
  from `OTEL_*` variables: to export, set up a provider yourself, e.g. with
  `opentelemetry-instrument`. Such a provider now gets fastapi's spans, metrics and logs, or, where
  the `opentelemetry-instrumentation-fastapi` middleware runs, that instrumentation's (GH-2407)
- REST API: `/api/interpolate` and `/api/summarize`, and the MCP tools of the same names, answer
  a point there is no estimate at -- beyond the latitudes UTM covers (80°S to 84°N) on
  interpolate, or a `station` without a position -- with a 400 rather than a 404, as they answer
  an elevation no station can be placed against. The server logs it as an info line, not as an
  error with its traceback (GH-2385)
- Values of `dwd/observation`, `dwd/derived`, `imgw/hydrology` and `imgw/meteorology` raise a
  download that timed out, where they used to drop it as a missing file and return no data for
  the station: the REST API answers a 500 and the CLI fails, and so do interpolate and summarize
  where a station they read times out. A 5xx after the retries is raised the same way only with
  the cache off (`WD_CACHE_DISABLE=true`); with it on, a 5xx still reads as a missing file (GH-2430)
- CLI: `values`, `interpolate`, `summarize`, `issues`, `stripes values` and the station lookup of
  `history` report a request the caller can rephrase -- such as a parameter the network does not
  have, a network without an issue listing, or a point there is no estimate at -- as a one-line
  usage error with exit code 2, and so does every command for an unknown provider or network.
  Scripts checking for exit 1 on such a mistake now see 2; an upstream failure still exits 1 with
  its traceback (GH-2426)
- REST API: `/api/interpolate` and `/api/summarize`, and their MCP tools, answer the other
  requests they refuse as phrased -- an empty or unparseable `date` or one as late as 9999-12-31, an
  unparseable `issue` or one the source does not list, an unknown parameter or unit target, a
  `sql_values` clause DuckDB refuses -- with a 400 rather than a 404, the status `/api/values`
  gives them. An unknown `station` stays a 404. The server logs these, and a window that ends
  before it starts on any of the three, as an info line, not as an error with its traceback
  (GH-2429)

### Fixed

- MCP: an MCP tool's in-process request to the REST API gets no fastapi server span and no
  `http.server.*` metrics of its own. It started a trace of its own, cut off from the tool call's,
  and counted each tool call a second time. Over `/mcp`, fastapi's operation spans for it now sit
  beneath the tool call's span. The middleware of `opentelemetry-instrumentation-fastapi`, where it
  runs, still records the request (GH-2432)
- On Windows, DWD road values and DWD radar BUFR read with `Settings(read_bufr=True)` decode. Road
  values raised `PermissionError`, and radar logged "Unable to read BUFR file." and left
  `result.df` as `None` (GH-2446)
- `Settings` reads a `null` Frost secret in a `WD_AUTH__METNO_FROST` pair as no secret, and refuses
  any other `null`, `true`, float or object in a `WD_AUTH__METNO_FROST` / `WD_AUTH__CEDA` pair with
  a `ValidationError` naming the element (`auth.ceda.1`; `WD_AUTH__CEDA[1]` in the CLI's
  message). Such an element was taken as the text of its repr, `None` or `True` (GH-2434)
- A `ValidationError` from `Settings` or `Auth` no longer repeats the value it refuses as its
  `input_value`, which for `auth` is a credential; `errors()` still holds it (GH-2435)
- A `file://` target of `to_target`, and of `--target` on `stations`, `values`, `interpolate` and
  `summarize`, reads everything after `file://` as its path, as `alerts` and `history` do:
  `file://out/data.csv` writes `./out/data.csv`, where it wrote `/data.csv` with `out` read as a
  host. `file:///abs/data.csv` is still absolute; a host is now read as a directory, so write
  `file://localhost/abs/data.csv` as `file:///abs/data.csv` (GH-2424)
- NOAA GHCN daily stations QOORNOQ and ARSUK on the coast of Greenland and SORFJORD_KRV and
  SKJOMEN_SLETTJORD by the fjords near Narvik, the four rows listed at -100.0 m, have a null
  `elevation` instead of one 100 m below sea level. Real heights below sea level, such as DEATH
  VALLEY NP's, stay (GH-2418)
- NOAA GHCN hourly station GJBAKKI (`ICM00004919`) in southwestern Iceland, the one row listed at
  -99.0 m, has a null `elevation`. `interpolate` and `summarize` given an elevation moved its air
  temperatures and dew points from about 100 m below sea level; they now leave it out for those,
  as other stations of unknown elevation. Real heights below sea level stay (GH-2377)
- `wetterdienst stripes values` checks `--target`'s suffix against `--format`: `--format=jpg` now
  takes a `.jpeg` target, and a target merely ending in the format's letters, such as `stripespng`
  or `out.xpng`, is refused instead of written without the extension. The refusal names the
  suffixes it takes, `'.png'` where it said `'png'` (GH-2371)
- `Settings` takes an all-digit `WD_AUTH__METNO_FROST` as the Frost client id it is, and refuses a
  `WD_AUTH__CEDA` or `WD_AUTH__METNO_FROST` that is neither text nor a pair, such as `5`, `true` or
  a JSON object, with a `ValidationError` naming `auth.ceda` / `auth.metno_frost`. It raised a
  bare `TypeError` that named nothing, or took a JSON object's keys as the pair (GH-2379)
- A credential assigned to `settings.auth` after construction, such as `settings.auth.knmi = "key"`,
  is held as a secret and checked as one given to the constructor is: a `username:password` text
  for `ceda` is split, and the mask a JSON dump leaves behind is refused. It was kept as plain
  text, which `reveal()` and the providers failed on (GH-2387)
- `wetterdienst issues` reports a refused option, such as `--lead_time` on MOSMIX, as a one-line
  usage error with exit code 2 instead of a traceback with exit code 1. An upstream failure still
  logs its traceback and exits 1 (GH-2368)
- The climate stripes refuse a station that returns no rows, such as one whose data file is
  missing, with `NotEnoughDataError` ("has data for no year"): a 400 from `/api/stripes/values`
  and `/api/stripes/image` and their MCP tools, and that message from `wetterdienst stripes`. They
  raised polars' `ComputeError`, a 500 (GH-2369)
- `wetterdienst history --target file://history.json`, the form its docs show, writes
  `history.json`. The `file://` prefix was kept, so the write went to `file:/history.json` and
  failed with "No such file or directory". A plain path works as before (GH-2370)
- The Docker image reads BUFR: DWD road weather data, and radar BUFR with `read_bufr`. It had the
  eccodes bindings but no ecCodes library behind them; it now installs Debian's, which adds about
  55 MiB. That library is 2.41.0, so the bindings warn on import that 2.42.0 is recommended
  (GH-2409)
- `Settings()` no longer fails where no home directory resolves (HOME unset and the uid missing
  from the password database), which it did with platformdirs 4.12 even with
  `cache_disable=True`. Without `WD_CACHE_DIR` the cache is then kept in a temporary directory, one
  per process and removed at exit, with a warning to set `WD_CACHE_DIR` or `HOME`; a `~` directory
  below the working directory is no longer created with older platformdirs either (GH-2408)
- Reading BUFR (DWD road weather, radar with `read_bufr`) no longer warns "ecCodes 2.42.0 or
  higher is recommended" with an older ecCodes library, such as Debian trixie's 2.41 or Ubuntu
  24.04's 2.34; the version is logged at debug instead. Under `-W error` this advice no longer
  gets BUFR reported as not installed either. To see the advice, import eccodes before wetterdienst
  does. Other warnings still show (GH-2442)
- `wetterdienst history` refuses a `--target` with a scheme other than `file://`, such as
  `s3://bucket/history.json`, as `alerts` does: a usage error with exit code 2 before anything is
  fetched. It ran the whole fetch first and then failed to write the file (GH-2425)

## [0.140.0] - 2026-10-05

### Added

- WSV Pegelonline and Eaufrance Hub'Eau stations name the vertical datum of their `gauge_zero` in
  a new string column `gauge_zero_datum`: Pegelonline's as published (`m. ü. NHN`, `m. ü. NN`,
  ...), Hub'Eau's as the Sandre label of `code_systeme_alti_site` (`IGN 1969`, ...), or the code
  where it has none. Stations differ in it, so compare gauge zeros only where it agrees, and not
  between Hub'Eau stations labelled as on an unknown or a local system (GH-2228)
- `wetterdienst issues`, `/api/issues` and the MCP `issues` tool list the DWD SWSMOS runs, and
  `DwdSwsmosRequest.available_issues(settings)` returns them as UTC datetimes. They refused
  dwd/swsmos as unsupported. One run holds every road station, so the list is the same for any
  station (GH-2319)
- `GET /api/settings` reports the settings `/api/values`, `/api/interpolate` and `/api/summarize`
  take where a request leaves them out: the server's `WD_TS_*` variables over wetterdienst's
  defaults, with the unit of every quantity. With `with_metadata`, those three endpoints' JSON and
  GeoJSON, and their MCP tools', carry a `settings` block next to `metadata`, with the settings the
  result was got with. Their OpenAPI schemas, which declare it, are now named
  `_ValuesWithSettingsDict`, `_ValuesWithSettingsOgcFeatureCollection` and so on (GH-2359)
- `GET /api/settings` takes the settings query parameters of `/api/values`, `/api/interpolate` and
  `/api/summarize`, and answers what they resolve to over the server's, for each endpoint that
  takes the parameter. A value one of them refuses is refused here with its 400 or 422, and an
  unknown parameter is a 422, as on those endpoints. Nothing is stored on the server (GH-2383)

### Changed

- `pydantic-settings` now has a floor of `>=2.14.0` (was `>=2.7.0`): `Settings` reads `.env` with
  its `dotenv_filtering` option, which 2.14.0 added. Upgrade it where it is pinned lower (GH-2349)
- **Breaking**: DWD derived `monthly/soil` returns its monthly totals of potential
  evapotranspiration as the new `evapotranspiration_potential_grass_fao` and
  `evapotranspiration_potential_grass_haude`, where they came as the daily `..._last_24h` names.
  Use the new names for monthly in requests, `parameter` filters, wide-frame columns and
  `ts_geo_station_distance`; daily keeps `..._last_24h` (GH-2042)
- **Breaking**: `/api/stripes/*` and MCP match a stripes `name` at a threshold of 0.8 by default,
  as the CLI and the stations and values requests do; it was 0.9, so a name may now find a station
  where it found none. Pass `name_threshold=0.9` to match as before (GH-2063)
- Climate stripes are coloured over the years asked for: with `start_year` and `end_year`, the
  lowest and highest of them take the ends of the colour map, and `value_scaled` in the CSV of
  `/api/stripes/values` runs from 0 to 1 over the years returned. They were scaled over the
  station's whole record (GH-2063)
- **Breaking**: `/api/stripes/values` and `/api/stripes/image` refuse neither or both of `station`
  and `name`, an `end_year` not after `start_year`, or a `name_threshold` outside 0 to 1 with a 422
  of typed entries, as the other endpoints do, where they answered a 400 with a string `detail`.
  An unknown query parameter is a 422 as well. Match on the entries' `type`: each is located at a
  parameter, but neither `station` nor `name` at `["query"]` alone. `wetterdienst stripes values`
  tells the same refusals in click's terms, with exit status 2 where it was 1 (GH-2060)
- **Breaking**: the REST API and MCP refuse with a 422 a stations, values or history request they
  answered before: one selecting stations in two ways, answered for the first (`station` with
  `name` returned the station alone), and one sending `rank` or `distance` beside anything but a
  point (or `rank` beside `name`), which was ignored. No selection, or half a point or bounding
  box, is a 422 where it was a 400. Each error is located at the parameter it concerns, typed
  `missing_one_of`, `mutually_exclusive`, `missing_with` or `requires`, the others in `ctx`. Send
  exactly one of `all`, `station`, `name`, a point with `rank` or `distance`, a bounding box, or
  `sql`, and drop a `rank` or `distance` left over from a point (GH-2056)
- `wetterdienst` no longer depends on cloup. Each command's `--help` lists its options in one
  list -- what is requested, which stations, then the output -- and ends with examples, and
  `wetterdienst --help` is a short overview rather than a hand-kept copy of every option. The CLI
  takes `--rank` beside `--name`, as the REST API does. A refused request is told in click's own
  terms, a line per problem -- `Missing option '--longitude'`, `Options '--station' and '--name'
  cannot be used together`, `Invalid value for '--distance'` with the value refused -- instead of
  pydantic's echo of every option given (GH-2056)
- **Breaking**: `DwdDmoRequest.available_issues` lists the runs of `lead_time="short"` by default,
  as its docstring said and a default request reads; it listed every lead time, so `wetterdienst
  issues` and `/api/issues` named runs the default `values` request rejected with `IndexError`.
  Pass `lead_time="long"` (`--lead_time long`) for the long runs, or `lead_time=None` in Python
  for every lead time together (GH-2009)
- **Breaking**: DWD DMO refuses the values of a request naming a parameter its lead time's run does
  not carry with `ParameterNotCarriedError`, a `ValueError` naming the lead time that does, where
  the parameter answered with an empty frame: `icon`'s four 3-hourly parameters under the default
  `lead_time="short"`, its three 1-hourly ones under `"long"`. The REST API answers 400. Ask for
  them with the lead time named, apart from any parameter only the other lead time carries; a
  request for a whole dataset is not refused (GH-1976)
- **Breaking**: `cloud_cover_below_1000ft` is `cloud_cover_below_2km`. It is DWD's `nl` in
  `dwd/mosmix` and `dwd/dmo`, low cloud below 2 km, which the old name and its glossary entry put
  at 1000 ft. Request the new name; the old one in a request, as a `ts_geo_station_distance` key or
  as a wide column in a SQL filter is reported with its replacement. A wide DuckDB, SQLite or
  PostgreSQL table `to_target` wrote before takes no append of it: write it anew (GH-1977)
- **Breaking**: `imgw/meteorology` `daily/precipitation` returns `precipitation_amount` as 0 mm,
  with `quality` 11, for a day the file leaves out of a month the station reports in; such a day
  was missing. Drop `quality` 11 to get the rows as before. Other parameters and datasets are
  unchanged (GH-2000)
- **Breaking**: Eaufrance Hub'Eau stations list the altitude of the gauge's zero, in metres, as
  `gauge_zero`, as WSV Pegelonline does; it was listed as `elevation`. Read `gauge_zero` for it
  (GH-2020)
- Each station history gives the `resolution` and `dataset` it belongs to beside its `station_id`,
  whichever `sections` are asked for. DWD observation answers up to one history per station and
  dataset, and a request for several datasets left them to be told apart by the records inside
  (GH-2224)
- **Breaking**: the `postgresql` extra installs psycopg 3 instead of psycopg2, and a bare
  `postgresql://` target writes through psycopg 3 whenever it is installed, on every SQLAlchemy
  version; under 2.1 it failed with `No module named 'psycopg'`. `postgresql` and `mysql` bring
  SQLAlchemy and pandas, so neither needs `export` beside it. For `postgresql+psycopg2://`,
  install `psycopg2-binary` yourself; the Docker image has psycopg 3 only, so drop `+psycopg2`
  there (GH-2202)
- Eaufrance Hub'Eau stations list as `elevation` the altitude of their site, `altitude_site` from
  Hub'Eau's sites referential, in metres. It is null where the site gives none, gives 0, or gives
  one below -10 m or from 4810 m up, and for every station when that referential cannot be read,
  which is logged as a warning. About three stations in four have one (GH-2223)
- **Breaking**: `/api/values`, `/api/interpolate`, `/api/summarize` and their MCP tools answer a
  failure on the server's or the data source's side with a 500 carrying its message, where values
  answered 400 and the other two 404. Retry or report a 500 rather than rephrasing. A request
  refused for what it asks keeps its 400 or 404. Those refusals that raised a bare `ValueError` or
  `IndexError` raise a subclass of it: `InvalidTimeIntervalError`, `InvalidEnumerationError`, or
  the new `InvalidBoundingBoxError`, `LocationOutOfRangeError` and `IssueNotFoundError`. Catch
  `InvalidTimeIntervalError` for the day `9999-12-31`, which raised `OverflowError`, and
  `LocationOutOfRangeError` for a point outside UTM, which raised `utm.error.OutOfRangeError`
  (GH-2252)
- **Breaking**: `/api/stations`, `/api/history`, `/api/issues`, the `/api/stripes` endpoints and
  their MCP tools answer a failure on the server's or the data source's side to read what was asked
  for with a 500 carrying its message, where they answered 400, as `/api/values` does. Retry or
  report a 500 rather than rephrasing. A request refused for what it asks keeps its 400 (GH-2276)
- **Breaking**: `/api/alerts` and its MCP tool answer a failure to list, download or read DWD's CAP
  feed with a 500 carrying its message, where they answered 400. Retry or report a 500 rather than
  rephrasing; a `date` that does not parse or lies before DWD's rolling window keeps its 400, and
  one an offset carries past a datetime's range is a 400 where it was a 500.
  `DwdWeatherAlertRequest.query()` raises a date before the window as `InvalidTimeIntervalError`,
  still a `ValueError`, and a listing without any snapshot as `FileNotFoundError` (GH-2294)
- The `mysql` extra takes pandas 3, as the other extras that bring pandas do. It asked for pandas
  below 3, so installing it downgraded an environment on pandas 3 to 2.x (GH-2250)
- DWD DMO's coverage, from `discover`, `/api/coverage`, the CLI and MCP, gives each parameter
  `lead_times`: the lead times whose run carries it, such as `["long"]` for `icon`'s
  `precipitation_amount_last_3h` and `["short"]` for every `icon_eu` parameter. A caller can offer
  only what the `lead_time` it sends will answer; the other keys are as they were (GH-2256)
- **Breaking**: a dict given as `fsspec_client_kwargs` or `WD_FSSPEC_CLIENT_KWARGS` is merged into
  the defaults, `headers` one level deep, where it replaced them, so the docs' proxy example
  `{"trust_env": True}` no longer drops the 30 s timeout and the User-Agent. A key given still wins:
  give `"timeout": None` for aiohttp's own timeout, which a dict without one used to get, and a
  `User-Agent` header of your own to send that instead of wetterdienst's (GH-2269)
- **Breaking**: the InfluxDB sinks read a target as the SQL sinks' SQLAlchemy does: the password
  ends at the first `@`, and the username, password and database are percent-decoded, as the
  CrateDB database (its schema) now is too. Write an `@` in an InfluxDB org, password or token as
  `%40`, and a literal `%` followed by two hex digits there or in an InfluxDB database or CrateDB
  schema as `%25`. An `@` in the path or query of an InfluxDB or CrateDB target with a `host:port`
  is read as ending a password too; write it as `%40` there (GH-2248)
- **Breaking**: the InfluxDB 3 sink connects with the scheme and port its target names:
  `influxdb3://` is http and `influxdb3s://` https, on the target's port or, with none, 8181 (an
  InfluxDB 3 Core's) for http and 443 for https. It took only the host and went to https on 443
  whatever the target said, so a local InfluxDB 3 Core could not be reached. Write an https
  server, such as InfluxDB Cloud, as `influxdb3s://` (GH-2279)
- **Breaking**: `Settings` refuses a `ts_skip_threshold` outside (0, 1], as `--skip_threshold`
  does. One above 1, as `WD_TS_SKIP_THRESHOLD=5`, skipped every station under `ts_skip_empty`, and
  `values` said "No data available" with no hint at the setting. Such a variable, or one of 0, now
  fails every `Settings()`; correct or remove it. `/api/values` answers a `skip_threshold` of 0
  with a 422, and the MCP `values` tool refuses it; to skip no station, leave `skip_empty` off
  (GH-2334)
- **Breaking**: DWD SWSMOS raises `IssueNotFoundError` for an `issue` naming a run DWD does not
  hold, as MOSMIX and DMO do, so the REST API answers it as the caller's error. It returned no rows,
  as if the run held nothing for the station. Catch `IssueNotFoundError`, or pick the issue from
  `DwdSwsmosRequest.available_issues` (GH-2324)
- A NOAA GHCN station asked for at both `hourly` and `daily` has the daily list's `elevation` on
  its hourly row as well, where the two lists put it within 5 km of each other, unless the daily
  list gives 0.0 against an hourly height. Interpolate and summarize, by station id or by point,
  then use one elevation for such a station whatever the order of the parameters. Otherwise each
  row keeps its own list's elevation. A request for one resolution is not affected by this
  (GH-2336, GH-2362)
- Locked dependencies refreshed within their declared ranges -- 21 packages, among them
  duckdb 1.5.6, platformdirs 4.12.2, and SQLAlchemy 2.1.2 and xarray 2026.9 on Python 3.11 and
  later; 3.10 keeps the release lines that still support it (GH-2403)

### Deprecated

- `summarize`'s `use_nearby_station_distance` (the CLI's `--use_nearby_station_distance`,
  `/api/summarize` and the MCP `summarize` tool) is deprecated and will be removed in a future
  release. It never had an effect on a summary; leave it out. The CLI warns when it is given, the
  REST API logs it, and the schema marks it deprecated. The setting
  `ts_geo_use_nearby_station_distance` stays, for interpolation (GH-2333)

### Fixed

- `Settings` ignores a key of `.env` that is no setting, such as another program's
  `POSTGRES_PASSWORD`, as it ignores one in the environment. Such a key made every `Settings()`
  fail with its value in the error, and the CLI commands and the REST API that read the settings
  refused to run. A `WD_*` key that names no setting, such as the misspelt `WD_CACHE_DIABLE`, is
  ignored too, as in the environment. A keyword to `Settings(...)` that is no setting is still
  refused (GH-2349)
- `Settings` no longer takes a `.env` key without the `WD_` prefix for the setting it names, as it
  did with pydantic-settings older than 2.11, which the `>=2.7.0` floor allowed: another program's
  `CACHE_DIR` or `TS_SHAPE` set wetterdienst's cache directory or result shape (GH-2373)
- `Settings` refuses a non-empty `ts_geo_station_distance` or
  `ts_geo_station_distance_resolution_factors` that is not a mapping, such as
  `WD_TS_GEO_STATION_DISTANCE=5`, with a `ValidationError` naming the setting, where it raised a
  bare `TypeError` that named nothing (GH-2353)
- Climate stripes values and images (CLI `stripes values`, `/api/stripes/values`,
  `/api/stripes/image`, MCP `stripes_values` and `stripes_image`) no longer fail under
  `WD_TS_SHAPE=wide`, which raised `ColumnNotFoundError`, or under `WD_TS_SKIP_EMPTY=true`, which
  raised a `ComputeError` for a station with gaps in its record. They read the values long and
  unskipped whatever those two say (GH-2348)
- `wetterdienst issues --dataset/--lead_time`, and the `/api/issues` and MCP `issues` descriptions
  of `dataset` and `lead_time`, said other networks ignore them. They are DWD DMO only, and MOSMIX
  and SWSMOS refuse them, so leave them out there (GH-2347)
- Interpolate and summarize answer under `ts_humanize=False` and `ts_shape="wide"`, however they
  are set: `Settings`, `WD_*`, the CLI's or REST API's `humanize`. The first returned no data and
  the second raised `ColumnNotFoundError`. The result is long either way, its parameters named by
  the source's codes under `ts_humanize=False` (GH-2331)
- The `/api/values` description, which is the MCP `values` tool's, and the MCP instructions said
  the `values` array is sorted by timestamp. It is grouped by station, then by resolution, dataset
  and parameter, in timestamp order within each group, so a parameter's latest timestamp is the
  last of its group. The description now also says what a wide item and a GeoJSON response hold
  (GH-2295)
- Values: a station asked for several datasets is no longer skipped when one dataset has no
  `start_date` in the station list and another starts after `end_date`. With NOAA GHCN `hourly`
  and `daily` together, such a station returned no hourly values inside the window (GH-2292)
- Interpolation and summary take a station's elevation from another requested resolution's row
  where the first row they read gives none. With NOAA GHCN `hourly` named before `daily`, the
  `..._by_station_id` methods answered without the elevation of 859 stations the hourly list gives
  none for (6 the other way round), and an answer at an elevation could leave such stations out
  (GH-2300)
- `/api/values` and its MCP tool answer `unit_targets` naming a quantity the converter does not
  have, such as `{"foo": "bar"}`, with a 400 saying so, where they answered a bare 500 (GH-2272)
- `/api/interpolate`, `/api/summarize`, `/api/alerts` and their MCP tools answer a malformed `WD_*`
  setting in the server's `.env` with a bare 500, where they answered 400 with the setting's value
  in `detail`; `/api/stations`, `/api/history` and `/api/issues` no longer give the value in their
  500. A request refused for what it gives keeps its 400 (GH-2297)
- `wetterdienst values` refuses such `--unit_targets` with `Invalid value for '--unit_targets'`
  and exit status 2, where it died with a traceback (GH-2296)
- `Settings` refuses a `ts_unit_targets` unit the converter does not have for its quantity, such as
  `{"temperature": "furlong"}`, or one only a source publishes in. It was refused once the stations
  had been fetched, so the CLI died with a traceback; `values`, `interpolate` and `summarize` now
  exit with status 2, and `/api/interpolate` and `/api/summarize` answer 400 where they answered
  404. Such a unit in `WD_TS_UNIT_TARGETS` now fails every `Settings()`, as an unknown quantity
  there does, where it broke only values requests: set when the REST server starts, it stops it at
  import; set in `.env` later, requests answer 500. Correct or remove it. An unknown quantity's
  refusal names only the unknown ones (GH-2306)
- `/api/values` answers a malformed `WD_TS_UNIT_TARGETS` in the server's `.env` with a bare 500,
  where it answered 400 with the setting's value in `detail`; `/api/stripes/stations`, `/values`
  and `/image` no longer give a malformed setting's value in their 500. The MCP tools answer the
  same (GH-2312)
- Interpolation places stations across a UTM zone boundary (in Germany at 6 and 12 deg E, most
  places every 6 deg of longitude) or the equator in the zone of the point. Each was placed in its
  own zone, hundreds of kilometres off, or 10000 km off across the equator, so a point near either
  got no value, or one weighted as if those stations stood elsewhere. A station beyond 80 deg S or
  84 deg N, where UTM ends, is now left out; it failed the whole interpolation. The
  `interpolation` extra needs utm 0.8 or later, the first to keep the point's hemisphere (GH-2277)
- Network: a download that keeps arriving no longer fails with `FSTimeoutError` once it runs past
  the `timeout` in `fsspec_client_kwargs` (30 s by default), so a slow link can fetch large files.
  A number there now bounds each wait, to connect and for the next bytes of the answer, not the
  whole request. The settings docs give that default, where they listed `{}` (GH-2258)
- Eaufrance Hub'Eau stations are listed when the station referential takes more than 30 seconds
  to arrive, which it often does; the list failed with `FSTimeoutError`. The referential now has
  the 120 seconds the observations requests have (GH-2221)
- `to_target` and the CLI's `--target` log the target with its password as `***`. They logged it
  verbatim at INFO, which the CLI shows by default, so a database password or the InfluxDB 2/3 API
  token in the password slot reached stderr and any log it was captured in (GH-2219)
- A `/`, `?` or `#` in the password of an InfluxDB or CrateDB target, or a `?` or `#` in a SQL one,
  is read as part of it. It was read as the end of the host part, so the export went to the wrong
  host, port, database or table, and pieces of the password reached the log. A password whose
  unencoded `@` cannot be read is refused with `ExportRefusedError`, naming none of it (GH-2248)
- DWD derived can be used on a base install. Its station lists were read with pandas, so
  `Wetterdienst("dwd", "derived")` failed with an `ImportError` unless an extra that brings pandas,
  such as `export`, was installed. They are read with polars now, with the same result (GH-2213)
- Precipitation stripes colour dry years brown and wet years teal; they were the other way round.
  A year range holding fewer than two years with data is refused, where one beyond the station's
  record answered with no values and an empty image, and stripes start and end at a year with data.
  Years all of one value take the middle colour rather than none (GH-2063)
- Images are sent as `image/jpeg`, `image/svg+xml` and `application/pdf`, where charts and stripes
  were sent as `image/jpg` and `image/svg`, and stripes as `image/pdf` (GH-2063)
- DWD DMO returns in metres the elevation of 32 `F9` stations that DWD gives in feet: `F9051`
  QUERETARO/GUTIERREZ is at 1919 m, not 6296 m. A warning names such a station once DWD gives it
  another value. An elevation in a run that is not a number is returned as null; it previously
  failed the whole station list (GH-2017)
- `interpolate` and `summarize` estimate for a point on the equator or the prime meridian. A
  latitude or longitude of 0 was taken for no point at all, and the request failed with "Either
  latitude and longitude or station must be provided" (GH-2056)
- `wetterdienst about fields` applies `--debug`, and for any network but DWD observation answers
  with a usage error naming the one it describes; it ended in an `AttributeError` traceback
  (GH-2056)
- `wetterdienst radar --wmo_code` finds the site it names. The option was read as text and compared
  with the sites' integer WMO codes, so every lookup failed with a `KeyError` traceback. A code no
  site carries now answers `Error: Radar site not found` and exit status 1, and an ODIM code of the
  wrong length is a usage error rather than a traceback (GH-2023)
- `wetterdienst history --sections` returns only the sections it names; it returned all five. The
  REST API filtered already but in a random order, and both now keep the history's own order. A
  section name the history does not have is a usage error rather than a traceback, as is a request
  with neither `--all` nor `--station` (GH-2022)
- `wetterdienst --help` and the command help name only options and commands that exist:
  `--convert_units` for `--si_units`, no `--tidy`, `--wmo_code` and `--country_name` for `radar`,
  and `stripes values` for `warming_stripes`, the command's old name. `--convert_units` converts to
  the unit targets, not to SI units: temperature stays in °C by default. The overview that listed
  options under commands that do not take them is gone, the `--sql_values` example on a column
  runs in the wide shape it needs, and the README counts nearly 600 parameters, not 514 (GH-2021)
- DWD observation history gives the station id zero-padded in its `parameter`, `device` and
  `geography` sections, `01048` as in `name`, `missing_data` and the stations and values frames.
  They gave `1048`, so joining them with those frames on `station_id` found nothing. Each history
  also gives its station's `station_id` beside the sections, whichever `sections` are asked for, so
  one whose sections hold no records still names its station (GH-2058)
- Values converted to a much larger unit keep their precision. Every converted value was rounded to
  four decimals, so with `WD_TS_UNIT_TARGETS='{"length_short": "mile"}'` 5 cm of snow came back as
  `0.0`. A conversion now keeps one more decimal per order of magnitude it shrinks a value by, so
  under the default targets a reading published in percent, Pa, mm, kJ/m² or l/s can carry up to
  three more decimals where its source gives them (GH-2002)
- `interpolate` and `summarize` round a value as `values` rounds a converted reading of the same
  parameter, where they rounded every value to two decimals: with
  `WD_TS_UNIT_TARGETS='{"length_short": "mile"}'` a summarized 5 cm of snow came back as `0.0`, and
  a cloud cover of 0.875 as 0.88. Values are rounded to four decimals or more, so an interpolated
  6.64 °C now reads 6.6422; `distance` and `distance_mean` keep two (GH-2225)
- With `WD_TS_CONVERT_UNITS=false`, `interpolate` and `summarize` no longer round away a reading
  published in mm/s: `dwd/road` publishes 0.1 mm/h of precipitation intensity as 0.0000278 mm/s,
  which came back as `0.0`. A value is now rounded as one converted into its source unit from its
  target unit would be, so the decimals follow `WD_TS_UNIT_TARGETS` even though nothing is
  converted. Under the default targets mm/s keeps seven, as do durations in hours and visibility in
  km, durations in minutes, kPa and depths in metres keep five or six, and every other unit four
  (GH-2257)
- PostgreSQL and MySQL export targets no longer fail on `?table=`: it names the table and is no
  longer passed to the database driver, which refused it as a connection option, so no such target
  could be written to. The rest of the query, such as `sslmode` or `charset`, still reaches the
  driver (GH-1974)
- On Windows, a request that downloads many files at once with a cache no longer fails with
  `PermissionError: [Errno 13]` when two of its download threads read and replace the cache's
  metadata file at the same time; the threads of one process now take turns. Two processes
  sharing a cache directory can still meet that way (GH-1990)
- DWD DMO dates each run as the latest date on or before now that its `DDHHMM` stamp can name.
  Between the 1st's 00 UTC run appearing (about 03:10 UTC) and 04:01, every run was a month early:
  `available_issues` listed past issues and `values` for the newest issue raised `IndexError`. On
  1 January, April, June, August and November it named days the month lacks, such as 31 November,
  so `available_issues` and `values` raised `InvalidOperationError` and the station list lost the
  stations only a run describes (GH-2203)
- The REST API's OpenAPI schema types a station's `elevation`, `latitude`, `longitude` and `name`
  as nullable, and declares that a station may carry the columns its provider adds, such as
  `gauge_zero`, so a client generated from it keeps them. MCP tools no longer fail output
  validation on a station row holding such a null, as every WSV station does (GH-2226)
- GeoJSON of stations and values gives a station without an elevation the position `[lon, lat]`;
  it was `[lon, lat, null]`, which strict GeoJSON parsers reject. One collection can now hold both
  lengths, so read an elevation from a third number only where there is one. Each feature's
  `properties` also carry the station columns a provider adds, such as WSV's `gauge_zero` and
  characteristic values, DWD road's station group and road columns, and the `icao_id` of DWD
  MOSMIX, DMO and POI (GH-2222)
- DWD observation history no longer fails for a station whose name holds a non-ASCII letter, such
  as 01684 Görlitz: its missing-data file is read as latin-1, as DWD writes it, where it raised
  `UnicodeDecodeError` and `/api/history` answered 400 (GH-2214)
- `/api/values` answers a `ValueError` raised while reading a provider's values with a 400
  carrying its message, where it answered a 500 with none, and the MCP `values` tool, which calls
  it, now passes the message on. `wetterdienst values` still logs it and exits 1 (GH-2218)
- MySQL and MariaDB export targets create `DATETIME` columns holding UTC, so values before 1970
  can be written. Their `TIMESTAMP` columns started in 1970, so the first earlier row was refused or
  stored as zeros. A table created by an earlier version keeps its `TIMESTAMP` columns and what
  they stored; to get `DATETIME`, write it anew with `if_exists='replace'`, which drops every row
  it held (GH-2229)
- SQL Server export targets (`mssql://`) create `DATETIME2` columns holding UTC for datetimes.
  They created `timestamp` columns, which SQL Server takes as `rowversion`, a row counter that
  refuses any value written to it (GH-2249)
- GeoJSON of values gives each feature, one per dataset of a station, that dataset's values only,
  and no feature to a dataset the station returned no values for; each feature carried the values
  of every dataset, so each value appeared once per dataset (GH-2253)
- GeoJSON of values in the wide shape gives a station one feature per resolution into which
  several requested datasets were merged, with `dataset` null as its rows have it, and dates from
  the earliest start to the latest end of those datasets. Each merged dataset got a feature holding
  all of the rows, so each value appeared once per dataset. Read a value's dataset from its column
  prefix; the REST API's schema types `dataset` as nullable (GH-2274)
- The MCP `values` tool answers with GeoJSON and in the wide shape; it failed its own output
  validation. The REST API's schema for `/api/values` gives a GeoJSON feature's values no
  `station_id`, which the feature's properties carry, and a wide row `resolution`, a nullable
  `dataset`, `timestamp` and, outside GeoJSON, `station_id`, plus a value and a quality column per
  parameter, typed as nullable numbers where pydantic is 2.12 or later (GH-2282)
- GeoJSON of stations and values gives a station without a latitude or longitude, such as a
  postcode of DWD derived `monthly/climate_correction_factor`, the geometry `null`, as RFC 7946
  has an unlocated feature; it was a `Point` of null coordinates, which strict parsers reject. The
  REST API's schema types `geometry` as nullable, so check for `null` before reading it (GH-2241)
- DWD derived stations at 1000 m or higher keep the first digit of their elevation and their
  `end_date`: Brocken was listed at 135 m and Zugspitze at 956 m, both with a null `end_date`.
  This affects the monthly degree-day and degree-hour datasets and hourly `radiation_global` and
  `sunshine_duration` (GH-2234)
- NOAA GHCN daily stations without a known elevation have a null `elevation`. They were listed at
  -999.9 m, the station list's missing value, and `interpolate` and `summarize` given an elevation
  took it for a known one (GH-2247)
- NOAA GHCN hourly stations without a known elevation have a null `elevation` too. They were
  listed at -999.9 m, the station list's missing value (GH-2260)
- NOAA GHCN stations asked for both `hourly` and `daily` in one request are listed; the request
  failed with a polars schema error. The hourly stations have a null `start_date` and `end_date`,
  as their station list gives none (GH-2267)
- DWD MOSMIX takes an `issue` given without an offset as UTC, as DWD DMO does, and converts one
  with an offset to UTC before flooring it to a run. A naive issue was read in the server's local
  time, and an offset one floored in its own hours, so a published run could go unfound. The
  request's `issue` is now a UTC datetime; compare it with aware datetimes (GH-2275)
- DWD SWSMOS converts an `issue` given with an offset to UTC before flooring it to a run, as DWD
  MOSMIX and DMO do. It kept the issue's wall-clock hour and relabelled it UTC, so
  `2026-10-01T13:00+02:00` read the 13 UTC run rather than the 11 UTC one it names (GH-2288)
- The InfluxDB 2 sink reaches an IPv6 host, such as `influxdb2://acme:tok@[::1]:8086/`. It dropped
  the brackets and sent `http://::1:8086`, which names no valid host (GH-2279)
- The InfluxDB 1 sink reaches an IPv6 host, such as `influxdb://root:pw@[::1]:8086/`. It dropped
  the brackets, so its client's base URL was `http://::1:8086`, which names no valid host (GH-2287)
- DWD SWSMOS reads the run an `issue` names when asked through the CLI (`--issue`), the REST API or
  MCP. The issue was dropped on the way, so the latest run was read whatever was asked. An `issue`
  that is no ISO date raises `InvalidTimeIntervalError`, a `ValueError`, as MOSMIX and DMO do, so
  the REST API refuses it as the caller's error, as it does theirs (GH-2299)
- `wetterdienst alerts` reports a DWD feed it cannot read as an error with exit status 1, as it does
  a failed download, where it reported an invalid option with exit status 2. A `--date` before
  DWD's rolling window is still a usage error, now named as `Invalid value for --date` (GH-2313)
- The CLI's `values`, `interpolate` and `summarize` leave a setting whose option is not given on
  the command line to its `WD_TS_*` variable, such as `WD_TS_SHAPE=wide`. They passed every
  option's default, which outranks the environment, so those variables had no effect (GH-2307)
- The CLI's `interpolate` and `summarize` refuse a bad station distance or unit target in one line
  naming its option, as `values` does, where they printed pydantic's whole message. All three raise
  a malformed `WD_*` variable as it is rather than as a usage error, also one merged into the dict
  an option gives, such as `WD_TS_UNIT_TARGETS` beside `--unit_targets` (GH-2308)
- `WD_TS_GEO_USE_NEARBY_STATION_DISTANCE`, `WD_TS_GEO_MIN_GAIN_OF_VALUE_PAIRS` and
  `WD_TS_GEO_NUM_ADDITIONAL_STATIONS` can be set from the environment or `.env`. The settings
  refused the string an environment variable gives, so setting any of them made every `Settings`
  fail (GH-2326)
- The REST API's and MCP's `values`, `interpolate` and `summarize` leave a setting the request does
  not give to the server's `WD_TS_*` variable, such as `WD_TS_SHAPE=wide`, as the CLI does, where
  those variables had no effect. A client that parses one layout whatever the server sets sends
  `shape`, `humanize` and `convert_units` with its request (GH-2325)
- The REST API refuses a bad `unit_targets` or station distance in one line naming its field and
  quoting what the request gave, where the 400 was pydantic's whole message quoting the dict merged
  from it and the server's `WD_TS_UNIT_TARGETS` or `WD_TS_GEO_STATION_DISTANCE` entries (GH-2329)
- A malformed `WD_*` setting is told by the variable that sets it and what is wrong with it, a
  line each and without pydantic's echo of the value, where it ended in pydantic's traceback. The
  REST API refuses to start with it, also under `uvicorn` directly unless its lifespan is turned
  off, and `wetterdienst restapi` exits with uvicorn's status 3; the other CLI commands that read
  the settings exit with status 1 (GH-2335)
- Values in the wide shape can be drawn: `ValuesResult.to_plot`, and with it the image formats
  (`html`, `png`, `jpg`, `webp`, `svg`, `pdf`) of the CLI's `values` and `/api/values`, draw a wide
  result as they draw the long one. They raised `ColumnNotFoundError` on `parameter` (GH-2330)
- `wetterdienst alerts` refuses a `--date` that does not parse, or that an offset carries out of a
  datetime's range, as `Invalid value for --date` with exit status 2; the latter was a traceback.
  It raises a malformed `WD_*` variable as it is rather than as an invalid option, as `values`
  does, and a `--target` it cannot write is an error with exit status 1, not a traceback (GH-2322)
- NOAA GHCN hourly stations listed at 9999.0 m or 8191.0 m, 154 placeholders such as the North
  Sea lightship ELBE NO. 1, have a null `elevation`. `interpolate` and `summarize` given an
  elevation took them for known ones (GH-2336)
- `wetterdienst history` and `wetterdienst stripes values` end a `--target` they cannot write,
  such as one in a directory that does not exist, as `Error: Could not write --target: ...` with
  exit status 1, as `alerts` does; it was a traceback after the whole fetch (GH-2346)
- NOAA GHCN daily stations of the Brazilian network (`BR0...`) listed at 0.0 m, 912 placeholders
  such as ALFENAS at about 880 m, have a null `elevation`. `interpolate` and `summarize` given an
  elevation took them for stations at sea level. A 0.0 m outside that network stays (GH-2362)
- NOAA GHCN hourly stations listed at -999.0 m, 93 placeholders such as BOGUS ALGERIAN, have a
  null `elevation`. `interpolate` and `summarize` given an elevation took them for known ones
  (GH-2352)
- A `Settings` field assigned after construction is validated as one given to the constructor:
  `settings.ts_skip_threshold = 5` or `settings.ts_shape = "foo"` raises a `ValidationError` naming
  the field, where it was taken and failed later or skipped every station. A radius assigned
  reaches `ts_geo_station_distance` at once, and a dict assigned to `fsspec_client_kwargs` is
  merged into the defaults as one given is, where it replaced them (GH-2342)
- NOAA GHCN hourly stations listed at 0.0, 0.0, or named `BOGUS ...`, 15 placeholders such as
  BOGUS AUSTRIAN, have a null `latitude` and `longitude`. They are still fetched by id, but no
  rank, distance or bbox search, `interpolate` or `summarize` picks them. A rank search now leaves
  out every station without a position, which it sorted first, ahead of the nearest; estimating
  at one by station id is refused with a `LocationOutOfRangeError`. The CLI prints that error in
  one line, also for a point beyond the latitudes UTM covers, where it was a traceback (GH-2380)
- A `Settings` once in the wide shape drops nulls again once it is long. The wide shape wrote
  False into `ts_drop_nulls` for good, so a `Settings` reused for a long request returned the
  null rows. The field now keeps the value given, so `Settings(ts_shape="wide").ts_drop_nulls`
  reads True; read `ts_drop_nulls_effective` for whether nulls are dropped (GH-2388)
- The REST API's OpenAPI schema, and the MCP tools built from it, give each settings parameter of
  `/api/values`, `/api/interpolate`, `/api/summarize` and `/api/settings` the server's value as
  its default: with `WD_TS_SHAPE=wide`, `shape` is `wide`. `drop_nulls` is `WD_TS_DROP_NULLS` or
  true, what leaving it out means whatever the shape. They gave wetterdienst's, which a client
  filling in defaults sent, hiding the server's. Read once per server process: restart it after
  editing its `.env` (GH-2393)

### Security

- **Breaking**: the `sql` and `sql_values` filters run on a DuckDB connection holding only the
  frame, so they raise a `duckdb.Error` on a table of DuckDB's default connection, a file, a URL
  or an extension; join or filter the returned frame with polars instead. The clause is a single
  condition: a statement after `;`, `ORDER BY` or `LIMIT` raises `duckdb.ParserException`; sort or
  slice the returned frame instead. It runs on one thread, with DuckDB's memory limit at 1 GiB
  plus the frame's size and no disk to spill to (`duckdb.OutOfMemoryException`). The REST API
  answers these as client errors. Any REST or MCP client could read the server's files, read
  DuckDB's settings through an appended statement, or run a query on every core with most of the
  memory (GHSA-rpwr-qmm5-m9wp)
- **Breaking**: the REST API and MCP server refuse `sql` (stations, values) and `sql_values`
  (values, interpolate, summarize) with a 403 unless they run with the new setting `restapi_sql`
  enabled; set `WD_RESTAPI_SQL=true` to accept them as before. Enabled, the clause runs in DuckDB
  on the server within the limits above, which hold per request: it can still read DuckDB's
  settings, which name paths on the server, run for as long as it likes on one thread, and
  allocate memory DuckDB's limit does not count. The library and the CLI are not gated
  (GHSA-rpwr-qmm5-m9wp)

## [0.139.0] - 2026-09-29

### Changed

- **Breaking**: the station column `height` is now `elevation`, in every stations frame and its
  JSON, CSV and `with_stations` output. History's `station_height` is `station_elevation`, the DWD
  radar BUFR frame's `height` is `elevation`, and `NoStationsWithHeightError` is
  `NoStationsWithElevationError`. Read `elevation` instead; a SQL filter still naming `height` fails
  with an error naming `elevation`. A DuckDB, SQLite or PostgreSQL table `to_target` wrote before
  takes no append of `elevation`: write it anew (GH-2024)
- **Breaking**: the station column `state` is now `region`, in every stations frame and its JSON,
  CSV, GeoJSON and `with_stations` output. Read `region` instead; a SQL filter still naming `state`
  fails with an error naming `region`. A DuckDB, SQLite or PostgreSQL table `to_target` wrote before
  takes no append of `region`: write it anew (GH-2026)
- **Breaking**: the values column `date` is now `timestamp`, in long and wide values, interpolated
  and summarized values, their JSON, CSV, GeoJSON, NetCDF and Zarr output, the stripes values and
  the DWD radar BUFR frame. The `date` request parameter, `filter_by_date` and the station columns
  `start_date`/`end_date` keep their names. Read `timestamp` instead; a SQL filter on values still
  naming `date` fails with an error naming `timestamp`. A DuckDB, SQLite or PostgreSQL table
  `to_target` wrote before takes no append of `timestamp`: write it anew (GH-2028)
- **Breaking**: in wide values, each parameter's quality column is `<parameter>_quality` rather than
  `qn_<parameter>` (`<dataset>_<parameter>_quality` where several datasets are requested). Read the
  new name instead; a SQL filter still naming a `qn_` column fails with an error naming its
  `_quality` successor. A DuckDB, SQLite or PostgreSQL table `to_target` wrote before takes no
  append of the new columns: write it anew (GH-2030)
- **Breaking**: 31 parameter names lose a misspelling, a German word or a mistranslation: `gras` is
  `grass`, `chlorid` `chloride`, `loamysilt`/`loamysand`/`winterwheat` are split into words,
  `count_weather_type_ripe` is `count_weather_type_hoar_frost`, `thawing_thickness_plantstock*` is
  `thawing_thickness_plant_cover*`, `wave_height_sign` is `wave_height_significant`,
  `thawing_thickness_bare*` is `thawing_thickness_bare_ground*`, `number_of_{days,hours}_per_month`
  are `count_{days,hours}_in_month`, `wind_movement_24h` is `wind_movement`, and
  `cloud_cover_between_2km_to_7km` is `cloud_cover_between_2km_and_7km`. Request the new name; an
  old one in a request, or as a wide column in a SQL filter, is reported with its replacement. A
  wide DuckDB, SQLite or PostgreSQL table `to_target` wrote before takes no append of them
  (GH-2032)
- **Breaking**: `dwd/observation` `snow_depth_excelled` and `water_equivalent_snow_depth_excelled`
  are `snow_depth_sampled` and `water_equivalent_snow_depth_sampled`. They are DWD's *ausgestochene
  Schneehöhe*, the snow cut out as a sample to measure its water equivalent; their descriptions and
  app labels said snow beyond the measuring range, which neither is. Request the new names; an old
  one in a request, or as a wide column in a SQL filter, is reported with its replacement. A wide
  DuckDB, SQLite or PostgreSQL table `to_target` wrote before takes no append of them (GH-2034)
- **Breaking**: `humidity`, `humidity_max` and `humidity_min` are `humidity_relative`,
  `humidity_relative_max` and `humidity_relative_min`; `humidity_absolute` is unchanged. Request the
  new names; an old one in a request, as a `ts_geo_station_distance` key or as a wide column in a
  SQL filter is reported with its replacement. A wide DuckDB, SQLite or PostgreSQL table
  `to_target` wrote before takes no append of them (GH-2036)
- **Breaking**: every parameter name containing `precipitation_height` or `evaporation_height` says
  `precipitation_amount` or `evaporation_amount` instead -- 66 names, from `precipitation_height`
  itself to `count_days_precipitation_height_ge_1mm` and `evaporation_height_multiday`. Request
  the new names; an old one in a request, as a `ts_geo_station_distance` key or as a wide column in
  a SQL filter is reported with its replacement. A wide DuckDB, SQLite or PostgreSQL table
  `to_target` wrote before -- a nightly `daily/kl` export, say -- takes no append of them (GH-2038)
- **Breaking**: `visibility_range`, `visibility_range_index` and
  `visibility_range_measurement_method` are `visibility`, `visibility_index` and
  `visibility_measurement_method`. Request the new names; an old one in a request, as a
  `ts_geo_station_distance` key or as a wide column in a SQL filter is reported with its
  replacement. A wide DuckDB, SQLite or PostgreSQL table `to_target` wrote before takes no append
  of them (GH-2040)
- Locked dependencies refreshed to their latest compatible versions -- 41 packages, among them
  fastmcp 4.0.10, fsspec 2026.9, SQLAlchemy 2.1 on Python 3.11 and later and zarr 3.4 on 3.12 and
  later; each older Python keeps the release line that still supports it (GH-2050)

## [0.138.0] - 2026-09-28

### Added

- `--if_exists` on `stations`, `values`, `interpolate` and `summarize`, taking `replace` (the
  default, and what the CLI did before), `append`, `fail` or `skip`. `to_target` has taken the
  argument since it was written but no command passed it, so every CLI export replaced: a nightly
  timer pointed at a DuckDB table held one run's rows rather than a history. A pairing the sink
  refuses is reported as a line and exit 1 rather than a traceback
- `precipitation_intensity` can be declared in `millimeter_per_second`, which is what BUFR publishes
  a precipitation rate in (`kg m-2 s-1`). It is a source unit only: `WD_TS_UNIT_TARGETS` cannot ask
  for values in it, because `_convert_units` rounds to four decimals and would quantise mm/h into
  0.36 mm/h steps. A rounding rule that scales with the target is GH-2002 (GH-1984)
- `imgw/meteorology` `daily/synop` returns the five columns it read and never declared: the daily
  maximum, minimum and 5 cm minimum temperature, the precipitation total and the snow depth (`TMAX`,
  `TMIN`, `TMNG`, `SMDB`, `PKSN`). No synop station could return any of them (GH-1991)
- `imgw/meteorology` carries IMGW's own status in `quality`, which was null for every value the
  provider returned. "8" and "9" are IMGW's codes; `Z` (*opad zbiorczy*) is reported as 10, since
  `quality` is numeric and IMGW's code is a letter. A blank status is a measurement and stays null
  (GH-1998)
- Six dataset descriptions the docs carried and the model did not, so `discover`, the REST API and
  MCP report them too: `dwd/mosmix` hourly `small` and `large`, the three `dwd/derived` monthly
  `cooling_degreehours_*`, and `imgw/meteorology` monthly `climate`. The three
  `cooling_degreehours_*` are each described by the reference temperature they use rather than by
  the docs page's shared blurb about "13, 16 and 18 degree Celsius", those interfaces reporting a
  dataset at a time
- Documentation for running wetterdienst on a schedule, with ready-made units for systemd timers,
  launchd, cron and `docker run`. A `DynamicUser=yes` service has no writable `$HOME`, so without
  `CacheDirectory=` and `WD_CACHE_DIR` the run fails rather than going uncached, and
  `No data available for given constraints` exits 1 indistinguishably from a real failure (GH-255)
- DWD road: a temperature below -60 °C is marked suspect whatever window was asked for. The stopped
  sensors reporting `-75.00` °C were already caught by the rule marking a sensor held at one value
  for six hours, but only where the request covered six hours to find them in. Germany's record low
  air temperature is -45.9 °C, so the line stands 14 K under it (GH-1917)

### Changed

- **Breaking**: Every export a sink refuses raises `ExportRefusedError` -- a mode it does not do, a
  target already holding data under `if_exists="fail"`, or a format or protocol nothing here writes.
  It replaces a `NotImplementedError`, a `FileExistsError`, two `KeyError`s and pandas' `ValueError`
  in the SQLAlchemy sinks, so callers matching on those have to match on this one instead
- **Breaking**: DWD DMO declares the elements its runs carry, 23 parameters for `icon` and 19 for
  `icon_eu` rather than 122 and 40. The old lists were MOSMIX's, copied in when the provider was
  written, so a request for one of the 99 and 22 that are gone now raises `NoParametersFoundError`
  where it used to return an empty frame. `precipitation_height_last_1h` is added to `icon_eu`,
  which serves it and did not declare it. The model has no lead-time axis, so four of `icon`'s 23
  are carried only by `lead_time="long"` and three only by the default `"short"`; those still answer
  with the empty frame, tracked in GH-1976. Three served elements stay undeclared: no canonical
  parameter describes a net radiation flux, and `radiation_global_last_3h` is taken by one, which
  GH-1977 carries
- **Breaking**: `DwdDmoRequest.available_issues` takes the product it is answering for -- `dataset`,
  `station_group` and `lead_time`, keyword-only. It used to list `icon/single_stations/` whatever
  the request would read, and named issues that request then rejected. `wetterdienst issues` and
  `/api/issues` take `--dataset`/`--lead_time` to match. `dataset` and `station_group` default to
  `DwdDmoRequest`'s own; `lead_time` defaults to `None`, which lists every lead time together, so
  with no arguments this still answers more than a default request accepts -- GH-2009 (GH-1956)
- **Breaking**: `Settings.auth` holds `SecretStr` rather than `str`, so reading a credential back
  has to ask for it: `reveal(settings.auth.aemet)`, or `.get_secret_value()`. Setting them is
  unchanged, as is every `if not settings.auth.x` check. An f-string or `str()` of a credential now
  yields `**********`, and the mask is refused as a credential on the way in
- **Breaking**: `filter_by_name` refuses a name that is not a string before it downloads anything.
  The same `TypeError` came out of rapidfuzz before, one whole station index later -- except for
  `None`, which came back as an empty result and now raises like any other non-string. Check the
  name is there before asking, rather than reading an empty result as "no station by that name"
  (GH-2003)
- **Breaking**: The `mcp` extra requires `fastmcp>=4,<5` (was `>=3.4.4,<4.0.0`), and `ui/mcp.py`
  builds the `OpenAPIProvider`'s in-process ASGI client with `httpx2` (`>=2.12,<3`, now declared
  alongside the extra) rather than `httpx`, which FastMCP 4 has moved off entirely
- Locked dependencies refreshed to their latest compatible versions -- 74 packages, among them cloup
  4, fastmcp 4 (mcp 2), plotly 7 and tzfpy 2 -- which widened `cloup<5` and `tzfpy<3`. Plotly 7
  leads an HTML export with a doctype where 6.x began at `<html>`, the only change visible in output
- `DwdRadarValues.period` is annotated `Period | None`, which is what it has always held. The
  annotation claimed `Period` and carried a `ty: ignore`, which made both `not self.period` guards
  in the radar API read as dead code to the type checker

### Fixed

- **Breaking**: `dwd/road` declares the units BUFR publishes its precipitation intensity and water
  film in, so both are converted instead of being served 3600 and 100 times too small.
  `intensityOfPrecipitation` is `kg m-2 s-1`, millimetres per second, and was declared
  `millimeter_per_hour`, so a shower came back as 0.0056 mm/h; `waterFilmThickness` is metres and
  was declared `centimeter`. A request now answers 20.16 mm/h and 0.2 cm. The page's warning to
  multiply by 3600 by hand is gone with it -- do not apply that factor to a value from this version
  (GH-1984)
- **Breaking**: `imgw/meteorology` returns no value where IMGW records no measurement, rather than a
  zero. Each of the 61 declared value columns is followed by a status column and none was read,
  while the value cell of a missing measurement holds a literal `.0` -- so PSZCZYNA reported 0 %
  relative humidity for January 2010 and WARSZOWICE 0 cm of snow cover every day of it. Only status
  `8` becomes null. Under the default `ts_drop_nulls` a frame can come back shorter, or a parameter
  empty where it used to read zero throughout (GH-1994)
- **Breaking**: `imgw/meteorology` returns a documented *brak zjawiska* as the zero it means, where
  it returned no value at all. Status "9" was handled by passing the value cell through, which only
  works where the cell holds a zero, and the files disagree that it does: `o_d_07_2024` leaves it
  empty beside all 8,490 of its "9"s. WARSZOWICE on 2024-07-02 answered null and now answers 0.0 mm;
  `daily/synop` lost whole parameters that way rather than single days (GH-1997)
- **Breaking**: `imgw/meteorology` returns three parameters that were permanently empty and one that
  published a different column's numbers, and `monthly/climate/precipitation_height_max` answers to
  a different original name. Two rename targets carried a typo -- `opadóww` a doubled `w` and
  `minimalnaj` a stray `j` -- and `daily/precipitation/precipitation_height` carried
  `daily/climate`'s mean-temperature name for what upstream calls `SMDB` -- the one measurement that
  dataset exists to publish. `monthly/precipitation/precipitation_height_max` was worse for never
  looking empty: it read `o_m` field 7, the count of days with snowfall, and published that count as
  millimetres. A request for `monthly/climate/opad maksymalny` now raises `NoParametersFoundError`;
  the canonical name is unaffected (GH-1981)
- **Breaking**: `imgw/meteorology` declares `daily/climate`'s grass temperature as
  `temperature_air_min_0_05m`, the name its monthly siblings already use for the same measurement,
  rather than `temperature_air_mean_0_05m` -- `k_d_format.txt` names field 12 a daily minimum, and
  every other provider declaring the mean means a genuine 5 cm mean by it. A request for the old
  name raises `NoParametersFoundError` and names the new one in its hint (GH-1993)
- **Breaking**: A DuckDB `if_exists="append"` matches columns by name. `INSERT INTO t SELECT *`
  matches by position, so two frames with the same number of columns under different names were both
  accepted and the second one's values landed under the first one's headings -- a `--shape=wide`
  schedule that changed one parameter put a precipitation value into `temperature_air_mean_2m`, exit
  0 and nothing said. A frame whose columns are a subset of the table's is still accepted
- `ts_unit_targets` applies all of a mapping or none of it. `update_targets` validated and assigned
  entry by entry, so a mapping carrying one entry it could not use applied those written before it
  and then raised (GH-1984)
- `wsv/pegel` returns no data for a timeseries between measurements rather than raising
  `ColumnNotFoundError`. Pegelonline answers `[]` with HTTP 200 for a series it lists but holds no
  current measurements for, which `pl.read_json` reads as a frame with no columns (GH-1987)
- The InfluxDB sink takes `if_exists="append"`, which is the one word for what it does: every write
  is points, and a point repeating another's timestamp and tags replaces it. Refusing that spelling
  made a multi-station export impossible, `to_target` writing every station after the first with
  `append` -- the three export examples in the docs had been broken since `if_exists` was added
- DWD mosmix: a `kml/` directory that exists and holds nothing is answered rather than raising past
  the line written for it. `next` raises `StopIteration` where its filter matches nothing and the
  `except IndexError` never caught it, so a caller saw
  `RuntimeError: generator raised StopIteration` naming neither the directory nor what was looked
  for. A run is read as the ten digits DWD stamps a `.kmz` with rather than as the third
  `_`-separated part of the name: MOSMIX-L all-stations carries no station id, so that part was
  `2026092203.kmz` with the extension still on it and every row met
  `conversion from str to datetime failed` -- that layout could not be asked for a run at all.
  `available_issues` answers such a directory with no issues, as `dwd/dmo` now does for its own
  (GH-1946)
- DWD dmo: a run is read by its whole name (`_<lead>_<n>_<DDHHMM>.kmz`), where every part of it was
  read by position or by substring and each wrongly. The lead time matched a bare `"78"` anywhere in
  the URL, which 187 of 5811 station ids also satisfy, so ~3% of stations raised
  `can only call '.item()' if the Series is of length 1`; the run stamp took four characters off the
  last name part, so a README raised `conversion from str to i64 failed`. `available_issues`
  returned tz-aware datetimes that this compared against a naive column, so `wetterdienst issues`
  printed issues `wetterdienst values` could not accept. An issue is floored to the run before it,
  where `hour % 12` sent 1 through 11 up to 12, and one given in another zone is converted rather
  than relabelled (GH-1948)
- DWD DMO: a station the shared catalogue omits is described from the product's newest run, so it
  can be asked for. 135 of `icon`'s stations and 132 of `icon_eu`'s are absent from
  `dmo_stationsliste_txt.asc` -- `Y0353` is Mont Blanc -- and were filtered out of every request
  although their forecasts publish and fetch with HTTP 200. Both products now advertise exactly what
  they publish, 5757 and 3688. The added stations report `icao_id` as null (GH-1964)
- **Breaking**: DWD DMO: a station is advertised only for the product that forecasts for it. The
  shared catalogue matches neither product, so a request for `icon_eu` listed 2255 stations that
  could only ever answer with an empty frame. Coverage is read from the product's `single_stations/`
  directory, one listing rather than a 20 MB parse; a listing that cannot be read keeps the
  catalogue (GH-1964)
- DWD DMO: a station position is read as the degrees and minutes the catalogue writes it in
  (`{degrees}.{minutes:2d}`), and the seven hardcoded station patches are gone. Read as plain
  decimals, `.5` became 0°50' -- a station 84 km from where DWD says it is, and nothing raised --
  while `.-6` raised `conversion from str to f64 failed` naming neither column nor station. Of the
  file's 11 622 position fields, 21 needed repairing and all 21 now land on the coordinate DWD's own
  placemarks carry. `P0563` (London Luton) is beyond reach, written `.22` where the sign is missing
  rather than misplaced
- DWD DMO: a run stamp becomes the hour it names whatever that hour is. `DDHHMM` had its day, month
  and minute padded back to two digits before parsing but not its hour, so `3` made `...01300` and
  `%H` took the `30` it could see. DMO publishes at `00` and `12`, so no run has hit this
- DWD DMO: both dataset descriptions were MOSMIX's, word for word -- `icon` described as MOSMIX-L's
  "115 parameters for worldwide stations", `icon_eu` as MOSMIX-S's 40-parameter one, and neither
  count is DMO's. Neither description names a parameter count any more, and `icon_eu` names the set
  it is published for rather than "European": 11 of its 3688 stations sit east of 35° longitude
- DWD mosmix: `LATEST` reads the newest run the listing names rather than the alias beside it, and a
  named run is held for twelve hours instead of five minutes. The two are the same bytes -- one
  ETag, one content-length -- but a run named by its timestamp is that run for good, where the alias
  is a name DWD replaces hourly. MOSMIX-S, 36 MB published hourly, was refetched up to twelve times
  an hour: 10.4 GB a day over the wire against 871 MB now, at the cost of one blob an hour where it
  reused one -- reclaimed by the TTL sweep below, a named run being held under a positive one
  (GH-1945)
- DWD mosmix: a station whose directory DWD has emptied or retired costs that station and no more.
  `get_url_for_date` raised on a listing that named nothing and nothing between it and
  `values.all()` catches, so one such station ended a request for fifty. It answers `None` now, the
  split `dwd/dmo` has always made. A cached body that is not a zip is dropped and asked for once
  more, since fsspec records a cache entry before the copy that fills it finishes (GH-1949)
- DWD swsmos: the run is read once for the request rather than once for every station it answers
  for. One run file holds every road station's whole forecast -- 306 612 rows -- and was listed,
  fetched and parsed once per station with all but one station's rows thrown away. Twenty-five
  stations took 14.1 s and now take 0.8 s. The run is pinned for the length of a query and no
  longer, so a caller querying again on a timer is answered with the run published since (GH-1922)
- DWD swsmos: `LATEST` no longer answers with a run up to twelve hours old. The alias is a name
  whose content DWD replaces hourly and was cached by URL for twelve hours like everything else, so
  "the latest run" could be one whose first twelve forecast hours had already happened -- measured
  at 22:57 UTC, the alias answered from the 21:00 run while DWD served 22:00 (GH-1922)
- DWD swsmos: a run that cannot be read is reported and skipped, where it used to end the request in
  a traceback out of `bz2.decompress` and repeat it for the twelve hours it stays cached. `LATEST`
  falls back to the run before the newest, an hour-old forecast being what it should mean while a
  run is still being written. A run is matched exactly (`swsmos_<14 digits>_opendata.csv.bz2`),
  since a `swsmos_` prefix also matches a checksum sidecar that sorts after the run it belongs to,
  and a zero-byte 200 no longer parses to a run that simply holds nothing. The body is asked for
  once more past the cache before the fallback, and only once where the caller disabled the cache,
  which `cache_disable` can now say (GH-1922)
- Network: the cache says what it did, where it used to decide on a caller's behalf and keep quiet.
  `cache_dir`, `cache_disable` and `use_certifi` decided what `NetworkFilesystemManager.register`
  built and were not part of the key it was filed under, and `register` runs only for a new key --
  so the first caller in a thread decided for every later one, and a request made with caching
  disabled could be served by a caching filesystem. A listing that could not be read is no longer
  answered as an empty directory either: `fs.find` walks with `on_error="omit"` and aiohttp's
  `ClientOSError` is an `OSError`, so a connection reset was swallowed inside fsspec. A directory
  that is not there stays `[]`, as does being offline (GH-1947)
- Network cache: the on-disk blob directory is separated by the TTL and by the headers that can
  change what a server sends back, and by nothing else. Named for a hash of the whole of
  `client_kwargs`, it moved whenever the default User-Agent's version number did -- one developer
  machine held 129 directories and 4.3 GB, of which 115 MB was reachable by the installed version
  and 1.4 GB sat under `ttl-INFINITE-*`, a provider saying those bytes never change. Directories of
  the older layout are reclaimed on the first cached download of a process, and one a rotated
  credential named ages out at a month (GH-1959)
- Network cache: a blob its own TTL has already made useless is dropped, once per directory per
  process. A TTL that is not a positive number is not swept at all, because `CacheExpiry.INFINITE`
  is `False` and fsspec reads an expiry of zero as "every entry is expired" -- it would have thrown
  away the immutable archives `lhmt` and both `meteofrance` providers keep there. The lock is held
  across the sweep, which is what keeps a `download_files` thread pool from writing rows the sweep's
  own snapshot would then drop and orphan (GH-1955)
- Network: two credentials never share a cache directory or a filesystem, whatever shape their
  headers arrive in. `str()` of a `SecretStr` is `**********`, so every secret hashed to one value
  and the second caller was handed the first caller's filesystem, built with the first caller's
  `Authorization` header; `client_kwargs["headers"]` reaches aiohttp as a mapping or as a sequence
  of pairs and only the mapping was read. The cache also separates on every header but the ones that
  cannot change a body, rather than on a list of those known to carry credentials --
  `Accept-Language: de` and `en` shared a directory. An unknown header now costs a cache miss
- met.no Frost: the credential probe builds its own headers rather than writing into the dict
  `Settings` holds. `{**settings.fsspec_client_kwargs}` copies one level, so
  `setdefault("headers", {})[...] = ...` mutated the shared mapping and every later request from
  that `Settings` -- any provider, not only this one -- carried met.no's basic auth
- Network: the log says whether a file was downloaded or read from the cache, rather than saying
  "Downloading file" for both -- and it was wrong for every cache hit, the one thing a reader could
  already tell was not happening. `download_files` says what it is fetching up front and then how
  many arrived and how many the cache answered, `uncached` where there is no cache to report on
- A token exchange that meets a server error is asked a second time. `post_file` retried a
  connection that never carried a response but took every response that did arrive as an answer, and
  a 502 from a token endpoint is a blip. A mint is made once every three days and empties a whole
  Met Office query when it fails. A 401 is still an answer, and so is a 429 deliberately:
  `download_file` no longer retries every failing status, so a 429 from AEMET or met.no Frost is not
  answered by doubling the request rate against a provider that has just said it is rate-limiting. A
  404 and a 5xx are still asked twice, a file index being read minutes before the files it names
  (GH-1939)
- Met Office works on a plain `pip install wetterdienst`. Its CEDA token exchange imported `httpx`
  at module level, which only the `restapi` extra declared, so
  `Wetterdienst("metoffice", "observation")` raised on an installation that had not asked for the
  REST API. The exchange goes through fsspec now, by way of a new `post_file` in `util/network.py`,
  and `httpx` is no longer a dependency of wetterdienst at all. A redirect is not followed, since
  aiohttp would repeat a redirected POST as a GET and turn CEDA's login page into a 200 whose body
  parses as nothing (GH-1929)
- A provider that cannot be loaded says which package it is missing. `importlib` raises
  `ModuleNotFoundError` for an absent dependency as readily as for an absent module, and
  `Wetterdienst.resolve` rewrote both into `Module wetterdienst.provider.X not found`. Where an
  extra of this package would install it the message says which, read out of the installed metadata
  rather than from a list kept in the code (GH-1929)
- The three paths that do not go through the provider registry say which extra they want, where they
  used to raise a bare `ModuleNotFoundError`: `wetterdienst restapi` without `[restapi]`,
  `.interpolate()` without `[interpolation]`, and the radar HDF5 dump without `[radar]` (GH-1938)
- The MCP server tells a client which wetterdienst it is talking to. `FastMCP(version=...)` was
  never set, and left unset it reports the installed FastMCP release as the server's own version --
  so a client asking what it had connected to was answered "Wetterdienst 4.0.3"
- Examples: the DuckDB dump addresses its database file with three slashes rather than four, so it
  opens on Windows, where the leftover slash left DuckDB reading `//C:\...` as a UNC share. The same
  count was wrong in `to_target`'s docstring and the PyConDE notebook, which showed
  `duckdb://name.duckdb` -- read as a host rather than a path, so the data went to an extensionless
  file named `dwd` in the working directory with no error
- Three documented parameters that no request could ask for, and four requestable ones no page
  documented. `dwd/mosmix` hourly documented `cloud_base_convective` and `cloud_cover_below_7km`
  under `small`, which the model declares for `large` alone, and carried a stale `n1` row for
  `cloud_cover_below_1000ft` that the model has never mapped; `imgw/meteorology` monthly `synop`
  documented none of its four precipitation parameters at all
- Three unit cells disagreeing with the model about the quantity rather than the notation:
  `dwd/road` 15_minutes wrote `mm/s` where the model declared `millimeter_per_hour` -- there the
  page was right and the model wrong, which GH-1984 settles in this release -- and `dwd/observation`
  monthly and annual wrote `Bft` for `wind_gust_max`, which the model declares `meter_per_second`,
  copied from the `wind_force_beaufort` row above it
- The stale MOSMIX and DMO figures the docs carried: MOSMIX-L at "~115 parameters" and both products
  at "over 5000 stations worldwide" in two files beside the `docs/data/overview.md` being corrected
  in the same change, and a fourth copy of the 115 in `dwd/mosmix` hourly's own dataset description.
  Measured: MOSMIX 5649 stations, 40 parameters for `small` and 122 for `large`; DMO 5757 stations
  and 23 parameters for `icon`, 3688 and 19 for `icon_eu`
- `imgw/meteorology`'s page states what its status column does not settle. A `0` in
  `monthly/climate`'s `snow_depth_max` carrying no status means either no snow cover in the month or
  a maximum that could not be determined -- 96 of the 196 rows of 2024, returned as 0 cm -- and
  `daily/precipitation` omits a *brak zjawiska* day rather than returning 0 mm for it. The page had
  said a parameter a station does not measure "comes back with no values" (GH-1997, GH-1998)
- `imgw/hydrology` monthly is described as "historical monthly hydrology data", not "historical
  daily climate data" -- wrong in both the resolution and the subject, and wrong in the model and
  the page alike. A caller asking `discover`, the REST API or MCP for `monthly/hydrology` was told
  it holds daily climate data
- The three `dwd/derived` *Kuehltage* overrides are described as "Number of days with at least one
  cooling hour", which is what DWD counts, rather than "Number of days on which cooling was
  required". The canonical `count_days_cooling_degree` keeps the general wording, as its
  `count_days_heating_degree` sibling does

### Security

- Provider credentials are held as `SecretStr`, so that rendering the settings does not print them.
  `Settings.__repr__` serialises the whole model, `auth` included, and a request's dataclass repr
  embeds a `Settings` -- so an API key reached every ordinary way of looking at an object on a
  failure path: a pytest assertion diff, a traceback, `print(request)`, a debugger, a notebook.
  Anyone pasting such a traceback into an issue or a CI log published every credential they had
  configured. All four -- AEMET, KNMI, met.no Frost and CEDA -- now render as `**********`, and
  `reveal()` is the one way back to a value (GH-1920)
- A credential no longer travels in the error a failed download hands back. aiohttp hangs the
  request's headers on a `ClientResponseError` and on its `args`, so an `Authorization` header
  reached anything that rendered the `File` the download returned. It travelled three further ways:
  the traceback's frames in `util/network.py` hold the caller's client kwargs as locals, which
  `pytest --showlocals` prints; `ClientResponseError.history` holds a copy per redirect; and
  `stamina`'s retry hook logs a `repr` of what failed. None of the four shows in `str(error)`. The
  header is redacted, the history and traceback dropped, and the error scrubbed on its way into the
  retry as well as out of it
- A failed request that carried its credential in a header of another name has that header redacted
  too. The scrubbing knew `Authorization`, where KNMI's key, met.no Frost's basic auth and Met
  Office's bearer token go, but AEMET sends its key as `api_key`
- `httpx2` now has a floor of `>=2.12` wherever it is declared -- the dev group, which held
  `>=2.4.0`, and the `mcp` extra, which now declares it -- and the lockfile carries 2.13.0 where it
  held 2.10.0. Six advisories stand against 2.10.0, three distinct defects: multipart part header
  injection through an unvalidated file `Content-Type` (CVE-2026-84379, fixed in 2.11.0),
  conflicting `Content-Length` and `Transfer-Encoding` headers generated together (CVE-2026-84380,
  2.11.0), and unbounded peak memory decompressing a streamed response (CVE-2026-84382, 2.12.0).
  `uv audit` has failed on `main` since 2026-09-16 on exactly these, and passes again

## [0.137.0] - 2026-09-18

### Added

- Interpolation and summary take an `elevation` for the point they answer for, in metres above sea
  level, and bring each station's readings to it before using them. Air temperature falls about 0.65
  K per 100 m, so the stations within 40 km of Garmisch span 630 m to 2956 m -- 15 K interpolated as
  though it were horizontal structure. Named `elevation` on the API and the REST API, `--elevation`
  on the CLI, and it names the point too, so two elevations at one place no longer share a station
  id. A station whose height the provider does not report is left out of such an answer; where that
  leaves a parameter with no station at all, `NoStationsWithHeightError` names it and how to ask for
  the readings uncorrected (400 on the REST API)
- Parameter table: `lapse_rate` says how fast a quantity falls with height, in its own unit per
  metre, for the 17 air temperatures measured at 2 m and the dew point. Not for the 5 and 10 cm
  readings, which are governed by the ground beneath them, nor for anything in or on the ground, nor
  for the comfort indices, nor for pressure, which wants the barometric formula rather than a rate
- Export: `file://` targets for `.json`, `.jsonl` and `.nc`. JSON could not be written to a file at
  all; it holds the frame's records rather than the `{"metadata": ..., "values": [...]}` envelope a
  response carries. NetCDF joins Zarr as the second array format, written through xarray with CF
  time units and gaps as NaN rather than the -999 Zarr fills them with. The `export` extra carries
  `h5netcdf`, which needs no compiled netCDF library
- DWD road: the `quality` column carries the station's own verdict on its sensors, where it was null
  on every road reading. `qualityInformationAwsData` (BUFR `0 33 005`) is a 30-bit flag naming which
  quantities the station calls suspect, and it was read and thrown away. A reading is `1` where the
  station checked it and calls it suspect, `0` where it checked and does not, and null where nothing
  is known -- the common case, 817 of 1199 station-minutes reporting no checks performed.
  `road_surface_condition` and `water_film_thickness` stay null, the WMO's generic table naming no
  state of a road. `quality` carries whatever a source publishes and the scale differs by provider,
  which the column's description now says rather than promising one meaning (GH-1917)
- DWD road: a sensor that has stopped is marked suspect. Where an air temperature, dew point or road
  surface temperature reports the identical value for 24 readings -- six hours here -- `quality`
  becomes `1` and the reading is left exactly as DWD published it. Measured rather than chosen: over
  a day of ~700 stations per quantity a working sensor's longest run was 9 to 17 readings, a broken
  one 86 to 96 of 96. Only those three quantities, since a dry day's surface condition and water
  film legitimately sit at 0 all day. A road at its melting point is exempt where the station's own
  air came near freezing, salted roads holding a constant sub-zero value by the same physics
  (GH-1917)

### Changed

- DWD road: the precipitation type is reported as `precipitation_type_flags` rather than
  `precipitation_form`, being a different kind of number. `precipitationType` is BUFR `0 20 021`, a
  30-bit flag table with a bit per type, where `precipitation_form` elsewhere holds a single code --
  so rain came back as `33554432` against DWD observation's `6` for the same weather, under one
  canonical name. The value is unchanged. The bit layout and how to mask for a type are on the
  provider's docs page (GH-1916)
- Interpolation and summary by station id answer at that station's altitude, it being the one case
  where the elevation is known without being given. **This changes what `interpolate_by_station_id`
  and `summarize_by_station_id` return** where the stations drawn on stand at other altitudes -- for
  the reading uncorrected, pass the station's coordinates to `interpolate` or `summarize` instead
- Dependencies: the `bufr` extra is the whole of what reading BUFR takes. pdbufr requires eccodes
  but asks for any version, and the two were named as separate extras with the docs telling you to
  install both, neither being any use without the other. `pybufrkit` is no longer pulled in by
  `bufr`: nothing in the library imports it, only the radar tests do, and they skip on it now
- Dependencies: shapely is required from 2.0.6 rather than 2.0.4. The two releases before it raise
  out of `create_collection` under numpy 2, which is what every other dependency here resolves to
- REST API: `/api/summarize` answers a window that ends before it starts with a 400 rather than a
  404, as `/api/interpolate` already did. Both endpoints decide that from one place now

### Fixed

- Unit conversion: the mile and the knot are derived from the metres they are defined as, rather
  than from decimals rounded to four figures. `1.944` left knots to metres per second 0.0080% from
  its km/h route, so the same quantity converted differently depending on which unit its source
  published -- the Met Office publishes wind in knots and the speed target is m/s, so every one of
  its wind speeds carried the error. A round trip hid all three, both directions sharing the
  rounding
- Interpolation: four stations that surround the target point are a valid group however they are
  ordered. The check drew a polygon through them in the order they are held -- by distance from the
  point, which says nothing about the order around it -- so roughly half of all groups described a
  self-intersecting shape, where `covers` is undefined: 11676 of the 37415 groups that do surround
  the point the tests use were rejected. The convex hull decides now, which is also the region
  `LinearNDInterpolator` can answer for. No interpolated value in the test suite changes
- Interpolation: stations that do not span a triangle are no group, and four on a line come back
  without a value rather than raising scipy's `QhullError`. A hull with no width still covers a
  point lying on it, so such a set counted as valid -- which is what stops the collection of further
  stations, so a set that cannot be interpolated at all could end a search that would have found one
  that can
- Interpolation: a point the interpolation has no answer for comes back empty rather than as a zero.
  `LinearNDInterpolator` answers NaN outside the stations it was given, and for the quantities
  carrying an occurrence test -- precipitation, new snow -- `NaN >= 0.5` is False, so the NaN was
  reported as a precipitation of exactly none
- Interpolation: whether four stations surrounding the point exist is answered from the hull of all
  of them rather than by enumerating groups, which costs C(N,4) hulls -- 91390 for the 40 stations a
  wide radius reaches, seconds per station against 0.2 ms
- DWD road: a station with two road sensors is read as having two, and a reading is one sensor's.
  The sensors are a delayed replication inside the station's subset, so the rank on the key names
  the sensor where `positionOfRoadSensors` reads 0 or missing in all 1199 subsets measured. Only
  what is inside that replication can arrive twice -- 3 of the dataset's 14 parameters -- so a row
  can never hold one sensor's air temperature beside another's road surface. Of 75 stations whose
  sensors both reported a surface temperature the median disagreement was 0.3 K. Everything
  contested is taken from the one sensor reporting most of it, and what is dropped is logged at
  debug (GH-1908)
- DWD road: a station's reading is kept whole where it arrives in parts. `read_bufr` emits an
  observation only where every column asked for is present, so asking for all fourteen parameters
  threw away every reading of anything not universally fitted -- against one file of the DD group
  the parse returned 105 values where the file held 121, the whole of `roadSurfaceTemperature` among
  the missing, on a road weather network. The file is read flat instead, one row per station and
  minute, and a parameter no subset carries comes back as a null column
- DWD road: a station group is read once for a request rather than once per station of it. A road
  file holds a whole group where the collection above asks one station at a time, so every file was
  decoded once per station and all but that station's rows thrown away: three stations of one group
  over two hours parsed nine files twenty-seven times, and now nine (GH-1922)
- DWD road: a subset that names no station or no minute is one reading lost rather than a file. One
  null minute made the whole of pandas' column a float, where 2026 written as "2026.0" took the
  timestamp of every station in the file with it
- DWD road: a listing entry is a file when it carries the timestamp the file index reads it by, and
  two entries never do -- the directory of a group that holds nothing, which made the listing
  non-empty so `No files found` never said so, and the `LATEST` alias duplicating each family's
  newest file, which a request without dates parsed twice. A name that is neither is reported, so a
  group publishing under two families cannot lose half its readings to a rename
- DWD road: having nothing to answer with is one shape. There were three -- no columns where the
  group published no file, five where its files held nothing, and the seven a reading has -- so the
  collection walk raised
  `ColumnNotFoundError: unable to find column "station_id"; valid columns: []` from its middle. A
  frame of no readings now carries the columns a reading does. The empty files of GH-1526 were
  turned away by their exact length, which is a guess at a shape rather than a reading of one, so
  one holding no subsets at another length reached the parse and raised `KeyError: 'year'`. This is
  what failed `test_pdbufr_examples` on every CI job
- REST API: a BUFR reader missing on the server answers 501 rather than 400. The blanket handler
  read every failure as the caller's, so a deployment installed without the `bufr` extra told the
  client to `pip install wetterdienst[bufr]` on a machine they do not administer, and `interpolate`
  and `summarize` called the same thing a 404. The install line moves to the server log
- CLI: a missing optional reader is reported rather than raised. `values`, `interpolate` and
  `summarize` caught `ValueError`, and the `ImportError` naming the extra is not one, so the
  sentence saying what to do arrived as the last line of a traceback. The refusal has a type of its
  own, `BufrReaderMissingError`, so a cycle or a typo inside a provider module keeps its traceback
- DWD road: a missing BUFR reader is refused at the request rather than at the parse. The values
  class called `ensure_pdbufr()` and threw the answer away, so the request went through and a bare
  `ImportError` came back out of the middle of a parse
- BUFR: asking whether this environment can read BUFR answers, whatever the import does. Each probe
  had a hole: `ensure_eccodes` did not catch the plain `ImportError` an eccodes with no compiled
  library raises, and `ensure_pdbufr` re-raised a `RuntimeError` matched on gribapi's phrasing of
  the day. A reader that is installed and does not work says why,
  `No module named 'gribapi.bindings'` being a broken install rather than an absent one
- Export: a file target renders what the matching format returns. `to_csv` joined a list of station
  ids into one field and the CSV file target did not, so `--target=file://out.csv` on an
  interpolation died with `CSV format does not support nested data` where `--format=csv` wrote the
  same data out fine. Zarr failed on the same column
- Export: station metadata can be filtered by SQL and written to Zarr, NetCDF or CrateDB. All three
  named the `date` column a values frame has, while a stations frame carries `start_date` and
  `end_date`, so `request.all().filter_by_sql(...)` raised `ColumnNotFoundError`. The CLI's `--sql`
  went through a second copy of the filter that worked but called whatever came back UTC; both run
  the one filter now
- CLI: an empty window is reported once, where `get_values` logged "No data available for given
  constraints" and the CLI logged the identical line again before exiting

## [0.136.0] - 2026-09-04

### Added

- DWD: new `poi` network (`dwd/poi`) covering DWD's POI current weather reports -- the hourly
  observations of roughly the last day, one `<station_id>-BEOB.csv` per station. 39 parameters at
  `hourly` resolution and the `now` period. This is the observed counterpart to `dwd/mosmix`: the
  two share the MOSMIX station catalogue, so a station keeps one id across both and a forecast can
  be compared against what was measured. About 970 of the catalogue's ~5600 stations report. The
  file's two 24-hour radiation columns are left unmapped, both declared W/m2, which a 24-hour figure
  cannot be -- sum the hourly column for a daily total

### Changed

- Periods: `periods` is an argument of every request rather than of the three that hand-rolled it,
  and is resolved against the periods the requested datasets declare. A dataset published under a
  single period is answered for that period and raises `NoPeriodsFoundError` for another. Left out,
  the periods are still derived from `start_date`/`end_date` where the provider has a release
  schedule (DWD observation and phenology) and are otherwise every period the requested datasets
  publish, which for a request naming one dataset is narrower than the provider-wide set it used to
  be. `TimeseriesRequest.available_periods()` replaces the per-provider `_available_periods`
- Parameter parsing: a parameter the provider does not have is logged as a warning naming what did
  not match -- resolution, dataset or parameter -- with the closest name as a "did you mean", where
  it used to be an `info` line saying only that it was not found. Half a request silently resolving
  to less data than was asked for is otherwise invisible
- Provider metadata: `MetadataModel` carries the name it was built with as a `name` field. Read
  `DwdObservationMetadata.name` rather than `DwdObservationMetadata.__name__`
- Lookups on the metadata models (`metadata["daily"]["kl"]`, `metadata.daily.kl`) match the source's
  own name case-insensitively, as looking one up by `name_original` in a request already did, and
  suggest the closest name when nothing matches
- Parameter parsing: the parts of a parameter must be strings. A tuple mixing in an enum member,
  `(Resolution.DAILY, "kl")`, raises a `TypeError` naming the accepted forms rather than an
  `AttributeError` from deep inside the parser
- Periods: narrowing the periods of a provider that does not read its data per period -- SMHI,
  MeteoSwiss, met.no Frost and Meteo-France observation fetch all of them by design -- is logged as
  a warning saying the request was not narrowed, rather than answered with everything in silence

### Fixed

- Dates: a date string covers everything it names instead of only the instant it starts with.
  `2020-05` is the month of May, `2020` the year, and `2020-05-01` a whole day. Every one of these
  formats is documented as supported, and `filter_by_date` matched a single date with `==`, so a
  month or a year of hourly data came back empty -- no reading falls exactly on the 1st at 00:00. An
  interval ran to the *first* instant of the span its second half names, so `2017-01/2019-12` ended
  on the 1st of December and `2010/2020` dropped all of 2020. The CLI and REST API read the string
  the same way. A date carrying a time still names one instant
- Periods: a period no requested dataset publishes is no longer silently turned into *every* period.
  `periods="future"` intersected the request with the available periods and the empty result read as
  "no periods requested", so asking for a period that does not exist returned more data than asking
  for one that does. It raises `NoPeriodsFoundError` now
- Periods: `periods` reaches providers that never accepted the argument. It was a per-provider
  constructor field, so `NoaaGhcnRequest(..., periods="historical")` was a `TypeError` and the CLI's
  `--periods` was dropped for every provider but DWD observation, derived and phenology -- including
  met.no Frost, whose datasets are published under both `historical` and `recent`
- Periods: a period derived from `start_date`/`end_date` is checked against the datasets like a
  requested one. An interval reaching into today derives `now`, which `daily/kl` has no release for,
  and the request then read no station index at all -- reporting *no stations* where asking for
  `periods="now"` outright raises. Where the interval reaches past a dataset's newest release, that
  release answers for it
- Periods: an explicit period is answered for a dataset published under a single one. The CLI and
  REST API forwarded `periods` only where some requested dataset had more than one, so asking DWD
  derived for `historical` on a `recent`-only dataset read every period the provider has
- Interpolation and summarization: the values of one station are no longer read together with
  another station's coordinates and distance. Both walks paired the distance-sorted stations frame
  against the values generator by position, but that frame carries a row per station *and* dataset
  while the generator yields one result per station and skips those that returned nothing, so any
  gap shifted every station after it onto its neighbour's location
- Interpolation and summarization: a result with no rows is a feature collection with no values
  rather than an `OutOfBoundsError`. The feature's id was read out of the frame's first row, so a
  point and window no station covers raised `gather indices are out of bounds` from `to_geojson`,
  where `to_dict` on the same result answered fine. The id belongs to the point
- Values: a request that collected nothing returns an empty frame carrying its columns rather than
  one with no columns at all, which wrote an empty file where a header was meant and raised
  `ColumnNotFoundError` from `get_column("date")`. Having no data for the constraints given is an
  ordinary outcome, so it is no longer logged with a traceback either
- Ranked station values: a station whose record lies entirely outside the requested window no longer
  counts against the station count of `filter_by_rank`. It was checked for data before the window
  was cut and never again after, so it spent one of the ranked slots on an empty frame and the walk
  stopped short of the stations that do cover the window -- which reads exactly like no data
  existing at all
- Values: a ranked request no longer reads the whole provider to answer for a window that predates
  it. A station returning nothing inside the window rightly does not count towards `rank`, but then
  nothing bounded the walk either. A station the index says began after the window ended is skipped
  without being downloaded; only that direction is read from the index, a station still reporting
  carrying an `end_date` a little behind what it can answer for
- Values: a dataset named more than once in a request -- interleaved with another -- is fetched and
  parsed once instead of once per run of consecutive mentions. The station index of NOAA GHCN,
  Geosphere and MeteoSwiss gained a duplicate row per station the same way
- Plots: a parameter is labelled with the unit its values are actually written in. The label mapping
  was keyed on the canonical name alone while a frame carries `name_original` unless `ts_humanize`
  is on, so nothing matched and the label repeated the name -- `sd_10 (sd_10)`. The symbol was also
  always the target unit's, though `ts_convert_units=False` leaves the values as published:
  `10_minutes/solar/sunshine_duration` comes in hours and was labelled seconds. Keyed by resolution
  and dataset as well as name now, a canonical name being unique only within its dataset
- Parameter parsing: a quality flag requested by name (`daily/kl/quality_wind`) says that quality
  flags come back in the `quality` column next to their parameter, where it used to be dropped as if
  it did not exist. Requesting one as a `ParameterModel` was dropped the same way
- Parameter parsing: parameters requested more than once -- a dataset and one of its parameters, or
  the same dataset twice -- are returned once rather than per mention, and an iterator of parameters
  no longer parses as empty, having been consumed by the checks that tell `("daily", "kl")` apart
  from a list
- Provider metadata: a misspelled key in a metadata declaration is rejected instead of dropped. Only
  `ParameterModel` forbade extra keys, so `date_requiered` anywhere else was silently ignored and
  the declaration fell back to a default. An invalid `periods` or `date_required` on a resolution is
  now reported as the validation error it is rather than a bare `KeyError('periods')`
- CI: the Coolify deploy step had failed on every run since 2026-08-17, so no release or nightly
  reached the live deployment. Coolify moved `/api/v1/deploy` from GET to POST and left the GET
  route answering `405`, which `curl --fail` turned into an exit 22 after the images had been pushed

## [0.135.0] - 2026-08-31

### Added

- DWD: new `phenology` network (`dwd/phenology`) covering the DWD phenological observation network
  -- the day of the year on which a plant reached a developmental phase, at `annual` resolution,
  reaching back to 1925. 110 datasets, one per plant and reporter group (`annual_common_hazel`,
  `immediate_winter_wheat`, ...), each carrying that plant's phases as parameters. A value is DWD's
  `Jultag` dated to the 1st of January of the reference year, so the entry date is that date plus
  the value. Both reporter groups are covered, with their own station catalogues

### Removed

- `Resolution.UNDEFINED` and `Period.UNDEFINED`, which no provider declared any more -- the last
  sources without a stated interval went when WSV and Hubeau began reporting theirs.
  `periods="undefined"` now raises `InvalidEnumerationError` where it used to parse and then match
  no dataset, which is the one visible change. `PeriodType` goes with it, as `ResolutionType` did
  before, and so does `Frequency.MINUTE_2`, which named a resolution that never existed

### Fixed

- Environment Agency: 15-minute values arrived empty for every window of the last decade and a half.
  The readings endpoint answers a request naming no window with its default page of 100_000
  readings, oldest first, and reports no truncation; at 15 minutes that page runs out after some 2.8
  years, so the readings of 2008 to 2011 came back whatever was asked for and the post-filter
  dropped all of them. The window is now asked for, and the page raised to what it can hold. Daily
  was never affected, 100_000 daily readings being 274 years, and this also stops a 22 MB download
  per station
- Environment Agency: the whole 15-minute resolution was unreachable, both `discharge` and
  `groundwater_level` raising `KeyError` while building the station listing from a hand-kept map
  that still spelled them `*_instant`. The measure parameter and the period are read off the
  notation the metadata declares -- `flow-i-900` is flow measured every 900 seconds -- so renaming a
  parameter cannot separate the two again
- Environment Agency: a station is listed once rather than once per matching measure. The listing
  carries a row per measure, so a station recording two of the requested parameters came back
  duplicated and `filter_by_rank` spent rank on it twice
- DWD observation: the `climate_urban` URL was pinned to the `recent` directory whatever period was
  requested, so a `now` request for a 10-minute urban dataset was answered with data ending at the
  previous midnight and `historical` could not be read at all. The hourly urban datasets are
  unchanged, DWD publishing a single `recent` directory that already holds the full record
- DWD observation: where two periods reported the same timestamp, which record survived was decided
  by neither of the two things that should decide it -- the periods were read in the iteration order
  of a set, varying between interpreter runs, and the deduplication ran over a frame `how="align"`
  had already reordered by value, so the survivor was the lower reading, or a null where one period
  was missing a measurement the other had. Values now settle on the quality-marked historical record
  and stations on their most current description
- DWD observation: station `history` returned nothing for the 10-minute urban datasets, looking for
  them under a `meta_data` directory only the non-urban high resolutions have, while the urban zips
  carry their `Metadaten_*.txt` files themselves. `describe_fields()` raised an opaque `.item()`
  length error for them, DWD publishing no description PDF at all, and now names what it looked at
- Network: the fsspec listings cache silently never hit for `CacheExpiry.INFINITE`. The expiry
  reaches `FileDirCache` as `False`, which diskcache read as `now + False == now`, so every entry
  was stored already expired and each listing was refetched. Falsy expiries now mean "never expire",
  as the download-side cache has always read them
- Network: a listing whose TTL lapsed between fsspec's `in dircache` probe and the following lookup
  raised a `KeyError` out of `ls()`/`find()`. The dircache is read with a single lookup now, which
  also stops a `detail=False` call from caching a name-only listing that later `detail=True` reads
  would receive
- Network: a disabled listings cache created a cache directory named `False`, `0.0` or `0.01` that
  nothing readable was ever written to. Those are no longer created, and any left by an earlier
  version are swept on the next run, guarded so that a folder still holding valid entries is kept
- Network: a float timeout in `fsspec_client_kwargs` reached aiohttp unwrapped and failed every
  request with `ValueError: timeout parameter cannot be of <class 'float'> type`, only int timeouts
  being wrapped in `ClientTimeout`. `download_file()` also raised
  `AttributeError: 'NoneType' object has no attribute 'get'` where `client_kwargs` was left at its
  `None` default, and `FileDirCache` could not be unpickled, its `__reduce__` passing three
  positional arguments in the wrong order to an `__init__` that takes one
- The app's `Resolution` type restates the backend enum and had drifted both ways: it still offered
  `undefined` and `dynamic`, and had never gained `6_minutes`, which Meteo-France is served under

## [0.134.0] - 2026-08-22

### Added

- The DWD climate indices as four datasets: `annual`/`monthly` `climate_indices` count tropical
  nights and frost, summer, hot and ice days, while `annual`/`monthly` `precipitation_indices` count
  the days reaching precipitation heights of 0.1 to 20 mm and snow depths of 1 and 5 cm. DWD derives
  them from the daily observations of the same stations and publishes them in the familiar CDC
  layout, so they arrive as metadata alone. Twelve canonical parameters are new with them, named for
  the index the literature knows (`count_days_frost`, `count_days_tropical_night`) rather than for
  its threshold, which the description carries
- The two interpolation search radii are settings of their own:
  `ts_geo_station_distance_homogeneous` (40 km, for a quantity that varies slowly across a region)
  and `ts_geo_station_distance_heterogeneous` (20 km, for one that decorrelates within a few tens of
  kilometres). They were module constants, so widening the search for everything meant naming all
  514 parameters individually in `ts_geo_station_distance`, which keeps its role as the
  per-parameter override. On the CLI as `--interpolation_station_distance_homogeneous` and
  `--…_heterogeneous` (`--summary_…` for `summarize`), and on the REST API under the same names
- `wetterdienst summarize` reaches the settings `interpolate` always could:
  `--summary_station_distance` and `--use_nearby_station_distance` had no command options at all, so
  the summary CLI always ran with the defaults

### Changed

- **Breaking**: WSV Pegelonline reports under the interval it actually records at, so its single
  `dynamic` resolution is replaced by `1_minute`, `5_minutes`, `10_minutes`, `15_minutes` and
  `hourly`, and `dynamic/data/...` no longer resolves. Pegelonline publishes an `equidistance` on
  every timeseries in the station listing the provider already downloads. The 77 of 787 stations
  recording different parameters at different intervals appear under each, serving only the
  parameters that belong there -- to find a station's resolution, request the parameter at every
  interval that could carry it and read the `resolution` column of the station list
- **Breaking**: Eaufrance Hubeau reports under the interval each station transmits at, so its single
  `dynamic` resolution is replaced by `5_minutes`, `6_minutes`, `10_minutes`, `15_minutes` and
  `hourly`, and `dynamic/data/...` no longer resolves. Hubeau publishes the interval nowhere, so
  unlike Pegelonline's declared `equidistance` it is measured from the timestamps a station has just
  published: of 3018 stations reporting over six hours, 2987 resolved to one of the five. A station
  that has published nothing to measure, or transmits every 20 or 30 minutes, is listed under no
  resolution rather than a guessed one, and returns as soon as it transmits on a covered interval.
  `Resolution.DYNAMIC` goes with these two, and `ResolutionType` with it
- **Breaking**: the heterogeneous search radius follows the resolution of the request, so an
  interpolation or summary that already worked returns different values without anything being
  changed by hand: daily precipitation is drawn from 40 km rather than 20, `minute_10` from 15 km. A
  quantity that decorrelates fast in space does so less the longer it is accumulated -- gauge
  studies put precipitation's correlation length at roughly 8 km over ten minutes and 33 to 94 km
  over a day. The factors are `ts_geo_station_distance_resolution_factors`: 0.75 for the minute
  resolutions, 1.0 hourly, 1.5 for `6_hour` and `subdaily`, 2.0 from daily upwards. Every factor set
  to 1.0 turns the scaling off; a radius written out per parameter in `ts_geo_station_distance` is
  used exactly as given. The table stops at 2.0 because past a day what binds is terrain, the
  interpolation reading UTM x/y and never station height
- **Breaking**: the `"default"` key of `ts_geo_station_distance` is gone in favour of the two radii
  settings above. It was undocumented and did more than it said: it rebuilt the mapping around the
  given number, so `{"default": 30}` gave precipitation, fresh snow and visibility 30 km as well as
  setting the fallback. Setting it now raises and names its replacements
- **Breaking**: `skip_empty` works through the CLI and the REST API. Neither surface ever set
  `ts_complete`, and `ts_skip_empty` was silently switched off wherever it was not, so
  `--skip_empty`, `--skip_threshold` and `--skip_criteria` did nothing at all and `filter_by_rank`
  never skipped a station over its coverage the way it is documented to. A CLI or REST request that
  passes `--skip_empty` starts skipping stations it used to return
- A station's coverage is the share of the readings the requested window can hold at the parameter's
  resolution that the station delivered, counted from the window and the resolution rather than by
  measuring a frame reindexed onto a grid first. The denominator is the one `ts_complete` produced,
  with two departures: a reading that does not land on the grid counts as delivered rather than
  missing, and a request naming no window is measured against the span of the station's own series.
  `subdaily` is measured on what came back, being a bucket rather than an interval whose two
  providers disagree on the spacing
- An NWS request asks the observations endpoint for its own window. The endpoint answers an
  unqualified request with its whole retention -- a rolling week, close to a megabyte -- however
  little was wanted, and the frame was trimmed only after it arrived

### Removed

- **Breaking**: the `ts_complete` setting is gone. It reindexed a series onto the grid its
  resolution implies, at the cost of a materialized timestamp per reading, a station-local-to-UTC
  window conversion and a three-way interlock with `ts_drop_nulls` and `ts_shape`. The join it built
  was exact, so a station reporting off the grid -- an hourly gauge at seven minutes past, which is
  how a good third of Hubeau's hourly stations report -- came back as a column of nulls. A caller
  who wants the grid can build it in a few lines of polars, where the phase is theirs to choose
- **Breaking**: `MetadataModel.timezone_data` is gone, and with it the `timezone_data` key all 29
  providers declared. It named the zone a provider's own `date` labels are stamped in and
  `ts_complete` was the only thing that read it. `metadata.timezone`, the provider's civil timezone,
  is a different field and remains. Every `date` a request returns is UTC either way

### Fixed

- **Breaking**: `ts_shape="wide"` puts one timestamp of one resolution in a row, and stops filling
  rows with values that belong to another. The row was keyed on the dataset as well while the
  parameters were joined on the date alone, so a request spanning two datasets emitted every
  timestamp once per dataset and filled all of those rows with all of the values -- the two rows
  were identical but for the label. Datasets recorded at one resolution now share a row, with
  `dataset` null where no single name describes it. The parameter joins are also outer rather than
  inner, so a parameter with no reading at a timestamp leaves a null instead of removing the
  timestamp: chained inner joins had reduced the result to the timestamps every requested parameter
  happened to share
- Values of two resolutions are sorted apart in both shapes. The row order was `dataset`,
  `parameter`, `date`, so an hourly and a 10-minute precipitation series came back shuffled into
  each other, one hourly row every six 10-minute ones
- Eaufrance Hubeau lists every station it has rather than the first thousand. The referential
  answers with a page of 1000 of its 4150 stations and a cursor to the rest, and the query named no
  page size and followed no cursor, so three quarters of the French gauges were unreachable --
  including by `filter_by_station_id`, which filters against that list
- Eaufrance Hubeau serves the overseas departments. Metropolitan station codes begin with the letter
  of their hydrographic basin and those of Guadeloupe, Martinique, Guyane, La Réunion and Mayotte
  with a digit, and the list kept only codes beginning with a letter -- excluding all 176 overseas
  gauges, 86 of them transmitting
- The NWS station list holds three American stations it used to leave out -- Barking Sands on Kauai
  and the two US Virgin Islands airports, which MADIS files under a state code rather than a country
  code. They are named one by one, that column not being readable as a state code in general: `PR`
  in it is Peru and `GU` is Guatemala. The list was also narrowed to
  `longitude < 0 and latitude > 0`, which is not where the United States ends -- the Aleutians west
  of Amchitka lie beyond the antimeridian and Pago Pago below the equator -- so that box is gone,
  having decided nationality by hemisphere
- An NWS station of unknown elevation reads as null rather than as standing 9999 m up. MADIS writes
  a missing elevation as 9999 and it was cast to a float and passed on unread, for 31 of 3120
  stations -- and height is what interpolation weighs a neighbouring station by
- An NWS request no longer rewrites the settings every other request shares. It stamped its own
  headers onto `Settings.fsspec_client_kwargs` in `__post_init__`, so a DWD request made after an
  NWS one went out under NWS's headers, naming a version eighty-five releases old
- A Zarr export names its group for what the whole frame holds rather than for whatever its first
  row says. A frame of two datasets was filed under whichever came first, and one merging them would
  have gone to the store root, where `mode="w"` clobbers every other group in it
- `ts_geo_station_distance` validates what it is given: a key that is not a canonical parameter is
  rejected rather than kept and never read, and a negative distance is rejected as it already was
  for `ts_geo_use_nearby_station_distance`. The CLI and REST API report the rejection as a bad
  parameter and a 400 rather than a pydantic traceback
- Settings round-trip through `model_dump()` faithfully: `ts_geo_station_distance` serializes the
  overrides it was given rather than the mapping they were expanded into, which came back as
  explicit per-parameter overrides that then won over a `ts_geo_station_distance_heterogeneous` set
  alongside
- `poe docs` builds the documentation again. It ran `make html` in `docs/`, which holds no Makefile,
  so it had failed with "No rule to make target" for as long as that file has been gone. It runs
  sphinx against `docs/conf.py` now, as Read the Docs does, and `poe docs:clean` removes the build
- Docs: `ts_geo_min_gain_of_value_pairs` is documented with its actual default of 0.1, not 1.2

## [0.133.0] - 2026-08-19

### Added

- Every parameter of every provider carries a description, 1681 of 1681, closing the last 508 gaps,
  and they are reported by `discover()` -- so by `GET /api/coverage`, the `coverage` MCP tool and
  `wetterdienst about coverage`. 388 come from the source itself: MeteoSwiss, met.no Frost, KNMI,
  FMI, AEMET, SMHI, CHMI, Météo-France, the Met Office's CEDA tables and LHMT publish per-field
  metadata, translated here where it is not in English, and DWD's English `DESCRIPTION_*_en.pdf`
  sheets and `MetElementDefinition.xml` cover its own. Those say what a canonical sentence cannot:
  that Météo-France's daily precipitation runs 06h to 06h UTC and is attributed to the earlier day,
  that Met Office pressure is uncorrected for altitude, that CHMI's daily temperature is the mean of
  three fixed observations. The rest are the canonical sentence for the quantity, kept in
  `DERIVED_DESCRIPTIONS` so generated text is never mistaken for a source's own wording
- A one-sentence description for all 505 canonical parameters, provider- and resolution-independent,
  so the glossary says what each quantity *is* rather than only which unit it comes back in.
  `metadata.source_descriptions` carries what a given provider's field means alongside it, for 1057
  parameters
- Parameter discovery across all three interfaces: `GET /api/glossary`, the `glossary` MCP tool and
  `wetterdienst about glossary`. `coverage` answers which parameters a provider offers; the glossary
  answers what any of them measures and which unit it comes back in, including any `ts_unit_targets`
  override. Filter with `parameter=` (substring over the 505 names), `unit_type=` (a closed
  vocabulary, so an unknown one is a 422 rather than an empty result) and `limit=`. A filter
  matching nothing is an empty list over HTTP and a non-zero exit on the CLI, following grep
- Dataset and resolution descriptions on the metadata models, 88 of 148 datasets and 2 resolutions.
  `DatasetModel.description` and `ResolutionModel.description` had been declared but never
  populated, so `metadata["hourly"]["data"].description` returned `None` for every provider
- 216 more parameters can be interpolated and summarized, 343 of 514 rather than 127: soil
  temperature under a named cover and depth (114), forecast probabilities (65), soil moisture (12),
  evaporation per crop and soil, concrete slab temperature, humidex, climatological normals, and at
  the shorter radius precipitation intensity and visibility. The classification was never about the
  data being unavailable, only about which names had been written into the list by hand. What stays
  out stays out on purpose: coded observations, quality flags, counts, directions, and the 14 GHCNd
  soil temperatures whose cover is recorded as `unknown`. One cost: `interpolate()` stops querying
  stations once *every* requested parameter has enough of them, so a whole-dataset request against
  MOSMIX now has 65 probabilities to satisfy and walks further down the ranking
- Canonical parameter table (`wetterdienst.metadata.parameter_table`) holding the `unit_type` of
  each of the 505 canonical names in one place, plus a test checking every provider declaration
  against it. `wetterdienst.metadata.unit_type.UnitType` types it, so a mistyped unit type is a type
  error rather than something only a test can catch
- ECCC monthly and hourly expose the fields that were previously left undeclared, with twelve new
  canonical parameters: the monthly day counts and the climatological normals, and hourly
  `temperature_humidex`. Units were taken from the values rather than assumed -- each normal matches
  the range of the quantity it is a normal of, and humidex sits at or above the air temperature in
  all 233 paired observations sampled
- DWD hourly solar `true_local_time_offset` (`mess_datum_woz`), holding how far true local solar
  time runs ahead of a record's timestamp -- the longitude correction plus the equation of time.
  Solar records are stamped with the UTC instant of a whole true-solar-time hour, so the correction
  sits in the minutes, which wetterdienst rounds away; it was not reachable at all. At station 00183
  it runs 40 to 71 minutes, tracing the equation of time about a 54.7 minute longitude term
- DWD's two measurement method indicators are returned instead of dropped:
  `cloud_cover_total_measurement_method` (`v_n_i`) and `visibility_range_measurement_method`
  (`v_vv_i`). DWD writes them as letters -- `P` for a person, `I` for an instrument -- in otherwise
  numeric files, and the value column is Float64, so both were declared but silently dropped.
  Decoded to 1 and 2; the digits are wetterdienst's, and 0 is left unused so "not measured" stays
  distinct
- New canonical parameters `radiation_global_intensity`, `radiation_sky_long_wave_intensity` and
  `radiation_sky_short_wave_diffuse_intensity` for sources reporting irradiance (power per area)
  rather than irradiation accumulated over the interval, plus `cooling_degree_day`, the counterpart
  of `heating_degree_day`, and the `mass_per_volume` and `degree_hour` unit types the audit turned
  up
- `GET /api/version` reports `mcp_enabled` alongside the version. Whether `/mcp` exists is a
  property of the installation, and a client had no way to find out short of opening a session
  against it
- Docs: a parameter glossary on the Parameters page, built from the canonical parameter table at
  build time, with every provider metadata row linking to its entry

### Changed

- **Breaking**: `discover()` nests its answer so that every level has a place for its description:
  `{resolution: {"description": ..., "datasets": {dataset: {..., "parameters": [...]}}}}`. Consumers
  reading `data[resolution][dataset]` as a list of parameters now read
  `data[resolution]["datasets"][dataset]["parameters"]`
- **Breaking**: irradiance (`power_per_area`) is returned in W/m² rather than W/cm², so affected
  values are 10⁴ times larger. W/m² is what WMO specifies and what every source here publishes --
  MeteoSwiss global radiation now reads 0–1344 where it read 0–0.1344. Affects the 17 declarations
  using `power_per_area`: KNMI, MeteoSwiss, met.no Frost and RMI. Set
  `ts_unit_targets={"power_per_area": "watt_per_square_centimeter"}` to keep the old output.
  Irradiation (`energy_per_area`) is unchanged, still J/cm²
- **Breaking**: KNMI (10 minutes), RMI, MeteoSwiss and met.no reported irradiance under the
  `radiation_global`, `radiation_sky_long_wave` and `radiation_sky_short_wave_diffuse` names, which
  elsewhere mean irradiation in J/cm². These declarations moved to the `radiation_*_intensity`
  names. KNMI is the clearest case: its 10-minute `qg` is W/m² while its hourly `Q` is J/cm², so one
  name covered two quantities no conversion relates without the accumulation interval
- **Breaking**: Geosphere 10-minute and hourly radiation is returned as published rather than
  silently rescaled. `cglo` and `chim` are irradiance in W/m² and the parser multiplied them by the
  interval length to present them as irradiation; values are 16.67× and 2.78× larger, so multiply by
  0.06 and 0.36 to recover the old numbers. Daily and monthly are unaffected, using a distinct
  upstream parameter genuinely accumulated over the interval. This was the last in-parser unit
  conversion in the library
- **Breaking**: Météo-France synop `visibility_range` was the only declaration of that parameter
  using `length_long`, so it was returned in km while all 15 others return m. It now uses
  `length_medium`
- How a parameter behaves in space is declared once, on `CanonicalParameter`, rather than as three
  hand-maintained name lists that had to agree: `TimeseriesRequest.interpolatable_parameters`, the
  `ts_geo_station_distance` defaults and `_OCCURRENCE_BASED_PARAMETERS` are all views of the new
  `interpolation` (`"homogeneous"` at 40 km, `"heterogeneous"` at 20 km, or `None`) and
  `zero_inflated` fields. The two are separate facts: visibility decorrelates over a few kilometres
  without being zero-inflated. `_OCCURRENCE_BASED_PARAMETERS` is gone -- ask
  `PARAMETERS[name].zero_inflated`
- **Breaking**, mildly: `TimeseriesRequest.interpolatable_parameters` is a `frozenset` rather than a
  `list`. Every caller in the library only tests membership, but it is public, so code that indexes
  or slices it or relies on its order needs updating
- The `Parameter` enum is no longer used inside the library. The three places that hard-coded
  parameter names used it purely to spell a lowercased string and now spell the canonical name
  directly; all 186 references resolve to the same names as before
- `uv` resolves with a three-day cooldown (`tool.uv.exclude-newer = "3 days"`), so a release has to
  survive its first days in the wild before entering the lockfile. Recorded as a relative span so it
  does not churn between runs
- Locked dependencies refreshed to their latest compatible versions (cryptography 50, fastapi
  0.141.1, starlette 1.6, numpy 2.5.2, zarr 3.3, mcp 1.29), and several floors raised to what the
  code actually needs: `aiohttp>=3.14.0`, `stamina>=25.1.0`, `pandas>=2.2.2`, `shapely>=2.0.4`,
  `h5py>=3.11`, `plotly>=6.1.1` with `kaleido>=1.0.0` and `click>=8.2`
- Provider docs tables no longer carry the `unit type` column or own the description text. The unit
  type is a property of the canonical parameter, stated once in the glossary; the descriptions lived
  only in markdown, where no interface could reach them and the two copies drifted apart in both
  directions -- three defects found during the unit audit were each caught by the *other* source
  being right

### Removed

- **Breaking**: the `Parameter` enum, exported from the package root. It listed the canonical names
  but could not be used to request them -- `parameters=` accepts strings, tuples, `ParameterModel`
  and `DatasetModel`, so passing a member raised
  `AttributeError: 'Parameter' object has no attribute 'strip'`. The names live in
  `wetterdienst.metadata.parameter_table` and are discoverable through the glossary endpoint, MCP
  tool and `wetterdienst about glossary`
- The `unit_type` key from provider metadata declarations, 1575 of them across 29 files. It is a
  property of the measured quantity rather than of the provider, and restating it once per
  declaration is what let one canonical name pick different output units in different providers. All
  1692 parameters resolve to the same `unit_type` as before, but a **third-party metadata dict that
  still declares `unit_type` will now fail to validate** and should drop the key. It is no longer
  part of `ParameterModel.model_dump()`
- **Breaking**: seven DWD observation parameters that were declared but never returned a value, so a
  request for one now says so instead of answering with an empty frame:
  `cloud_type_layer1..4_abbreviation`, `weather_text`, `end_of_interval` and `true_local_time`. Each
  was checked against the archive: `v_sN_csa` matches `v_sN_cs` exactly across 398,381 records,
  every `ww` maps to one text across 443,827 while two codes share a text, and `end_of_interval`
  names a column that does not exist in the solar files at all
- **Breaking**: five `Parameter` members no provider declared, so no request could return them:
  `HUMIDEX`, `PRECIPITATION_FREQUENCY`, `PRECIPITATION_HEIGHT_LIQUID_MAX`, `TIME_WIND_GUST_MAX` and
  `TIME_WIND_GUST_MAX_1MILE_OR_1MIN`
- The `magnetic_field_intensity` and `wave_period` unit types. Each existed for exactly one
  parameter and both turned out mis-typed: WSV `current` is a bearing in degrees and WSV
  `wave_period` a duration in seconds
- Docs: `eccc/observation/annual.md` and `humidex` under hourly -- ECCC's `annual` resolution was
  dropped when values moved to the OGC API, and the overview still described bulk CSV downloads and
  four resolutions. The `pressure_air_sea` row of IMGW meteorology daily goes too, that provider no
  longer exposing it

### Fixed

- **Breaking**: conductivity conversions between per-centimetre and per-metre units were wrong, 8 of
  the 12 pairs by 10²–10⁴. Conductivity is per unit *length*, so a shorter length in the denominator
  means a larger number -- 1 S/cm is 100 S/m -- and the conversions had that inverted on top of
  mishandling the µ prefix. Since `siemens_per_meter` was the default target, every conductivity
  value the library returned was affected: WSV station 71160198 read 0.0021 S/m where the correct
  figure is 0.2059. Only the two pairs the tests covered were right
- **Breaking**: conductivity is returned in µS/cm rather than S/m, which is the convention in
  hydrology and what the sources publish -- S/m is large enough that rounding to 4 decimals cost
  real precision, 8.481 µS/cm coming back as `0.0008`. Set
  `ts_unit_targets={"conductivity": "siemens_per_meter"}` for the old unit, which now also returns
  the correct value
- **Breaking**: WSV Pegelonline values are scaled to the unit the metadata declares. The service
  publishes the unit per *timeseries*, not per parameter, and its stations disagree, so a single
  declaration was silently wrong wherever a station differed: water level is `cm` at most gauges but
  `m+NN` at 66 and `m+PNP` at 2, conductivity `µS/cm` or `mS/cm`, wave height `cm` or `m`. Wave
  height at MELLUMPLATE came back as 0.07–1.32 next to 12.66–280.6 at LT ALTE WESER for the same
  quantity, both labelled cm. A station publishing a unit the provider does not know is skipped with
  an error rather than reported under the wrong one. The `m+NN` gauges measure against sea level
  rather than the gauge datum even once scaled -- the `gauge_zero` column says which
- **Breaking**: WSV `current` is renamed `flow_direction` and returned in degrees, the source's
  `MGN` unit being degrees relative to magnetic north rather than a magnetic quantity; `wave_period`
  is returned in seconds, having been declared with a unit whose symbol was `1/s`; and
  `clearance_height` is returned in centimetres, having been declared in metres while every station
  publishes centimetres, so values were 100× too large
- **Breaking**: WSV parameter names are humanized like every other provider's. The parser wrote the
  source name lowercased while the humanizing map is keyed on it as declared, so values came back as
  `sigh`, `tp` and `r` rather than `wave_height_sign`, `wave_period` and `flow_direction`. With
  `ts_humanize=False` the names are now the source's own casing (`SIGH`) rather than lowercased
- WSV `gauge_zero` is populated rather than always null for all 738 stations -- the station frame
  built the column as `gauge_datum`, which `_base_columns` then dropped. This is the column that
  says which datum a water level is on, so it matters most for the `m+NN` gauges above. Turbidity is
  checked against the station's own unit like the other scaled parameters: `FNU`, `TE/F` and `NTU`
  all name the same formazin scale so no value changes, but a unit that is not on it is now skipped
- **Breaking**: ECCC hourly and monthly return data at all. Both declared parameters the OGC API
  never publishes -- hourly carried a copy of the *daily* field list, monthly carried bulk-CSV
  column headers -- so every request came back empty, and monthly additionally crashed on a
  `"2023-06"` timestamp. The requested field list is derived from the declarations now rather than
  hand-maintained per resolution, which is what let hourly drift into a copy of daily. Parameter
  names change for both resolutions
- **Breaking**: ECCC value requests return the whole period rather than an arbitrary 500 records.
  The OGC endpoint pages at 500 features and a station-year of hourly data is ~8800, so every
  request was silently truncated -- June 1972 at station 4055 returned 16 timestamps where it holds
  697. ECCC also exposes its whole ~8600-station network rather than the first 500, so 94% of it
  could not be requested at all, including every station whose data the hourly collection holds
- ECCC no longer fails on the daylight-saving fall-back hour, and stations opened before standard
  time no longer fail the listing -- `America/Toronto` is `-5:17:32` in 1895, an offset that is not
  a whole number of minutes and that polars rejects, so the conversion to UTC happens in Python.
  Neither showed up while the listing stopped at 500 rows. ECCC hourly `wind_direction` is returned
  in degrees rather than tens of degrees
- **Breaking**: ECCC daily `cooling_degree_days` and `heating_degree_days` were mapped onto
  `count_days_cooling_degree` and `count_days_heating_degree`, which mean a number of days. ECCC
  publishes the degree day total for the single day the record covers -- for station 2 on 1979-11-02
  the mean temperature is 6.3 °C and the value is 11.7, which is `18 - 6.3` and not any count. They
  now use `heating_degree_day` and the new `cooling_degree_day`, in °Cd; the values are unchanged
- **Breaking**: ECCC `wind_direction_gust_max` is returned in degrees rather than tens of degrees.
  ECCC's own docs call the column `Dir of Max Gust (10s deg)` and the declaration said `degree`, so
  every bearing came back 10× too small: 17–26 where the true directions are 170–260. Because the
  wrong values still sit inside 0–360, no range check could have caught it
- **Breaking**: four DWD subdaily parameters named the wrong quantity, not merely the wrong unit,
  each contradicted by the `Metadaten_Parameter_*.txt` shipped inside every data ZIP. `e_tf_ter` is
  whether ice had formed on the wet bulb thermometer, carrying only 0 and 1 across 82901 values, and
  was declared `temperature_air_mean_0_05m` in °C -- now `temperature_wet_ice_formation`. `ek_ter`
  is a 0-9 ground-state code declared `temperature_soil_mean_0_05m` -- now `soil_state_index`.
  `vk_ter` is a 0-9 visibility code declared `visibility_range` in metres, so subdaily visibility
  returned "5 metres" for class 5 -- now `visibility_range_class`. `tf_ter` is the wet bulb
  temperature declared `temperature_air_mean_2m`, where DWD's hourly moisture dataset already maps
  the same quantity to `temperature_wet_mean_2m`; confirmed against 83994 paired observations, a
  median 1.6 °C below the air temperature and never above it
- **Breaking**: DWD's `v_n_i` and `v_vv_i` are named for what they hold, both being *measurement
  method* indicators where `cloud_cover_total_index` and `visibility_range_index` described a coded
  value. `visibility_range_class` takes the freed `visibility_range_index` name, which it only ever
  lacked because the method indicator held it; `cloud_cover_total_index` is removed, no provider
  declaring a coded cloud cover
- **Breaking**: DWD hourly cloud cover no longer reports -0.125 of the sky. `cloud_cover_total` and
  `cloud_cover_layer1` to `_layer4` carry -1 where the sky could not be seen at all, SYNOP's N = 9,
  which in eighths converted to -0.125. It is null now. DWD documents only -999, so the reading is
  from the data: -1 stands in 1.2% of station 00003's hourly observations and fog codes accompany
  69.1% of those against 0.8% of the rest. The cloud *type* codes keep their -1, being dimensionless
- **Breaking**: MET Norway's in-band codes are decoded rather than returned as measurements. Frost
  writes them into the value itself: snow depth -1 is "no snow", a depth of zero rather than an
  absent one, and cloud cover -3 and 9 both mean the cover could not be estimated -- in eighths
  those converted to -0.375 and 1.125 of the sky, the second looking like a plausible reading. Snow
  depth -1 returns 0 and cloud cover -3 and 9 return null. Frost keeps the codes out of its own
  means, so only the elements are touched
- **Breaking**: MET Norway `cloud_cover_total` was declared `percent` while Frost publishes octas --
  its own `unit` field says so and the values run 0 to 8 -- so a fully overcast sky was reported as
  `8 %`. Now `one_eighth`
- **Breaking**: Geosphere `cloud_cover_total` is returned as a fraction rather than a percentage
  passed off as one. It was declared `decimal` while Geosphere documents `bewm_mittel` as `1/100`
  and returns 0-100, so the raw percentage went through the `fraction` target unconverted and every
  value was 100x its stated meaning. Its own `humidity` already declared `percent`
- **Breaking**: DWD road `visibility_range` is returned in metres rather than 1000x too large. It
  was declared `kilometer`, but BUFR `0 20 001 horizontalVisibility` is metres, nothing in the
  parser converts, and the provider's docs page already said `m`
- **Breaking**: AEMET daily `dir` is `wind_direction_gust_max`, not `wind_direction`. AEMET
  documents it as the direction of the maximum gust, and its hourly block already separates the two
- DWD `humidity_absolute` (`absf_std`) was declared `dimensionless`. It is a mass of water vapour
  per volume of air published in g/m³ -- station 00433 reads 1.6 to 19.1 -- so it now uses
  `mass_per_volume`. DWD `cooling_degree_hour` was declared in degree days while it accumulates per
  hour, reporting a monthly 4179.8 °Ch as 4179.8 °Cd, a figure no month can reach. Both values are
  unchanged
- Requesting several parameters at once no longer fails when one of them has no data for the
  station. Concatenating the empty result raised polars'
  `ShapeError: unable to append to a DataFrame of width 6 with a DataFrame of width 0`. This
  affected every provider that reports parameters separately. A parameter whose *download* fails is
  indistinguishable from one that has no data at this point, so such a parameter is omitted from the
  result rather than failing the request
- `summarize()` searched for stations within 20 km whatever the parameter. It bounded its search
  with `max(ts_geo_station_distance.values())`, and that mapping only holds entries for the
  parameters that get the *shorter* radius, everything else being answered by the default factory.
  It takes the widest radius among the requested parameters now, as interpolation already did
- The three new `radiation_*_intensity` parameters are listed in
  `TimeseriesRequest.interpolatable_parameters`; without them `interpolate()` and `summarize()`
  silently dropped the renamed radiation parameters for the affected providers
- Descriptions no longer leak between resolutions. `build_metadata_model` wrote them into the
  metadata dicts it was given, and providers commonly build one resolution's parameter list from
  another's by comprehension, reusing those very dicts: AEMET's annual parameters are its monthly
  ones minus humidity, so annual reported "Monthly mean temperature" and its own seven descriptions
  went nowhere
- 34 docs rows named a field the provider does not use -- DWD MOSMIX and DMO documented low cloud
  cover as `n1` where the element is `nl`, DWD 1-minute and 5-minute carried `precipitation_form`
  for `precipitation_index`, and ECCC and IMGW carried names from before their APIs changed. Each
  was a row whose description could not reach the model, so correcting them recovered 25
  descriptions that already existed. DWD's layer cloud cover descriptions are correct too: the
  English sheet truncates `V_S1_NS` to "cloud cover of 1. laye" and repeats it for `V_S2_NS`, so the
  second layer was described as the first
- `CITATION.cff` names the released version again and is valid CFF 1.2.0 once more. It had lost
  `version` and `date-released` and carried an empty `identifiers:` key, which parses as null and
  fails the schema, so the file every citation tool reads described no particular release and could
  not be converted at all. A test now ties it to the sources it duplicates

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

[Unreleased]: https://github.com/earthobservations/wetterdienst/compare/v0.180.0...HEAD
[0.180.0]: https://github.com/earthobservations/wetterdienst/compare/v0.179.0...v0.180.0
[0.179.0]: https://github.com/earthobservations/wetterdienst/compare/v0.178.0...v0.179.0
[0.178.0]: https://github.com/earthobservations/wetterdienst/compare/v0.177.0...v0.178.0
[0.177.0]: https://github.com/earthobservations/wetterdienst/compare/v0.176.0...v0.177.0
[0.176.0]: https://github.com/earthobservations/wetterdienst/compare/v0.175.0...v0.176.0
[0.175.0]: https://github.com/earthobservations/wetterdienst/compare/v0.174.0...v0.175.0
[0.174.0]: https://github.com/earthobservations/wetterdienst/compare/v0.173.0...v0.174.0
[0.173.0]: https://github.com/earthobservations/wetterdienst/compare/v0.172.0...v0.173.0
[0.172.0]: https://github.com/earthobservations/wetterdienst/compare/v0.171.0...v0.172.0
[0.171.0]: https://github.com/earthobservations/wetterdienst/compare/v0.170.0...v0.171.0
[0.170.0]: https://github.com/earthobservations/wetterdienst/compare/v0.169.0...v0.170.0
[0.169.0]: https://github.com/earthobservations/wetterdienst/compare/v0.168.0...v0.169.0
[0.168.0]: https://github.com/earthobservations/wetterdienst/compare/v0.167.0...v0.168.0
[0.167.0]: https://github.com/earthobservations/wetterdienst/compare/v0.166.0...v0.167.0
[0.166.0]: https://github.com/earthobservations/wetterdienst/compare/v0.165.0...v0.166.0
[0.165.0]: https://github.com/earthobservations/wetterdienst/compare/v0.164.0...v0.165.0
[0.164.0]: https://github.com/earthobservations/wetterdienst/compare/v0.163.0...v0.164.0
[0.163.0]: https://github.com/earthobservations/wetterdienst/compare/v0.162.0...v0.163.0
[0.162.0]: https://github.com/earthobservations/wetterdienst/compare/v0.161.0...v0.162.0
[0.161.0]: https://github.com/earthobservations/wetterdienst/compare/v0.160.0...v0.161.0
[0.160.0]: https://github.com/earthobservations/wetterdienst/compare/v0.159.0...v0.160.0
[0.159.0]: https://github.com/earthobservations/wetterdienst/compare/v0.158.0...v0.159.0
[0.158.0]: https://github.com/earthobservations/wetterdienst/compare/v0.157.0...v0.158.0
[0.157.0]: https://github.com/earthobservations/wetterdienst/compare/v0.156.0...v0.157.0
[0.156.0]: https://github.com/earthobservations/wetterdienst/compare/v0.155.0...v0.156.0
[0.155.0]: https://github.com/earthobservations/wetterdienst/compare/v0.154.0...v0.155.0
[0.154.0]: https://github.com/earthobservations/wetterdienst/compare/v0.153.0...v0.154.0
[0.153.0]: https://github.com/earthobservations/wetterdienst/compare/v0.152.0...v0.153.0
[0.152.0]: https://github.com/earthobservations/wetterdienst/compare/v0.151.0...v0.152.0
[0.151.0]: https://github.com/earthobservations/wetterdienst/compare/v0.150.0...v0.151.0
[0.150.0]: https://github.com/earthobservations/wetterdienst/compare/v0.149.0...v0.150.0
[0.149.0]: https://github.com/earthobservations/wetterdienst/compare/v0.148.0...v0.149.0
[0.148.0]: https://github.com/earthobservations/wetterdienst/compare/v0.147.0...v0.148.0
[0.147.0]: https://github.com/earthobservations/wetterdienst/compare/v0.146.0...v0.147.0
[0.146.0]: https://github.com/earthobservations/wetterdienst/compare/v0.145.0...v0.146.0
[0.145.0]: https://github.com/earthobservations/wetterdienst/compare/v0.144.0...v0.145.0
[0.144.0]: https://github.com/earthobservations/wetterdienst/compare/v0.143.0...v0.144.0
[0.143.0]: https://github.com/earthobservations/wetterdienst/compare/v0.142.0...v0.143.0
[0.142.0]: https://github.com/earthobservations/wetterdienst/compare/v0.141.0...v0.142.0
[0.141.0]: https://github.com/earthobservations/wetterdienst/compare/v0.140.0...v0.141.0
[0.140.0]: https://github.com/earthobservations/wetterdienst/compare/v0.139.0...v0.140.0
[0.139.0]: https://github.com/earthobservations/wetterdienst/compare/v0.138.0...v0.139.0
[0.138.0]: https://github.com/earthobservations/wetterdienst/compare/v0.137.0...v0.138.0
[0.137.0]: https://github.com/earthobservations/wetterdienst/compare/v0.136.0...v0.137.0
[0.136.0]: https://github.com/earthobservations/wetterdienst/compare/v0.135.0...v0.136.0
[0.135.0]: https://github.com/earthobservations/wetterdienst/compare/v0.134.0...v0.135.0
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

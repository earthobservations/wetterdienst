# Climate Stripes

Climate stripes (also known as
["warming stripes"](https://en.wikipedia.org/wiki/Warming_stripes)) are a minimalistic
visualization popularized by Ed Hawkins that encodes the long-term trend of a climate
variable as a sequence of coloured bars — one bar per year, coloured from blue (cooler) to red
(warmer) for temperature, and from brown (drier) to teal (wetter) for precipitation, relative to a
reference (see [Method](#method)).

Wetterdienst can generate climate stripes from two sources, for two kinds:

- **DWD** (`provider=dwd`, `network=observation`, the default): the annual values DWD publishes
- **NOAA GHCN daily** (`provider=noaa`, `network=ghcn`): worldwide, with the years calculated from the daily values
  (see [Sources](#sources))

and the kinds are

- `temperature` — based on the annual mean air temperature
- `precipitation` — based on the annual precipitation sum

## Sources

Every stripes surface, the REST endpoints `/api/stripes/stations`, `/values` and `/image`, the command line's
`stripes stations` and `stripes image`, and the MCP tools `stripes_stations`, `stripes_values` and `stripes_image`, takes
`provider` and `network`. They default to `dwd` and `observation`, so a call that names none is answered as it
always was. `noaa` and `ghcn` are the second pair, and any other pair, `dwd`/`ghcn` or `eccc`/`observation`, is refused
(a 422 over REST, a usage error on the command line, naming the pairs that are served). A station id is the
provider's own: `01048` for DWD, `USW00094728` for GHCN.

Everything after the annual values is the same for both: the [method](#method), the minimum of 10 years with data,
the reference period and its fallback to the whole record, the classes, the palette and the units (`unit_targets`).

### GHCN daily: the years from the days

[GHCN-Daily](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily)
has daily values only, so the year is built from the days by the rules of the WMO Guidelines on the Calculation of
Climate Normals (WMO-No. 1203). A year that fails them is a **gap** in the stripes, as a year DWD has no value for is,
and is never filled.

| | temperature | precipitation |
|---|---|---|
| a day | the **midrange** (**TMAX** + **TMIN**) / 2; a day with one of the two alone is missing. **TAVG** only at a station with no day that has both | the **PRCP** |
| a month counts | with at most 10 days missing, and at most 4 of them in a row | only when **complete**: every day has a value |
| the month's value | the mean of the days | the sum of the days |
| a year counts | with all 12 months counting | with all 12 months counting |
| the year's value | the mean of the 12 monthly means (each month weighs the same, whatever its length) | the sum of the 12 monthly sums |

A day with no row in the station's file is missing, as a day with no value is. A value whose quality flag
names a check it failed (NOAA's `QFLAG`, which the readme asks to treat as missing), and a value the
[plausibility checks](../data/plausibility.md) flag `suspect`, are missing days. A run of missing days is counted in
its month, so 3 missing days at the end of one month and 3 at the start of the next are two runs of 3. The first year of
a record that starts mid-year, and the year still running, have fewer than 12 months and are gaps.

**The day's temperature is the midrange, never mixed with TAVG.** The midrange of the daily maximum and minimum is not
a 24-hour mean, and the stripes do not claim it is. It is used for every day of a station that has TMAX and TMIN, and
the source's TAVG is not used there at all, even on the days that have it; TAVG is used (for every day) only at a
station whose data has no day with both. Which of the two a station's data has is decided from the days that were
read, not from the inventory, whose spans of TAVG are stale (for Los Angeles, USW00023174, it lists TAVG to 2005 and
the data runs to 2025). The reason is that a steady method over the whole record matters more for anomalies than the
accuracy of each day: a constant bias cancels against the station's own reference, while a change of method would show
as a false step. GHCN's TAVG covers only part of most records, mostly the 1990s on, and differs systematically from the
midrange: where the choice was made day by day, Los Angeles switched method four times and its recent years read about
0.4 °C cooler. The `processing_note` names the method the series used, "midrange of TMAX and TMIN" or "TAVG".

The answer says so: the `processing_note` of `/api/stripes/values` (and the `X-Wetterdienst-Processing` header of the CSV
and the image) says that the annual values were calculated from the provider's daily values by these rules, before the
sentence on the reference. The `series` names the daily parameter the years were built from
(`daily/data/temperature_air_mean_2m` or `daily/data/precipitation_amount`), and the `request` of the `metadata` all of
them (for the temperature also `temperature_air_max_2m` and `temperature_air_min_2m`, which the day is made of, and `temperature_air_mean_2m`, the TAVG, which only a station without them is read from).

A station's file holds its whole record and is one download per request, with the cache expiry of the values of GHCN
(5 minutes).

#### The stations of GHCN

`stripes stations` lists the stations whose record can reach the 10 years, as for DWD: the span from the first to the last
year that `ghcnd-inventory.txt` lists for the elements the kind is made from, that is TAVG together with the span TMAX
and TMIN have in common for the temperature (the listing is generous: the day is the midrange wherever there is both),
and PRCP for the precipitation, not the span of any element the
station has. As for DWD, a record with gaps is listed where its span is long enough and is still refused where it has
fewer than 10 years with values. `start_timestamp` and `end_timestamp` of the list are that span, and
`end_timestamp` is empty for a station whose last year is the current one. `active` (default `true`) keeps the
stations whose span reaches into this or the last year. Measured on 2026-11-18:

| | temperature | precipitation |
|---|---|---|
| stations of the list | 132,894 | 132,894 |
| span of 10 years or more | 32,594 | 79,780 |
| and active | 12,248 | 26,908 |

The list is long, so `stripes stations` takes a **bounding box**, `left`, `bottom`, `right` and `top` (all four, or
none), as `/api/stations` does, for DWD as well: the stations inside it, borders included. A box that is not whole, or
whose `left` is not west of its `right` or `bottom` not south of its `top`, is refused.

```bash
# The GHCN stations of the temperature stripes in a box around New York, as GeoJSON.
http localhost:7890/api/stripes/stations provider==noaa network==ghcn kind==temperature \
  left==-75 bottom==40 right==-73 top==41 format==geojson

# The stripes of one of them.
http --download localhost:7890/api/stripes/image provider==noaa network==ghcn kind==temperature station==USW00094728
```

## Method

The colours follow [Ed Hawkins' method](https://en.wikipedia.org/wiki/Warming_stripes), which the
FAQ of [#ShowYourStripes](https://showyourstripes.info/) states (the page renders in the browser;
[its capture of 2021-09-07](https://web.archive.org/web/20210907033708/https://showyourstripes.info/faq)
has the text):

> For each country, the average temperature in 1971-2000 is set as the boundary between blue and
> red colours, and the colour scale varies from +/- 2.6 standard deviations of the annual average
> temperatures between 1901-2000.

So a year is not coloured by where it lies between the coolest and the warmest year shown, but by
its distance from a fixed reference:

- **Centre**: the mean of the station's annual values of 1971-2000. A year at it is on the boundary
  between blue and red.
- **Range**: ±2.6 standard deviations of the station's annual values of 1901-2000, in 16 classes
  of 2.6 / 8 = 0.325 standard deviations each: 8 below the centre, 8 above. A value beyond ±2.6
  standard deviations takes the end class. Hawkins' own published graphics hold exactly these 16
  colours and no other (counted pixel by pixel in
  [one of 2018](https://www.climate-lab-book.ac.uk/files/2018/05/globalcore.png)), and he said of the 2023 stripe that it
  [was "off the end of the scale"](https://reading.ac.uk/news/2024/University-News/Climate-stripes-off-the-scale-for-hot-2023).
- **Colours**: the 8 most saturated classes of ColorBrewer's 9-class
  [Blues](https://colorbrewer2.org/#type=sequential&scheme=Blues&n=9) below the centre and
  [Reds](https://colorbrewer2.org/#type=sequential&scheme=Reds&n=9) above it, as in Hawkins'
  graphics: `#08306b #08519c #2171b5 #4292c6 #6baed6 #9ecae1 #c6dbef #deebf7` and
  `#fee0d2 #fcbba1 #fc9272 #fb6a4a #ef3b2c #cb181d #a50f15 #67000d`.
- **Precipitation** has no stripes of Hawkins' (his FAQ: "visual representations of the change in
  temperature"), so this is our extension of the method: the same centre, range and 16 classes,
  with the two halves of ColorBrewer's 11-class BrBG, brown for dry and teal for wet, 8 colours
  sampled at even steps along each.

The reference is calculated from the station's whole record and not from the years shown: a year
keeps its colour whatever `start_year` and `end_year` are, and the colours are the same in any unit.
The global graphic of Hawkins' is the exception (a fixed ±0.75 °C scale, its average
[1961 to 2010](https://www.reading.ac.uk/planet/climate-resources/climate-stripes)), and no station
here is.

### A station with too few years

Few of DWD's stations (and of GHCN's) have 30 years in 1971-2000 or 100 in 1901-2000, so a period that has too few
years with data is replaced by the station's **whole record**, for the mean and for the standard
deviation each on its own:

| | period of the method | years it needs | otherwise |
|---|---|---|---|
| mean (centre) | 1971-2000 | 20 | the mean of the whole record |
| standard deviation (range) | 1901-2000 | 30 | the standard deviation of the whole record |

A record of fewer than **10 years** with data is refused (HTTP 400, as is one with fewer than two
years in the years asked for). The standard deviation is the sample's (n - 1).

`stripes stations` (REST, command line and MCP, and so the app's station list and map) lists only stations
whose record, as DWD's description of the stations gives it, spans 10 or more calendar years (first to last year,
inclusive): one that does not could not be drawn. That is all the listing knows, so a station whose record has gaps is listed
where its span is long enough and is still refused if it has fewer than 10 years with values: measured on
2026-11-16, 5 of the 489 active temperature stations and 61 of the 2039 active precipitation stations
(23 of 1080 and 180 of 5697 of all of them). The other way round, 11 precipitation stations (none of them
active) have 10 or more years with values and a shorter span, and so are not listed; a request for one by its id
is answered.

Of the stations with annual data in DWD's historical files (`annual/climate_summary`,
`annual/precipitation_more`; the stripes read these only, and the recent files add 3 stations of
precipitation and no year), as measured on 2026-11-16:

| | temperature | precipitation |
|---|---|---|
| stations with annual values | 1161 | 6039 |
| the method as it is (both periods) | 403 | 3234 |
| whole record for the mean | 167 | 759 |
| whole record for the standard deviation | 60 | 271 |
| whole record for both | 427 | 1264 |
| refused (fewer than 10 years) | 104 | 511 |
| all 30 years of 1971-2000 | 214 | 1739 |

Every answer says which was used: the `reference` of `/api/stripes/values` names, for the centre and
for the spread, its `value`, the `first_year` and `last_year` and the number of `years` it is
calculated from, and `fallback`. Its `processing_note`, the `X-Wetterdienst-Processing` header of the
CSV and the image, says the same in a sentence, and the image prints the periods under the stripes.
The values have their `anomaly` to the centre, in the unit of the `value`, and their `stripe_class`,
0 (the lowest) to 15. The CSV of `/api/stripes/values` has the same two columns, and no longer
`value_scaled` (a min-max over the years shown).

At least two of the years asked for must have data. The JSON names the unit of the `value`s in
`series.unit`, e.g. `degree_celsius`: `degree_celsius` and `millimeter` unless the request chooses
another with `unit_targets` (see [REST API](#rest-api)), or the server's `WD_TS_CONVERT_UNITS` and
`WD_TS_UNIT_TARGETS` do, the target of the quantity where the values are converted, the source's
unit where not. The unit changes the numbers only (the reference and the anomaly are in it): the
classes and so the colours are the same in any unit.

The feature is exposed via the [command line interface](#command-line-interface) and the
[REST API](#rest-api). The hosted [web app](https://wetterdienst.eobs.org) also
offers an interactive Climate Stripes view.

## Command Line Interface

The `stripes` command group has two subcommands: `stations` and `image`. The command line has no
command for the yearly values the REST API answers at `/api/stripes/values`; `stripes values`, which
wrote the image until 0.172.0, is gone: `stripes image` writes it, and the name is not reused.

### Stations

List the stations for which climate stripes can be generated:

```bash
# Stations available for temperature stripes.
wetterdienst stripes stations --kind temperature

# Only currently active stations, as CSV.
wetterdienst stripes stations --kind precipitation --active true --format csv

# The stations of NOAA GHCN daily in a bounding box.
wetterdienst stripes stations --provider noaa --network ghcn --kind temperature \
  --left -75 --bottom 40 --right -73 --top 41
```

Its options are `--kind` (required), `--provider` and `--network` (default `dwd` and `observation`, see
[Sources](#sources)), `--active` (default `true`), `--left`, `--bottom`, `--right` and `--top` (a bounding box,
all four or none), `--format` (`json`, `geojson` or `csv`) and `--pretty`; the [command line reference](cli.md) has them
with their defaults.

### Image

Render the stripes image for a single station, selected either by `--station` (station id)
or by `--name` (fuzzy name match):

```bash
# Temperature stripes for station 1048 (Dresden-Klotzsche) written to a PNG file.
wetterdienst stripes image --kind temperature --station 1048 --target dresden.png

# Precipitation stripes selected by name, restricted to a year range, as SVG to stdout.
wetterdienst stripes image --kind precipitation --name Hohenpeissenberg \
  --start-year 1900 --end-year 2020 --format svg

# A station of NOAA GHCN daily: the years are calculated from its days.
wetterdienst stripes image --provider noaa --network ghcn --kind temperature --station USW00094728 \
  --target new_york.png
```

The options are `--kind` (required), `--provider` and `--network` (see [Sources](#sources)), `--station` or `--name` (with `--name-threshold`), `--start-year`, `--end-year`,
`--show-title`, `--show-years`, `--show-data-availability`, `--format` (`png`, `jpg`, `svg` or `pdf`), `--dpi` and
`--target`; the [command line reference](cli.md) has them with their defaults. The image needs the `plotting` extra.

A `--station` that no station has is a 404 over REST and a usage error on the command line, and so is a `--name`
that matches nothing. Where the lookup of the stations went without a directory of DWD's server (the stripes list
their stations from `annual/kl/historical` for the temperature and `annual/more_precip/historical` for the
precipitation) that came back empty or missing, or lists files and no description of its stations, a station may exist
and be listed only there. That is a 502 of the REST API whose `detail` names the directory, and exit 1 with the same
sentence on the command line. An empty or missing directory says nothing of its stations, so any `--station` the
lookup does not find gets it; a directory with files and no description names its stations in its file names, so only
an id among them does. Try again later.

## REST API

When the [REST API](restapi.md) is running, the same functionality is available via three
endpoints (the examples below use [httpie](https://github.com/httpie/cli)):

```bash
# List stations available for temperature stripes.
http localhost:7890/api/stripes/stations kind==temperature

# Get the underlying yearly values for a station.
http localhost:7890/api/stripes/values kind==temperature station==1048

# Render the stripes image for a station (write the binary body to a file).
http --download localhost:7890/api/stripes/image kind==temperature station==1048
```

The JSON answer of `values` has the `metadata` block every answer has, a `series` that says what the values
are of (`station`, `resolution`, `dataset`, `parameter`, and the `unit` of `value`), the `reference` the classes are
relative to (see [Method](#method)), and the `values`, each with its `anomaly` and `stripe_class`. The `value`s of DWD are its
own annual values, the same numbers as `/api/values` gives for the parameter; those of GHCN are calculated from its
daily values (see [Sources](#sources)), and `series` names the daily parameter. The `processing_note` of the block is the
plain note every answer has, and a sentence that says the anomalies and classes were calculated from them and which
reference they are relative to, the whole record included where it stood in for a period. An image has no place for it
in itself: the `X-Wetterdienst-Processing` header of `image` has it (as the CSV of `values` does), and adds "The image
is drawn from the provider's annual values." (for GHCN, whose note has said before that the years were calculated: "The
image is drawn from the annual values calculated above.")

`values` takes `unit_targets`, a JSON mapping of quantity to unit, as `/api/values` does, and refuses an unknown
quantity or unit with the same 400:

```bash
# The annual mean temperature in degree Fahrenheit; `series.unit` says `degree_fahrenheit`.
http localhost:7890/api/stripes/values kind==temperature station==1048 \
  'unit_targets=={"temperature": "degree_fahrenheit"}'
```

The MCP tool `stripes_values` takes it as an object (`{"unit_targets": {"temperature": "degree_fahrenheit"}}`). The
image draws no number or unit, so `image` takes no `unit_targets`, and the command line, which has no command for the
values, has none either. The precipitation takes `millimeter` or `liter_per_square_meter`.

`provider` and `network` choose the source (see [Sources](#sources)), and `stations` takes a bounding box. The
`image` endpoint accepts the same rendering options as the CLI (`start_year`,
`end_year`, `show_title`, `show_years`, `show_data_availability`, `format`, `dpi`): the command line
spells a name with hyphens (`--start-year`), REST and MCP with underscores (`start_year`).

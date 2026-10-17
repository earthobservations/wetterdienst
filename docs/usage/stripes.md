# Climate Stripes

Climate stripes (also known as
["warming stripes"](https://en.wikipedia.org/wiki/Warming_stripes)) are a minimalistic
visualization popularized by Ed Hawkins that encodes the long-term trend of a climate
variable as a sequence of coloured bars — one bar per year, coloured from blue (cooler) to red
(warmer) for temperature, and from brown (drier) to teal (wetter) for precipitation.

Wetterdienst can generate climate stripes from **DWD** annual observations for two kinds:

- `temperature` — based on the annual mean air temperature
- `precipitation` — based on the annual precipitation sum

The colours are scaled over the years shown: with `start_year` and `end_year`, the lowest and
highest of those years take the two ends of the colour map, so the coolest is blue and the warmest
red, or the driest brown and the wettest teal. At least two of the years must have data. The CSV of
`/api/stripes/values` gives each year's `value_scaled`, from 0 for the highest to 1 for the lowest.
Its JSON names the unit of the `value`s in the metadata's `unit`, e.g. `degree_celsius`. The
server's `WD_TS_CONVERT_UNITS` and `WD_TS_UNIT_TARGETS` set it, which a stripes request has no
parameter for: the target of the quantity where the values are converted, the source's unit where not.

The feature is exposed via the [command line interface](#command-line-interface) and the
[REST API](#rest-api). The hosted [web app](https://wetterdienst.eobs.org) also
offers an interactive Climate Stripes view.

## Command Line Interface

The `stripes` command group has two subcommands: `stations` and `values`.

### Stations

List the stations for which climate stripes can be generated:

```bash
# Stations available for temperature stripes.
wetterdienst stripes stations --kind temperature

# Only currently active stations, as CSV.
wetterdienst stripes stations --kind precipitation --active true --format csv
```

Its options are `--kind` (required), `--active` (default `true`), `--format` (`json`, `geojson` or `csv`) and
`--pretty`; the [command line reference](cli.md) has them with their defaults.

### Values

Render the stripes image for a single station, selected either by `--station` (station id)
or by `--name` (fuzzy name match):

```bash
# Temperature stripes for station 1048 (Dresden-Klotzsche) written to a PNG file.
wetterdienst stripes values --kind temperature --station 1048 --target dresden.png

# Precipitation stripes selected by name, restricted to a year range, as SVG to stdout.
wetterdienst stripes values --kind precipitation --name Hohenpeissenberg \
  --start-year 1900 --end-year 2020 --format svg
```

The options are `--kind` (required), `--station` or `--name` (with `--name-threshold`), `--start-year`, `--end-year`,
`--show-title`, `--show-years`, `--show-data-availability`, `--format` (`png`, `jpg`, `svg` or `pdf`), `--dpi` and
`--target`; the [command line reference](cli.md) has them with their defaults. The image needs the `plotting` extra.

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
are of (`station`, `resolution`, `dataset`, `parameter`, and the `unit` of `value`), and the `values`.

The `image` endpoint accepts the same rendering options as the CLI (`start_year`,
`end_year`, `show_title`, `show_years`, `show_data_availability`, `format`, `dpi`): the command line
spells a name with hyphens (`--start-year`), REST and MCP with underscores (`start_year`).

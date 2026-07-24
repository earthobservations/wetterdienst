# Climate Stripes

Climate stripes (also known as
["warming stripes"](https://en.wikipedia.org/wiki/Warming_stripes)) are a minimalistic
visualization popularized by Ed Hawkins that encodes the long-term trend of a climate
variable as a sequence of coloured bars — one bar per year, coloured from blue (cooler /
drier) to red (warmer / wetter).

Wetterdienst can generate climate stripes from **DWD** daily observations for two kinds:

- `temperature` — based on the annual mean air temperature
- `precipitation` — based on the annual precipitation sum

The feature is exposed via the [command line interface](#command-line-interface) and the
[REST API](#rest-api). The hosted [web frontend](https://www.wetterdienst.eobs.org) also
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

Options:

| option      | description                                          | default |
|-------------|------------------------------------------------------|---------|
| `--kind`    | `temperature` or `precipitation` (required)          | —       |
| `--active`  | only include stations that are still reporting       | `true`  |
| `--format`  | output format, one of `json`, `geojson`, `csv`       | `json`  |
| `--pretty`  | pretty-print the output                              | `false` |

### Values

Render the stripes image for a single station, selected either by `--station` (station id)
or by `--name` (fuzzy name match):

```bash
# Temperature stripes for station 1048 (Dresden-Klotzsche) written to a PNG file.
wetterdienst stripes values --kind temperature --station 1048 --target dresden.png

# Precipitation stripes selected by name, restricted to a year range, as SVG to stdout.
wetterdienst stripes values --kind precipitation --name Hohenpeissenberg \
  --start_year 1900 --end_year 2020 --format svg
```

Options:

| option                     | description                                                    | default |
|----------------------------|----------------------------------------------------------------|---------|
| `--kind`                   | `temperature` or `precipitation` (required)                    | —       |
| `--station`                | station id to plot                                             | —       |
| `--name`                   | station name to plot (fuzzy match)                             | —       |
| `--start_year`             | first year to include                                         | —       |
| `--end_year`               | last year to include                                          | —       |
| `--name_threshold`         | similarity threshold (0–1) for `--name` matching             | `0.80`  |
| `--show_title`             | draw the station name as a title                             | `true`  |
| `--show_years`             | draw the first and last year as axis labels                  | `true`  |
| `--show_data_availability` | draw a marker for the data availability                      | `true`  |
| `--format`                 | image format, one of `png`, `jpg`, `svg`, `pdf`              | `png`   |
| `--dpi`                    | image resolution in dots per inch                            | `300`   |
| `--target`                 | write the image to this file instead of stdout               | —       |

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

The `image` endpoint accepts the same rendering options as the CLI (`start_year`,
`end_year`, `show_title`, `show_years`, `show_data_availability`, `format`, `dpi`).

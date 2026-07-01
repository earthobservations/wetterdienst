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

- `[i18n]` Full internationalisation foundation: 11 locales (de, de-hh, en, fr, es, it, pl,
  nl, cs, da, lb) covering every page and component. Language switcher in the settings panel
  with flag icons. i18n key linting added to CI.
- `[i18n]` Hamburg-slang German locale (Hamburgisch / `de-hh`) with regional idioms.
- `[i18n]` Luxembourgish (`lb`), Danish (`da`), Dutch (`nl`), Czech (`cs`), Polish (`pl`),
  Italian (`it`), Spanish (`es`), and French (`fr`) translations.
- `[Settings]` Persistent settings store (Pinia, Zod-validated) for unit system, theme,
  language, and climate-stripes display toggles — survives page reloads via localStorage.
- `[Home]` Friendly task-oriented home page replacing the generic landing screen.
- `[Explorer]` Beginner-friendly preselection flow replaces the previous Simple/Expert mode
  toggle; the next required field is highlighted to guide users through the selection.
- `[Explorer]` Friendly parameter glossary so users can identify what each dataset parameter
  means without domain knowledge.
- `[Meteogram]` Optional map-based station picker on the meteogram page (lazy-loaded station
  list, single-select, collapsible). Visual "or choose on map" divider makes the option
  discoverable.
- `[Meteogram]` MOSMIX model run selector: available runs are fetched live from the
  `/api/issues` endpoint and presented in a dropdown; defaults to the latest run.
- `[Meteogram]` Forecast horizon selector (`24h | 3d | 7d | All`) in the chart toolbar.
  Clips the x-axis, tick labels, day annotations, midnight separators, and the "now" marker
  to the chosen window. Resetting zoom also clears the horizon to All. Translated across
  all 11 locales.
- `[Legal]` Legally-structured Impressum page with operator address and inclusive/
  anti-fascist values statement.

### Changed

- `[Meteogram]` Replace the custom debounced-API station search (with 2-character minimum
  and manual portal/positioning code) with a `USelectMenu` that loads all MOSMIX stations
  once and filters client-side. All station dropdowns (Meteogram, Explorer, Climate Stripes,
  Interpolation/Summary) now use `virtualize` for virtual-scrolled rendering so only visible
  rows are in the DOM regardless of list size.
- `[History]` History page now uses the shared `ParameterSelection` component (with
  `:show-parameters="false"`) instead of inline provider/network/resolution/dataset
  dropdowns, ensuring consistent behaviour and styling with the Explorer.
- `[All pages]` Unified page header structure: centred `h1` title with a gray subtitle
  paragraph across all pages. Station selection cards renamed to "Data Source" /
  "Datenquelle". Stripes and Support pages restructured for consistency.

### Fixed

- `[Meteogram]` Fix x-axis tick labels overlapping on narrow mobile screens. Tick interval
  is now chosen based on actual chart pixel width; day-name annotations shorten to
  weekday-only when a day occupies fewer than 44 px.
- `[Meteogram]` Fix wind barb artefacts appearing when zooming the chart.
- `[Meteogram]` Replace overflowing summary metrics cards with a compact single-row stat
  strip that works at all viewport widths.
- `[Meteogram]` Fix OpenStreetMap tiles not loading due to a missing `Referer` header.
- `[Meteogram]` Fix map centre-toggle button label not updating after the first click.
- `[Meteogram]` Fix toolbar overflow on narrow screens: panel toggles and horizon selector
  are grouped as a wrapping left block; right-side controls gain `shrink-0`. Timezone label
  and compact toggle text hide below the `sm` breakpoint.
- `[Meteogram]` Fix poor touch experience on mobile: Plotly defaults to pan mode on touch
  devices, preventing pinch gestures from conflicting with page scroll.
- `[i18n]` Tag English locale as `en-GB` to match British copy and flag.

## [0.6.0] - 2026-06-18

### Added

- Add Meteogram page with DWD MOSMIX hourly forecast visualization (temperature & dew point, wind speed & gusts with meteorological wind barbs, precipitation by phase, cloud cover by altitude, atmospheric pressure)
- Timezone-aware day/night bands derived from station coordinates via SunCalc and tz-lookup
- Compact overview mode with emoji weather icons, min/max temperature and precipitation per day
- Summary metrics cards (min/max temp, total precip, max gust, avg cloud cover, pressure range)
- Interactive panel visibility toggles for each chart panel
- Embeddable widget page at `/widget?station=XXXXX` with minimal chrome for iframe embedding; supports `?theme=dark|light`
- Widget link button in meteogram chart header to open the current station as a widget in a new tab

## [0.5.0] - 2026-06-09

### Added

- Sync history page form state (resolution, dataset, stations, sections) with URL query parameters for shareable links
- Add collapsible about section to history page explaining available history sections and DWD-only availability
- Add history endpoint and usage example to the API reference page
- Add full-screen overlay mobile navigation with fade and slide transition, including nav items, external links and theme toggle
- Set green as fixed primary color via `app.config.ts`
- Chore: update @duckdb/duckdb-wasm and @vitest/expect versions

### Removed

- Remove primary color picker from header
- Remove `ColorModeSelect` and `PrimaryColorSelect` components, inline color mode toggle directly in header
- Remove separate `frontend.dev.Dockerfile`; merged into a single `frontend.Dockerfile` with named `base`, `deps`, `dev`, `build`, and `prod` targets

### Changed

- `compose.yml` updated to use `docker/frontend.Dockerfile` with `target: dev`
- CI workflow updated to build with `target: prod`

### Fixed

- Add `confirmModulesPurge: false` to `pnpm-workspace.yaml` to prevent pnpm aborting with no-TTY error when restarting the dev container
- Replace `0.0.0.0` with `localhost` as default API base URL to fix Chrome blocking connections to `0.0.0.0` (Private Network Access)
- Delete `ColorModeSelect` component tests that referenced the removed component, fixing typecheck failure
- Override `semver@6` → `^7` and `apache-arrow>@types/node` → `^25` in `pnpm-workspace.yaml` to remove packages flagged by `trustPolicy: no-downgrade`, fixing `pnpm typecheck`

## [0.4.0] - 2026-02-17

### Added

- Add timeseries and trendline overlays to stripes visualization
- Add image download in PNG, JPG, and SVG formats for stripes
- Add collapsible settings with toggleable display options (title, years, source, data availability)
- Add DuckDB query component for direct SQL querying on data

### Changed

- Use new backend API endpoint for climate stripes data
- Reorganize stripes UI with collapsible settings section
- Match layout of API page with other pages for consistency
- Stripes: Fix dimensions for image download

### Remove

- Remove image response handling and related query interface

## [0.3.0] - 2026-02-05

### Added

- Add station history page

### Changed

- Fix setting interpolation and summary settings
- Unify data fetching logic across all pages

## [0.2.0] - 2026-01-22

### Added

- Add header version badge showing frontend (FE) and backend (BE) versions
- Add parameter label format selector to `DataViewer` with support for dataset and resolution prefixes

### Changed

- Sync stripes page state with URL (station, kind, options) to keep selection in address bar and enable direct linking
- Replace Getting Started card with a collapsible section in the explorer view for a cleaner UI
- Make backend API base URL configurable via `NUXT_PUBLIC_API_BASE` / `API_BASE` and include its origin in CSP
  `connect-src`
- Minor refactoring across app, explorer, and config files

## [0.1.0] - 2026-01-04

### Added

- Initial release: Modern Nuxt.js-based web application providing interactive data exploration, comprehensive settings
  interface for all API parameters, climate stripes visualization, theme customization, and enhanced user experience
- Add Andreas Motl to authors list
-

[Unreleased]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.6.0...HEAD

[0.6.0]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.5.0...frontend-v0.6.0

[0.5.0]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.4.0...frontend-v0.5.0

[0.4.0]: https://github.com/earthobservations/wetterdienst/releases/tag/frontend-v0.3.0...frontend-v0.4.0

[0.3.0]: https://github.com/earthobservations/wetterdienst/releases/tag/frontend-v0.2.0...frontend-v0.3.0

[0.2.0]: https://github.com/earthobservations/wetterdienst/releases/tag/frontend-v0.1.0...frontend-v0.2.0

[0.1.0]: https://github.com/earthobservations/wetterdienst/releases/tag/frontend-v0.1.0
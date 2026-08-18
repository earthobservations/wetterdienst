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

- `[API]` The API page documents the MCP endpoint the app has been serving unannounced: what it is,
  the URL, a ready-to-paste client configuration, and that it needs no key or account. The URL is
  built from the origin the page is served from rather than hard-coded, so a self-hosted or local
  instance shows its own address and the snippet can be copied as-is. The card appears only when
  the backend reports `mcp_enabled`: the endpoint is behind an optional extra, and an instance
  installed without it would otherwise hand every visitor a client configuration pointing at a 404
- `[About]` A page at `/about` carrying what the home page used to say about the project, plus a
  proper introduction to the maintainer -- what he works on, where he is, how to reach him -- and a
  flat entry for the co-author, with a pointer to the full contributor list. Reachable from the
  footer and from the bottom of the home page
- `[About]` LinkedIn and Mastodon next to the GitHub and email buttons in the maintainer card. The
  Mastodon link carries `rel="me"`, so the profile there can verify the link back to this site
- `[Home]` A "what data you get" section, which is what a first-time visitor actually needs: the
  headline numbers, all 22 weather services named with their flags, and the six kinds of data
  behind them -- measurements, forecasts, water levels, radar, warnings and road weather. The
  provider list is pinned to the backend registry by
  `tests/test_frontend_i18n.py::test_frontend_home_lists_every_provider`, so a provider added
  upstream fails a test rather than quietly going unmentioned

- `[Glossary]` A page at `/glossary` listing every canonical parameter with what it measures and the
  unit its values come back in, searchable by name or description and filterable by quantity. It
  reads `GET /api/glossary`, which the backend has served all along without anything using it
- Curated labels for the nine locales that had none. `cs`, `da`, `de-hh`, `es`, `fr`, `it`, `lb`,
  `nl` and `pl` fell back to English before, since only `en.ts` and `de.ts` existed
- Labels for the parameters the backend has since introduced: the cloud cover and visibility
  measurement methods, the visibility class, the ground state, ice on the wet bulb, and the true
  solar time offset
- `[All pages]` Glossary labels for the new `radiation_global_intensity`,
  `radiation_sky_long_wave_intensity` and `radiation_sky_short_wave_diffuse_intensity` parameters,
  which the backend introduced for sources reporting irradiance (W/m²) rather than irradiation
  accumulated over the interval (J/cm²). Affects KNMI (10 minutes), MeteoSwiss, met.no, RMI and
  Geosphere (10 minutes and hourly), whose radiation parameters are served under the new names.

### Changed

- `[Home]` The project description and the author avatars are gone from the home page, which is
  about the data now; both live on `/about`
- `[Home]` The features section is two cards rather than four, and titled for what it actually
  lists: what you can do with the data. "Multiple data sources" repeated the 22-service card, the
  `0 €` tile and the intro line; "geospatial queries" repeated the Explorer card's own pitch. What
  is left is export formats and interpolation/summarization, neither of which the page says
  anywhere else
- `[Home]` The values statement closes the page instead of sitting between the task cards and the
  data, where it interrupted the path from "what would you like to do" to "what data you get". The
  footer carries the same stance on every page regardless
- `[All pages]` Support leaves the main navigation, which is now seven entries with one rule
  between them: they are all things you do with weather data. Support is about the project, like
  About and the legal notice, so it joins them -- as a heart in the header's project links, where
  "sponsor this" is conventionally found, and as a footer link. It is in the mobile menu's bottom
  bar for the same reason it is in the desktop header
- `[Home]` Only the cards that go somewhere answer the pointer. The two feature cards lifted and
  ringed on hover exactly like the task cards above them, but nothing happens when you click one --
  a hover state is how a card promises it is a link, and those two were promising nothing
- `[All pages]` The footer is two rows split by kind -- copyright and links on one, the stance on
  its own line -- rather than one list of six items where "Love who you want" sat in the same
  register as "About", separated by the same pipe. The separators were flex siblings that cannot
  see where a line breaks, so a wrapped row ended on a dangling one; each row owns its separators
  now, and below the `sm` breakpoint the links row drops them for wider gaps instead

- `[Explorer]` The settings drawer held the app's only raw form controls -- seven `<input>` and one
  `<select>` with hand-maintained borders, padding and `dark:` variants, and none of the focus or
  accessibility behaviour the rest of the app gets from the design system. They are `UInputNumber`,
  `UInput` and `USelect` now, with min/max/step as real props, and the parameter-name field marks
  an unknown parameter with `highlight` rather than open-coded red border classes
- `[Glossary/Forecast/Widget]` Empty and no-data states use `UEmpty` instead of three differently
  styled paragraphs of muted text; the glossary shows a real loading state while fetching
- `[Parameter selection]` Follow the nested shape `GET /api/coverage` now returns. Datasets were
  listed with `Object.keys()` over the resolution, which answers `["description", "datasets"]`
  under the new shape, and the dataset was indexed as a list of parameters. Both now read through
  `datasets` and `parameters`, and the types gain `CoverageResolution` and `CoverageDataset` plus a
  `description` on `CoverageParameter`
- `[Parameter selection]` Show what the shape change makes reachable: the resolution and dataset
  selects carry the source's own description as help text, and each parameter in the menu shows its
  description beneath the label

### Fixed

- `[Explorer]` Plotly, at 1.0 MB the largest chunk in the build, was fetched and parsed as soon as
  the data viewer mounted -- before any chart existed, and regardless of the view mode, which
  defaults to the table. It is fetched the first time a chart is actually rendered now, so opening
  Explorer and reading the table no longer pays for it. Explorer is the only page that mounts the
  data viewer. This is not an initial-page-load fix: the viewer mounts after a query is run, and
  Explorer measures the same as the other pages on first load
- `[Explorer/History]` The station list was fetched twice, 332 KB each time for DWD daily climate
  summary. `useFetch` refetches on its own when its reactive query changes, and `fetchStations()`
  also calls `refresh()`; the request is driven explicitly here, so the automatic watch is off now.
  Measured in a browser against a local build: one request where there were two. Changing
  parameters with a picker open refetches explicitly, which the automatic watch used to cover --
  without it an expanded map lost its markers and stayed empty until it was reopened
- `[Explorer]` The parameter `<datalist>` was rendered inside the `v-for` over distance rows, so
  every row repeated the same element id. It is emitted once for all of them now
- `[All pages]` `cloud_cover_total_index` and `cloud_height` were labelled but no longer exist: the
  first was renamed `cloud_cover_total_measurement_method` upstream, the second has always been
  per-layer. Both labels silently stopped applying; they now name the parameters that exist
- The i18n guard covered German and English only, while nine further catalogs went unchecked --
  which is how `dataViewer.fetchError` and `dataViewer.fetchErrorToastTitle` came to be missing from
  all nine. It now checks every locale, and the glossary catalogs too
- `[All pages]` 464 of the 514 parameters the backend serves had no label and fell back to the
  prettified raw id -- "Chlorid Concentration", "Soil Moisture Winterwheat Loamysilt 00cm 60cm" --
  which reads as English whichever language was selected. All eleven catalogs now cover every
  parameter, including the agrometeorological long tail
- `[Glossary]` Parameters were listed in the order the API returns them, which is by raw id and
  bears no relation to the order of the labels on screen once those are translated. They are sorted
  by their label in the active language now, with the quantity filter's options likewise. The
  comparison is a locale collator, not the default one: Czech treats "ch" as a letter sorting after
  "h", German ignores the umlaut, and a code-point sort gets both wrong
- `[Glossary]` The quantity filter listed the backend's own ids ("energy per area", "wind scale")
  in every language, though translations existed for most of them. Six quantities had no label in
  any language at all: degree hours, dimensionless, mass per volume, significant weather, turbidity
  and wind scale. All twenty-three are named in all eleven languages now
- `[Explorer/Glossary]` Four pairs of distinct parameters shared one label in all eleven languages,
  so the picker showed two identical rows and one of each pair was labelled with the other's
  meaning: `count_days_heating_degree` is a count of days, `heating_degree_day` the summed
  temperature shortfall, and both read "Heating degree days". Same for the cooling day and cooling
  hour pairs, which `dwd/derived` serves together, and for `temperature_air_2m` against
  `temperature_air_mean_2m`, which `noaa/ghcn` serves together. The counts are named as counts now,
  and the mean temperature as a mean
- `[Glossary]` French, Spanish and Italian dropped the "soil" head noun from every covered soil
  temperature, leaving "Température maximale sous gazon (20 cm)" indistinguishable in kind from an
  air temperature. The head noun was dropped to avoid "Température du sol sous sol nu", but that
  only repeats where the cover names the soil itself, so it is kept everywhere else now
- The production image never copied `frontend/shared`, though seven components import types from
  it. Every one of those is an `import type`, which the transpiler strips before
  resolving, so the image built regardless -- and would have kept building until the first value
  exported from `shared/` turned one of those into a real import and broke the deploy instead. The
  `dev` target copies the whole of `frontend/`, so only production was ever a step away from this

## [0.12.1] - 2026-08-02

### Security

- `[Build]` Resolve all 15 `pnpm audit` advisories (1 critical, 10 high, 3 moderate, 1 low) in the
  frontend dependency tree. Refreshed transitive dependencies within their existing ranges via
  `pnpm update`, and added two scoped `pnpm` overrides for advisories that intermediate packages
  pinned below the fix: `brace-expansion` (ReDoS) to `^5.0.8` and `esbuild` (dev-server file read,
  GHSA-g7r4-m6w7-qqqr) to `^0.28.1`. `pnpm audit` now reports no known vulnerabilities.

## [0.12.0] - 2026-07-28

### Fixed

- `[API]` Return `404` for `/.well-known/oauth-*` on the app origin instead of letting the SPA
  catch-all serve a `200` HTML page there, so MCP clients such as Claude Desktop treat the proxied
  `/mcp` server as no-auth and connect without failing OAuth Dynamic Client Registration.

## [0.11.0] - 2026-07-27

### Added

- `[API]` Proxy the backend's `/mcp` (Model Context Protocol) endpoint through the frontend so it is
  reachable on the app origin (e.g. `wetterdienst.eobs.org/mcp`), preserving the streamable-HTTP
  transport (POST + SSE + the `mcp-session-id` header).

### Changed

- `[Build]` Bumped frontend dependencies within their existing ranges (nuxt 4.5, vue 3.5.40,
  tailwindcss 4.3.3, plotly 3.7, luxon 3.7.2, playwright 1.62, vitest 4.1.10, oxlint/eslint,
  and others). Bumped `@nuxt/test-utils` to 4.1.0, whose nuxt vitest environment drops the
  `vitest/environments` import and `transformMode` option deprecated in Vitest 4 (now using
  `vitest/runtime` and `viteEnvironment`), removing the deprecation warnings from the test run.
  TypeScript is held at 5.x: the current vue-tsc cannot load TypeScript 7's native compiler,
  which breaks `nuxt typecheck`.

## [0.10.0] - 2026-07-10

### Fixed

- `[Build]` Silenced the `@tailwindcss/vite` "Sourcemap is likely to be incorrect"
  warning that flooded the production build log on every CSS chunk; the plugin doesn't
  emit sourcemaps for its transform yet (upstream limitation), so the warning was
  purely cosmetic.
- `[Explorer]` Failed value requests (e.g. auth misconfiguration or upstream provider
  errors) were silently swallowed: the data viewer never inspected the fetch `error`,
  so any failure looked identical to "no query run yet", showing the generic
  "select parameters and stations" hint with no indication anything went wrong.
  The actual error message is now shown in the data viewer and as a toast.
- `[History]` Provider and network were freely selectable from all 10 supported
  providers, even though History is DWD-observation-only. The selects are now
  disabled and locked to `dwd`/`observation`; Explorer is unaffected and keeps full
  provider/network choice.
- `[Explorer]` Opening Explorer with no existing selection auto-selected daily
  climate-summary data and every one of its parameters, which made the page feel
  like it hung for a couple of seconds before becoming interactive. Provider,
  network, resolution, dataset, and parameters are now all left unset for the
  user to pick explicitly.
- `[Explorer/History]` Station map rendered as blank white space: the
  "removed the global Leaflet plugin" change below assumed `<LMap
  use-global-leaflet>` sets `window.L` itself, but it only reads it -- nothing
  ever set it, so the map's `mounted` hook threw before rendering any tiles.
  `window.L` is now set from within the map component itself (still
  lazy-loaded, so the fix doesn't reintroduce the bundle-size regression the
  removal fixed).
- `[Explorer/History]` The station picker (select menu or map) fetched the full
  station list as soon as a dataset's parameters were chosen, even before the
  user opened it. It's now fetched lazily on first open of either the select
  menu or the map, except when restoring a station preselected via a shared URL.
- `[Explorer/History]` A failed station list fetch (e.g. transient network/
  backend error) was still marked as "loaded", so reopening the picker never
  retried and the empty result looked like a confirmed "no stations found"
  instead of a failed request. A failed fetch now resets the loaded state
  (retried on next open) and shows a distinct error message.
- `[History]` `ParameterSelection`'s provider/network restriction (used by
  History to lock to DWD/observation) silently fell back to showing every
  provider/network, unrestricted, if the restricted value wasn't actually
  offered by the backend (e.g. a stale restriction or missing auth config).
  A mismatch now shows a clear error instead of a confusingly half-locked form.
- `[Explorer/History/Stripes/Meteogram]` Each page's URL-sync watcher fired
  `router.replace()` without handling a rejected navigation (e.g. one
  superseded by a subsequent `replace()` before it resolves), an unhandled
  promise rejection Vue Router is known to produce. Each call now has a
  no-op `.catch()`.

### Changed

- `[Performance]` Switched from `plotly.js-dist-min` to `plotly.js-basic-dist-min`
  (only `scatter` and `bar` traces are used across Meteogram, Explorer, and Stripes),
  cutting the lazily-loaded Plotly chunk from ~4.8 MB to ~1.1 MB (~1.45 MB to ~0.37 MB
  gzipped).
- `[Performance]` Removed the eager global Leaflet plugin: `leaflet` and
  `leaflet.markercluster` (~450 KB) were being bundled into every page's initial load,
  even pages with no map. The map components already lazy-load Leaflet themselves via
  `@vue-leaflet`'s `use-global-leaflet` mechanism, so pages without a station map (API
  docs, Impressum, etc.) no longer pay for it.
- `[Performance]` Replaced the 400×400 `favicon.ico` (actually a mislabeled PNG, 160 KB)
  with a properly-sized 128×128 version (~19 KB), used both as the browser tab icon and
  the in-page logo (rendered at 20-28px in the header and widget pages).

## [0.9.0] - 2026-07-07

### Fixed

- `[Explorer]` Parameters selector was invisible due to Vue 3 boolean prop casting:
  `showParameters?: boolean` was silently cast to `false` when not passed by the parent,
  making the field hidden in the Explorer. Fixed with `withDefaults({ showParameters: true })`.
- `[Explorer]` All parameters for the selected dataset are now auto-selected when a
  dataset is chosen (initial load and on dataset change). URL-specified parameters are
  preserved if still valid; otherwise all parameters are selected as the default.

### Added

- `[Explorer]` The date range selector is now marked required for providers that need a
  date range for value queries (e.g. MET Norway Frost), reflecting the backend's
  `date_required` coverage flag instead of always showing "optional".
- `[Explorer]` When a date range is required and stations are selected, the date range
  auto-fills from the min start date / max end date across the selected stations
  (stations still collecting data are treated as ending today).

## [0.8.0] - 2026-07-06

### Added

- `[Meteogram]` Forecast model run (`issue`), horizon filter (`horizon`), visible panels
  (`panels`), and compact mode (`compact`) are now synced to the URL. Sharing or
  bookmarking the page restores the full view state.
- `[Stripes]` `show_timeseries`, `show_trendline`, and `show_source` toggles are now
  persisted in the URL, consistent with the other `show_*` parameters already synced.
- `[Explorer]` Data-settings toggles (`shape`, `humanize`, `convertUnits`, `dropNulls`,
  `skipEmpty`) are now persisted in the URL so the selected data view is shareable.

### Changed

- `[Explorer]` Provider/network combinations that require authentication are now hidden
  from the parameter selector unless credentials are both present (`configured`) and
  verified (`valid`) by the backend. This prevents selecting a provider that cannot be
  used without a working API key.

## [0.7.0] - 2026-07-02

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
- `[Explorer]` Interpolation and summary modes now display a one-liner description beneath
  the mode selector and a collapsible "How it works" panel. Interpolation explains the
  Delaunay triangulation approach (synthetic estimate at exact coordinates); summary explains
  the nearest-neighbour lookup (real measurement from the closest station with data). The
  contrast between estimated and measured values is explicit. DE/EN translated; other locales
  fall back to EN.

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
- `[All pages]` Lucide icons added to all card headers, action buttons, empty states, and
  status elements throughout the app (including the `ParameterSelection` component).

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
- `[Meteogram]` Fix `selectedIssue` not resetting when switching stations — stale run from
  the previous station no longer bleeds into the next fetch.
- `[Stripes]` Fix display toggles (title, years, source, data availability, timeseries,
  trendline) not persisting across page reloads; they are now written back to the settings
  store on every change.
- `[E2E]` Fix strict mode violation in Playwright navigation test — stripes link selector
  now scoped to the navigation element to avoid matching the home page card.
- `[Mobile]` Fix settings inaccessible on mobile — replace non-functional `UPopover` inside
  the fullscreen overlay with a direct link to `/settings`.
- `[Explorer]` Fix mode/station/data-source cards collapsing when switching dataset or
  provider/network — show them as soon as a dataset is selected instead of requiring
  parameters to be chosen first. Also prevent stale coverage data from blocking the
  resolution and dataset dropdowns during a network-coverage reload.
- `[Explorer]` Add friendly EN/DE labels for all missing dataset names across every
  provider: `weather_phenomena_more`, `water_equivalent`, MOSMIX-S/L, ICON, ICON-EU,
  urban-climate datasets, DWD derived products, IMGW datasets, and the generic
  `data` dataset used by NOAA, Geosphere, ECCC, and others.
- `[Footer]` Move FE/BE version display from the header to the footer; show as a
  two-row layout with coloured "Frontend" / "Backend" labels and muted version numbers.

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

[Unreleased]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.12.1...HEAD
[0.12.1]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.12.0...frontend-v0.12.1
[0.12.0]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.11.0...frontend-v0.12.0
[0.11.0]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.10.0...frontend-v0.11.0
[0.10.0]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.9.0...frontend-v0.10.0
[0.9.0]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.8.0...frontend-v0.9.0
[0.8.0]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.7.0...frontend-v0.8.0
[0.7.0]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.6.0...frontend-v0.7.0
[0.6.0]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.5.0...frontend-v0.6.0
[0.5.0]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.4.0...frontend-v0.5.0
[0.4.0]: https://github.com/earthobservations/wetterdienst/releases/tag/frontend-v0.3.0...frontend-v0.4.0
[0.3.0]: https://github.com/earthobservations/wetterdienst/releases/tag/frontend-v0.2.0...frontend-v0.3.0
[0.2.0]: https://github.com/earthobservations/wetterdienst/releases/tag/frontend-v0.1.0...frontend-v0.2.0
[0.1.0]: https://github.com/earthobservations/wetterdienst/releases/tag/frontend-v0.1.0
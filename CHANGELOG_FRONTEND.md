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

- Sync history page form state (resolution, dataset, stations, sections) with URL query parameters for shareable links
- Add collapsible about section to history page explaining available history sections and DWD-only availability
- Add history endpoint and usage example to the API reference page
- Add full-screen overlay mobile navigation with fade and slide transition, including nav items, external links and theme toggle
- Set green as fixed primary color via `app.config.ts`

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

[Unreleased]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.4.0...HEAD

[0.4.0]: https://github.com/earthobservations/wetterdienst/releases/tag/frontend-v0.3.0...frontend-v0.4.0

[0.3.0]: https://github.com/earthobservations/wetterdienst/releases/tag/frontend-v0.2.0...frontend-v0.3.0

[0.2.0]: https://github.com/earthobservations/wetterdienst/releases/tag/frontend-v0.1.0...frontend-v0.2.0

[0.1.0]: https://github.com/earthobservations/wetterdienst/releases/tag/frontend-v0.1.0
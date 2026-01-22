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

[Unreleased]: https://github.com/earthobservations/wetterdienst/compare/frontend-v0.1.0...HEAD

[0.1.0]: https://github.com/earthobservations/wetterdienst/releases/tag/frontend-v0.1.0
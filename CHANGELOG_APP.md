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

### Changed

- `[Design]` A new look in the logo's colours: the home page asks for a place first and shows its
  weather now, its forecast, climate stripes and nearby measurements; the place is kept in the
  browser (`wd_place`, named in the privacy policy). The header names the forecast, stripes and
  explorer, a menu holds every page, and a search (its button, or Ctrl+K / ⌘K on any page) finds
  the pages, the appearance and language settings and the places. Every page shares one width and
  gutter, the head of the page shows a sky of the place's time of day and weather, and the text is
  set in Figtree, served by the app itself (GH-3518)

## [0.39.0] - 2026-10-28

### Security

- `[Dependencies]` The lock file no longer holds `qs` 6.16.0 (GHSA-6pq8-jhm2-2vcw): it is
  floored at 6.16.1 by an override. The app never loads it (DuckDB-WASM declares it and its
  files do not use it), so the shipped app was not affected. The `happy-dom` of the test
  environment is 21.0.4 (GHSA-834v-8h66-3h79); it is a dev dependency and not in the app.
  The CSP end-to-end test now reads script tags in any letter case (GH-3515)

## [0.38.0] - 2026-10-27

### Added

- `[Licences]` The app serves the licence notices of the packages in the browser bundle (Leaflet,
  Vue, Plotly, DuckDB-WASM, Swagger UI, ...) at `/third-party-licenses.txt`, linked from the
  footer as "Third-party licences". The production build writes it from the packages' own licence
  files, so it is also in the Docker image and the release tarball. It adds the licences of the
  code inside the DuckDB-WASM, Plotly and marker cluster files, and names the one library whose
  package and repository ship none. It lists what was found and is no guarantee of completeness
  (GH-3469)
- `[Search]` The app can be found by a search engine: every public page has a descriptive title
  and description, a canonical link and `og:`/`twitter:` tags (the widget, the settings, a
  provider's page and unknown paths have no canonical link), and the server writes them, with a
  `<noscript>` text that links the pages, into the HTML it sends, for a crawler or link preview
  that runs no script. `/sitemap.xml` lists the public pages and `/robots.txt` names it; both take
  their addresses from the new setting `NUXT_PUBLIC_SITE_URL` (default
  `https://wetterdienst.eobs.org`, read when the server starts): set it to the address of your own
  instance. `/robots.txt` is a server route now, not a file, with the same rules as before
  (everything allowed). `/widget` and `/settings` ask not to be indexed (GH-3497)

### Changed

- `[Map]` The station map loads no image from Cloudflare or GitHub any more: its markers are
  Leaflet's own images, served by the app, and the selected marker is the same image tinted green
  and drawn larger. The Content Security Policy's `img-src` drops `cdnjs.cloudflare.com` and
  `raw.githubusercontent.com`, and the privacy policy no longer names them (GH-3420)

### Fixed

- `[Search]` An unknown path that ends in `.xml` or `.txt` (`/sitemap_index.xml`, `/ads.txt`) is a
  404 and no longer the app's page with a 200, which a crawler read as the file (GH-3497)
- `[Layout]` The page for an unknown address has its back button again: Nuxt's own page drew it
  with an inline script, which the Content Security Policy refuses. The app draws the page itself
  now, in the app's language (it was English, with no `lang` on the document), with a link to the
  home page and a back button where there is a page to go back to (GH-3453)

### Security

- `[Build]` `serialize-javascript`, which the bundler uses at build time and which is not in the
  app's output, is held to 7.1.3 or later through a `pnpm-workspace.yaml` override (the lockfile
  has 7.1.4), which resolves its Dependabot alert (GH-3096)
- `[Proxy]` The `/mcp` proxy sends a request on only to the backend's `/mcp` and below: a path that
  resolves elsewhere (such as `/mcp/../health`) is answered a 404 problem, as the `/api` proxy
  answers one, and is not asked of the backend (GH-2607)

## [0.37.0] - 2026-10-26

### Changed

- The app has a new icon: four weather tiles (sun, rain, wind, temperature). It is the tab icon
  (`/icon.svg`, with a 32 px `/favicon.ico` for browsers that ask for that), the iOS home-screen
  icon (`/apple-touch-icon.png`) and the logo in the header and the widget. `/favicon.ico` is a
  real ICO now, no PNG under that name. The 0.36.0 image was built before the icon was merged and
  has none of these files (GH-3431)

### Security

- `[Security headers]` The Content Security Policy lists only the hosts the app loads from: it no
  longer allows images from `unpkg.com`, which nothing loads, nor fonts from any `https:` host, as
  the app uses no web font (GH-2607)
- `[Widget]` `/widget` can be put in a frame of another site, as its documentation says it can:
  the server sends it `frame-ancestors *` and no `X-Frame-Options` when the request line is
  `/widget` or `/widget/`, the one page that is. Every other page, and `/widget` written another
  way (`/Widget`, `/%77idget`, `/widget//`), answers only to the app's own origin. Behind a proxy
  that rewrites the path, the server cannot see the spelling, so the page itself draws nothing
  outside `/widget` while it is framed by another site. A self-hosted app gets the
  same, there is no setting. The docs have an `<iframe>` to copy (GH-2607)

## [0.36.0] - 2026-10-25

### Added

- `[Docker]` The app image has a `HEALTHCHECK`: it asks the page at `/` on the server's own port
  every 30 s, which does not ask the backend and is outside the rate limit, so `docker ps` shows
  `healthy` or `unhealthy` for the app alone. A platform without a health check of its own routes
  through a proxy such as Traefik on this one. `docker run --no-healthcheck` switches it off
  (GH-3346)
- `[Legal]` A privacy policy (Datenschutzerklärung) at `/datenschutz`, also served at `/privacy`
  and linked in the footer next to the legal notice. It is in German, the binding text, for the
  German locales and in English for every other language, and names the logs, the cookie and
  local storage, and the third parties the map and the About page load images from (GH-3402)

### Changed

- The backend URL is private runtime config now, so no page carries it any more. Set it with
  `NUXT_API_BASE` (the compose file and the docs do); the old `NUXT_PUBLIC_API_BASE` is read
  while `NUXT_API_BASE` is not set, so a deployment keeps working until it is renamed (GH-3096)
- `[Build]` `compose.yml` publishes the app on `127.0.0.1:4000`, no longer on every interface; set
  `WETTERDIENST_BIND_HOST=0.0.0.0` to open it to the network (GH-3096)
- `[Build]` `pnpm dev` listens on `localhost`, no longer on every interface, so Nuxt DevTools is
  reachable from this machine only; `HOST=0.0.0.0 pnpm dev` opens it to the network. The dev
  container sets `HOST=0.0.0.0` itself (GH-3096)

### Deprecated

- `NUXT_PUBLIC_API_BASE`: the server logs one warning when it starts with it set, and a future
  release stops reading it. Rename it to `NUXT_API_BASE`, the value stays the same (GH-3096)

### Security

- `[Docker]` The app image carries a build provenance signed with the GitHub Actions identity of
  the workflow through Sigstore, from this release on: `gh attestation verify
  oci://ghcr.io/earthobservations/wetterdienst-app:<version> --repo earthobservations/wetterdienst`
  checks it. An unsigned BuildKit provenance and an SBOM per platform come with it (GH-3346)

## [0.35.0] - 2026-10-24

### Fixed

- `[Explorer]` Clearing the distance input of a parameter under "Station distance by parameter"
  (interpolation and summary) no longer makes the request fail with a 422. The parameter is left
  out of the request and the general (homogeneous or heterogeneous) radius applies to it until a
  distance is typed again (GH-3356)

### Security

- `[Build]` No install script of a dependency runs any more (`allowBuilds` in
  `pnpm-workspace.yaml`, replacing `dangerouslyAllowAllBuilds`): a new dependency that has one fails
  `pnpm install` until it is listed there. pnpm is pinned to 11.22.0 with its hash
  (`packageManager`), the image gets it from the Node image's corepack and installs with
  `--frozen-lockfile`, and the accessibility job's Playwright image is pinned by digest (GH-3345)

## [0.34.0] - 2026-10-24

### Changed

- `[Glossary]` The label of `radiation_sky_short_wave_direct_perpendicular` replaces that of
  `radiation_sky_short_wave_direct` (Met Office), in all eleven languages (GH-3316). Needs the
  backend that serves the new name: release the backend first. The Low German and Luxembourgish
  labels are not reviewed by a native speaker
- `[Glossary]` `volume_reservoir` (the volume of a reservoir, `wsv/pegel`) has a label in all
  eleven languages, and the new unit type `volume` has its label in the unit filter ("Volume").
  Needs the backend that serves them (0.173.0): release the backend first. The Low German and
  Luxembourgish labels are not reviewed by a native speaker (GH-3242)

### Security

- `zod` is 4.6.7 (range `^4.6.6`), which fixes the memory exhaustion on a large array that
  fails an array schema (GHSA-mrhx-c7xc-m3w5). `zod` is in the app's browser bundle, where it
  validates the settings kept in `localStorage`; those schemas use no array, so the app did not
  reach the flaw (GH-3368)

## [0.33.0] - 2026-10-23

### Changed

- `[Explorer]` The inputs of the interpolation and summary settings hold the bounds the REST API
  now enforces on `interpolate` and `summarize`: a station radius of at most 200 km, at most 20
  additional stations and a minimum gain above 0 (the input offers 0.01 as its smallest). A value
  the host's settings (`GET /api/settings`) name beyond them is clamped: a radius above 200 km is
  left to the server, as an infinite one is, a count above 20 becomes 20, and a gain of 0 is not
  taken, the explorer keeping its own. Release it with backend 0.172.0, which refuses a request
  past the bounds (GH-2606)

## [0.32.0] - 2026-10-23

### Changed

- `[Glossary]` The label of `radiation_sky_short_wave_direct_perpendicular_intensity` replaces that
  of `radiation_sky_short_wave_direct_intensity` (DWD POI), in all eleven languages (GH-3263).
  Needs the backend that serves the new name: release the backend first. The Low German and
  Luxembourgish labels are not reviewed by a native speaker

### Security

- `[Build]` `nuxt` and `@nuxt/nitro-server` are 4.6.2, which fixes the case-variant paths that
  skipped the server's route rules (GHSA-vjh5-4x84-xrqp; the app's `routeRules` set a response
  header), the unsanitised `useHeadSafe` input of server islands (GHSA-xfq5-w38q-pc2x) and the
  `javascript:` link of `<NuxtLink>` (GHSA-jjm6-p2m9-9w4x). `vue` is 3.5.44, which Nuxt 4.6 needs
  (GH-3280)

## [0.31.0] - 2026-10-22

### Security

- `[Build]` The advisories of `vite` and `launch-editor` (six, three of them shared),
  `@vitest/mocker` and the MCP SDK are resolved with `vite` 8.3.4, `launch-editor` 2.14.2, `vitest`
  4.1.12 and `@modelcontextprotocol/*` 2.3.1, and the four of `simple-git` and
  `@simple-git/argv-parser` with `@nuxt/devtools` 3.4.4, which no longer depends on them. All of
  these are build, lint and test tooling the built app does not ship. `braces` and `node-forge`
  have no fixed release and stay open (GH-3280)

## [0.30.0] - 2026-10-22

### Changed

- `[Glossary]` The labels of `soil_moisture_winter_cereals_*`, `soil_moisture_mean_winter_cereals_*`
  and `evaporation_amount_winter_cereals_*` replace those of the winter wheat names, and
  `road_surface_condition_forecast` and `wind_speed_max` have labels, in all eleven languages
  (GH-3263, GH-3264). Needs the backend that serves them: release the backend first. The Low German
  and Luxembourgish labels are not reviewed by a native speaker

### Fixed

- `[Meteogram]` The wind barbs were missing when the chart was first drawn and showed only once
  something made Plotly draw again, such as a resize of the browser window. They are drawn with the
  chart now, in the meteogram page and in the embeddable widget (GH-3240)

## [0.29.0] - 2026-10-21

### Changed

- `[Accessibility]` The weather symbols of the forecast's compact day cards have a text alternative:
  the symbol is hidden from a screen reader and the card says "Rain", "Thunderstorm", "Sunny" and so
  on, in the language of the page, as it does "Precipitation:" before the rain's amount. The words are
  in all eleven languages; Polish, Czech, Luxembourgish and Hamburg German are not reviewed by a native
  speaker (WCAG 1.1.1; GH-3186)
- `[Accessibility]` Escape dismisses the hover label of the charts (forecast, explorer, climate
  stripes) and the names of the toolbar buttons that show on hover, while the pointer is over the
  chart, until the pointer moves on. The label itself still cannot be moved onto, which Plotly does
  not allow; its values are in "Show as table" (WCAG 1.4.13, partly; GH-3186)
- `[Glossary]` Two parameters have labels in all eleven languages (GH-2614): `temperature_air` and
  `temperature_dew_point`. Needs the backend that serves them: release the backend first. The Low
  German and Luxembourgish labels are not reviewed by a native speaker

### Fixed

- `[Forecast]` The compact day cards drew a wrong symbol for some WMO weather codes: dust and sand
  storms and drifting or blowing snow (30-39) as a thunderstorm, the phenomena of the hour before
  (20-29: drizzle, rain, snow, fog, thunderstorm) as wind, and mist, lightning, precipitation in sight
  and a funnel cloud (10-19) as clouds. They show 🌪 for a dust or sand storm, 🌨 for blowing snow and
  for rain and snow, the phenomenon of the code otherwise, and, where a code names none the card can
  (haze, hail, a funnel cloud), the symbol the day's cloud cover and rain give (GH-3186)

## [0.28.0] - 2026-10-20

### Changed

- `[Glossary]` Five parameters have labels in all eleven languages (GH-2614):
  `radiation_short_wave_net_last_3h`, `radiation_long_wave_net_last_3h`, `snow_depth_sum`,
  `temperature_air_min_0_05m_night`, `precipitation_amount_max_30min`. Needs the backend that
  serves them: release the backend first. The Low German and Luxembourgish labels are not reviewed
  by a native speaker
- `[Glossary]` The labels of the 19 parameter names that no dataset of any provider declares are
  gone from all eleven languages, among them the two renamed DMO radiation names,
  `cloud_base_convective`, `temperature_radiant_mean_2m` and eleven `quality_*` flags, so the
  glossary no longer lists names the backend does not serve (GH-2614). Goes with the backend that
  removed them: release the backend first

## [0.27.0] - 2026-10-20

### Changed

- `[Accessibility]` The climate stripes and the forecast chart (also the embeddable widget) have a
  text alternative: the chart is described by a sentence, and "Show as table" below it lists what it
  draws, every year with its value and class for the stripes, every time with the values of the
  shown panels for the forecast, so a screen reader or a keyboard reads the data that colour and
  shape carry. The strings are in all eleven languages; Polish, Czech, Luxembourgish and Hamburg
  German are not reviewed by a native speaker (WCAG 1.1.1, 1.3.1; GH-3145)

## [0.26.0] - 2026-10-19

### Changed

- `[Translations]` German, French, Czech and Luxembourgish address you informally, as the other
  languages already do (GH-3157): `du`, `tu`, `ty` (singular) and `du` instead of `Sie`, `vous`, `vy`
  and `Dir`, with `Wähle`, `Choisis`, `Vyber` and `Wiel`. The text is not reviewed by a native speaker
- `[Navigation]` The Providers tab sits right of API, so the tabs read History, API, Providers,
  Glossary, in the header and in the narrow menu (GH-3164)

## [0.25.0] - 2026-10-18

### Changed

- `[Glossary]` The means of the irradiances, the soil moisture (twelve names), the snow depth, the
  precipitation intensity and the Beaufort wind force have labels in all eleven languages (GH-3151):
  `radiation_global_intensity_mean`, `radiation_sky_long_wave_intensity_mean` (which replaces the
  plain key), `radiation_sky_short_wave_diffuse_intensity_mean`, `precipitation_intensity_mean`,
  `snow_depth_mean`, `wind_force_beaufort_mean`, `soil_moisture_mean_*`. Needs the backend that
  serves them: release the backend first
- `[Glossary]` The means of humidity, pressure, cloud cover and visibility have labels in all eleven
  languages (GH-3151): `humidity_relative_mean`, `pressure_air_site_mean`,
  `pressure_air_sea_level_mean`, `pressure_vapor_mean`, `cloud_cover_total_mean`, `visibility_mean`, and
  `cloud_cover_total_mean_midnight_to_midnight` and its three siblings, which replace the old ones.
  Needs the backend that serves them: release the backend first
- `[Glossary]` The mean wind has labels in all eleven languages for the backend names that carry the
  statistic (GH-3151): `wind_speed_mean`, `wind_direction_mean` and the `_mean_last_10min` /
  `_mean_last_2min` ones, which replace the `_last_10min` / `_last_2min` ones. Needs the backend
  that serves them: release the backend first, as this renames the parameters it lists
- `[Home]` The home page no longer says "no rate limit", which the app's rate limit made untrue
  (GH-3093): its data section promises "No key, no account." in all eleven languages (GH-2610)
- `[Translations]` Review of the eleven catalogs: Spanish speaks to the reader as "tú" throughout
  (`Qué datos obtienes`, `Convierte esa columna`); the history page is "Stationsverlauf" in German
  where it was "Chronik" and "Verlauf"; Spanish and Italian call a station's elevation "Altitud" and
  "Altitudine" on the history page as on the interpolation panel; the API page's endpoints are
  "Puntos de acceso", "Eindpunten", "Endepunkter" and "Points d'accès" like the MCP texts around
  them; Danish "Vejvejr" for road weather; Polish, Italian and German sentences made grammatical
  (GH-2610)
- `[Translations]` Quotation marks and apostrophes follow each language (“…” in English, Danish
  and Dutch, «…» in Italian, „…“ in Luxembourgish) where the newest texts had a straight `"` or
  `’`, and French sets a no-break space before `: ; ? !` and inside « » (GH-2610)

### Fixed

- `[Accessibility]` The keyboard focus is shown by a solid 2 px outline in the primary colour
  (4.9:1 on light, 10:1 on dark; the map keeps the light one), where Nuxt UI's own halo was 1.2:1
  to 2.2:1 on white and the search fields of the menus showed none (WCAG 2.4.7, 1.4.11; GH-2559)
- `[Accessibility]` Every page has a title of its own (`Explorer - Wetterdienst`; the tab, the
  history and a screen reader's page list all said just `Wetterdienst`), and a screen reader is
  told which page a navigation within the app has arrived at (WCAG 2.4.2, 4.1.3; GH-2559)
- `[Accessibility]` The menu of the narrow layout is a dialog: the focus stays in it, Escape
  closes it and gives the focus back to the menu button, which says whether the menu is open, and
  the page behind is hidden from a screen reader while it is. Tab used to walk on into the page
  behind the overlay. Its top bar shows "Menu" and a close button, no longer the logo (WCAG 2.1.2,
  2.4.3, 4.1.2; GH-2976)
- `[Accessibility]` Text that changes colour under the pointer stays readable: the chips of the home
  page (2.2:1 hovered in light mode, now 4.9:1), every link button (3.4:1, now 7.1:1) and the
  day cards of the compact forecast (4.4:1, now 6.9:1) (GH-2991)
- `[Accessibility]` A station marker of the map that takes the focus by Tab is brought into the
  map's view, and is named by its station, not "Marker", for a screen reader (WCAG 2.4.11;
  GH-2559)
- `[Accessibility]` The weather emoji of the compact forecast cards bounce once, and only for a
  visitor who has not asked for reduced motion, not for ever (WCAG 2.2.2; GH-2559)
- `[Accessibility]` The list of selected stations has a heading of the level below its section's
  (`h3`, was `h4`) (GH-2559)

### Security

- The page's Content Security Policy names the nonce its inline scripts carry
  (`script-src 'self' 'nonce-...' 'wasm-unsafe-eval'`) and no longer allows `'unsafe-inline'` for
  scripts, which the nonces never switched off: an inline script that gets into the page, or an
  event handler attribute, is refused now (GH-3112)

## [0.24.0] - 2026-10-18


### Changed

- **Breaking**: the app looks for the backend at `http://localhost:7890/api` by default, where
  `wetterdienst restapi` listens, not 3000; the Docker image of the backend and `compose.yml` use
  7890 too. A deployment that runs the backend on another port sets `NUXT_PUBLIC_API_BASE` (the
  compose file does for its own network), as before (GH-3106)
- The home page states the number of parameters the backend counts (`/api/providers`,
  `metadata.counts.parameters`), not a number it was written with, which no longer held: it shows
  a placeholder until the backend has answered and a dash where it did not (GH-3105)
- **Breaking for deployments that relied on the old limit** `[Rate limit]` The rate limit counts
  what costs something, 300 requests per client in 5 minutes for `/api/values`, `stations`,
  `interpolate`, `summarize`, `stripes`, `history` and the rest of `/api` but the catalogue, and
  `/mcp`, and leaves the pages, `/docs` and the catalogue routes (`version`, `settings`,
  `providers`, `coverage`, `glossary`, `auth`, `health`) out. It was one bucket of 150 requests
  in 5 minutes for every page and call. A 429 is a problem
  (`urn:wetterdienst:problem:rate-limited`) with `Retry-After`, and counted answers carry
  `X-RateLimit-*`. Set `NUXT_RATE_LIMIT_TOKENS`, `NUXT_RATE_LIMIT_WINDOW_SECONDS` or
  `NUXT_RATE_LIMIT_ENABLED=false` at run time (GH-3093)
- **Breaking behind a reverse proxy** `[Rate limit]` The client is the address of the connection,
  not the leftmost `X-Forwarded-For`, which any client could write: behind a proxy all users share
  one count until `NUXT_RATE_LIMIT_CLIENT_IP_HEADER` names the header the proxy sets (read from
  its end). See `docs/usage/app.md` (GH-3093)
- `[Build]` The install drops `@scarf/scarf` (`.pnpmfile.cjs`), the analytics package that
  `swagger-ui-dist` depends on, whose postinstall reported every install (GH-3094)

### Security

- The icons are served by the app itself (`/_nuxt_icon`, from the installed `@iconify-json` sets)
  and no longer fetched from api.iconify.design, so a visitor's address and the icons of a page
  go to no third party and the icons are there with that host unreachable. The Content Security
  Policy drops `api.iconify.design` and `code.iconify.design` (GH-3111)

- A `..` in the path of a request to `/api` no longer leaves the backend's `/api`: the proxy
  resolves the URL before it fetches it and answers a 404 problem for one that is not under
  `apiBase`, where `/api/../health` reached the backend's `/health` (GH-3092)
- The production image runs the server as the unprivileged `node` user instead of root, as the
  backend image does. A volume or file the server writes to has to be writable by uid 1000, but
  the server writes nothing (GH-3091)
- **Breaking for a page of another origin that reads the app** `[CORS]` The app no longer answers
  `access-control-allow-origin: *` on every response, so only its own pages can read it. Set
  `NUXT_CORS_ALLOWED_ORIGINS` to the origins that may (comma separated; `*` is the old behaviour),
  at run time. Without it, such a page gets a CORS error (GH-3095)
- `[Proxy]` The `/mcp` proxy no longer sends the client's `cookie`, `authorization` or any other
  header to the backend but the session, protocol version, resumption point, content type, accept
  and request id of the transport, and drops the backend's `server`, `set-cookie` and `alt-svc`
  as `/api` does (GH-3095)
- `[CSP]` DuckDB-wasm (the SQL panel, about 35 MB, 5 MB over the wire) and Swagger UI (`/docs`) are
  served by the app, not loaded from jsdelivr without a hash, and the Content Security Policy
  allows no CDN and no `'unsafe-eval'` any more (`'wasm-unsafe-eval'` stays, for DuckDB's module).
  The browser calls only its own origin: `connect-src` no longer holds the backend's address
  that the build read. `/docs` is the app's own page of Swagger UI (it was the backend's, proxied)
  with a policy of its own. The SQL panel needs a browser with WebAssembly exception handling
  (every one since 2022), and the build is about a minute longer for the compression of the
  module (GH-3094)

## [0.23.0] - 2026-10-17

### Added

- `[Providers]` A Providers page, in the navigation and linked from the home page, says what each
  of the backend's providers is: name in English and in its own language, country with its flag,
  the licence (linked, with its SPDX identifier) and the credit line to give, with a button to copy
  it, and for each network its kind, source, whether it needs credentials, and its resolutions and
  datasets. The list filters by name, country or code and by kind of data, and a provider's page
  opens the explorer on one of its networks. It reads `GET /api/providers`, so it needs backend
  0.158.0 or newer (GH-2565). The Providers texts are in all eleven languages; the Polish, Czech,
  Luxembourgish and Low German ones are not natively reviewed

### Changed

- `[API page/Home]` The MCP client configuration and the home link name the pinned endpoint
  `/mcp/v1`, as the backend reports it in `/api/version` (`mcp_path`), so a client set up from here
  does not move with the next version. A backend that does not report it is still given `/mcp`
  (GH-3074)
- `[Home]` The weather services on the home page, and their number, are the backend's providers
  (`GET /api/providers`), not a list written in the app: a provider added upstream is on the page
  without a release. Each chip, by the provider's short name and the flag of its country, links to
  its Providers page; until the backend has answered there are placeholders of the same size, and
  where it does not answer or lists none the block says so, with a Retry. It needs backend 0.158.0
  or newer (GH-2565)
- **Breaking**: `[Stripes]` The stripes page reads the station, parameter and unit of the values
  from the `series` member of `stripes/values`, where the backend 0.157.0 had them in `metadata`;
  it needs backend 0.158.0 or newer, and against an older one the page cannot draw (GH-3076)
- `[Proxy]` Where the app's `/api` cannot reach the backend, the problem it answers is of the type
  `urn:wetterdienst:problem:backend-unreachable` (it was `about:blank`) and carries `request_id`,
  `instance`, `X-Request-ID` and `Retry-After` like the backend's own. The proxy sends the client's
  `X-Request-ID` on to the backend, which answers with it (GH-3080)

### Fixed

- `[Meteogram]` A navigation that fails after the forecast horizon, the panels or the compact view
  is changed is no longer an unhandled promise rejection (GH-3081)
- `[Meteogram]` The weekday and the date of the hover heading, and the weekday of the day labels
  and day cards, are written in the language of the page (`Do 15.10.`, `jeu. 15/10`), where the
  hover said "Thu" and `dd.mm` in every language, and Luxembourgish labels fell back to the
  system's language in Chrome (GH-3051)
- `[Meteogram/Widget]` A failure shown while the language is switched is written in the new
  language at once, where it kept the language it was made in. The status text after "Backend
  error 502" is the server's own and stays English (GH-3052)

## [0.22.0] - 2026-10-17

### Changed

- `[Languages]` Hamburgisch (`de-hh`) is Low German (Plattdüütsch) throughout, where its menus and
  texts were German and only the glossary was Low German; the glossary's quality flags say
  `Göödkennen`, as its `quality` says `Gööd`, where they said `Gütenkennen` (GH-2969)
- `[Languages]` Luxembourgish shows the explorer mode descriptions, the SQL panel and "Methode" in
  Luxembourgish, where they were English, and says `Datesaz` where it said "Dataset" (GH-2970).
  The Polish, Czech, Luxembourgish and Low German text is not natively reviewed; a native
  speaker's review is welcome (`app/i18n/TERMS.md`)
- `[Meteogram/Widget/Interpolation]` The English fallbacks "Request failed" and "Backend error 502"
  and the placeholders "e.g. 52.5200", "e.g. 13.4050" and "e.g. 34" are translated in all 11
  languages (GH-2971). The Polish, Czech, Luxembourgish and Low German text is not natively
  reviewed; a native speaker's review is welcome (`app/i18n/TERMS.md`)

### Fixed

- `[DataViewer/Glossary]` Counts take their plural form: "1 value", "1 row copied to clipboard" and
  "1 of 1 parameter", where they read "1 values" and the like, in all 11 languages. Polish and Czech
  write three forms ("1 wartość", "2 wartości", "5 wartości") and French counts 0 as singular
  (GH-2968)
- `[Meteogram/DataViewer/Stripes]` The charts write the language's decimal separator in their hover
  texts and axes ("9,5" in German, French and Polish), where Plotly wrote a point in every
  language, and draw again when the language is switched. The stripes' bar hover shows the value to
  two places, as its line and trend do, where it showed the number as it came (GH-2971)
- `[Meteogram]` The day labels of the chart and of the compact view's cards write the date as the
  language does ("15.10." in German, "15/10" in English and French, "15-10" in Dutch), where every
  language read "15.10". Luxembourgish, which Chrome has no data for, is written as German is
  (GH-2971)

## [0.21.0] - 2026-10-16

### Changed

- `[API errors]` The app reads the backend's errors as RFC 9457 problems: a refused request shows
  `errors`, one line for each invalid parameter, and else `detail`, which is text. The proxy answers
  a backend it cannot reach as a problem too (`type`, `title`, `status`, `detail`). It still reads
  the list a backend from before the change put under `detail` (GH-2634)
- `[Meteogram]` The pressure panel reads MOSMIX `pressure_air_sea_level`, the name the backend gives
  `pppp` in the release following 0.154.0, and keeps `pressure_air_site_reduced` as a fallback:
  against an older backend it works as before, but an app older than this one against the new
  backend draws no pressure panel (GH-2842)
- `[Glossary]` The new parameters `wind_gust_max_last_10min`, `wind_speed_last_2min`,
  `wind_direction_last_2min`, `radiation_global_relative_last_1h`, `weather_past`,
  `weather_secondary_past` and `precipitation_amount_liquid_last_6h` have a label in all 11
  languages, `pressure_air_site_reduced` says sea level with the standard atmosphere and
  `temperature_surface_mean` a surface, ground or grass, where it said the ground. The
  labels of `probability_radiation_global_last_1h`, `weather_last_3h` and
  `weather_secondary_last_3h` are gone with those names: against an older backend the prettified id
  shows (GH-2836, GH-2837, GH-2840, GH-2843, GH-2844, GH-2845)
- `[Glossary]` The new parameter `temperature_air_mean_minmax_2m`, the mean computed from the
  day's maximum and minimum (ECCC, Geosphere daily), has a label in all 11 languages (GH-2839)
- **Breaking** `[API requests]` The app asks `stations`, `values` and `history` for `stations`, the
  plural the backend takes a list by, where it sent `station`, and the API page lists it so. A
  backend from before the change refuses the plural as an input it does not know: use an app and a
  backend from the same release. The pages' own links, `/meteogram?station=` and
  `/widget?station=`, are unchanged (GH-2561)
- `[Glossary]` The new parameter `precipitation_amount_since_last_routine_report`, the METAR
  precipitation of `noaa/ghcn` hourly and `nws/observation`, has a label in all 11 languages;
  against an older backend those two datasets still show `precipitation_amount` (GH-2841)
- **Breaking** `[Glossary]` The labels of `count_days_valid_temperature_air_mean_2m` and
  `temperature_air_mean_2m_normal` are now keyed by `count_days_valid_temperature_air_mean_minmax_2m`
  and `temperature_air_mean_minmax_2m_normal`, the names the backend gives ECCC's monthly counts and
  normals of the mean of the daily maximum and minimum: against an older backend the prettified id
  shows (GH-3017)

### Fixed

- `[Explorer]` The descriptions of the three modes and "How it works" are in Czech, Danish,
  Spanish, French, Italian, Dutch and Polish, where they were the English text. Luxembourgish
  still shows English there until a native speaker writes it (GH-2610)
- `[QueryPanel]` The SQL panel's buttons, hint, example queries and failure messages follow the
  language, where they were English in all of them. Luxembourgish still shows English (GH-2610)
- `[Stripes]` The chart's hover text says "Value" and "Trend" in the active language (GH-2610)
- `[DataViewer/Meteogram]` The statistics table and the Meteogram's gust, precipitation and day
  totals write their numbers as the language does: "2,50" and "1.234,50", no longer "2.50" and
  "1234.50" in German, French or Polish (GH-2610)
- `[Glossary]` Spanish writes "Periodo de la ola", as its other "periodo" is spelled (GH-2610)
- `[Layout]` A page title that is one long word, "Stationsgeschiedenis" on a 320 px phone in
  Dutch, breaks inside the word where it could run past its box (GH-2610)
- `[Home]` Spanish says "Qué puedes hacer con ellos", as the rest of its text addresses the
  reader (GH-2610)
- `[Map]` The German map hints say "Tippen Sie auf ...", as the rest of the German text addresses
  the reader, where they said "Tippe" (GH-2610)
- `[Accessibility]` The table/chart toggle, the copy, download, clear-station and remove-distance
  buttons, the settings page's and popover's selects and switches, the data viewer's column,
  rows-per-page and label selects, the forecast model run and the glossary's quantity filter have
  a name a screen reader announces, in every language, where they had none (GH-2975)
- `[DataViewer]` The SQL panel no longer claims to be an expandable control, which it is not, and
  the download menus of the data viewer and of the stripes do not hide the page from assistive
  technology while open (GH-2976)
- `[Layout]` Grey, green and red text, and placeholders, reach the 4.5:1 contrast of WCAG 2.2 AA
  on the light and the dark background: slightly darker in light mode, slightly lighter in dark
  mode (GH-2974)
- `[Layout]` Links inside running text are underlined, so they stand out without their colour
  (GH-2977)
- `[Layout]` The label of the solid green buttons ("Show", the table/chart toggle, the current
  page, the Meteogram's Compact) is dark (`#0f172b`) in light mode too, 8.0:1 on the brand green
  where white was 2.2:1; dark mode had it already and the green itself is unchanged. Outline, soft
  and ghost buttons keep their colours (GH-2974)

## [0.20.0] - 2026-10-15

### Changed

- `[Meteogram]` The temperature and dew point panels read MOSMIX `temperature_air_2m` and
  `temperature_dew_point_2m`, the names the backend gives `ttt` and `td` after the release following
  0.144.0, and keep `temperature_air_mean_2m` and `temperature_dew_point_mean_2m` as a fallback:
  against an older backend it works as before, but an app older than this one against the new
  backend draws neither panel (GH-2657)
- `[Meteogram]` The Tx/Tn band reads `temperature_air_max_2m_last_12h` and
  `temperature_air_min_2m_last_12h`, the names the backend gives MOSMIX `tx` and `tn` after the
  release following 0.144.0, and keeps the old names as a fallback: against an older backend it
  works as before, but an app older than this one against the new backend draws no band (GH-2614)
- `[DataViewer]` The table shows the one string column `quality_flags` the backend gives a values
  row in the release following 0.146.0 in place of `quality`: against an older backend the numeric
  `quality` column moves to the end of the table (GH-2758)
- `[Glossary]` MOSMIX `error_absolute_temperature_air_2m` and
  `error_absolute_temperature_dew_point_2m` have a label in all 11 languages: the names the
  backend gives `e_ttt` and `e_td` in the release following 0.151.0, in place of the `_mean_`
  ones. Against an older backend the labels of the old names are gone and the prettified id shows
  (GH-2659)

### Fixed

- `[DataViewer]` The chart names its series, facets and their axes by the plain-language label of
  the active language, as the table of statistics already did, where it showed the raw id (or the
  prettified id for an unlabelled one): "Mittlere Windrichtung (letzte 10 min)", no longer
  `wind_direction_last_10min`. The label format choice joins resolution, dataset and parameter
  labels with " / ". The raw ids stay with "Plain-language labels" off (GH-2865)
- `[Glossary]` `6_minutes` (Météo-France) and the datasets `core`, `others`, `rain`, `radiation`,
  `weather`, `temperature`, `soil_temperature`, `urban_solar`, `urban_temperature_extreme` and
  `urban_wind_extreme` have a label in all 11 languages, where the select showed their prettified
  ids (GH-2865)
- `[Glossary]` The 110 `dwd/phenology` datasets have a label in all 11 languages, plant and
  reporter group, where the select showed "Annual Winter Rye": "Annual reporters: Winter rye",
  "Jahresmelder: Winterroggen". Low German and Luxembourgish give the plant's own word only where
  it is well attested and the German one otherwise (GH-2866)
- `[DataViewer]` The trendlines of the chart are named for their series in the active language,
  "... (Trendlinie)", where every language read "... (trend)" (GH-2869)
- `[DataViewer]` The hover label of the chart shows a series' name whole, where Plotly cut it after
  15 characters (GH-2870)
- `[DataViewer]` A Fetch shows its table sooner: the chart's rows, series and facets are made when
  the chart is opened, not for every answer. Measured on `dwd/observation` `daily/climate_summary`,
  14 parameters, 3 stations (1.1 million rows), the table came up after 5.4 s, where it takes 3.8 s
  now; the server's part (2.7 s) did not change. Opening the chart takes about 1.6 s longer
  (GH-2560)
- `[Meteogram]` The Tx/Tn band holds each value across the 12 hours before its stamp, as DWD gives
  it, in steps, where a line between the two daily stamps let the temperature curve out of the
  band for a tenth to a sixth of the hours (GH-2647)
- `[Explorer]` A link with `stations=` restores its stations whichever of the station list and the
  parameter selection answers first, where it lost them (and the `stations=` of the address) when
  the list came first, which it usually does. Choosing other parameters of the same dataset no
  longer clears stations restored from a link either (GH-2959)
- `[DataViewer]` The query panel no longer reads every field of every row at each answer: about
  0.2 s less main-thread time on 1.1 million rows (GH-2958)

### Security

- `[Build]` The `katex` advisory (low: prototype pollution) is resolved with 0.19.0 through a
  `pnpm-workspace.yaml` override; `katex` is lint tooling the built app does not ship.
  `simple-git` and its `@simple-git/argv-parser` (fixed only in 4.x, which `nuxt`'s devtools
  cannot load), `braces` and `node-forge` (no fixed release) stay open in Dependabot (GH-2605)
- `[Server]` The `/api` proxy answers a backend it cannot reach with a fixed text, "The backend
  could not be reached. The cause is in the server log.", with the status it had (502), where the
  detail was the connection error, which names the backend's host and port. The error is now in
  the app server's log (GH-2936)

## [0.19.0] - 2026-10-08

### Changed

- `[History]` The page reads each record's span from `valid_from` and `valid_to`, as the backend now
  returns it, where it read `start_date` and `end_date`, so it needs a backend that sends the new
  names: against an older one the start and end columns show "-", and a card can be named by a
  station name that is no longer the current one (GH-2440)
- `[Explorer/API]` The explorer sends its date range to the backend as `timestamp`, the new name
  of the backend's `date` parameter, and the API page's examples and parameter table name it so.
  It needs a backend that takes `timestamp`, the release after 0.141.0: 0.141.0 and older refuse a
  request with a date range. The explorer's own links keep `startDate`/`endDate`, and open as
  before (GH-2438)
- `[Explorer/Stripes]` The span a station has records for is read from `start_timestamp` and
  `end_timestamp`, the backend's new names for `start_date` and `end_date`, so the app needs a
  backend that sends them, the release after 0.141.0: against 0.141.0 or older the station table's
  start and end show "-", the stripes page's available years are blank, and a required date range
  is filled from the selected stations with today as its end but no start. Links open as before
  (GH-2439)

## [0.18.1] - 2026-10-06

### Fixed

- `[Explorer]` The Unit Targets hint no longer says to leave a select empty, which none of them
  can be: it names the "Default" choice each select shows, which converts to the unit named in its
  parentheses, in all eleven languages (GH-2395)
- `[Explorer]` A link whose interpolation or summary point is a station opens with that station
  chosen as the point, with the elevation the link names, once the station list has loaded. Until
  then, and when the list fails, the link keeps the station; it used to drop it as the page loaded.
  A station the list does not have, or has without a position, is left for the user to choose, and
  leaves the link (GH-2392)
- `[Explorer/Stripes/Meteogram/Widget]` A screen reader announces each chart as a figure with a
  name: the data viewer's chart, or each facet by its parameter, the meteogram (also in the widget)
  by its station and the stripes by their kind and station. The charts were unnamed, so reaching
  one announced nothing useful (GH-2376)

## [0.18.0] - 2026-10-05

### Added

- `[Explorer]` The settings start from the backend's, as its `GET /api/settings` reports them: its
  `WD_TS_*` variables over wetterdienst's defaults, and each "Default (...)" unit choice names the
  backend's unit. A request names every setting, now the two search radii too, so it asks for the
  same on any backend. The page's link names its five settings at any value; an older link that
  leaves one out takes the backend's. A backend without the endpoint, or one that fails, leaves
  wetterdienst's defaults, which are then sent (GH-2359)

### Changed

- `[Explorer]` The nearby station distance is offered, and sent, for an interpolation only. It had
  no effect on a summary, and the backend deprecates it there (GH-2333)

### Fixed

- `[Explorer]` Switching the shape takes the backend's Drop nulls for the new shape. On a backend
  with `WD_TS_SHAPE=wide`, switching to long left Drop nulls unchecked, so the long result kept its
  null rows. A Drop nulls the page link names applies on load, and a switch replaces it too.
  A Drop nulls the user changed stays, as does the current one on a backend
  that can't report the new shape's (GH-2398, GH-2400)
- `[Explorer]` Each Unit Targets select left at its default shows "Default (...)" with the unit,
  and the choice is offered again. Opening Unit Targets raised an error per unit type, every select
  showed nothing, and a type moved to another unit could not be put back to Default (GH-2391)
- `[Explorer]` `[Meteogram]` `[Widget]` `[Stripes]` A Retry that works moves the keyboard focus to
  what it brought back: the station select of the interpolation/summary picker, or the chart.
  The focus fell to the top of the page, sending a keyboard or screen reader user to find their
  place again. Focus moved elsewhere meanwhile stays where it is (GH-2357)
- `[Explorer]` Each unit type the Unit Targets setting lists is asked for in the unit its choice
  names, "Default (°C)" in °C. On a backend whose `WD_TS_UNIT_TARGETS` sets another unit, such as
  `{"temperature": "degree_fahrenheit"}`, a type left at "Default" came in that unit instead. A
  backend without `WD_TS_UNIT_TARGETS` answers as before (GH-2358)
- `[Meteogram]` `[Widget]` The forecast is asked for in °C, m/s, mm, hPa and degrees, the units
  the charts label it in. On a backend whose `WD_TS_UNIT_TARGETS` sets another unit, such as
  `{"temperature": "degree_fahrenheit"}`, the charts drew those values under the labels of the
  defaults. The request also names the long, humanized layout the charts read (GH-2350)
- `[Widget]` A failed station lookup is told by the backend's status and reason, as a failed
  forecast is, where it read "Station not found" for any failure, such as the MOSMIX station list
  failing to download. "Station not found" is kept for a station id the backend does not know,
  which left the widget blank before (GH-2311)
- `[History]` A station's card names its id whatever sections are fetched, where it read
  "Station ID:" with nothing after it when the sections fetched held no records, as the missing
  data of a station without gaps. The id is the one the backend now sends with each history,
  spelt as in the stations list (GH-2215)
- `[Explorer]` DWD DMO's `icon` offers a choice of forecast run: short (to 78 h, hourly, the
  default) or long (78 to 168 h, 3-hourly). The 3-hourly parameters, such as
  `precipitation_amount_last_3h`, are carried only by the long run, which the explorer could not
  ask for, so they answered with no data or an error. The run chosen is kept in a shared link and
  goes back to short when the provider, network, resolution or dataset changes (GH-2227)
- `[Explorer]` DWD DMO's `icon` offers only the parameters the chosen forecast run carries, and
  switching runs drops the others from the selection; a selection of all of them becomes all the
  new run carries. A selection mixing 1-hourly and 3-hourly parameters, as unticking one of the
  default selection left, was refused under either run until those were unticked by hand. Needs a
  backend whose `/api/coverage` gives each parameter its `lead_times` (GH-2256)
- `[Stripes]` `[Meteogram]` Where the chart's code could not be loaded, as after a new version of
  the app was deployed under an open tab, the chart area says that reloading the page helps where
  Retry does not, and offers a Reload page button, as the explorer's chart does. Retry asked for the
  replaced code again and failed every time, with no word that only a reload would help (GH-2200)
- `[Stripes]` A station's values that fail to load are told in the chart area, with the backend's
  reason or the answer's status, where nothing was said. Another station's stripes go as Show
  fetches the chosen one's, where they stayed. A fetch under way when Reset is clicked, the kind
  changes or another station is chosen draws nothing and tells no failure, where it drew its
  stripes into the cleared area or under the newly chosen station (GH-2195)
- `[Stripes]` Ticking "Show title", "Show years" or "Show data availability" redraws the stripes
  from the values already loaded, where it also fetched them again and drew them twice (GH-2199)
- `[Explorer]` `[History]` `[Meteogram]` Where the station map's code could not be loaded, as
  after a new version of the app was deployed under an open tab, the map area says the stations
  could not be shown and offers a Reload page button. It stayed empty, with no word why (GH-2194)
- `[Explorer]` The station map's "Center on all stations" fits the map to a network of any number of
  stations, where it did nothing past about 120,000 stations (65,536 in Safari), as NOAA GHCN daily
  lists (GH-2189)
- `[Explorer]` The chart's trendline is drawn for a series of any number of points, where the chart
  was not drawn once the trendline was ticked past about 120,000 points (65,536 in Safari), as three
  years of one station's 10-minute data (GH-2189)
- `[Explorer]` Where the chart's code could not be loaded, as after a new version of the app was
  deployed under an open tab, the chart area says that reloading the page helps where Retry does
  not, and offers a Reload page button. Retry asked for the replaced code again and failed every
  time, with no word that only a reload would help (GH-2183)
- `[Explorer]` The SQL query panel runs the string function `replace()` and
  `SELECT * REPLACE (...)`, and takes a refused keyword after `AS` or a `.` for a name, as in
  `1 AS update` or `t.delete`, where it refused each as a disallowed operation. A query that writes
  is still refused (GH-2181)
- `[Explorer]` The chart faceted by parameter gives each station one colour in every facet, where a
  station took another colour in a facet that lacked a station before it or listed the stations in
  another order (GH-2178)
- `[Explorer]` The parameter statistics show for a parameter of any number of values, where they
  failed to show past about 120,000 values (65,536 in Safari), as three years of one station's
  10-minute data or a year of daily data for 400 stations (GH-2179)
- `[Explorer]` The query panel loads an interpolation's `taken_station_ids` as a list, which
  `list_contains` and `unnest` take, where it loaded them as text joined by commas and refused both;
  a query's result hands the column on as a list (GH-2162)
- `[Explorer]` A query that returns no rows shows an empty table and "0 row(s) returned", where the
  table went on showing every fetched row with no word, as if the query had filtered nothing. Cancel
  brings the fetched rows back (GH-2163)
- `[Explorer]` The SQL query panel reads comments and strings as DuckDB does when it checks for a
  SELECT and for a refused keyword such as INSERT: a comment that nests, or a `--` inside a string,
  no longer hides an INSERT, COPY or SET that DuckDB then ran. A keyword inside a string, quoted
  name or comment is let through, and a `LIMIT` there no longer silences the no-LIMIT warning
  (GH-2166)
- `[Explorer]` A refused request is told in the error toast by each parameter and what is wrong
  with it -- "station: Cannot be combined with name" -- where a 422 showed `[object Object]`. A
  GeoJSON download the backend refuses shows that toast instead of saving the error as the file and
  reporting it downloaded (GH-2056)
- `[Explorer]` Downloads save what the table holds, where they fetched the current selection again,
  which could be another station or unit than the table's: they are offered once Fetch has filled
  the table, GeoJSON not while the query panel has rewritten it. CSV and JSON carry the table's rows
  after the query panel and sorting, with every column the rows carry, whatever the column picker
  shows. GeoJSON is fetched with the table's request. The copy buttons quote a field holding a
  comma, and copy nothing from an empty table (GH-2065)
- `[Explorer]` Show is offered again after a fetch fails, so the same selection can be retried, and
  after the station is removed and chosen again, which empties the table; it stayed disabled until a
  setting changed or Reset was pressed (GH-2073)
- `[History]` Show is offered again after a fetch fails, so the same selection can be retried; it
  stayed disabled until a setting changed or Reset was pressed. Show no longer reorders the chosen
  sections, and a fetch under way still shows its answer when the selection changes (GH-2077)
- `[History]` A failed fetch's error goes once Show is pressed again, where it stayed beside the
  loading indicator until the retry answered (GH-2078)
- `[History]` A failed fetch is told by the backend's reason, or by its status when the backend
  gave none, as the explorer already does; the message no longer begins with the request URL
  (GH-2082)
- `[Meteogram]` `[Widget]` A failed forecast is told by its status and the backend's reason,
  `Backend error 422: station: ...`, or by its status alone, with its status text where the
  connection carries one, when the backend gave none. The meteogram showed the error body as raw
  JSON, or a proxy's HTML page, and the widget left the reason out (GH-2084)
- `[History]` The Selected stations overview lists the stations the histories shown were fetched
  for. It listed the current selection, so after choosing other stations it named them above the
  histories of the ones fetched before (GH-2080)
- `[Explorer]` The table starts again at its first page when a Fetch answers, a query's result comes
  in or query mode is left. The page chosen in the rows shown before was kept against the new ones,
  and where they had fewer pages the table showed empty until the pager was used (GH-2075)
- `[Stations]` A station without a region, such as every DWD MOSMIX station, is labelled by its
  name and id in the station picker and on the map, as `JAN MAYEN (ID: 01001)`, where it read
  `JAN MAYEN (ID: 01001, null)` (GH-2046)
- `[Stations]` A station without a name or position, such as the postcodes dwd/derived
  `climate_correction_factor` has for stations, is labelled by its id, `ID: 01067` in the station
  picker and `01067` on its chip, where it read `null`, and left off the map, where it was drawn at
  0°N 0°E. Choosing one no longer fails the explorer's station details table, or the point an
  interpolation takes from its station (GH-2098)
- `[Explorer]` A query still running when a Fetch answers no longer replaces the new rows with its
  result: the table showed the query result of the rows fetched before under the new request, and
  CSV and JSON downloads saved it (GH-2072)
- `[Explorer]` A query's timestamps and dates read as the REST API writes them, times and intervals
  as text, integers and decimals as numbers -- an integer or a DECIMAL(p,0) past 2^53 as its digits
  -- in lists, structs and maps too. They came as epoch milliseconds, which failed the table's
  timestamp cell, BigInts, microsecond counts, unscaled integers or Arrow objects (GH-2068, GH-2071)
- `[Explorer]` The column picker and the query panel describe the rows the table shows, and follow
  the selected mode only while it is empty. Selecting another mode without fetching reset the picker
  to that mode's columns, hiding the `taken_station_ids` of interpolated rows, or the
  `taken_station_id` of summarized rows, still shown (GH-2069)
- `[Explorer]` The column picker offers every column the rows carry, a wide table's parameters, an
  interpolation's `distance_mean` or a query's `avg_value`, and the table and copies show them
  unless unticked. Only the nine fixed columns were known: a wide table showed empty `parameter`,
  `value` and `quality` columns and no measurement, and a query's own columns never showed (GH-2074)
- `[Explorer]` The chart's PNG, JPEG and SVG downloads save the facets, stacked into one image, when
  the graph is faceted by parameter, and are offered only while a chart is shown. Faceted, or with
  no chart shown, they saved nothing, without a word (GH-2067)
- `[Explorer]` A query's NaN and infinities, `'nan'::DOUBLE` or `value / 0.0`, are missing values,
  as the REST API has none: the table and copies show them empty, a CSV download writes nothing
  and a JSON download null. The CSV wrote `NaN`, `Infinity` or `-Infinity` where the JSON wrote
  null (GH-2111)
- `[History]` A number of 0 shows as 0 in the device, geography and missing data tables, where it
  showed as `-`: a station or sensor at 0 m, a latitude or longitude of 0, a missing count of 0.
  `-` is kept for a value the backend has none for (GH-2100)
- `[History]` A station's card is named by the name the station holds now, as its name history
  gives it, where it showed no name whenever the name section was fetched, which it is by default.
  The name is shown once, beside the station id, and no longer repeated in a row of its own below
  (GH-2092)
- `[Explorer]` The query panel's "Available columns" lists the columns of the rows it queries, in a
  download's order: a wide table's parameters, and an interpolation's `distance_mean` or a summary's
  `distance`. It listed the mode's fixed columns, among them a `quality` that interpolated and
  summarized rows lack, and a wide table's `parameter` and `value`, which a query written from the
  hint then failed on (GH-2109)
- `[Explorer]` Sorting the table keeps rows without a value in the order they came, last in either
  direction, in every browser. Firefox reversed them, and the copies and downloads wrote that order
  (GH-2112)
- `[Explorer]` A query's row without a timestamp shows an empty timestamp cell and is left out of
  the chart. The table failed to draw, and the chart placed the row at 1970-01-01 (GH-2103)
- `[Explorer]` A query's struct under one of the table's own column names, such as `value`, shows as
  the JSON text the copies and downloads write, as it does under a name of the query's own, where
  it showed `[object Object]` (GH-2110)
- `[Explorer]` The chart draws a series per station for the rows of stations fetched, whatever mode
  is selected since. Selecting interpolation or summary without fetching again merged the stations
  into one series per parameter, zig-zagging between their values, labelled `interpolated` when
  faceted (GH-2097)
- `[Explorer]` A chart image chosen while the chart is still being drawn is saved once it is drawn.
  It saved an empty chart, or a stacked facet image with an empty panel, and reported it
  downloaded (GH-2106)
- `[Explorer]` Run Query is unavailable from the moment a query is run, and runs the query as it
  read when pressed. A run and the syntax check share one start of DuckDB and one load of the
  table: pressed twice, or with the query edited while DuckDB started, the table could be loaded
  twice at once and the query run on rows held twice or on none (GH-2104)
- `[Explorer]` A query left by Cancel, or by a Fetch, changes nothing when it answers: its result
  replaced the rows Cancel had handed back, its error showed the next time query mode was entered,
  and Run Query stayed disabled and loading until it answered, or turned idle under a newer run.
  DuckDB failing to start is told by the run, with its reason (GH-2096)
- `[Explorer]` Leaving the Explorer within half a second of editing a query no longer starts a
  DuckDB database for its syntax check, which stayed running in the browser until the page was
  reloaded; a database still starting as the panel goes is ended once it has started (GH-2108)
- `[Explorer]` A query's VARINT reads as its integer, where it came as DuckDB's bytes, but for
  one that is a MAP's own key or value. The query panel notes that the browser's DuckDB misreads
  BIT, TIME WITH TIME ZONE (dropping the offset) and UHUGEINT values of 2^127 or more (turning
  them negative), and that `CAST(column AS VARCHAR)` reads them as text (GH-2102)
- `[Explorer]` A query's row whose timestamp is not text beginning with an ISO date, such as
  `2020-01-01`, is left out of the chart: a time of day or `'n/a'` stopped the chart from being
  drawn, text such as `'1'` was drawn at a date the browser made of it, and a number, read as
  milliseconds whatever it counts, drew `epoch(timestamp)` in January 1970 (GH-2124)
- `[Explorer]` The chart draws no series or facet for rows it cannot plot, those without a value or
  a date, where each was an empty trace with a legend entry, or an empty panel; with no row to plot
  it says there is no chart data and offers no image. A large result counts only the points drawn,
  so a few among many such rows are drawn with markers (GH-2125)
- `[Explorer]` A query's MAP with DOUBLE or FLOAT keys of NaN, infinity and negative infinity keeps
  each of them, as `NaN`, `Infinity` and `-Infinity`. All three were keyed `null`, so only the
  last one's value was shown and downloaded (GH-2116)
- `[Explorer]` A query's MAP with DATE or TIMESTAMP keys of infinity and negative infinity keeps
  both, as `infinity` and `-infinity`, as DuckDB writes them. Both were keyed `null`, so only the
  last one's value was shown and downloaded (GH-2148)
- `[Explorer]` The query panel's note on the types the browser's DuckDB misreads names GEOMETRY,
  which comes as its WKB bytes, and `CAST(column AS VARCHAR)` reads it as text (GH-2134)
- `[Explorer]` The query panel's table has every column any row carries, each numeric when all
  its values are numbers. A column null in the first row, such as `value` or `quality`, was text,
  so `avg(value)` failed, and a column the first row lacked was missing from the table (GH-2136)
- `[Explorer]` The query panel runs a query whatever columns it returns, and notes those it lacks
  against the rows queried. It refused every query without `parameter`, `value` and `quality`, so
  none could run on wide, interpolated or summarized rows, nor an aggregate on any. Example queries
  are offered only where the rows carry the columns they read (GH-2122)
- `[Explorer]` A query that fails or is refused hands the table back to the fetched rows, where the
  table went on showing the previous query's rows under the new query's error, as if they were its
  output (GH-2138)
- `[Explorer]` Cancel, or a Fetch, stops the query under way in the query panel, where DuckDB ran it
  on to its end and the next run, and the syntax check, waited behind it. The syntax check no longer
  waits for a run's query either (GH-2143)
- `[Explorer]` A chart changed while its facets are still being drawn shows the last change in
  every facet. The drawing under way went on to the facets it had left with what it read at its
  start, such as a trendline unticked since, over the newer drawing (GH-2131)
- `[Explorer]` A chart image chosen after the chart failed to draw, as when Plotly failed to load,
  draws the chart again and saves it, or says the chart could not be drawn. It saved an empty
  figure and reported it downloaded (GH-2140)
- `[Explorer/History/Stripes/Meteogram]` The station map shows the markers of the current station
  list only. A list that changed while the markers were still being built could leave the previous
  list's markers on the map, and clicking one selected a station of that list (GH-2132)
- `[Explorer]` A station without a position, such as a postcode of dwd/derived
  climate_correction_factor, is no longer offered as the point to interpolate or summarize for,
  where choosing it left Fetch disabled with nothing saying why (GH-2133)
- `[Explorer/History/Stripes/Meteogram]` The station map's centre button counts only the selected
  stations it can show. Choosing only stations without a position no longer switches it to "Center
  on all stations" with nothing to centre on: it stays disabled until a chosen station has a
  position (GH-2133)
- `[Explorer]` Sorting a query's column that holds both numbers and text keeps them apart, the
  numbers before the text in ascending order and after it in descending. The rows, copies and
  downloads came in an order each browser's sort made up (GH-2126)
- `[Explorer]` The column picker is disabled and offers no columns while the table is empty, where
  it offered `parameter`, `value` and `quality` whatever the shape setting (GH-2115)
- `[Explorer]` A query's integers past ±2^53, which come as their digits, sort by their value among
  the column's numbers, where they sorted as text: `10000000000000000000` before
  `9007199254740993` (GH-2153)
- `[Explorer]` The query panel refuses a query of more than one statement, in the syntax check and
  in Run Query, before any of it runs. DuckDB ran each statement, so one after the SELECT, such as
  `SET` or `COPY`, ran unchecked (GH-2139)
- `[Explorer]` A query ending in a `;` or a `--` comment passes the syntax check. Its check failed
  with a syntax error, which kept Run Query disabled for a query DuckDB runs as typed (GH-2165)
- `[Explorer]` Entering query mode after a Fetch checks the query again against the new rows. The
  syntax error shown, or its absence, was the answer for the rows fetched before, which could keep
  Run Query disabled for a query that was fine for the new rows (GH-2142)
- `[Explorer]` Faceted, each parameter's chart counts its own points towards the 500 above which a
  chart is drawn without markers and hovered point by point. All facets' points were counted
  together, so six facets of 100 points each lost their markers (GH-2158)
- `[Explorer]` The chart's series keep their colours and legend places when the table is sorted.
  They followed the table's sort, so sorting by value could swap two stations' colours (GH-2159)
- `[Explorer]` The chart places a query's timestamp text without an offset, as `2020-01-01 00:00`,
  at that time in UTC, as the fetched rows are. The browser read it as its own local time, an hour
  or more away from the row it came from. Text with a space before the time or an offset of hours
  alone is placed the same in every browser, and a date or time that does not exist, as
  `2020-02-30`, is left out where it was drawn in the next month (GH-2157)
- `[Explorer]` The chart plots only a query's values that are numbers, and integers past ±2^53,
  which come as their digits. Other text under `value`, as from `CAST(value AS VARCHAR)`, is left
  out: the trendline added it up as text and drew nothing but its legend entry, and text that is no
  number, as `'n/a'`, turned the y axis into categories (GH-2156)
- `[Explorer]` The parameter statistics take only rows that carry a `parameter` and a `value` that
  is a number or missing. A wide table, or a query result with its own columns such as `avg_value`,
  shows no statistics, where it showed a row for an undefined parameter, or for an empty dataset,
  counting nothing (GH-2161)
- `[Explorer]` A chart that fails to draw, as when Plotly fails to load, says so in the chart area,
  with a Retry button that tries to draw it again. The chart area stayed empty without a word
  (GH-2169)
- `[Explorer]` A chart image whose export fails, such as a stack of many facets past the browser's
  canvas size, says the image could not be saved. Nothing was saved and nothing said so, or for
  such a stack, an empty PNG or JPEG was saved and reported downloaded (GH-2170)
- `[Explorer/History/Stripes/Meteogram]` Collapsing the station map, or leaving the page, while its
  markers are still being built no longer adds them to the removed map, which could throw an error
  into the browser console (GH-2155)
- `[Stripes]` The station map stays centred on all stations once "Center on all stations" is
  pressed, where it could move back to the chosen station by itself and undo the user's pan and
  zoom (GH-2164)
- `[Explorer/History/Stripes/Meteogram]` The station map no longer writes a warning holding the
  whole selection to the browser console each time the selection changes (GH-2168)
- `[Explorer/History/Stripes/Meteogram]` A station map whose markers cannot be built, as when the
  app was redeployed under an open tab, says so above the map and asks for a reload. The map stayed
  empty without a word (GH-2185)
- `[Stripes]` The stripes are labelled with the years the backend gives in a browser west of UTC,
  where every stripe's year, as its hover and the first and last years shown give it, was one year
  early (GH-2184)
- `[Stripes/Meteogram]` Stripes or a meteogram that fail to draw, as when Plotly fails to load,
  say so in the chart area, with a Retry button that tries to draw them again, and a stripes image
  whose export fails says the image could not be saved. The chart area stayed empty, and a failed
  image saved nothing, without a word (GH-2186)
- `[Explorer]` A Fetch of values, interpolated or summarized data that fails with the 500 the
  backend now gives where it or the source failed is asked for once, and its error is told at once,
  where the app asked a second time. So is one the browser's connection drops before any answer.
  A 502, as the app's server gives where the backend cannot be reached, a 503 or 504 from a proxy,
  or a 408, 409, 425 or 429 is still asked for once more (GH-2278, GH-2315)
- `[Explorer/History/Stripes/Meteogram/Widget]` A request for stations, a station history,
  stripes or forecast runs that fails with the 500 the backend now gives where it or the source
  failed is asked for once, where the app asked a second time and doubled the work behind it. So is
  one the browser's connection drops before any answer. A 502, 503 or 504, or a 408, 409, 425 or
  429 is still asked for once more, which fills a station list such a passing failure hit
  (GH-2298, GH-2315)
- `[Explorer]` The interpolation and summary's station picker asks for the station list once on a
  change of dataset, and not again for a parameter ticked or unticked while another stays ticked,
  where it asked more than once and the backend built the whole list for each (GH-2314)
- `[Explorer]` The skip threshold goes down to 0.05, where it went down to 0, which the backend
  now refuses (GH-2334)
- `[Explorer]` Where the station list of the interpolation and summary's station picker could not
  be loaded, the picker says so and offers Retry, where it stayed empty without a word (GH-2332)
- `[Explorer]` Where the station list of the interpolation and summary's station picker holds no
  station with a position, as for DWD derived's `climate_correction_factor`, whose stations are
  postcodes, or holds none at all, the picker says so, where it stayed empty without a word
  (GH-2356)

### Security

- `[Build]` The three `brace-expansion` advisories (2 high, 1 moderate: denial of service through
  recursion and quadratic expansion) are resolved with 5.0.12. `braces` and `node-forge` stay in
  `pnpm audit`: neither has a fixed release yet, and both are build and dev-server tooling that
  the built app does not ship (GH-2405)

## [0.17.0] - 2026-09-29

### Changed

- `[Stations]` Stations carry `elevation` where they carried `height`, as the backend now returns
  them; the history page labels it "Elevation (m)" and "Station elevation" in English (GH-2024)
- `[Stations]` Stations carry `region` where they carried `state`. English labelled the field
  "State" and every other locale a federal state -- "Bundesland", "Kraj związkowy", "Land" -- which
  most providers' regions are not; each now uses its own word for region (GH-2026)
- `[Explorer]` Values carry `timestamp` where they carried `date`: the column is headed
  `timestamp`, and the example queries group and order by it (GH-2028)
- `[Explorer]` A saved or shared link naming a parameter renamed for 1.0 -- `wave_height_sign`,
  say -- drops it, and with no parameter left the page selects the whole dataset; link the new
  name instead (GH-2032)

### Fixed

- `[Glossary]` `count_weather_type_hoar_frost` -- DWD's *Reif* -- was labelled as rime, a different
  deposit, in English ("rime"), German (*Raureif*), Low German (*Ruhreep*), Czech (*námraza*),
  Polish (*szadź*) and Italian (*galaverna*), and ambiguously in French (*givre*). Each now names
  hoar frost: *Reif*, *Riep*, *jíní*, *szron*, *brina*, *gelée blanche* (GH-2032)
- `[Glossary]` DWD's sampled snow depth and its water equivalent were labelled in every language as
  snow beyond the measuring range. They are the snow cut out as a sample to measure its water
  equivalent, and now read as such -- "Snow depth (sample)", German *Ausgestochene Schneehöhe*
  (GH-2034)
- `[Glossary]` The German, Low German and Luxembourgish labels for `precipitation_type_flags`
  borrowed the English "Flags" -- *Niederschlagsart-Flags* -- where each catalog calls a flag
  *Kennung* or *Kennen* in its quality entries. They now use that word (GH-1919)

### Security

- `[Build]` The 11 `pnpm audit` advisories (3 high, 8 moderate) are resolved: ReDoS and prototype
  pollution in Tiptap, script bypasses in `svgo`, and denial of service in `js-yaml`, `qs`,
  `devalue` and `undici`, plus a file read in the dev-only `vitest`. Dependencies are refreshed
  within their ranges -- `@nuxt/ui` 4.11, `vue` 3.5.43, `zod` 4.6 -- and `pnpm audit` is clean
  (GH-2049)

## [0.16.0] - 2026-09-18

### Added

- `[Tests]` The catalogs are checked against the backend the app runs on, rather than from the
  Python suite by reading `app/`. Every canonical parameter, every unit type and every provider has
  to be nameable here in eleven languages, and the app's own unit tests cannot notice one being
  added upstream: they read the catalogs and hold the locales to each other, so a new name in the
  backend leaves every catalog untouched and the parity green while the name falls back to a
  prettified English id in all eleven. `tests/e2e/i18n-coverage.spec.ts` asks `/api/glossary` for
  the names and the quantities and `/api/coverage` for the providers, which loses nothing -- the
  glossary serves the same 23 unit types the converter knows -- and the E2E workflow already runs
  on a change to `src/wetterdienst/**`, so an addition there still trips it
- `[Explorer]` An elevation for the point an interpolation or summary answers for, in metres above
  sea level, beside the coordinates. Air temperature falls about 0.65 K per 100 m, so a point in a
  valley and one on the ridge above it get different answers from the same stations; left empty,
  the readings are used as they come. Choosing the point by station fills it with that station's
  own height, a station naming its altitude as well as its position, and the field is shown either
  way so that a height is never carried without being seen

### Fixed

- `[Meteogram]` Wind barbs convert metres per second to knots the way the API does, a knot being a
  nautical mile -- 1852 m exactly -- per hour. Rounded to `1.944`, a speed sitting within 0.008% of
  a barb boundary or of the 2.5 kt calm threshold could be drawn as the next barb up from the one
  the value warrants

## [0.15.0] - 2026-09-04

### Added

- `[Glossary]` Names in all eleven languages for the twelve parameters the backend adds with the
  new DWD POI network -- the previous-day extremes (`temperature_air_max_2m_yesterday`,
  `wind_gust_max_yesterday`, `wind_speed_rolling_mean_max_yesterday` and their siblings), the
  12-hour extremes, the two past-weather codes and `radiation_sky_short_wave_direct_intensity`.
  The previous-day ones follow the phrasing `sunshine_duration_yesterday` already set in each
  locale -- "Vortag", "veille", "giorno precedente" -- rather than the "(last 24 h)" wording,
  since the value covers the previous calendar day and not a rolling window. The measured
  `evapotranspiration_last_24h` is labelled apart from the potential evapotranspiration it sits
  next to, which is what the two names mean

## [0.14.1] - 2026-08-31

### Fixed

- `[App]` Every page rendered nothing at all -- not even its own headings -- until the backend
  answered, most visibly on the Explorer. `useFetch` was awaited at the top level of `app.vue`,
  of the parameter selection and of the glossary page; with server-side rendering off, an async
  `setup()` suspends the surrounding boundary, so the version request blanked the whole app and
  the coverage request blanked whichever page asked for it. None of the three is awaited now: the
  page renders immediately, the provider and network selects show as loading while coverage is in
  flight, and the glossary's own loading state -- which the await had made unreachable -- appears
  again. The Explorer only showed this on a cold load, since a coverage answer already in the
  cache resolved the await at once
- `[Build]` The Coolify deploy step has failed on every run since 2026-08-17, so no release or
  nightly has reached the live app since -- which is why a published version could sit in GHCR
  while the running site stayed on the one before it. Coolify moved `/api/v1/deploy` from GET to
  POST and left the GET route answering `405 This endpoint has changed to a POST request.`, which
  `curl --fail` turned into an exit 22 after the image had already been built and pushed. The
  deploy call now uses POST

## [0.14.0] - 2026-08-31

### Added

- `[Glossary]` Names in all eleven languages for the twelve climate-index parameters the backend
  now serves, and for the two datasets carrying them. The threshold indices keep the term each
  language actually uses -- `Eistage`, `IJsdagen`, `Jours sans dégel`, `Dni mroźne` for the same
  quantity -- while the counted-threshold ones follow the phrasing already there for
  `count_days_precipitation_height_ge_1mm`, down to the decimal comma every locale but English
  writes
- `[Glossary]` Names in all eleven languages for the fifty phenological phases the backend serves
  with the new DWD phenology network -- `phenology_flowering_beginning`,
  `phenology_leaf_unfolding_beginning`, `phenology_harvest` and the rest. A phase is a day of the
  year on which something happened rather than a measured quantity, so the labels name the event
  and which end of it the day marks ("Flowering, start", "Blühbeginn", "Floraison, début") instead
  of the quantity-and-interval phrasing the rest of the catalog uses. The plant a phase was
  observed on is the dataset rather than the parameter, and those 110 names are not translated
  yet: they fall back to the prettified id, so "Annual Common Hazel" reads the same in all eleven
  languages until someone with the botanical vocabulary fills them in
- `[Explorer]` The interpolation settings show one field per search radius -- one for the
  parameters that vary slowly across a region, one for those that decorrelate faster -- where a
  single "Default (all)" box stood before. That box wrote a `default` key the backend has stopped
  accepting, and which never meant what it looked like: it replaced the shorter radius of every
  heterogeneous parameter along with the fallback, so setting 30 km there gave precipitation, fresh
  snow and visibility 30 km too. A radius left untouched is not sent at all, so a self-hosted
  instance configured through `WD_TS_GEO_STATION_DISTANCE_*` keeps its own. The hint below the
  fields says what the heterogeneous number means now that the backend scales it with the
  resolution: the value applies at hourly resolution and is scaled from there, times 0.75 at the
  minute resolutions and times 2 from daily upwards

### Fixed

- `[Explorer]` The CSV, Excel and JSON download in summary mode requested `/api/summary`, which is
  not a route -- nothing came back. The endpoint is `/api/summarize`, as the data view itself
  already used
- `[Explorer]` "Add parameter" no longer sends a row before it has a name. It seeded the row with
  the literal name `new_parameter`, which the backend used to ignore silently and now rejects, so
  clicking the button and requesting data without typing a name failed the whole request

## [0.13.0] - 2026-08-19

### Added

- `[API]` The API page documents the MCP endpoint the app has been serving unannounced: what it is,
  the URL, a ready-to-paste client configuration, and that it needs no key or account. The URL is
  built from the origin the page is served from rather than hard-coded, so a self-hosted or local
  instance shows its own address and the snippet can be copied as-is. The card appears only when
  the backend reports `mcp_enabled`: the endpoint is behind an optional extra, and an instance
  installed without it would otherwise hand every visitor a client configuration pointing at a 404
- `[About]` A page at `/about` carrying what the home page used to say about the project, plus a
  proper introduction to the maintainer -- what he works on, where he is, how to reach him -- and
  the same for the co-author, with a pointer to the full contributor list. Both cards render from
  one shape under a single "the people behind it" heading, so neither is a lesser layout than the
  other and no card header repeats the role beneath it. Nothing about a person is stated that
  they have not published themselves: the co-author's card carries no employer, location or age,
  because his GitHub profile gives none. Reachable from the footer and from the bottom of the home
  page
- `[About]` LinkedIn and Mastodon next to the GitHub and email buttons in the maintainer card. The
  Mastodon link carries `rel="me"`, so the profile there can verify the link back to this site, and
  wears the real Mastodon logo from simple-icons -- Lucide has no such glyph, and icons resolve
  through Iconify either way, so it adds no dependency
- `[Home]` A "what data you get" section, which is what a first-time visitor actually needs: the
  headline numbers, all 22 weather services named with their flags, and the six kinds of data
  behind them -- measurements, forecasts, water levels, radar, warnings and road weather. The
  provider list is pinned to the backend registry by
  `tests/test_app_i18n.py::test_app_home_lists_every_provider`, so a provider added
  upstream fails a test rather than quietly going unmentioned
- `[App]` `/docs` and `/openapi.json` are proxied onto this origin, so the hosted app serves the
  backend's Swagger UI as its own API reference. Only `/api/**` and `/mcp` were proxied before, and
  `/docs` on the app origin answered with the SPA shell
- `[Home]` A row pointing developers at the same data without clicking: the Python package on PyPI,
  the REST API at `/docs`, and the MCP endpoint at `/mcp`. The MCP chip says on hover that it is an
  endpoint rather than a page, because a browser GET to it answers 400 by design. The "514
  parameters" tile also leads to the glossary now, which is where each of them is explained
- `[Home]` The two open-source programmes the project runs on, as badges in a band of their own:
  JetBrains for a PyCharm licence and Anthropic for a Claude Max subscription, each linking to the
  programme and naming what it gives on hover
- `[Home]` A third line in the values statement: "Erderwärmung ist keine Meinung" / "Global warming
  is not an opinion". It is the one stance this project backs up by existing -- it serves the
  measurements, and the warming stripes are two clicks away. The solidarity line also reads LGBTQI+
  rather than LGBTQ+, in all eleven locales
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

- `[Build]` The Coolify deploy secret is `COOLIFY_APP_UUID`, not `COOLIFY_FRONTEND_UUID`, closing
  the last reference the rename had to leave behind: the name lived in GitHub settings rather than
  in this repo, so it could only follow once the secret itself had been re-created. The value is
  unchanged -- the same Coolify resource, under the name everything else already uses
- `[Build]` Dependabot watches the app's dependencies. There was no `npm` entry at all, so the
  ~50 packages under `app/` had never been offered an update by it -- only the Python side and the
  GitHub Actions were covered. Grouped into one weekly pull request, the way the Python group
  already is
- `[Footer]` The version line says `App` rather than `Frontend`. The rename below moved the
  directory, the image and the release tags, but left the one place a visitor actually reads the
  name -- so the footer went on calling the app by a name nothing else in the project uses. The
  backend half is untouched; `frontendVersion` is `appVersion`, and its counterpart is
  `backendVersion` rather than a bare `version`, since the two sit side by side
- `[Build]` The word "frontend" is gone from the rest of the app too -- the proxy and route
  comments, the parameter-label lookup chain, and the E2E guide, which told the reader to start a
  "frontend dev server" that no longer goes by that name. Two references stay on purpose: the
  `COOLIFY_FRONTEND_UUID` deploy secret, whose name lives in GitHub settings rather than in this
  repo, and the release-strategy note recording what the tags and image used to be called
- `[Build]` **Breaking for anyone pulling the image or tagging a release.** `frontend/` is now
  `app/`, and every artifact named after it followed: the image is
  `ghcr.io/earthobservations/wetterdienst-app`, releases are tagged `app-v*` rather than
  `frontend-v*`, and the workflows, Dockerfile and changelog were renamed to match. The 13
  historical tags were renamed on the remote and their GitHub Releases repointed, so the compare
  links below still resolve; the old image tags were copied to the new package, so nothing
  published becomes unpullable. A deployment pulling `wetterdienst-frontend` must be repointed --
  that package receives no further pushes
- `[Build]` `docker compose --profile app` now starts the app alone. The combined
  backend-plus-app profile is `--profile full`, because a service named `app` and a profile named
  `app` meaning something else could not both stand
- `[Build]` Node 24 (Krypton, the active LTS) everywhere. The image was on Node 25, which stopped
  at 25.9.0 and is end-of-life, and the release workflow was still on Node 20; the test workflow
  was already on 24. `engines.node` is `>=24.15.0` -- not a round number, but the floor the
  strictest dependency in the lockfile actually asks for
- `[Build]` pnpm pinned to 11.22.0 in the image, up from 11.9.0, which is what CI's `version: 11`
  already resolved to
- `[Build]` pnpm refuses dependency versions published less than three days ago
  (`minimumReleaseAge: 4320`), matching the cooldown Dependabot already applies by default to the
  other ecosystems in this repo. pnpm 11 defaults to one day
- `[Home]` The project description and the author avatars are gone from the home page, which is
  about the data now; both live on `/about`
- `[Home]` The features section is two cards rather than four, and titled for what it actually
  lists: what you can do with the data. "Multiple data sources" repeated the 22-service card, the
  `0 €` tile and the intro line; "geospatial queries" repeated the Explorer card's own pitch. What
  is left is export formats and interpolation/summarization, neither of which the page says
  anywhere else
- `[Home]` The end of the page has a structure. "What you can do with it" is a subsection of the
  data block, where it belongs, instead of a peer heading over two cards; the
  supporters are a band of their own in the same gradient as the stance above them, separated by a
  gap rather than a rule inside one box. Badges floating in bare whitespace between two structured
  blocks were what made the end of the page read as unstructured
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
- `[All pages]` The footer carries all four statements as icons, with the full wording on hover and
  as the accessible name, rather than two of them in short form. The four now live in one `values`
  section shared with the home page, so the two places cannot drift apart
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

- `[Tests]` The two E2E tests that reach for the API nav link match it exactly. `/api/i` had begun
  matching the home page's "REST API" link to the backend's Swagger UI as well, and Playwright's
  strict mode fails on an ambiguous locator rather than picking one
- `[de-hh]` The Hamburg locale spoke three languages at once. Sixteen strings were full Hamburger
  Platt -- "Wat jeder Parameter misst un in welke Eenheit de Weerten torüchkaamt", "Datenanfraag is
  fehlslaan" -- sitting between High German ones, and Platt is a separate language that the
  [Wikipedia article](https://de.wikipedia.org/wiki/Hamburger_Dialekt) describes as rarely spoken
  today; the living register is Hamburgisch, High German carrying the Low German layer. Fourteen
  further strings still addressed the reader as "Sie", inherited unchanged from `de`, so a reader
  met both forms. One register now: High German, "du" throughout, and the Hamburg vocabulary where
  a Hamburger would actually use it -- including the tagline, which read "för de Lüüd": the noun is
  Hamburg, the preposition and article were Low German, and the same page says "die Lüüd dahinter"
  a screen further down
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

[Unreleased]: https://github.com/earthobservations/wetterdienst/compare/app-v0.39.0...HEAD
[0.39.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.38.0...app-v0.39.0
[0.38.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.37.0...app-v0.38.0
[0.37.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.36.0...app-v0.37.0
[0.36.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.35.0...app-v0.36.0
[0.35.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.34.0...app-v0.35.0
[0.34.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.33.0...app-v0.34.0
[0.33.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.32.0...app-v0.33.0
[0.32.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.31.0...app-v0.32.0
[0.31.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.30.0...app-v0.31.0
[0.30.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.29.0...app-v0.30.0
[0.29.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.28.0...app-v0.29.0
[0.28.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.27.0...app-v0.28.0
[0.27.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.26.0...app-v0.27.0
[0.26.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.25.0...app-v0.26.0
[0.25.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.24.0...app-v0.25.0
[0.24.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.23.0...app-v0.24.0
[0.23.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.22.0...app-v0.23.0
[0.22.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.21.0...app-v0.22.0
[0.21.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.20.0...app-v0.21.0
[0.20.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.19.0...app-v0.20.0
[0.19.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.18.1...app-v0.19.0
[0.18.1]: https://github.com/earthobservations/wetterdienst/compare/app-v0.18.0...app-v0.18.1
[0.18.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.17.0...app-v0.18.0
[0.17.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.16.0...app-v0.17.0
[0.16.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.15.0...app-v0.16.0
[0.15.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.14.1...app-v0.15.0
[0.14.1]: https://github.com/earthobservations/wetterdienst/compare/app-v0.14.0...app-v0.14.1
[0.14.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.13.0...app-v0.14.0
[0.13.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.12.1...app-v0.13.0
[0.12.1]: https://github.com/earthobservations/wetterdienst/compare/app-v0.12.0...app-v0.12.1
[0.12.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.11.0...app-v0.12.0
[0.11.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.10.0...app-v0.11.0
[0.10.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.9.0...app-v0.10.0
[0.9.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.8.0...app-v0.9.0
[0.8.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.7.0...app-v0.8.0
[0.7.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.6.0...app-v0.7.0
[0.6.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.5.0...app-v0.6.0
[0.5.0]: https://github.com/earthobservations/wetterdienst/compare/app-v0.4.0...app-v0.5.0
[0.4.0]: https://github.com/earthobservations/wetterdienst/releases/tag/app-v0.3.0...app-v0.4.0
[0.3.0]: https://github.com/earthobservations/wetterdienst/releases/tag/app-v0.2.0...app-v0.3.0
[0.2.0]: https://github.com/earthobservations/wetterdienst/releases/tag/app-v0.1.0...app-v0.2.0
[0.1.0]: https://github.com/earthobservations/wetterdienst/releases/tag/app-v0.1.0
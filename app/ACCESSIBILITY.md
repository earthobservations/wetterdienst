# Accessibility

The app aims at **WCAG 2.2 level AA** (tracking issue: #2559). This file is a stub: it says what is
measured and how to run it. What was checked by hand, and the known limits, are added when the
baseline is empty.

## What is measured

`tests/e2e/accessibility.spec.ts` scans every page with [axe-core](https://github.com/dequelabs/axe-core)
(through `@axe-core/playwright`, in the Firefox project) against the tags `wcag2a`, `wcag2aa`,
`wcag21a`, `wcag21aa` and `wcag22aa`:

- every page, as it is first shown, in light and dark mode and in English and German,
- and, in light/English and dark/German, the states a first paint does not show: a station map with
  stations, a drawn chart (explorer, stripes, meteogram, widget), an open menu or popover, and an error
  notice.

The spec answers every `/api/*` request itself, in the browser (`tests/e2e/accessibility/mock-backend.ts`),
so it reaches neither the backend nor a provider. Map tiles and every other request to another host are
answered with a transparent pixel or refused. The icons the app loads from `api.iconify.design` at run
time are therefore not drawn in the scans.

## The baseline

The violations the app has today are recorded in `tests/e2e/accessibility/baseline.json`, one entry per
rule, page and state, with the modes and languages it occurs in. A scan fails on

- a rule broken that the baseline does not list, so the app cannot get worse, and
- a rule in the baseline that is no longer broken, so whoever fixes a violation removes its entry and the
  baseline only shrinks.

The CI job summary of `app-e2e.yml` reports the baseline's size.

## Running it

```bash
cd app
pnpm install
npx playwright install firefox
# the backend must answer /health (the e2e global setup checks it): docker compose --profile backend up -d
pnpm test:a11y             # the spec, against the baseline
pnpm test:a11y:report      # the baseline's size, as the job summary shows it
pnpm test:a11y:baseline    # regenerate the baseline from what the scans find now
```

The scripts set `CI=true`, which makes Playwright build and preview the production build, as CI does (stop
any server on port 4000 first, as it is no longer reused): the
baseline is of that build, as the dev server adds its own overlay. It was recorded in Firefox on Linux
(the `mcr.microsoft.com/playwright` image of the Playwright version in `package.json`), and rules that
depend on layout (`target-size`, `scrollable-region-focusable`) can differ on another system, so
regenerate it there. Regenerate it only when a violation has been fixed, to shrink it; a new violation is
fixed, not recorded.

## Not covered by the scans

Automated checks find only part of what WCAG asks for; a green suite is not an accessible app. Keyboard
use, a screen reader pass, reflow and zoom, text alternatives for the charts and the language of the page
are checked by hand, and written down here once the baseline is empty.

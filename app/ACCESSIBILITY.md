# Accessibility

The app aims at **WCAG 2.2 level AA** (tracking issue: #2559). This file says what is measured, how to run
it, what was checked by hand, and what is known not to conform.

## What is measured

`tests/e2e/accessibility.spec.ts` scans every page with [axe-core](https://github.com/dequelabs/axe-core)
(through `@axe-core/playwright`, in the Firefox project) against the tags `wcag2a`, `wcag2aa`,
`wcag21a`, `wcag21aa` and `wcag22aa`:

- every page, as it is first shown, in light and dark mode and in English and German,
- and, in light/English and dark/German, the states a first paint does not show: a station map with
  stations, a drawn chart (explorer, stripes, meteogram, widget), the table of the stripes' and the meteogram's values opened, the meteogram's compact day cards, an open
  menu or popover, an error notice, the explorer's notice for a request the server refused over a limit
  (`values-limit-refused`, and at 320 px `values-limit-refused-narrow`) and the note under the date range that
  says the page started one (`default-range-note`).

The spec answers every `/api/*` request itself, in the browser (`tests/e2e/accessibility/mock-backend.ts`),
so it reaches neither the backend nor a provider. Map tiles and every other request to another host are
answered with a transparent pixel or refused. The icons are the app's own (`/_nuxt_icon`, GH-3111), so
they are drawn in the scans.

### What axe does not see, measured anyway

The same pages and states (in light/English and dark/German) are scanned twice more
(`tests/e2e/accessibility/interact.ts`), and a rule broken is held to the baseline like any other:

- **hover**: every link, button, tab, option, menu item and element with a `hover:` style is hovered, once
  for each look (the same classes under a parent of the same classes are one), and axe's `color-contrast` is
  run on it (1.4.3; the scans at rest never hover, GH-2991),
- **keyboard**: the page is walked Tab by Tab from its top to where the order comes round, or to where a
  focus guard keeps the focus through more than three Tabs (an open menu or dialog, from where it holds the
  focus). Each stop is checked for a focus indicator, an outline, a ring
  (`box-shadow`, also on `::before` and `::after`) or Reka's highlight (2.4.7, `focus-not-visible`); for that
  indicator having 3:1 against what it lies on (1.4.11, `focus-indicator-contrast`); for not being hidden
  behind other content or outside what a map shows, sampled at five points of the part in the window and
  again half a second later (2.4.11, `focus-obscured`); for the focus leaving the page at once (2.1.2,
  `focus-lost`); and for the contrast of the text with the focus on it. Reka's invisible focus guards, and
  the proxies at either end of the toast region, are not stops. The rules are the app's own ids, in `CUSTOM_RULES` of `interact.ts`.

Beside the scans, `accessibility.spec.ts` drives widgets by keys alone (`keyboard operation`: the station
picker, a collapsible, a menu, and the narrow layout's menu, which is a dialog that keeps the focus and gives
it back; `chart controls by keyboard`: Plotly's modebar, and the table of values that stands for the stripes
and the meteogram, opened, reached and scrolled by keys; and Plotly's hover label and the names of its
modebar buttons, which Escape dismisses until the pointer moves, 1.4.13), checks that every page has a title of its own that a navigation announces (`page titles`, 2.4.2,
4.1.3) and that no page scrolls sideways at 320 px (`reflow at 320 px`, 1.4.10).

## The baseline

The violations the app has today are recorded in `tests/e2e/accessibility/baseline.json`, one entry per
rule, page and state, with the modes and languages it occurs in. A scan fails on

- a rule broken that the baseline does not list, so the app cannot get worse, and
- a rule in the baseline that is no longer broken, so whoever fixes a violation removes its entry and the
  baseline only shrinks.

What is left in it, and why it is not fixed in the app's own markup:

- `aria-required-children` and `scrollable-region-focusable`, the open station list: Nuxt UI's
  `USelectMenu` puts the search field and a focus scope inside the element with `role="listbox"`, and
  its scrolling viewport is not focusable. The app has no way to set either attribute; the fix is in
  Nuxt UI / Reka UI. Nuxt UI 4.12.0 moves the role to the viewport (nuxt/ui#7096); the app is on 4.11.3.
- `aria-hidden-focus`, the error toast: the two focus proxies in Reka UI's toast viewport are
  `aria-hidden` and focusable. Also upstream.

There is no `color-contrast` entry left. The brand green, `#00c950`, stays the fill of a solid primary
button; its label is `#0f172b` (`--app-text-on-primary` in `app/assets/css/main.css`, set for the
button in `app/app.config.ts`), 8.0:1 on the fill and 9.5:1 hovered in light mode, where the white
label it replaces was 2.2:1 and 1.9:1. Dark mode has the same label on its lighter fill, as Nuxt UI
already had it (10.0:1, and 6.1:1 hovered). A disabled button is exempt from 1.4.3 and from the scans; its
label is at 75 % opacity with its fill (4.2:1 in light mode). Text in the primary colour on white is
shade 700 and a fifth of the way to 800 (`.text-primary`), a hovered link button shade 800 (7.1:1; Nuxt UI's
75 % of the first was 3.4:1), and a hovered chip of the home page shade 700 (4.9:1; shade 500 was 2.2:1).
`tests/unit/button-contrast.test.ts` computes the hovered ratio of a solid button, as 75 % of the fill over
the page; the hover scan measures the rest.

The focus indicator is one solid 2 px outline for everything a keyboard reaches (`--app-focus-ring` in
`main.css`: shade 700 of the primary colour on light, 4.9:1 on white, shade 400 on dark, 10:1; the map takes
the light one in both modes). Nuxt UI's own is an outline at 25 % of the primary colour (1.2:1 to 1.7:1 on
white) and a ring in the primary colour (2.2:1), and its menu search fields draw none; they stay, beside it.

The Plotly charts take their chrome from the same tokens as the page (GH-3528): paper, plot, text, grid,
zero line, hover label and modebar are the `--app-chart-*` properties of `main.css`, made of Nuxt UI's
`--ui-*` tokens, which switch with the colour mode. `utils/chart-theme.ts` reads them with
`getComputedStyle` (resolved to `rgb()` by the browser's computed colour of a probe element, as Plotly does
not parse `oklch()`; no canvas, whose pixels a browser that resists fingerprinting scrambles), and
`useChartTheme()` reads them again when the class of `<html>` changes, so a chart follows a switch
without a reload. A chart that is saved (the download menus, and the camera of the modebar) or printed is
always the light one, whatever the screen shows: it is drawn again, off screen, in the light theme
(`utils/chart-export.ts`), and a print is drawn light for as long as it lasts (a light page is printed as
it is, and a zoom is kept), with a `@media print` rule in `main.css` for a chart that says it is still drawn dark
(`data-chart-scheme="dark"`) when the print comes before the redraw: transparent paper, black text and
wind barbs; a chart drawn light is left as drawn. On the themed chrome (the Explorer, the stripes, the
Forecast's hour labels) text and tick labels are the page's text and muted text (4.5:1 or more on the page
in both modes) and the zero line the muted text colour (3:1 or more), checked on the drawn charts by
`tests/e2e/chart-theme.spec.ts`; the grid is decoration. The series and the stripes' palette are data and
keep their colours, and the text that names a series is the series' hue at 4.5:1 or more on the paper
(`SERIES_LABEL` in `utils/chart-theme.ts`, GH-3618): the Forecast's y-axis titles and tick labels and its
weekend day labels, and the stripes' "data availability" label. On white that is a darker step of the
hue, #0e7490 for the wind's cyan (5.4:1; the line is #06b6d4, 2.4:1), #2563eb for the precipitation's blue
(5.2:1; 3.7:1), #dc2626 for the temperature's red and the weekend (4.8:1; 3.8:1), #4d7c0f for the pressure's
lime (5.0:1; 2.0:1) and #b45309 for the availability's gold (5.0:1; 2.2:1); on the dark paper (#0f172b) the
series' own colours already read (7.3:1, 4.9:1, 4.7:1, 9.0:1) and gold is #daa520 (8.0:1). The Forecast's
temperature zero line is the muted text colour like the Explorer's (3:1 or more). Not held to those ratios:
the Plotly logo of the modebar, Plotly's own black tile with coloured dots.

Every chart speaks the language of the page (GH-3625, 3.1.2): the names of the modebar's buttons and of
the weekdays and months of a date axis, through `plotly.js-locales` and Intl (`utils/plotly-locale.ts`,
which follows a switch of the language like a switch of the scheme). Plotly has no button names in Polish
or Danish and only some in Dutch, which stay English; Luxembourgish and Hamburg's German take German's.

There is no sepia mode. `main.css` once held a `html.sepia` block that redefined the `--ui-*` tokens, which
nothing in the app ever set (`colorMode` knows `light`, `dark` and `system`, and the settings offer those
three). It was removed (GH-2991): it could not be reached, its dimmed text was 4.1:1 and 3.6:1 on two of its own
panels, the brand green was 4.2:1 on its page, and most of the app's colours are `bg-white dark:bg-gray-900`
classes it would not have changed.

## On request, not by default

The scan takes half an hour and more, so it is not part of `pnpm test:e2e` or of the App E2E workflow
(`playwright.config.ts` ignores the spec unless `A11Y=1`). It runs

- from the Actions tab: *App accessibility*, *Run workflow*, or
- on a pull request that carries the **`a11y` label**: when the label is added, and on every push after it.

The *App accessibility* workflow (`.github/workflows/app-accessibility.yml`) has no path filter and is not
a required check. When it runs, the baseline is the gate: a rule broken that it does not list fails the
run, and so does an entry that is no longer broken. The run's summary page reports the baseline's size,
by rule, and what the run found against it; the scans' results are an artifact of the run. It runs in the
Playwright image the baseline was recorded in. A change that touches the markup, colours or ARIA of the app
should be run with the label before it lands.

## Running it

```bash
cd app
pnpm install
npx playwright install firefox
pnpm test:a11y             # the spec, against the baseline; needs no backend
pnpm test:a11y:report      # the baseline's size, as the job summary shows it
pnpm test:a11y:baseline    # regenerate the baseline from what the scans find now
```

The scripts set `CI=true`, which makes Playwright build and preview the production build, as CI does (stop
any server on the port first, as it is no longer reused): the
baseline is of that build, as the dev server adds its own overlay. It was recorded in Firefox on Linux
(the `mcr.microsoft.com/playwright` image of the Playwright version in `package.json`), and rules that
depend on layout (`target-size`, `scrollable-region-focusable`) can differ on another system, so
regenerate it there. Regenerate it only when a violation has been fixed, to shrink it; a new violation is
fixed, not recorded.

Two variables for a machine that is not CI: `E2E_PORT` serves the app on another port than 4000 (beside a
dev server that holds it), and `E2E_BROWSER=chrome` uses the system's Chrome where Playwright's Firefox does not
start. Chrome found the same violations as Firefox in the first-paint and state scans (on 2026-10-18), but
its layout is not the baseline's: use it to look, and Firefox on Linux to record.

## Checked by hand

On 2026-10-18, in Chrome 151 on macOS, by the scans above and by reading the components. The criteria new in
WCAG 2.2 first, as axe has no rule for most of them.

| Criterion | Result |
| --- | --- |
| 2.4.7 Focus visible, 1.4.11 Non-text contrast of the focus indicator | The keyboard scan measures it at every stop. **Was failing** nearly everywhere: 382 stops, counted per page so that the header links count on each, in 27 of the light/English scans had under 3:1; see above. |
| 2.4.11 Focus not obscured (minimum) | The keyboard scan checks it on every page and state. The sticky header hides no focused element. Leaflet draws markers beyond what the map shows and lets Tab reach them: a marker that takes the focus now pans the map until it is in view (`MapStations.vue`). The toasts stand over the foot of the page: while one is shown the page has room for it below the footer and a focused element scrolls clear of it (`useToastInset`, `html { scroll-padding-bottom }`; the footer's licences link was under the error toast at 1280x720, GH-3575). Tested (`keyboard operation`). |
| 2.5.7 Dragging movements | The map pans by drag, and by the arrow keys with the map focused, and zooms by its buttons and `+`/`-`; a station is also chosen in the list beside it. Plotly's charts zoom and pan by drag, with the modebar's buttons (zoom in, out, reset) as the single-pointer way. |
| 2.5.8 Target size (minimum) | axe's `target-size` is among the tags scanned (wcag22aa), on every page and state in both modes: no entry. |
| 3.2.6 Consistent help | The support and documentation links are in the header (icons) and the footer of every page, in the same order; the narrow layout has them in its menu. The widget has no header or footer by design. |
| 3.3.7 Redundant entry | Nothing is asked twice in a process. The explorer, forecast and stripes keep their selection in the URL, the settings in local storage. |
| 3.3.8 Accessible authentication | The app has no log-in and no cognitive test. |
| 2.4.2 Page titled | **Was failing**: every page was titled `Wetterdienst`. Each page names itself now, and a navigation is announced (`NuxtRouteAnnouncer`). |
| 2.2.2 Pause, stop, hide | **Was failing**: the emoji of the forecast's compact cards bounced for ever. They bounce once, and not at all under `prefers-reduced-motion`. Loading placeholders pulse while loading, which is a progress indication. |
| 1.4.10 Reflow | No page scrolls sideways at 320 px (tested). A table or chart scrolls in its own box. |
| 4.1.3 Status messages, 1.3.1, 2.4.3 Notice of a refused request (GH-3457) | A request the server refuses over a limit is a state of the table, not an error: its text (what the request comes to, what the server sends, what can be narrowed, with the selection's counts) is one `role="alert"` in a `section` that names itself by its heading, and the buttons (apply the window that fits, download everything as CSV) come after it in the tab order and outside the alert, so they are not read twice. A button's label wraps (320 px: no part of the notice reaches past the screen; tested), and it says what it does and how much, in the page's language. The notice raises no toast. When applying the window removes the notice while a button of it holds the focus, the focus goes to the table area (`useFocusAfterRetry`), which is where the answer, or the notice again, arrives. The note under the date range is a `role="status"` that stays in the page, hidden visually, when it has no text, and the description (`aria-describedby`) of both date fields. Tested in `tests/nuxt/components/limit-notice.test.ts`, `DateRangeSelector.test.ts` and the three states of the accessibility spec. |
| 2.1.2, 2.4.3 on the narrow layout's menu | **Was failing**: the menu was a fixed overlay that Tab walked out of. It is a dialog. |

The charts' text alternatives and keyboard access (#3145), checked on 2026-10-19:

| Criterion | Result |
| --- | --- |
| 1.1.1, 1.3.1 Text alternative of the climate stripes | **Was failing**: a `figure` with a name and nothing of what it shows. The figure is described (`aria-describedby`) by a sentence, the span of the years with the lowest and the highest value, and a "Show as table" button below it opens a table of every year drawn with its value and its class (the fifth of the range between the lowest and the highest year that gives its colour, named for temperature or precipitation). |
| 1.1.1, 1.3.1 Text alternative of the meteogram (also the widget) | **Was failing**: the same. The figure is described by the span of the forecast and its temperatures, and "Show as table" opens the values of the series the shown panels plot (as far as the horizon chosen reaches), one row for each time, in the station's time zone. The compact view is day cards with their own text (the weekday, the temperatures, the rain), and has no table. |
| 2.1.1 Plotly's modebar (explorer, stripes) | Not failing in the Plotly the app ships (3.7.0): the hand audit recorded `a` elements without `href`, but its buttons are native `button`s with an `aria-label`, in the tab order, operated by Enter and Space, and the toggles (zoom, pan) say so by their `active` class. The meteogram draws none. Tested (`chart controls by keyboard`), so an upgrade that changes it fails. |
| 1.1.1 Text alternative of the meteogram's compact day cards | **Was failing**: the weather of a day was an emoji, and a drop before the rain's amount, with no text. Both symbols are hidden from assistive technology (`aria-hidden`); the card holds the words for the weather, visually hidden (`meteogram.chart.weather.*`: thunderstorm, rain, snow, sleet, drizzle, fog, windy, dust or sand storm, blowing snow, cloudy, partly cloudy, sunny), in the language of the page, and "Precipitation:" before the amount. The name is held to the WMO's present-weather table: every code 0 to 99 has its kind in `tests/unit/weather-kind.test.ts`, and a code that names no weather the card can (haze, hail, a funnel cloud) is judged from the cloud cover and the rain. Tested for weather codes and for the cloud-cover heuristic, and in all eleven languages. |
| 1.4.13 Content on hover or focus, Plotly's hover label and the names of its modebar buttons | **Was failing**: nothing dismissed them. With the pointer over a chart, Escape hides the label (and the names of the modebar's buttons) until the pointer moves (`utils/chart-hover.ts`, `main.css`); the label stays while the pointer rests (persistent). Escape is not consumed, so it still closes a dialog. Tested (`chart-hover.test.ts`; in a browser, `chart controls by keyboard`). Hoverable: not met, see below. No hover of a chart starts with the focus, so that case does not arise. |

### Known not to conform

- **The hover label of the charts, 1.4.13, hoverable**: Plotly's hover label (the forecast's, the
  explorer's and the stripes') is dismissible (Escape) and persistent, but it cannot be moved onto. Plotly draws
  it in the chart's SVG without pointer events and takes it away as soon as the pointer leaves the point it
  belongs to, and its API has no option to keep it (`hoverlabel` styles it, `hovermode` and the
  `plotly_hover`/`plotly_unhover` events only choose and report the point). Replacing it with an element of
  the app's own that can be hovered would be a tooltip for three charts (positioning, touch, the unified
  forecast label with its day bands) for the sake of a pointer on a label whose values are in the table that
  stands for the chart ("Show as table": forecast, stripes, explorer), so the table is what the criterion's
  intent (a reader who magnifies the screen can reach what the label says) is met by. Not met to the letter.
- **The station map, 1.1.1 and 2.1.1**: markers are reachable by Tab and named by their station, but a map of
  hundreds of them is no way to choose a station by keyboard; the picker beside it is. Clusters are named by
  their count only.
- **Not checked**: a screen reader pass (VoiceOver, NVDA), text spacing (1.4.12), zoom to 200 % (1.4.4) and
  the nine languages besides English and German, which the scans do not cover.

## Lighthouse

Lighthouse is not part of CI (#2559 asked for it as a cross-check; it runs axe underneath, so it adds a
weighted score, its few best-practice rules, and a phone-sized viewport, not other WCAG rules). Run by hand on
2026-10-18 (Lighthouse 13.5.0, accessibility category, mobile and desktop, 17 URLs of the production build with the
spec's mock answers served as the backend), every page scores 100. One page did not before: the explorer with
a restored selection scored 98 for a heading that skipped a level (`heading-order`, an `h4` under an `h2`), now an `h3`.

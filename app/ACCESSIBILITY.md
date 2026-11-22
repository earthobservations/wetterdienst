# Accessibility

The app aims at **WCAG 2.2 level AA** (it was tracked in #2559, closed on 2026-11-10 with the acceptance below). This
file says what is measured, how to run it, what was checked by hand, and what is known not to conform.

## How it is accepted

What was decided for #2559 (maintainer, 2026-11-10), which is closed with the pull request that wrote this down:

- **axe runs on request, not in every e2e run.** `pnpm test:a11y` runs it locally, and the *App accessibility*
  workflow runs it in CI, from the Actions tab (*Run workflow*) or when a pull request carries the `a11y` label.
  It takes about 20 minutes on three workers of a laptop and several times that on one (445 tests, most of them a page
  load and a scan), which is why it is not part of `pnpm test:e2e` or of the App E2E workflow. The
  baseline is its gate (see below): a rule broken that the baseline does not list fails the run, and so does an
  entry that is no longer broken.
- **Lighthouse is run by hand before each app release**, and its accessibility score is recorded in this file
  (see *Lighthouse*): a row for each release. A release whose pages do not all score 100 says which did not and why.
- **The baseline lists its causes.** Every entry names the project that owns the cause and the issue there, if one
  exists, and says why the app does not fix it itself (see *The baseline*).

## What is measured

`tests/e2e/accessibility.spec.ts` scans every page with [axe-core](https://github.com/dequelabs/axe-core)
(through `@axe-core/playwright`, in the Firefox project) against the tags `wcag2a`, `wcag2aa`,
`wcag21a`, `wcag21aa` and `wcag22aa`:

- every page, as it is first shown, in light and dark mode and in English and German,
- and, in light/English and dark/German, the states a first paint does not show: a station map with
  stations, a drawn chart (explorer, stripes, meteogram, widget), the meteogram's chart at 390 px (scrolled sideways) and with its readout open from the keyboard, the stripes' and the meteogram's table view chosen, the meteogram's compact day cards, an open
  menu or popover, an error notice, the map tool with a place picked (wide, and at 390 px with the panel as a sheet under the map),
  with the measurements layer's choices, and with its stations failed to load, the explorer's notice for a request the server refused over a limit
  (`values-limit-refused`, and at 320 px `values-limit-refused-narrow`) and the note under the date range that
  says the page started one (`default-range-note`), and the chooser of the phone bar's four tools on the
  settings page at 390 px, with a tool moved, and at 320 px (`phone-bar-chooser`, `phone-bar-chooser-narrow`), the About page at 390 px
  scrolled down with both bars slid away (`phone-bars-hidden`, GH-4226) and the search at 390 px open as a bar over the top bar (`phone-search-open`), with the words of the app typed (`phone-search-words`, GH-3790; at 1280 px `search-words` and, for a position typed in, `search-place`) and the radar with the cells listed and the loop on a frame of the forecast (`cells-forecast-frame`, and at 390 px `phone-radar`, GH-3788).

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
  the proxies at either end of the toast region, are not stops (the proxies are found by where they are: a `span`
  with `tabindex="0"`, first or last in the `role="region"` that holds the toasts' list, as Reka UI 2.11 no longer
  gives them `aria-hidden`; `focus-guard.ts`, held by `tests/unit/a11y-focus-guard.test.ts`). The rules are the app's own ids, in `CUSTOM_RULES` of `interact.ts`.

Beside the scans, `accessibility.spec.ts` drives widgets by keys alone (`keyboard operation`: the station
picker, a collapsible, a menu, and the narrow layout's menu, which is a dialog that keeps the focus and gives
it back; `chart controls by keyboard`: the toolbars of the stripes' and the explorer's charts (the buttons in the tab order,
named, walked by Tab, Enter on zoom in narrowing the window and Space on reset putting the whole of it back), the stripes' and
the explorer's keys and readout (hoverable, dismissed by Escape, persistent, and the focus handed back from its Close button, 1.4.13),
the explorer's legend, which turns a series off and on from the keyboard, the forecast chart's readout (the same three) and its
keys, the table of values that stands for the explorer and the widget, opened, reached and scrolled by keys, and the table view of the stripes and of the meteogram, chosen and read by the arrow keys of their switch), checks that every page has a title of its own that a navigation announces (`page titles`, 2.4.2,
4.1.3) and that no page scrolls sideways at 320 px (`reflow at 320 px`, 1.4.10).

## The baseline

The violations the app has today are recorded in `tests/e2e/accessibility/baseline.json`, one entry per
rule, page and state, with the modes and languages it occurs in. A scan fails on

- a rule broken that the baseline does not list, so the app cannot get worse, and
- a rule in the baseline that is no longer broken, so whoever fixes a violation removes its entry and the
  baseline only shrinks.

The baseline is empty: the app has no recorded violation. `tests/e2e/accessibility/baseline.json` has an empty
`entries` list, so every rule broken in any scan fails the run. It held four entries (three rules) until
@nuxt/ui 4.12.0 (GH-3950), all caused by Nuxt UI's or Reka UI's own markup, which the app could not reach:

- `aria-required-children` and `scrollable-region-focusable` of the station `USelectMenu` (explorer and meteogram,
  `station-menu-open`): [nuxt/ui#7075](https://github.com/nuxt/ui/issues/7075), fixed by nuxt/ui#7096 in 4.12.0
  (the listbox role moves to the options viewport and the search field stays outside it).
- `aria-hidden-focus` of the toast viewport's two focus proxies (explorer, `values-error`):
  [unovue/reka-ui#2776](https://github.com/unovue/reka-ui/issues/2776), fixed by unovue/reka-ui#2980 in 2.11.0,
  which 4.12.0 depends on.

A violation found later is fixed, not recorded; if its cause is upstream and cannot be worked around in the app's own
markup, it is an entry (`issue` and `reason`, held by `tests/unit/a11y-baseline.test.ts`), and the entry goes with the
dependency bump that fixes it.

There is no `color-contrast` entry left. The colours are the tokens of `app/assets/css/main.css` (GH-3518):
the primary colour is the logo's blue, `#2E6FD1` (`brand-600`), the fill of a solid primary button with a
white label (4.9:1); hovered and pressed, the fill darkens to shades 700 and 800 (6.9:1 and 9.4:1) instead of
Nuxt UI's 75 % of the fill, which lightens it (`app/app.config.ts`). In dark mode the fill is shade 400 with
the logo's navy as the label (7.0:1), lightening to 300 and 200. Text in the primary colour on white is shade
700 (6.9:1, 5.9:1 on its own tint), a hovered link shade 800 by day and 300 at night. The neutrals are grey
with the logo's navy in it (`ink-*`): dimmed text is 5.4:1 on white and 4.7:1 on a hovered field, muted text
at night 6.2:1 on a card. A disabled button is exempt from 1.4.3 and from the scans. The edge of a field, a
checkbox and an unchecked switch is `--ui-border-accented`, 3.3:1 on white and 3.1:1 at night (1.4.11).
`tests/unit/button-contrast.test.ts` reads the tokens from `main.css` and holds each pair to its ratio; the
hover scan measures the rest.

The Meteogram's own chrome (GH-3642): the icons of its panel toggles and of its summary line are in the series' label
colours (`SERIES_LABEL` in `utils/chart-theme.ts`: cyan, lime, blue, red and slate for the cloud cover), not in
the Tailwind shades they had (cyan-500, lime-500, red-500, blue-500 and slate-400), which are 1.9:1 to 3.8:1 on white. Each is 4.6:1 or more on the toolbar by day and at night
and 3.9:1 or more on the wash behind a toggle that is on (a mark that carries a state: 3:1, 1.4.11); the card of today
has an edge of 3:1 or more. A toggle also says whether it is on (`aria-pressed`) and is named by an `aria-label` that
is its `title`, the same i18n key (4.1.2, GH-3951). Colour is not the only cue of the state (1.4.1, GH-3951): a toggle that
is on draws the filled variant of its icon (`i-ph-wind-fill`), one that is off the outline (`i-ph-wind`). In forced colours the
border is recoloured and is the same on and off, so only the icon's shape tells on from off there.
`tests/nuxt/components/Meteogram.test.ts` holds that, the colours and the card's edge in the rendered component.
`tests/unit/button-contrast.test.ts` reads every `text-<colour>-<step>`
class of the markup from Tailwind's palette, `gray` (the app's `ink`) and, since GH-3952, `primary` and `brand` (the app's
`brand` scale, read through `main.css`; `app.config.ts` makes `brand` the primary colour, and `.dark` changes which shade is
`--ui-primary` but redefines no shade) and fails for one under 4.5:1 where it
is painted: on white, and on the dark card for a `dark:` class and for a class that has no `dark:` partner in its class
string. A class it cannot read (an opacity, `text-[#hex]`) fails too. No class of the primary scale is exempt. The
48 icons and spinners in `text-primary-500` (3.47:1 on white, enough as a mark that carries meaning, 3:1 by 1.4.11, but not
as the text-coloured icon the test takes it for) are `text-primary-600 dark:text-primary-500` now: 4.87:1 on white by
day, and at night the shade they had, 4.53:1 on a card (600 would be 3.22:1 there). Links stay `text-primary-700` by day
(6.9:1) and 400 or 500 at night (6.3:1 and 4.5:1). An allow-list of non-text uses at 3:1 was not written: darkening costs
the look next to nothing, and a list of exemptions is something to keep.

The focus indicator is one solid 2 px outline for everything a keyboard reaches (`--app-focus-ring` in
`main.css`: shade 700 of the primary colour on light, 6.9:1 on white, shade 300 on dark, 9.6:1; the map takes
the light one in both modes). Nuxt UI's own is an outline at 25 % of the primary colour and a ring in the
primary colour, and its menu search fields draw none; they stay, beside it.

The shell (GH-3518) has a skip link, the first stop of every page, to the page's `main`; the header and the
tab bar of the narrow layout are fixed, and the page scrolls a focused control clear of them
(`scroll-padding`); in a window lower than 30 rem (a phone on its side, 400 % zoom) neither is fixed. On a phone (below 40 rem)
the bars hide while the page is scrolled down (GH-4226, the table below). In forced
colours (Windows contrast themes) the icons are painted in the colour of their text, so an icon-only button
keeps its icon, the tiles of the tools are outlined, and the tab of the current page is underlined.

The forecast's chart (GH-4059) is Apache ECharts, drawn as SVG, and takes its colours from the same tokens (the series'
label colours below, the text and muted text of the page, `useChartTheme()`, which a switch of the scheme and a print
read again); its weather symbols are the light or the dark set of Yr's (`public/yr-symbols/`, CC BY 4.0, credited under
the chart, under the day cards where there is no chart, and in `/third-party-licenses.txt`), in the mode of the page. It
has the shape of a chart that does not depend on the screen: fixed heights for the panels and 10 px for each hour (up to
22 px where the whole forecast fits), so that on a phone it scrolls sideways (the native scroll of a strip under the
chart, so the touch scroll, the scroll bar and the keys are the browser's) with its axes in view, and a rotation changes
how much of it is seen, not its shape. Where the pointer can do more than the keyboard, the keyboard can do the same
(2.1.1, 2.5.7): the chart is one tab stop (`role="figure"`, named, described by the span of the forecast and by the
keys); Left and Right step the crosshair by an hour (Shift: six hours; Page Up and Page Down: a day; Home and End: the
ends) and a live region says the hour and every value of it; `+`, `-` and `0` zoom in, out and back; buttons in the
toolbar do what a dragged box, a pinch and the scroll bar do (zoom in and out, earlier and later hours, reset); a mouse
drags a box to zoom to and a double click resets. The readout, which a hover and the keys show, is an element of the
page and meets 1.4.13: the pointer moves onto it (it stays level with the pointer, one step from the crosshair), it
stays until the pointer or the focus leaves, Escape closes it wherever they are without being consumed (a dialog still
closes) and it has a Close button for a touch; it returns when the pointer moves on or a key steps.
`prefers-reduced-motion` draws without animation. Held by `tests/nuxt/components/MeteogramChart.test.ts`,
`tests/unit/meteogram-*.test.ts` and, in a browser, `tests/e2e/meteogram-chart.spec.ts` and the scans of the meteogram
and the widget.

The climate stripes (GH-4068) are Apache ECharts, drawn as SVG, and take the colours of their text from the same tokens
(`useChartTheme()`, which a switch of the scheme and a print read again; the availability label is the gold of
`SERIES_LABEL`); the stripes are data and the same in both. The chart is one tab stop
(`role="figure"`, named, described by the sentence of what it shows and by its keys); Left and Right step through the
years that have a stripe (Page Up and Page Down ten at a time, Home and End the ends), `+`, `-` and `0` zoom in, out and
back, and a live region says each year and its value. Where the pointer can do more than the keyboard the keyboard can
do the same (2.1.1, 2.5.7): the toolbar's buttons (zoom in and out, earlier and later years, reset, the camera) do what a
dragged box, a pinch and Ctrl with the wheel do. The readout is an element of the page, level with the pointer and next to
its stripe, so that the pointer moves onto it from the stripe without crossing another; it stays until the pointer or the
focus leaves, Escape closes it wherever they are without being consumed, and a Close button is the way for a touch (1.4.13).
The stripe it is for is marked by a black ring in a white one, which reads on every colour of the scale. The chart draws no
animation, so `prefers-reduced-motion` has nothing to switch off.

The stripes' table is a view of its own (GH-4233), the fourth choice of the switch that also chooses stripes, bars and bars with a
scale (`variant=table` in the link): a radio group, one tab stop, the arrow keys, Home and End choose and move the focus, as the
forecast's switch does. In the table view the chart, its toolbar and its keys are not in the page (the chart's code is not even
loaded for a link that opens the table), and the table is the forecast's (`ValuesTable`, `full`): a caption that is the chart's name,
column headers with `scope`, the year as the header of its row, the header and the year kept in view while it scrolls, and its box
a region that takes the focus, so that the keys scroll it. The unit is in the headers, the values follow the unit settings, and the
only text above the table is the short line of what the colours are measured against (there is no note: what the class and the
anomaly are is in the page's About text, and the whole reference sentence in the CSV). The download of the table is a CSV, with
the reference, the credit and the licence as comment lines, after a UTF-8 byte order mark (Excel reads the file as UTF-8). In the image views (stripes, bars, bars with a scale) the figure is
described by the sentence of what it shows, the line of what its colours are measured against, and a hint that the values are in
the table (`stripes.tableHint`, which names the switch and its "Table" choice), so the data is reached by the summary and the switch;
there is no disclosure under the image any more. Printed, the table view is a table, whole (its box does not cut it at 70 % of the
height of the window), and the image views the chart. The line under the chart is short and the method (the centre of the scale,
the 16 colours, why a year keeps its colour, what the bars and the table are) is in the page's About text, the same for every
station. Held by `tests/nuxt/components/StripesChart.test.ts`,
`tests/unit/stripes-*.test.ts` and, in a browser, `tests/e2e/stripes-chart.spec.ts` and the stripes' tests of
`accessibility.spec.ts`.

The Explorer's chart (GH-4096) is Apache ECharts, drawn as SVG, in the chunk the forecast and the stripes load (the Explorer route
loads no Plotly), and is the stripes' and the forecast's in what it does for a keyboard, a screen reader and a pointer. It is one
tab stop (`role="figure"`, named, described by its keys); Left and Right step through the moments that have a value in a series
that is shown (Shift ten at a time, Page Up and Page Down a window's width, Home and End the ends), `+`, `-` and `0` zoom in, out and back,
and a live region says each moment and the values of the series there. Where the pointer can do more than the keyboard the keyboard can do the
same (2.1.1, 2.5.7): the toolbar's buttons (earlier, later, zoom out, zoom in, reset, the camera) do what a dragged box, Ctrl with the
wheel and a pinch do. The legend is drawn in the chart, so that a saved image has it, and operated from a button over each of its items
(`aria-pressed`, named by the series, in the tab order between the toolbar and the chart): a series that is turned off is out of the plot,
the axis, the readout and the keys, and is struck out and grey in the legend, so the state is not the colour's alone. The readout is an element of the
page, docked at the edge of the chart that the crosshair is not on (as the forecast's), so that a pointer that scrubs along the times does not meet it
on the way and can move onto it; it stays until the pointer or the focus leaves, Escape closes it wherever they are without being consumed, a Close
button is the way for a touch and gives the focus back to the chart (1.4.13). The crosshair and a dot on each series are drawn in the chart. The y axis follows the window, so a zoomed
chart is not flat; the times are in UTC (as the chart always had them) and written by Intl in the language of the page. A gap in the data (a row without a
value) is a gap in the line, and the keys step over it. A series of many points is cut to what the plot can tell apart (the lowest and the highest
value and the first and last of each pixel column of it, `drawnPoints` in `utils/explorer-model.ts`), so that a decade of hourly values
draws in a few milliseconds and no peak is lost; the readout and the keys read the data, not what is drawn. The chart draws no animation, so
`prefers-reduced-motion` has nothing to switch off. "Show as table" is the table of every value, as it was. The series' colours are data and
the same hues on both pages, the light page's a step darker where the hue is under 3:1 on white (green, amber, cyan, lime and orange:
`SERIES_COLOURS` in `utils/explorer-model.ts`), so every mark is 3:1 or more on the paper in both modes (1.4.11). Held by
`tests/nuxt/components/ExplorerChart.test.ts`, `DataViewer.test.ts`, `tests/unit/explorer-*.test.ts` and, in a browser,
`tests/e2e/explorer-chart.spec.ts`, the Explorer's tests of `accessibility.spec.ts` and `chart-theme.spec.ts` (the focus ring of a toolbar
button, a legend item and the chart: 2 px, 3:1 on the dark paper) and `chart-print.spec.ts`.

The charts take their chrome from the same tokens as the page (GH-3528): paper, plot, text, grid,
axis and zero line are the `--app-chart-*` properties of `main.css`, made of Nuxt UI's
`--ui-*` tokens, which switch with the colour mode. `utils/chart-theme.ts` reads them with
`getComputedStyle` (resolved to `rgb()` by the browser's computed colour of a probe element, as a chart library
does not parse `oklch()`; no canvas, whose pixels a browser that resists fingerprinting scrambles), and
`useChartTheme()` reads them again when the class of `<html>` changes, so a chart follows a switch
without a reload. A chart that is saved (the download menus, and the camera of the explorer's or the stripes' toolbar) or printed is
always the light one, whatever the screen shows: it is drawn again, off screen, in the light theme
(`save()` of `ExplorerChart.vue` and of `StripesChart.vue`; the explorer's image is as large as the chart on the page, one pixel to a pixel, and its facets are stacked into one), and a print is drawn light for as long as it lasts (a light page is printed as
it is, and a zoom is kept): `useChartTheme()` hands the light theme from `beforeprint` to `afterprint`, and each chart
is drawn again before the print is laid out. The forecast's chart is printed as it shows, scaled to the sheet. On the themed chrome (the
Explorer, the stripes, the Forecast's hour labels) text and tick labels are the page's text and muted text (4.5:1 or more on the page
in both modes) and the zero line the muted text colour (3:1 or more), checked on the drawn charts by
`tests/e2e/explorer-chart.spec.ts` (the Explorer's), `stripes-chart.spec.ts` and `meteogram-chart.spec.ts`, and `tests/e2e/chart-theme.spec.ts`, which also holds the focus ring of the explorer's toolbar button, legend item and chart to the page's own (2 px, 3:1 on the dark paper, 1.4.11; Plotly's modebar had a black one, 1.2:1 there); the grid is decoration. The series and the stripes' palette are data and
keep their colours, and the text that names a series is the series' hue at 4.5:1 or more on the paper
(`SERIES_LABEL` in `utils/chart-theme.ts`, GH-3618): the Forecast's y-axis titles and tick labels and its
weekend day labels, and the stripes' "data availability" label. On white that is a darker step of the
hue, #0e7490 for the wind's cyan (5.4:1; the line is #06b6d4, 2.4:1), #2563eb for the precipitation's blue
(5.2:1; 3.7:1), #dc2626 for the temperature's red and the weekend (4.8:1; 3.8:1), #4d7c0f for the pressure's
lime (5.0:1; 2.0:1) and #b45309 for the availability's gold (5.0:1; 2.2:1); on the dark paper (#0f172b) the
series' own colours already read (7.3:1, 4.9:1, 4.7:1, 9.0:1) and gold is #daa520 (8.0:1). The Forecast's
temperature zero line is the muted text colour like the Explorer's (3:1 or more).

The Forecast's snow panel (GH-4091, only at the 15 stations that have MOSMIX-SNOW) is three plots with one switch, each with its
own axis because their numbers differ in size: the new snow as bars, the snow depth and the chance of more than 10 cm as lines. Their
colours are the label colours of `SERIES_LABEL` themselves (indigo, teal and gold), so the bars and lines have 3:1 on the paper (1.4.11)
and the titles and tick labels 4.5:1 (1.4.3) in both schemes, held by `tests/unit/meteogram-snow.test.ts` and measured in the drawn
chart by `tests/e2e/meteogram-snow.spec.ts`. The readout, the live region and the table give the three values for the 3-hourly steps
that have them; the source (MOSMIX-SNOW, DWD) is text under the chart and prints with it.

Every chart speaks the language of the page (GH-3625, 3.1.2): the names of the toolbars' buttons, the legend's group, the readout and the keys' hint are
the page's own messages (`dataViewer.chart.*`, `stripes.chart.*`, `meteogram.chart.*`, in all eleven languages), and the
weekdays, months and numbers are Intl's, which follows a switch of the language like a switch of the scheme; Luxembourgish and
Hamburg's German take German's. (Plotly's own button names, through `plotly.js-locales`, were the explorer's until GH-4096; the
library is out of the app since GH-4102.)

There is no sepia mode. `main.css` once held a `html.sepia` block that redefined the `--ui-*` tokens, which
nothing in the app ever set (`colorMode` knows `light`, `dark` and `system`, and the settings offer those
three). It was removed (GH-2991): it could not be reached, its dimmed text was 4.1:1 and 3.6:1 on two of its own
panels, the brand green was 4.2:1 on its page, and most of the app's colours are `bg-white dark:bg-gray-900`
classes it would not have changed.

## On request, not by default

The scan is 445 tests, most of them a page load and a scan: about 20 minutes on three workers of a laptop
(`pnpm test:a11y --workers=3`), several times that on the one worker CI uses. So it is not part of `pnpm test:e2e` or of
the App E2E workflow (`playwright.config.ts` ignores the spec unless `A11Y=1`). It runs

- from the Actions tab: *App accessibility*, *Run workflow*, or
- on a pull request that carries the **`a11y` label**: when the label is added, and on every push after it.

The *App accessibility* workflow (`.github/workflows/app-accessibility.yml`) has no path filter and is not
a required check. When it runs, the baseline is the gate: a rule broken that it does not list fails the
run, and so does an entry that is no longer broken. The run's summary page reports the baseline's size,
by rule, and what the run found against it; the scans' results are an artifact of the run. It runs in the
Playwright image the baseline was recorded in. A change that touches the markup, colours or ARIA of the app
should be run with the label before it lands.

Last full run: 2026-11-10, on @nuxt/ui 4.12.0 and Reka UI 2.11.0 (`pnpm test:a11y --workers=3`, Chrome on macOS, as
Playwright's Firefox does not start there; axe 4.13.0): 393 tests, 393 passed, none retried, in 14.9 minutes, against the
empty baseline: 362 scans of 16 pages found no violation at all. (The run before the bump, on 4.11.3, found exactly the
four entries the baseline then held.)

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
| 2.5.7 Dragging movements | The map pans by drag, and by the arrow keys with the map focused, and zooms by its buttons and `+`/`-`; a station is also chosen in the list beside it. The explorer's chart zooms by a dragged box and a pinch (and Ctrl with the wheel), with the buttons of its toolbar (earlier and later, zoom in and out, reset) as the single-pointer way, and keys on the chart itself. The stripes zoom by a dragged box and a pinch, with the buttons of their toolbar (earlier and later years, zoom in and out, reset) as the single-pointer way, and keys on the chart itself. The forecast's chart zooms by a dragged box and a pinch and scrolls by its scroll bar or a touch, with buttons in its toolbar (earlier and later hours, zoom in and out, reset) as the single-pointer way, and keys on the chart itself. The chooser of the phone bar's tools is dragged by a handle and moved by an up and a down button on each row, which do all that dragging does (see "The phone bar and its chooser"). |
| 2.5.8 Target size (minimum) | axe's `target-size` is among the tags scanned (wcag22aa), on every page and state in both modes: no entry. |
| 3.2.6 Consistent help | The support and documentation links are in the footer of every page, in the same order, and support is also a heart in the header from 80 rem; the narrow layout has them in its menu sheet, and the search finds them. The widget has no header or footer by design. |
| 3.3.7 Redundant entry | Nothing is asked twice in a process. The explorer, forecast and stripes keep their selection in the URL, the settings in local storage. |
| 3.3.8 Accessible authentication | The app has no log-in and no cognitive test. |
| 2.4.2 Page titled | **Was failing**: every page was titled `Wetterdienst`. Each page names itself now, and a navigation is announced (`NuxtRouteAnnouncer`). |
| 2.2.2 Pause, stop, hide | **Was failing**: the emoji of the forecast's compact cards bounced for ever. They bounce once, and not at all under `prefers-reduced-motion`. Loading placeholders pulse while loading, which is a progress indication. |
| 1.4.10 Reflow | No page scrolls sideways at 320 px (tested). A table or chart scrolls in its own box. |
| 4.1.3 Status messages, 1.3.1, 2.4.3 Notice of a refused request (GH-3457) | A request the server refuses over a limit is a state of the table, not an error: its text (what the request comes to, what the server sends, what can be narrowed, with the selection's counts) is one `role="alert"` in a `section` that names itself by its heading, and the buttons (apply the window that fits, download everything as CSV) come after it in the tab order and outside the alert, so they are not read twice. A button's label wraps (320 px: no part of the notice reaches past the screen; tested), and it says what it does and how much, in the page's language. The notice raises no toast. When applying the window removes the notice while a button of it holds the focus, the focus goes to the table area (`applyWindow`, with `useFocusAfterRetry` as the fallback), which is where the answer, or the notice again, arrives; that area is a `role="group"` named by the page's own "Data" heading, so that the focus it takes is announced with a name (GH-3722). The note under the date range is a `role="status"` that stays in the page, hidden visually, when it has no text (announced as the text changes; the first station mounts the selector with the note in it, so the selector writes a note that is there at the start into the status 150 ms after the status is in the page, which is the change a screen reader announces; not checked with a screen reader), and the description (`aria-describedby`) of both date fields. "Clear date range" hands the focus it held to the two date fields as a group (`role="group"`, named "Date Range", with the focus ring when the button was pressed by keyboard) and not to the first date input, which iOS may answer by opening its picker (not checked on a device). Tested in `tests/nuxt/components/limit-notice.test.ts`, `DateRangeSelector.test.ts` and the three states of the accessibility spec. |
| 4.1.2, 1.4.1 The theme buttons | **Was failing** (GH-3969): the chosen theme of `/settings` (System, Light, Dark) was shown by the fill alone. The three are toggle buttons in a group named by the section's title (Appearance): the chosen one is `aria-pressed="true"`, the others `"false"`, as the map's layer buttons are. `tests/nuxt/pages/settings.test.ts` holds it. |
| 4.1.2, 1.4.1 The Explorer's toggle buttons | **Was failing** (GH-3989): the chosen mode (Station, Interpolation, Summary), forecast run, source of the interpolation's point, shape and skip criterion of the Explorer, and the theme buttons of the header's settings menu, were shown by the fill alone. Each row is a group named by its label (`role="group"` with `aria-label`, or `aria-labelledby` where the label is on the page) of toggle buttons, the chosen one `aria-pressed="true"`, the others `"false"`, as the theme buttons of `/settings` are. They are plain buttons, so Tab walks along them and Enter or Space chooses (no roving tabindex); the arrow keys of `SegmentedControl` (a radio group) are for the one-of-few views of a single result. `tests/nuxt/pages/explorer.test.ts`, `tests/nuxt/components/interpolation-summary-selection.test.ts` and `tests/nuxt/components/SettingsMenu.test.ts` hold it. |
| 2.1.2, 2.4.3 on the narrow layout's menu | **Was failing**: the menu was a fixed overlay that Tab walked out of. It is a dialog (the sheet the tab bar's Menu opens, GH-3518), as is the search. |

The map tool (`/map`, GH-3650), by the scans above (the states `map: station-picked`, `measured-layer`, `stations-failed` and
`phone-station-picked`) and by the tests of `tests/nuxt/pages/map.test.ts` and `tests/e2e/map.spec.ts`:

| Criterion | Result |
| --- | --- |
| 2.1.1, 2.5.7 The map and its stations | The stations are dots on canvas tiles, not markers, so Tab does not walk through some thousand of them. A station is reached by the panel: its search, the list of the eight stations nearest the centre of the map, and "Pick the centre of the map", which picks the station within half a kilometre of the centre, else the station for the place at the centre, as a click of a mouse that is not on a dot would (it has no ring of a finger). The map itself is a named `application` that pans by the arrow keys and zooms by `+` and `-` and by its two buttons (40 px), so no drag is needed. At the outer zooms the stations that lie close together are groups (GH-4079; made by distance, within 60 px of a station, down to zoom 8, GH-4241): a disc with a number, drawn on the same canvas tiles and so no more a stop of Tab than a dot is. A click or tap on one zooms in on its stations, which the polite status announces ("Zoomed in on a group. Stations in it: 40"); for the keyboard the way in is the map's own, `+` and the zoom buttons, and the panel, which lists and picks stations whatever the map groups. The legend is in the layers panel (GH-4227), under the switch, with a divider and a heading "Legend": it says what a number is while the map is grouped, and on a layer with stations that have stopped (the measurements) what a filled and a hollow dot are and that the filled part of a group's ring shows how many of its stations still report (the map carries no box of it; its swatches have the map's white halo, so they stand against the panel by day and at night; the panel scrolls where it is taller than the map, at 320 px too). The map's own description (`aria-describedby`, a text that is not shown) says the same in sentences, so a screen reader that does not open the panel learns what the dots and discs are: a place is one group, of stations of both kinds, drawn as a filled disc where all report, a hollow ring where none does, and for a mix a hollow ring with a band filled for the share that reports, a number in the dot's blue on the light middle (blue on white, 7:1; the edges are the dots' own, 1.4.11, so the share is a difference of shape and not of colour alone); the click's announcement says how many of the stations report ("Zoomed in on a group. Stations in it: 40, of them reporting: 25"). The layers and the grouping are behind one button over the map (GH-4209): a round button of 44 px with a layers icon in the map's top right corner, named "Layers and grouping" (`aria-label` and `title`), which says whether its panel is open (`aria-expanded`) and which it is (`aria-controls`). The panel is a Nuxt UI popover (a dialog named like the button): a radio group for the layer (forecast stations, DWD measurements; arrow keys, Space), on the measurements the two selects of the resolution and the dataset, and under them the switch "Group stations" (on by default; its row is 44 px high and its label is the whole of that height, so the row is the target). A layer of more than 10,000 stations cannot be left ungrouped: the switch is on and disabled, and a note, which the switch is `aria-describedby`, says why. Escape closes the panel and gives the focus back to the button; a press outside closes it too, and when that press is on the map, the click that belongs to it is swallowed by the map (it picks no place and zooms in on no group, whatever the press is on, however long it is held); the next click is the map's own. The panel fits a 320 px window in all eleven languages (tested). The zoom buttons are at the map's bottom right and the credit of OpenStreetMap under them, at the foot of the map. The station picked is drawn in a pane above the groups, so a group never hides it. A change of layer picks the station again, by its WMO number where both layers have one and otherwise by the place, and the polite status says which station was chosen and, for the same station by its number, that it is the same ("Hamburg-Fuhlsbüttel chosen. The same station, by its WMO number 10147."); the panel shows the same sentence under the station's position. Choosing a station by the list moves the focus to its name; "Back to the stations" gives it back to the station in the list. A pick by a click on the map does not move the focus, and is announced in a polite status. |
| 1.3.2, 2.4.3 Order | On a phone the map comes first and the panel under it as a sheet; from 72 rem the panel is on the left. The page puts the two in the order the window shows them (`parts` in `map.vue`: the DOM is reordered, not hidden). The phone's tab bar holds the four tools the reader chose (Forecast, Explorer, Stripes and the Radar until then, GH-3788) and the Menu, and marks its Menu as the page one is on while that is the map, as long as the map is not one of the four and so is in the Menu's sheet (`aria-current="true"`, which a screen reader says, and the bar over the tab; tested at 390 px, after a pick that changes the address too; the map marks its own tab where the reader has put it in the bar), so the keyboard and a screen reader meet the layers button, the map and the panel in the order of the screen at both widths. Tested. |
| 2.1.1, 2.4.3, 2.1.2, 4.1.2 The full screen of the map (GH-4227) | A button with the zoom buttons, at the head of their bar (40 px), named "Full screen" and, while the map is full screen, "Exit full screen" (`aria-label` and `title`; it is a button whose name says what it does, not a toggle, so it has no `aria-pressed` besides). Where the browser has the Fullscreen API for an element (the page's `Permissions-Policy` allows `fullscreen` for itself) the map's stage goes full screen by it; where it has none (iPhone Safari) or refuses, the stage covers the whole page (`position: fixed` over the header and the tab bar, `data-fullscreen` is there only while it does) and everything else of the page is `inert`, so the keyboard and a screen reader do not leave it, and the page behind does not scroll. Entering moves the focus into the map (which pans by the arrow keys); Escape leaves, closing the layers panel first where it is open, and leaving by Escape, the button or the browser's own exit gives the focus back to the button. The view, the layer and the station picked are kept (the map is the same element, told its size again by `invalidateSize`). The panel is out of reach while it lasts, so a sheet under the map stands in for it, and is the part of the page that says what was picked: the station's name and id (a polite status says what a pick was), "Pick the centre of the map" (the keyboard's way to a place, which the panel has too) and "Show details", which leaves full screen and, once the browser has left it, puts the focus on the panel's heading. One Escape closes one thing: the layers panel and the About panel have the first press (they `preventDefault` it), the next leaves. A request of WebKit's prefixed API, which answers nothing, is told by its events (`webkitfullscreenchange`, `webkitfullscreenerror`, or none in 1.5 s: the app covers the page). Tested (`tests/e2e/phone-fullscreen.spec.ts` in Chromium, with the API present, absent and refusing; `tests/nuxt/composables/useElementFullscreen.test.ts`; the state `phone-fullscreen` of the accessibility spec). |
| 2.4.3, 4.1.2, 2.5.8 The "About" as an ⓘ on a phone (GH-4227) | Below 40 rem (a phone; a tablet and a desktop have the labelled button as before) the "About" row of a tool is a 44 px button with an info icon beside the page title, named like the row was ("About the map"), with `aria-expanded` and `aria-controls` that name the panel, which is in the page all the time and hidden while closed. Escape closes it, and the focus goes back to the ⓘ where it was in the panel (it is not taken from where the reader has gone). From 40 rem it is the labelled button of the row of actions, as before. The same breakpoint holds for the cards running edge to edge (only a card that is a child of the page: not one in a grid or inside another card, nor the chart of the widget or of a facet's box) and for the map filling the window between the bars. Tested (`PageHeader.test.ts`, `phone-fullscreen.spec.ts`, the state `phone-about-open`). |
| 1.4.11 Non-text contrast | The violet tile: 5.7:1 against a card and 5.3:1 against the paper by day (`#7c3aed`), 4.8:1 and 5.3:1 at night (`#9a79f8`), held by `tests/unit/button-contrast.test.ts`; its glyph is white by day (5.7:1) and navy at night (5.3:1). The map is a light surface in both modes: a station dot is `#2358a8` with a white halo on the map's tone (5.7:1), the station picked a yellow disc in a navy edge, told apart from the dots by its size and edge and not by colour; a group is a disc of the same blue with its number in white (7:1), hollow with the number in blue where its stations have stopped, as their dots are. The layers button is a round button of the page's own background (white by day, the card's navy at night) with a border of the neutral's accented edge and an icon in the text colour; the layer chosen in its panel is a checked radio, which the radio's own ring and dot show (3:1 or more, 1.4.11), and its card is outlined in the primary colour. |
| 1.1.1, 1.3.1 The panel's pictures | The forecast is day rows with the weather in words (as the compact day cards have it); the climate stripes are a `role="img"` named for the station with a caption that gives the span of the years and the lowest and highest value (the stripes page's sentence); the map has a name that says the layer. |
| 4.1.3 Status messages | A click or tap on a group of stations ("Zoomed in on a group. Stations in it: 40", said again for a second click on the same group: the status is emptied first), a station chosen, a station named by the address and the station picked again after a change of layer, and a point with no station within 100 km, are announced in a polite status; the stations that could not be loaded, a forecast or stripes that could not be read are `role="alert"` with a Retry; a search without a match and the list loading are `role="status"`. |
| 1.4.10 Reflow | No sideways scroll at 320 px with a station picked, in en, de, de-hh, lb, nl, pl, cs, it and fr (the cards' links wrap: `Open the measurements in the Explorer` was 331 px wide in English), and at 390 px; the map has one button of 44 px over it and its status chips (the count, hidden on a phone, the loading status and the failure), so that it is nearly all map at 320 px on the measurements layer too, the selects of the source being in the layers panel; the panel fits the window in all eleven languages; the legend of the dots, in the layers panel, is whole in the panel at 320 px in all eleven languages (the panel scrolls where it is taller than the map). The empty space of the status row does not take the pointer. Tested. Not checked: a screen reader on a phone (VoiceOver, TalkBack), and the map by touch with 200 % text. |

The Radar tool (`/radar`, GH-3788), by the tests of `tests/nuxt/pages/radar.test.ts`, `tests/nuxt/components/RadarPlayer.test.ts`,
`RadarLegend.test.ts`, `RadarStormCells.test.ts`, `tests/nuxt/composables/useRadarPlayer.test.ts` and `tests/e2e/radar.spec.ts`, and the
states `radar: cells-forecast-frame` and `radar: phone-radar` of the accessibility spec, and the page `radar`. It is the map of the map tool with no stations (`StationMap.vue`), a player
under it and a panel beside it (under it on a phone, in the order the window shows them):

| Criterion | How the Radar meets it |
| --- | --- |
| 2.2.2 Pause, stop, hide; 2.3.3 Animation from interactions | The loop starts by itself once its frames are loaded, so it has a pause button (the play button, named "Pause" while it runs and "Play" while it does not, 44 px). Any control (pause, a step, the slider) pauses it, and it never starts by itself again after one. It stands still while the tab is hidden. Under `prefers-reduced-motion: reduce` it does not start by itself at all, and the player says why; the reader can still run it by pressing Play. The picture changes by swapping the image, with no animation of its own. |
| 1.4.1, 1.3.3 Observed or forecast | A frame is told observed or forecast in words ("Observed", "Forecast, 35 min ahead") with an icon, on the player and on a chip over the map, and the forecast has a dashed edge, never by colour alone; the slider's track is solid for the observed frames and hatched for the forecast, with a line under it that says so (`radar.trackKey`). A screen reader gets the same in the slider's value text ("21:35 CET, forecast, 35 minutes ahead"). The chip over the map is `aria-hidden`: the player is its text. |
| 1.4.1, 1.1.1 The legend | The classes are numbers in mm/h beside the swatches ("0.1–0.5" ... "25+", read as "0.1 to under 0.5 mm/h"), from the answer, in the language of the page; "No colour" says what the transparent part is. The swatches have an edge of the neutral's accented tone, so the palest class stands against the page (1.4.11). The picture on the map is no text: its alternative is the player, the legend and the loop's lines in the panel; the image has `alt=""` and no focus. |
| 2.1.1, 2.4.3, 2.5.7, 2.5.8 The player's controls | The slider is the browser's own range input, named by a label, with the arrow keys, Home, End and Page Up and Down, and a description of them; the two step buttons (44 px) do for a pointer that does not drag what dragging does. A step that cannot go on (the first or the last frame) is `aria-disabled` and does nothing, not `disabled`: a native disabled button drops the focus the reader has on it. A step is told in a polite status where the loop is not playing, never while it plays; the slider says its own value, so a move of it adds no second line. While the frame the player stands at is still loading, the player says so (and is `aria-busy`) and the chip over the map describes the frame whose picture is on the map. |
| 3.2.1, 4.1.3 Status | The loading of the frames (5 at a time), frames that were skipped, a loop that is old (`radar-stale`, or a newest run over 20 minutes old by the server's own time), a refresh that failed and a loop that cannot be loaded are lines of the panel, the last two with a Retry (a backend with no radar, a 404 or a 501, says so and has none); a failure is `role="alert"`. The count of the frames is no live region: one status line says "Loading the radar frames" when it starts and "The radar frames are loaded" when it is over, never 49 counts. |
| 1.3.1, 4.1.2 The thunderstorm cells | Drawn on the map with `interactive: false` and `keyboard: false` and `aria-hidden` (no stop of Tab, no click); their text is the list in the panel (position, severity as a number and a word, the calculated motion), a press or Enter on a row centres the map on the cell, and a switch (`role="switch"`, 44 px) turns them off and stops asking. Severity is never colour alone: the number is on the mark and in the words, the edge is heavier the more severe. A scan over 20 minutes old is told out of date and not drawn. The cells are the latest scan's, so they are shown only on frames within 15 minutes of it: on an older frame and on the forecast they fade out of the map (no transition under `prefers-reduced-motion`), the panel says so in a line of its own, and their credit leaves the map's. The count of the cells is a status line that is in the page from the start (empty, never `display: none`), so that its first text is announced. |
| 1.4.10 Reflow | No sideways scroll at 390 and 320 px in all eleven languages, the player and the legend whole (tested in `radar.spec.ts`); the map is as wide as the window and the panel under it on a phone. |
| 3.1.1 Times | A frame's time is written in the reader's own zone with the zone's name ("09:10 MEZ"), the weekday where it is not today; the language is the page's (`formatFrameTime`). |

Not checked: a screen reader on a phone (VoiceOver, TalkBack), and the slider by touch with 200 % text.

The station picker of the Explorer, History, Forecast and Stripes (GH-3877), by the tests of `tests/nuxt/components/StationPicker.test.ts`, the
keyboard tests and the `station-map` states of the accessibility spec, and `tests/e2e/i18n-layout.spec.ts` at 320 px (Chrome):

| Criterion | Result |
| --- | --- |
| 2.1.1, 4.1.3, 1.3.1 The station picker (GH-3877) | The four tools that pick a station (Explorer, History, Forecast, Stripes) share one picker: a toggle of "List" and "Map" over the one place of the choice, and the picked stations as chips under it in both modes. The toggle is a radio group (`SegmentedControl`): one stop in the tab order, the arrow keys, Home and End select and keep the focus on the group to walk along it, and each option's `aria-controls` is the one element that holds the search or the map, which is in the page in both modes. A click or Enter/Space on an option is a decision to use the mode: the focus goes into the search, or into the map (the map's container, which takes Tab and the arrow keys; a map whose code or stations are still on their way takes it when it is there). A change of mode the reader made is told in a polite status ("Station search", or what a tap on the map does); a map that is not there yet takes the focus when it is only while the focus is still in the picker, and a click of the pointer does not scroll the page to it. A chip is a button named "Remove {station} from the selection" (it was a badge that only a mouse could press); a removed chip hands the focus to the one that took its place, else to the one before, else to the toggle, and "Clear all" to the toggle. "Center on selected stations" is a 34 px button beside the map's zoom buttons, named by its label (an icon alone); a marker that Tab reaches is scrolled into the window as well as into the map. Tested (`tests/nuxt/components/StationPicker.test.ts`, the keyboard test and the `station-map` states of the accessibility spec). |

The phone bar, its Menu's sheet and its chooser (GH-3846, GH-3851, GH-3934, GH-3936), by the tests of `tests/nuxt/components/AppTabBar.test.ts`,
`AppHeader.test.ts`, `TabBarChooser.test.ts`, `tests/unit/tab-bar.test.ts`, `button-contrast.test.ts` and `tests/e2e/tab-bar.spec.ts` (at 390 and 320 px
and, for the header and the chooser from 64 rem, at 1280 px, light and dark, in Chrome), and by the scans above
(`phone-bar-chooser`, `phone-bar-chooser-narrow`, `mobile-menu-open`, the settings page):

| Criterion | Result |
| --- | --- |
| 2.5.7 Dragging movements, 2.1.1 Keyboard | A tool is dragged by its handle (pointer events: mouse, finger, pen), and moved by an up and a down button on its row, which do everything the drag does, including across the line between the bar and the Menu. The buttons are in the tab order, in the order of the list, and work with Enter and Space. The handle is for the pointer only: it is `aria-hidden` and no stop. At the end of the list a button is `aria-disabled` and stays a stop, so the focus of a button pressed up to the end is not lost. Tested by keys alone. |
| 4.1.3 Status messages, 3.3.1 | What a move did is said in a polite status that is in the page from the start (`role="status"`): the tool's new place in the bar (`Climate stripes moved to place 2 of 4 in the bar.`), or that one is now in the bar or only in the Menu and which tool it pushed out or pulled in; the same for a drag and for the buttons, and for the reset. The status is in the page's language (all eleven locales have the sentences, machine-made; read by no native speaker). Not checked with a screen reader. |
| 2.4.3 Focus order, 3.2.2 | After a move by a button the focus is on the same button of the row where the tool now is (the row is built again where it crosses the line, and the focus is given back to it). A drag moves no focus. The Menu's link to the chooser (`/settings#bar`) takes the focus to the heading of the chooser's card instead of letting the sheet give it back to its tab (`onCloseAutoFocus`). Tested. |
| 2.5.8 Target size (minimum) | The handle is 40 px wide and as tall as its row (54 px) and each button 40 x 40 px, at 320 px as well (the spec measures every handle and button; the minimum is 24 px). |
| 1.4.11, 1.4.3 | The row, the handle, the buttons and the line use the page's own tokens: the preview's edge is `--ui-border-accented` (3.3:1 on white and 3.1:1 at night), the dashed line between the two lists is `--app-mark-bar` (brand-700 by day, 6.9:1 on the card; brand-300 at night, 8.7:1), the arrow buttons' edge is the muted text colour (4.5:1 or more against the row's raised background and against the button's own fill, light and dark; held by `button-contrast.test.ts`), and the glyph in them is the highlighted text; the scans of the settings page in both modes have no entry. A button at the end of the list is dimmed (`aria-disabled`, exempt from 1.4.3). The place a dragged tool will land on is a 4 px bar in the page's current-page colour, and the preview shows it as well, so colour is not the only sign. |
| 1.1.1, 1.3.1 The preview and the lists | The preview of the bar is a `role="img"` named by what it shows (`Preview of the bar: Forecast, Explorer, Climate stripes, History, Menu`); what is only in the Menu is written under it. The two lists are ordered lists named by the heading over each (`In the bar`, `Only in the Menu`), so the line between them is also told in words. From 64 rem, where the header shows every tool and there is no bar and no Menu, the chooser is one ordered list named by its `aria-label` (`Tools in the header, in order`), with no preview, no heading and no line; the settings card has one title (`Arrange tools`) at every width. |
| 1.4.11 The sheet's lines | In the Menu's sheet a tool of the bar has a 3 px line at the left of its row in `--app-mark-bar` (brand-700 by day: 6.9:1 on the sheet, 6.0:1 on a hovered link; brand-300 at night: 8.7:1 and 7.6:1) and a tool that is only in the Menu one in `--app-mark-menu` (brand-500: 3.5:1 and 3.0:1 by day, 4.5:1 and 4.0:1 at night), so both clear the 3:1 of a non-text mark and the bar's is the stronger, light and dark. Held by `button-contrast.test.ts`, which also holds the two against each other, and measured in the browser against the sheet's own background (`tab-bar.spec.ts`). In forced colours the lines are `CanvasText` and `GrayText` (`forced-color-adjust: none`). |
| 1.4.1 Use of colour | The two lines differ by shape as well as by colour: 1.25 rem high for the bar's tools, 0.75 rem for the others, and the bar's tools come first in the list (measured in `tab-bar.spec.ts`). |
| 1.3.1 Info and relationships in the sheet | A line is `aria-hidden`; the group is in the link's name as visually hidden text (`Map, in the bar`, `History, only in the Menu`, translated in all eleven locales), so a screen reader is told what the lines show. There is no heading or rule between the groups. Tested (`AppTabBar.test.ts`, `tab-bar.spec.ts`). Not checked with a screen reader. |
| 2.4.11 Focus not obscured | The preview stays in view under the header while the list is scrolled or dragged (`position: sticky`), so a focused button could be under it: the arrow buttons and Reset have a `scroll-margin-top` that clears it, and the spec samples five points of every focused one for what covers it, forwards by Tab and back by Shift+Tab, at 390 px, 320 px and 320 x 568. The preview has an edge of its own (a border and a shadow) and only the lists pass under it. On a phone it is as wide as the window and has no sides, like the bar it shows, so a name that the bar shows whole (Pronóstico, Explorador) is not broken in it (tested in es, fr, it, pl, cs and de-hh). In a window lower than 30 rem (where the header is not fixed) the preview does not stay. |
| 1.4.10 Reflow | No part of the chooser reaches past a 320 px window in any of the eleven languages (tested); a long name takes two lines in its row. The settings page in Spanish is wider than 320 px: its "Restablecer valores predeterminados" button does not wrap (not part of the chooser, found while testing it, not fixed there). |
| 4.1.2, 1.3.1 The Menu's mark | The Menu's tab is `aria-current="true"` on every page that is in its sheet and has no tab: a tool that is not in the reader's bar, the reference (Providers, Glossary, Measurement, API) and the project (About, Support, Settings); a tool in the bar marks its own tab (`aria-current="page"`); the home page and the legal pages mark nothing. Tested for every kind of page, and while going from page to page and back, with the default bar and a chosen one. |
| 3.3.7 Redundant entry, storage | The choice is kept with the settings in the browser (`wd_settings`, no account); a stored choice that names a tool that is gone, repeats one or has too few is repaired to a valid list of all the tools and never an error, and where the browser refuses its storage altogether (access to `localStorage` throws) the settings are kept in memory for the visit and the app starts: before this, pages that read the settings showed an error page there (measured on `main` with `localStorage` throwing: `/` and `/meteogram` loaded; `/explorer`, `/stripes`, `/history`, `/map`, `/glossary` and `/settings` did not; `useLocalStorage` reads the property outside a try). Tested in `useSettingsStorage.test.ts` and `tab-bar.spec.ts`. |

The bars of a phone that hide on scroll and the slimmer top bar (GH-4226), by `tests/unit/bar-scroll.test.ts` (the direction logic and the stylesheet),
`tests/nuxt/composables/useBarsHideOnScroll.test.ts`, `tests/e2e/bars-hide.spec.ts` (at 390, 320, 820 and 1280 px and in a window as low as a phone on its
side, in Chrome) and the scans `phone-bars-hidden` and `phone-search-open`:

| Criterion | Result |
| --- | --- |
| 2.2.2 Pause, stop, hide; 2.3.3 Animation from interactions | Only a phone (below 40 rem) has it; a tablet and a desktop are as they were. Scrolling down by 12 px (past the first 48 px of the page) slides the top bar up and the tab bar down, scrolling up by 12 px or reaching the top slides both back: a movement that answers the reader's own scroll, 200 ms (160 ms away) and a transform, so the page does not change its length and does not jump. With `prefers-reduced-motion: reduce` nothing is transitioned: the bars are away or in view at once (the app's rule for the setting also sets every duration to 0.01 ms). A tremble of a few pixels and iOS's rubber band change nothing (a position past an end of the page is read as that end). A page that has just arrived (a first load, a step to another path) keeps its bars in view until the reader's first touch, wheel, key or press, so one that arrives scrolled to an anchor (`/settings#bar`) has them; the gate is one-shot for each page, so once the reader has touched it every scroll counts, a script's (`scrollIntoView`) as well. A step that only changes the query of the address (a chart's panels, a picked station) is the same page: the bars stay as they are. |
| 1.3.1, 2.4.1 Landmarks and bypass blocks | The hidden bars are not `display: none` or `visibility: hidden`: they stay in the page, so the `banner` and the `navigation` are in the accessibility tree and in the tab order while they are out of view (checked: the same landmarks hidden and shown). The skip link is not in a bar; it is fixed at the window's top and shown by its focus whether the bars are in view or not. |
| 2.4.7 Focus visible, 2.4.11 Focus not obscured | A focus in either bar, by Tab, Shift+Tab or a script, brings both back (`focusin`), so a control that Tab arrives at is never out of view, and they do not hide while the focus is in one (the search button after Escape is not scrolled out of view with its bar); the count starts again from where the page is. A control of the page that the focus brings into view is scrolled clear of where the bars would be (`scroll-padding`, which is the bars' height whether they are in view or not). |
| 2.1.1, 4.1.2 Search, menus and popovers | The bars never hide while a dialog is open (the Menu's sheet, the search), nor while a popover, a menu or a list that a trigger says is open (`aria-expanded` with `aria-haspopup`, or a combobox) hangs from them, so a popover under the top bar is not left in the air; the offset iOS puts back when a dialog closes is no scroll. The search on a phone is a bar at the top of the window over the top bar, with its field where the top bar's was: Escape closes it and the focus goes back to the button that opened it (tested). |
| 2.5.8 Target size (minimum) | The top bar is 44 px of content (it was 64) with a 28 px logo and the name, and the search and the settings are icon-only 44 x 44 px buttons named by `aria-label` ("Search", "Settings"); measured at 390 and at 320 px, where the logo, the name and both buttons fit the bar and the page does not scroll sideways. |
| 2.4.11 What sticks under the top bar | The preview of the settings page's chooser (`.bar-sticky`) sticks at `--header-height` times `--bars-shown`, the number (1 with the bars in view, 0 away) that also drives both bars' transforms and the toasts' place, each transitioned by one time and curve, so it follows the top bar frame by frame and stands at the window's top edge while the bar is away (measured). The map page keeps both bars (`definePageMeta({ barsHide: false })`): it fills the window between them, and what it measures does not change. A window as low as a phone on its side (30 rem) has bars that scroll with the page and no hiding. |

Not checked: a screen reader (VoiceOver, TalkBack) and a real iPhone's Safari (its own toolbar, the rubber band, the safe areas of a notch and a home indicator: the
tab bar's transform is its own height, the home indicator's room included, and the stylesheet's test holds that; the room is `env()`, which Chrome cannot serve);
Firefox and Safari (the e2e spec was run in Chrome only).

Not checked: a screen reader (VoiceOver, TalkBack) on the chooser and its announcements; the drag by touch on a real device (it is tested in Chrome
by the browser's touch events: a finger on the handle drags and does not scroll, a finger on the rest of a row scrolls); Firefox and Safari
(the e2e spec was run in Chrome only).

The charts' text alternatives and keyboard access (#3145), checked on 2026-10-19:

| Criterion | Result |
| --- | --- |
| 1.1.1, 1.3.1 Text alternative of the climate stripes | **Was failing**: a `figure` with a name and nothing of what it shows. The figure is described (`aria-describedby`) by a sentence, the span of the years with the lowest and the highest value, and a table of every year drawn with its value, its anomaly and its class (the class named for temperature or precipitation) is the "Table" choice of the switch above the chart (it was a "Show as table" disclosure below it until GH-4233); the sentence says so. |
| 1.1.1, 1.3.1 Text alternative of the meteogram (also the widget) | **Was failing**: the same. The figure is described by the span of the forecast and its temperatures, and "Show as table" opens the values of the series the shown panels plot (as far as the horizon chosen reaches), one row for each time, in the station's time zone. The compact view is day cards with their own text (the weekday, the temperatures, the rain), and has no table. |
| 2.1.1 The explorer's toolbar and legend | Not failing (they were Plotly's modebar, whose buttons were native `button`s too, until GH-4096): the toolbar's six buttons are native `button`s with an `aria-label` of their own, in a `role="group"`, in the tab order, operated by Enter and Space, off where they would do nothing; the legend's items are buttons with `aria-pressed`, and the chart is one tab stop whose keys step through its values. Tested on the explorer's chart (`chart controls by keyboard`: the buttons in the tab order and named, walked by Tab, Enter on zoom in narrowing the window and Space on reset putting the whole of it back, Space on a legend item turning its series off and Enter on again, the keys and `+`, `-`, `0`), each of which fails if the behaviour is broken. |
| 1.1.1 Text alternative of the meteogram's compact day cards | **Was failing**: the weather of a day was an emoji, and a drop before the rain's amount, with no text. Both symbols are hidden from assistive technology (`aria-hidden`; the weather is Yr's symbol, as the chart draws it since GH-4193, an `<img alt="">`); the card holds the words for the weather, visually hidden (`meteogram.chart.weather.*`: thunderstorm, rain, snow, sleet, drizzle, fog, windy, dust or sand storm, blowing snow, cloudy, partly cloudy, sunny), in the language of the page, and "Precipitation:" before the amount. The name is held to the WMO's present-weather table: every code 0 to 99 has its kind in `tests/unit/weather-kind.test.ts`, and a code that names no weather the card can (haze, hail) is judged from the cloud cover and the rain. The symbol is Yr's, as the chart's (GH-4193); Yr has none for wind, a dust or sand storm or a funnel cloud, which are drawn as the sky of the day with a small badge in its lower corner (the Phosphor wind icon, the tornado icon for a funnel cloud) on a disc of the page's background, so that a windy day under a clear sky is no sun alone; the badge is hidden with the symbol and the words name the weather. Tested for weather codes and for the cloud-cover heuristic, and in all eleven languages. |
| 2.1.1 The compact view's strip of day cards (GH-4127) | The strip shows every day of the run (10 or 11 cards, about 1315 px) and so scrolls sideways at any width. It is a `role="region"` named by the station (`meteogram.chart.daysLabel`) with `tabindex="0"`, so the arrow keys scroll it from the keyboard in every browser (Safari does not focus a scroll container) and the global focus ring shows where it is. `tests/nuxt/components/Meteogram.test.ts` holds it. |
| 1.3.2, 2.4.3 Order of the forecast's toolbar (GH-4124) | The toolbar is a grid whose DOM order is the screen order from `md` up: the panels and horizon on the left, the view switcher, then the zoom buttons under it. Below `md` the switcher and the zoom buttons are drawn above the panels (`order`), so the focus order there is the panels first. `tests/e2e/meteogram-view-switcher.spec.ts` holds the switcher's place. |
| 1.4.13 Content on hover or focus, the forecast chart's readout | **Was failing** (as Plotly's hover label, which the forecast had): met since GH-4059. The readout is an element of the page that the pointer moves onto (hoverable), that stays until the pointer or the focus leaves or it is dismissed (persistent), and that Escape closes without moving either and without being consumed (dismissible); its Close button is the way for a touch. A keyboard puts it there by stepping the crosshair, so the focus case is covered too. Tested (`MeteogramChart.test.ts`; in a browser, `meteogram-chart.spec.ts` and `chart controls by keyboard`). |
| 1.4.13 Content on hover or focus, the stripes' readout | **Was failing** (as Plotly's hover label, which the stripes had): met since GH-4068. The readout is an element of the page that the pointer moves onto (hoverable), that stays until the pointer or the focus leaves or it is dismissed (persistent), and that Escape closes without moving either and without being consumed (dismissible); its Close button is the way for a touch. A key puts it there by stepping, so the focus case is covered too. Tested (`StripesChart.test.ts`; in a browser, `accessibility.spec.ts`, `chart controls by keyboard`). |
| 1.4.13 Content on hover or focus, the explorer's readout | **Was failing** (as Plotly's hover label, which the explorer had, and the names of its modebar's buttons): met since GH-4096. The readout is an element of the page that the pointer moves onto (hoverable: docked at the edge of the chart that the crosshair is not on, so that the pointer does not meet it on the way), that stays until the pointer or the focus leaves or it is dismissed (persistent), and that Escape closes without moving either and without being consumed (dismissible); its Close button is the way for a touch and gives the focus back to the chart. A key puts it there by stepping, so the focus case is covered too. The names of the toolbar's buttons are the browser's own `title`, which the browser draws and the page does not change. Tested (`ExplorerChart.test.ts`; in a browser, `accessibility.spec.ts`, `chart controls by keyboard`). |

The measurement page, "How weather is measured" (GH-3787), checked on 2026-11-20:

| Criterion | Result |
| --- | --- |
| 1.3.1, 2.4.6 Headings | One `h1`, the sections `h2`, each entry an `h3` (an `article` named by it) and its parts `h4`: no level is skipped. Tested (`measurement.test.ts`, which walks the levels). |
| 2.1.1, 2.4.5 The table of contents | A `nav` named by its `h2`, a list of links: each is a real `a href` to `/measurement#<entry>`, so Tab and Enter work with no script of the page. |
| 2.4.3 Focus after an anchor | A link to an entry (the contents, the link beside each heading, a link from the glossary) puts the focus on the entry's heading (`tabindex="-1"`), so a keyboard and a screen reader continue there; the router does the scrolling and respects reduced motion, and the sticky header is cleared by the page's `scroll-padding-top`. Tested. |
| 3.1.2 Language of parts | A text that is not in the language of the interface (English or German, with a note that says so) names its language (`lang`) on the heading, the sentence under it, its parts and its sources; the labels around it are in the interface's. Tested. |
| 2.4.4 Link purpose | The link beside a heading is named "Link to the entry ..." with the entry's title; a source is linked by its citation; the glossary's "How is this measured?" carries the parameter's name as visually hidden text. |
| 1.4.3, 1.4.11, 2.4.7 Contrast and focus | The page uses the colours of the other pages' text and links, and `accessibility.spec.ts` scans `/measurement` in light and dark, English and German, at first paint, hovered and walked by Tab, and at 320 px. Run for this page alone, in Chrome against the dev server (Firefox did not start on the machine): no rule broken on the page; the only findings were of the dev server's Nuxt devtools overlay, which a build does not have. The full scan is the next *App accessibility* run's. |

Not checked: a screen reader (VoiceOver, TalkBack).

The methods page, "How the answers are worked out", and the explanation under an answer of Ask the weather (GH-3764), checked on 2026-11-21:

| Criterion | Result |
| --- | --- |
| 1.3.1, 2.4.6 Headings | The methods page has one `h1`, the sections `h2`, each question's method and each work cited an `h3` (an `article` named by it) and the parts of a method `h4`: no level is skipped. Tested (`methods.test.ts`, which walks the levels). Under an answer the disclosure is an `h4` that holds the button (the pattern of an accordion), its parts `h5`. |
| 4.1.2, 2.1.1 The disclosure | "How was this worked out?" is a real `<button type="button">` with `aria-expanded` and `aria-controls` that names the region it opens (`role="region"`, `aria-labelledby` the button); it opens with Enter and Space and the focus stays on it. The region is in the page, `hidden` while closed. Tested (`AskTheWeather.test.ts`, `ask-weather.spec.ts`). |
| 1.4.1 The mark of what is wetterdienst's own | The words "wetterdienst's own choice." in a bordered label, not a colour alone; the reasoning follows it. |
| 2.4.3 Focus after an anchor | A link to a method (`/methods#season`) or a work (`/methods#work-wmo-1203`) puts the focus on its heading (`tabindex="-1"`), as the measurement page does. Tested (`ask-weather.spec.ts`). |
| 3.1.2 Language of parts | A text that is not in the language of the interface (English or German, with the note of the measurement page) names its language (`lang`) on the heading and on each element of the text (a step, a rule, what a source says, a reason, a limit, a term and its sentence), and on no section or label around them: the headings of the parts, the kind of a rule, the own mark and "Source:" are the interface's. Tested (`methods.test.ts`, `ask-weather.spec.ts`). |
| 1.4.10 Reflow | The disclosure opened at 390 px does not scroll sideways (`ask-weather.spec.ts`); the page is in a reading column. |
| 1.4.3, 1.4.11, 2.4.7 Contrast and focus | `accessibility.spec.ts` scans `/methods` and the open disclosure (`ask-explanation-open`) in light and dark, English and German, at first paint, hovered and walked by Tab, and `/methods` at 320 px. Run for these rows alone (15 tests), in Chrome against a production build (Firefox did not start on the machine): all passed, with no rule broken. The full scan is the next *App accessibility* run's. Not checked: a screen reader (VoiceOver, TalkBack). |

The season and reference-period choices of the season question of Ask the weather (GH-3764, step 2a), checked on 2026-11-22:

| Criterion | Result |
| --- | --- |
| 1.3.1, 3.3.2, 4.1.2 Labels and role | The season and the reference period are two native `<select>` elements, each with a `<label for>` ("Season", "Compared with") and its value; they are outside the question's button, which stays one `<button aria-pressed>`. Tested (`AskTheWeather.test.ts`, `ask-weather.spec.ts`, which finds each by its role and name). |
| 3.3.2 A greyed-out choice says why | A season or a normal the station has too little of is a disabled `<option>` whose own text says how many it has ("1961–1990 = 1960/61–1989/90 (only 16 of 30 seasons here, 20 needed)", "Winter (only 5 complete seasons here)"), since a native option has no other place for a reason, and a screen reader reads it with the option. Under the choices a line (`role="status"`, in the page always so that a change is announced) says why something is greyed out and, where a link or a choice named a season or normal with too little data, that the one shown instead is the default. The newest normal, where the station has too few but ten or more seasons stand before the last, is not greyed out and says in its option that the seasons before stand in for it. Tested (`AskTheWeather.test.ts`, `ask-weather.spec.ts`). |
| 2.1.1 Keyboard | A select is reached by Tab in the order season, then normal, after the question's heading, and changed with the keys the browser gives a native select; the answer follows the change and the live region says the new verdict; where the verdict is the same sentence as before, the status is cleared and set again so that the change is announced. Tested (`ask-weather.spec.ts`). |
| 2.5.8 Target size, 1.4.10 Reflow | Each select is 44 px high and no wider than the panel; at 390 px, in English, German, Spanish and Polish (the longest season names and options), nothing scrolls sideways. A winter's chart labels are two years each (`2025/26`) and do not touch each other at 320 px. Tested (`ask-weather.spec.ts`). |
| 1.4.3, 1.4.11, 2.4.7 Contrast and focus | `accessibility.spec.ts` scans the chip with its choices and the disclosure open (`ask-season-choices`) and the chip on a phone at a station with a disabled normal (`ask-season-disabled-phone`), in light and dark, English and German, at first paint, hovered and walked by Tab. Run for these rows and the other Ask rows (30 tests), in Chrome against a production build (Firefox did not start on the machine): all passed, with no rule broken and nothing added to the baseline. Not checked: a screen reader (VoiceOver, TalkBack), and how each reads a disabled option. |

The measure and the day of the day question of Ask the weather (GH-3764, step 2b), checked on 2026-11-22:

| Criterion | Result |
| --- | --- |
| 1.3.1, 3.3.2, 4.1.2 Labels and role | The measure (wind, sunshine, rain, heat and cold, snow) is a native `<select>` with a `<label for>` ("Measure") beside the day's date field ("Day"), outside the question's button, which stays one `<button aria-pressed>`. The question's heading and the verdict follow the measure. Tested (`AskTheWeather.test.ts`, `ask-weather.spec.ts`, which finds the select by its role and name). |
| 3.3.2 A greyed-out measure says why | A measure the station has no reading of for the day is a disabled `<option>` whose own text says so ("Snow (no reading here for 26 December 2025)"), and the line under the choices (`role="status"`) says why something is greyed out and, where a link named such a measure, that the wind or the first measure with a reading is shown instead. Tested (`AskTheWeather.test.ts`, `ask-weather.spec.ts`). |
| 4.1.3 Status messages | The verdict is announced by the live region when the measure changes, also where the sentence is the same as before (the status is cleared and set again). A change of the measure asks the backend nothing, so no loading status comes between. Tested (`AskTheWeather.test.ts`). |
| 1.4.1, 1.4.10 Reflow, 2.5.8 Target size | The classes a day counts as are said in words (a line "Counts as: frost day."), not by colour; the select is 44 px high and no wider than the panel; at 320 px in German, 390 px and 1280 px in English no chart label touches another and nothing scrolls sideways, for every measure (the temperature chart hangs bars below a zero line). Tested (`ask-weather.spec.ts`). |
| 1.4.3, 1.4.11, 2.4.7 Contrast and focus | `accessibility.spec.ts` scans the day question with the sun measure and the disclosure open (`ask-day-choices`), the temperature measure with its table of values open (`ask-day-temperature`) and, on a phone at a station with no snow reading, the greyed-out measure (`ask-day-greyed-phone`), in light and dark, English and German, at first paint, hovered and walked by Tab. Run for these rows and the other Ask rows (60 tests), in Chrome against a production build (Firefox did not start on the machine): all passed, with no rule broken and nothing added to the baseline. Not checked: a screen reader (VoiceOver, TalkBack), and how each reads a disabled option. |

### Known not to conform

- **The station map, 1.1.1 and 2.1.1**: markers are reachable by Tab and named by their station, but a map of
  hundreds of them is no way to choose a station by keyboard; the picker beside it is. Clusters are named by
  their count only.
- **Not checked**: a screen reader pass (VoiceOver, NVDA), text spacing (1.4.12), zoom to 200 % (1.4.4) and
  the nine languages besides English and German, which the scans do not cover.

## Lighthouse

Lighthouse is not part of CI (#2559 asked for it as a cross-check; it runs axe underneath, so it adds a
weighted score, its few best-practice rules, and a phone-sized viewport, not other WCAG rules). **It is run by hand
before each app release, and its accessibility score is recorded here**, a row for each run. A release whose pages
do not all score 100 names the ones that did not and the audit.

| Date | App | Lighthouse | Pages x devices | Accessibility score |
| --- | --- | --- | --- | --- |
| 2026-10-18 | 0.24.0 with #3146 (released as 0.25.0) | 13.5.0 | 17 URLs x mobile, desktop | 34 x 100. Before the heading fix of that run: 32 x 100 and 2 x 98 (the explorer with a restored selection: `heading-order`, an `h4` under an `h2`, now an `h3`). |
| 2026-11-10 | 0.46.0 with this change (GH-3642, GH-2559) | 13.6.0 | 17 URLs x mobile, desktop | 34 x 100. First run of the same pages: 32 x 100 and 2 x 98 (the widget: `landmark-one-main`, a page with no main landmark, which the widget now has). |

How a row is made, by hand before each app release:

```bash
cd app
pnpm build
pnpm lighthouse            # --version 13.6.0 (the default), --port 4413, --mock-port 4412
```

`pnpm lighthouse` (`tests/e2e/accessibility/lighthouse.mjs`) serves the production build with `NUXT_API_BASE` pointing at a
server that answers every `/api/*` request as the spec's mock backend does (`defaultHandlers` of
`tests/e2e/accessibility/mock-backend.ts`), so that a page shows what it shows with data and no provider is reached. It
runs `npx lighthouse@<version> <url> --only-categories=accessibility` for the 17 URLs (the 16 pages of the spec's first
paint and the explorer with a station chosen; `tests/unit/lighthouse-urls.test.ts` holds the list to the spec's), each
twice: Lighthouse's default mobile profile and `--preset=desktop`. It needs the network (for `npx`) and a Chrome (set
`CHROME_PATH` if Lighthouse does not find it), prints each score with the audits that failed, then the line for the
table (version, Chrome, the scores of the 34 runs), and exits 1 if one run is under 100. Add a row, with the app's
version from `app/package.json`. The repository pins no Lighthouse version: the script defaults to the one of the last
row, and a row says the one it used.

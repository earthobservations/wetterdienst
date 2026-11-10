# Accessibility

The app aims at **WCAG 2.2 level AA** (it was tracked in #2559, closed on 2026-11-10 with the acceptance below). This
file says what is measured, how to run it, what was checked by hand, and what is known not to conform.

## How it is accepted

What was decided for #2559 (maintainer, 2026-11-10), which is closed with the pull request that wrote this down:

- **axe runs on request, not in every e2e run.** `pnpm test:a11y` runs it locally, and the *App accessibility*
  workflow runs it in CI, from the Actions tab (*Run workflow*) or when a pull request carries the `a11y` label.
  It takes about 20 minutes on three workers of a laptop and several times that on one (393 tests, most of them a page
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
  stations, a drawn chart (explorer, stripes, meteogram, widget), the table of the stripes' and the meteogram's values opened, the meteogram's compact day cards, an open
  menu or popover, an error notice, the map tool with a place picked (wide, and at 390 px with the panel as a sheet under the map),
  with the measurements layer's choices, and with its stations failed to load, the explorer's notice for a request the server refused over a limit
  (`values-limit-refused`, and at 320 px `values-limit-refused-narrow`) and the note under the date range that
  says the page started one (`default-range-note`), and the chooser of the phone bar's four tools on the
  settings page at 390 px, with a tool moved, and at 320 px (`phone-bar-chooser`, `phone-bar-chooser-narrow`).

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
(`scroll-padding`); in a window lower than 30 rem (a phone on its side, 400 % zoom) neither is fixed. In forced
colours (Windows contrast themes) the icons are painted in the colour of their text, so an icon-only button
keeps its icon, the tiles of the tools are outlined, and the tab of the current page is underlined.

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

The scan is 393 tests, most of them a page load and a scan: about 20 minutes on three workers of a laptop
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
| 2.5.7 Dragging movements | The map pans by drag, and by the arrow keys with the map focused, and zooms by its buttons and `+`/`-`; a station is also chosen in the list beside it. Plotly's charts zoom and pan by drag, with the modebar's buttons (zoom in, out, reset) as the single-pointer way. The chooser of the phone bar's tools is dragged by a handle and moved by an up and a down button on each row, which do all that dragging does (see "The phone bar and its chooser"). |
| 2.5.8 Target size (minimum) | axe's `target-size` is among the tags scanned (wcag22aa), on every page and state in both modes: no entry. |
| 3.2.6 Consistent help | The support and documentation links are in the footer of every page, in the same order, and support is also a heart in the header from 80 rem; the narrow layout has them in its menu sheet, and the search finds them. The widget has no header or footer by design. |
| 3.3.7 Redundant entry | Nothing is asked twice in a process. The explorer, forecast and stripes keep their selection in the URL, the settings in local storage. |
| 3.3.8 Accessible authentication | The app has no log-in and no cognitive test. |
| 2.4.2 Page titled | **Was failing**: every page was titled `Wetterdienst`. Each page names itself now, and a navigation is announced (`NuxtRouteAnnouncer`). |
| 2.2.2 Pause, stop, hide | **Was failing**: the emoji of the forecast's compact cards bounced for ever. They bounce once, and not at all under `prefers-reduced-motion`. Loading placeholders pulse while loading, which is a progress indication. |
| 1.4.10 Reflow | No page scrolls sideways at 320 px (tested). A table or chart scrolls in its own box. |
| 4.1.3 Status messages, 1.3.1, 2.4.3 Notice of a refused request (GH-3457) | A request the server refuses over a limit is a state of the table, not an error: its text (what the request comes to, what the server sends, what can be narrowed, with the selection's counts) is one `role="alert"` in a `section` that names itself by its heading, and the buttons (apply the window that fits, download everything as CSV) come after it in the tab order and outside the alert, so they are not read twice. A button's label wraps (320 px: no part of the notice reaches past the screen; tested), and it says what it does and how much, in the page's language. The notice raises no toast. When applying the window removes the notice while a button of it holds the focus, the focus goes to the table area (`applyWindow`, with `useFocusAfterRetry` as the fallback), which is where the answer, or the notice again, arrives; that area is a `role="group"` named by the page's own "Data" heading, so that the focus it takes is announced with a name (GH-3722). The note under the date range is a `role="status"` that stays in the page, hidden visually, when it has no text (announced as the text changes; the first station mounts the selector with the note in it, so the selector writes a note that is there at the start into the status 150 ms after the status is in the page, which is the change a screen reader announces; not checked with a screen reader), and the description (`aria-describedby`) of both date fields. "Clear date range" hands the focus it held to the two date fields as a group (`role="group"`, named "Date Range", with the focus ring when the button was pressed by keyboard) and not to the first date input, which iOS may answer by opening its picker (not checked on a device). Tested in `tests/nuxt/components/limit-notice.test.ts`, `DateRangeSelector.test.ts` and the three states of the accessibility spec. |
| 2.1.2, 2.4.3 on the narrow layout's menu | **Was failing**: the menu was a fixed overlay that Tab walked out of. It is a dialog (the sheet the tab bar's Menu opens, GH-3518), as is the search. |

The map tool (`/map`, GH-3650), by the scans above (the states `map: station-picked`, `measured-layer`, `stations-failed` and
`phone-station-picked`) and by the tests of `tests/nuxt/pages/map.test.ts` and `tests/e2e/map.spec.ts`:

| Criterion | Result |
| --- | --- |
| 2.1.1, 2.5.7 The map and its stations | The stations are dots on canvas tiles, not markers, so Tab does not walk through some thousand of them. A station is reached by the panel: its search, the list of the eight stations nearest the centre of the map, and "Pick the centre of the map", which picks the station within half a kilometre of the centre, else the station for the place at the centre, as a click of a mouse that is not on a dot would (it has no ring of a finger). The map itself is a named `application` that pans by the arrow keys and zooms by `+` and `-` and by its two buttons (40 px), so no drag is needed. Choosing a station by the list moves the focus to its name; "Back to the stations" gives it back to the station in the list. A pick by a click on the map does not move the focus, and is announced in a polite status. |
| 1.3.2, 2.4.3 Order | On a phone the map comes first and the panel under it as a sheet; from 72 rem the panel is on the left. The page puts the two in the order the window shows them (`parts` in `map.vue`: the DOM is reordered, not hidden). The phone's tab bar holds the four tools the reader chose (Forecast, Explorer, Stripes and History until then) and the Menu, and marks its Menu as the page one is on while that is the map, as long as the map is not one of the four and so is in the Menu's sheet (`aria-current="true"`, which a screen reader says, and the bar over the tab; tested at 390 px, after a pick that changes the address too; the map marks its own tab where the reader has put it in the bar), so the keyboard and a screen reader meet the chips, the map and the panel in the order of the screen at both widths. Tested. |
| 1.4.11 Non-text contrast | The violet tile: 5.7:1 against a card and 5.3:1 against the paper by day (`#7c3aed`), 4.8:1 and 5.3:1 at night (`#9a79f8`), held by `tests/unit/button-contrast.test.ts`; its glyph is white by day (5.7:1) and navy at night (5.3:1). The map is a light surface in both modes: a station dot is `#2358a8` with a white halo on the map's tone (5.7:1), the station picked a yellow disc in a navy edge, told apart from the dots by its size and edge and not by colour. The layer chip pressed is navy with white text (12.5:1) by day and the primary's light blue at night, and is `aria-pressed`. |
| 1.1.1, 1.3.1 The panel's pictures | The forecast is day rows with the weather in words (as the compact day cards have it); the climate stripes are a `role="img"` named for the station with a caption that gives the span of the years and the lowest and highest value (the stripes page's sentence); the map has a name that says the layer. |
| 4.1.3 Status messages | A station chosen, a station named by the address and the station picked again after a change of layer, and a point with no station within 100 km, are announced in a polite status; the stations that could not be loaded, a forecast or stripes that could not be read are `role="alert"` with a Retry; a search without a match and the list loading are `role="status"`. |
| 1.4.10 Reflow | No sideways scroll at 320 px with a station picked, in en, de, de-hh, lb, nl, pl, cs, it and fr (the cards' links wrap: `Open the measurements in the Explorer` was 331 px wide in English), and at 390 px; the layer chips stand one over the other under 24 rem and break a long word, and leave the map more than 60 % of its height on the measurements layer at 320 px. The empty space of the chips' row does not take the pointer. Tested. Not checked: a screen reader on a phone (VoiceOver, TalkBack), and the map by touch with 200 % text. |

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
| 4.1.2, 1.3.1 The Menu's mark | The Menu's tab is `aria-current="true"` on every page that is in its sheet and has no tab: a tool that is not in the reader's bar, the reference (Providers, Glossary, API) and the project (About, Support, Settings); a tool in the bar marks its own tab (`aria-current="page"`); the home page and the legal pages mark nothing. Tested for every kind of page, and while going from page to page and back, with the default bar and a chosen one. |
| 3.3.7 Redundant entry, storage | The choice is kept with the settings in the browser (`wd_settings`, no account); a stored choice that names a tool that is gone, repeats one or has too few is repaired to a valid list of all the tools and never an error, and where the browser refuses its storage altogether (access to `localStorage` throws) the settings are kept in memory for the visit and the app starts: before this, pages that read the settings showed an error page there (measured on `main` with `localStorage` throwing: `/` and `/meteogram` loaded; `/explorer`, `/stripes`, `/history`, `/map`, `/glossary` and `/settings` did not; `useLocalStorage` reads the property outside a try). Tested in `useSettingsStorage.test.ts` and `tab-bar.spec.ts`. |

Not checked: a screen reader (VoiceOver, TalkBack) on the chooser and its announcements; the drag by touch on a real device (it is tested in Chrome
by the browser's touch events: a finger on the handle drags and does not scroll, a finger on the rest of a row scrolls); Firefox and Safari
(the e2e spec was run in Chrome only).

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

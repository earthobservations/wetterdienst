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

- A documented parameter has to exist and a declared parameter has to be documented.
  `test_docs_parameter_descriptions_match_the_model` compares the *text* of rows that appear on
  both sides and says nothing about a row appearing on one side alone, in either direction, so a
  table could advertise a parameter no request can ask for or quietly omit one it can.
  `test_docs_parameter_tables_hold_the_parameters_the_dataset_declares` asserts both, plus that
  every documented section names a dataset the model declares. That last one is what had been
  hiding the rest: `dwd/mosmix` heads its sections `Small` and `Large` while the datasets are
  `small` and `large`, so the parse matched nothing on that page and *every* row on it went
  unchecked -- the description comparison silently skipped the whole file through its "no
  documented text" branch. The dataset now comes from the `name` row of the section's own metadata
  table rather than from the heading, which also lets `dwd/derived` keep documenting
  `cooling_degreehours_13`, `_16` and `_18` in one section as it says it does, rather than forcing
  three copies of an identical table. The plain `quality` flag stays out of the presence check --
  58 datasets declare it and 25 document it -- and the exclusion stops there rather than covering
  every `quality*` name, so that it matches what the descriptions test skips: the other five are
  all documented, and holding them here is what says so. The exemption applies to the *declared*
  side alone, because the gap runs one way: no page carries a `quality` row for a dataset that has
  no quality flag, and exempting the documented side too would have let one in -- along with a
  wrong `name_original` on any of those 25 rows, which the descriptions test skips as well, so
  nothing at all would have checked them
- `test_docs_cover_every_resolution`, asserting that each resolution the model declares has a docs
  page. The three tests above pair a resolution with its page and can only check the pages that
  exist, so a resolution added without one was compared by nothing -- the same silent skip as a
  page that parses to nothing, which they already report. `test_data_coverage` checks the other
  direction, that every page is linked from its network index, and could not see this one
- Dataset descriptions are held in both directions, the way the parameter rows are. A deleted
  `description` row, a missing `#### metadata` table or a mistyped `name` row was answered by
  comparing nothing, and so was text living only in the markdown, where the REST API, MCP and CLI
  never see it. All 217 described datasets now document it and vice versa, and the 54 that document
  none describe none either, so nothing is demanded that does not exist. A second metadata table
  for one dataset is reported rather than overwriting its twin, for the same reason as the
  parameter rows below. The repeat is counted from the sections rather than from the descriptions,
  so it is reported for the 54 datasets no description names as much as for the 217 that do, and a
  second table carrying no `description` row at all is reported too
- The three `dwd/derived` monthly `cooling_degreehours_*` datasets are each described by the
  reference temperature they actually use, phrased as their `heating_degreedays` sibling is, rather
  than sharing the docs page's blurb about "13, 16 and 18 degree Celsius". The page documents all
  three in one section and says so, which is the right documentation, but `discover`, the REST API
  and MCP report a dataset at a time and were telling a caller asking for `cooling_degreehours_13`
  that it covers three base temperatures. One `description` cell cannot equal three descriptions,
  so the text of a section naming several datasets is no longer compared -- their presence still
  is, and exactly one section is in that state
- Six dataset descriptions the docs carried and the model did not: `dwd/mosmix` hourly `small` and
  `large`, the three `dwd/derived` monthly `cooling_degreehours_*`, and `imgw/meteorology` monthly
  `climate`, whose siblings `daily/climate`, `monthly/precipitation` and `monthly/synop` were all
  already there. They are what the assertion above was missing, and what let the `mosmix` figure
  below go stale unnoticed
- A description cell that is blank, or holds a `-`, is compared like any other text rather than
  waved through. No row writes either and no parameter lacks a description, so the two escapes this
  replaces could never have caught anything -- they could only have hidden a description being
  dropped from a page, which is the failure this test exists to report
- `test_docs_resolution_descriptions_match_the_model`, holding the one description table the other
  two never reached: the `## metadata` block a page opens with, above its first dataset section.
  `RESOLUTION_DESCRIPTIONS` carries the model side, so it is compared in both directions like the
  rest. Three pages have one -- `dwd/observation` subdaily, `meteofrance/synop` subdaily and
  `metno/frost` 6_hour -- and the model has the same three
- `imgw/hydrology` monthly is described as "historical monthly hydrology data", not "historical
  daily climate data" -- wrong in both the resolution and the subject, and wrong in the model and
  the page alike, which is why a comparison between the two could not see it. A caller asking
  `discover`, the REST API or MCP for `monthly/hydrology` was told it holds daily climate data. Its
  `daily` sibling and every `imgw/meteorology` entry already follow the pattern it now follows
- A `#### metadata` table is read only under the section's own `metadata` heading, and that heading
  is matched whatever its case -- `dwd/mosmix` hourly writes `#### Metadata`. Taking any
  property/value table inside a `###` section made a second one, a `#### source file` or `####
  periods`, read as a repeated metadata table: correct documentation reported as "carries 2
  metadata tables", with its rows compared against the model besides. All 238 such tables in the
  tree are under that heading, so nothing is lost by asking for it, and the resolution-level reader
  was already asking
- A `description` cell documenting several datasets has to name what tells them apart, on top of
  the model's descriptions having to differ from each other. Its text still cannot be compared
  against any one of them, but rewriting the `cooling_degreehours` blurb to "13, 16 and 20 degree
  Fahrenheit" passed before and fails now. The prose between those tokens is what stays unchecked,
  which is the price of documenting several datasets in one section and why the exemption is kept
  this narrow
- A network exposing no `metadata` attribute is named in `NETWORKS_WITHOUT_A_METADATA_MODEL` rather
  than merely skipped. The skip was keyed on an attribute, so renaming it would drop that provider
  out of all four comparisons and, because it lands in `skipped`, exempt its published pages from
  the page side of `test_docs_cover_every_resolution` too. Renaming `metadata` to `_metadata` on
  `ipma/observation` left all nine tests passing; it now says which network and why
- The parameter-count check walks every resolution the model declares rather than only the
  documented ones, since what it asserts is a model fact. Gated on the page, deleting
  `dwd/mosmix/hourly.md` stopped the only two count-bearing descriptions being checked at all
- `test_docs_descriptions_do_not_misstate_a_parameter_count`, tying a count written into a
  description to `len(dataset.parameters)`. `dwd/mosmix` hourly describes `small` and `large` by
  how many parameters they carry, and a count in prose is the very fact whose drift set this change
  off -- the page said 115 where the model declared 122, long enough that three other pages still
  say it. Without this, adding a parameter to `large` would leave `discover`, the REST API, MCP and
  the page all saying 122 of 123 with every other test green. Two descriptions name a count
- The malformed-table report comes before the "parses to no parameter row at all" one, so a page
  whose only table is the broken one says why. It used to print nothing but the symptom -- the
  message that check was added to replace -- and a table is now reported for missing either column
  it is read for, `description` or `unit`: losing `unit` made the units test compare nothing, and
  no other test noticed
- `test_docs_parameter_units_name_the_quantity_the_model_declares`, holding the `unit` column,
  which was hand-written and compared by nothing -- which is how three cells came to name a
  different physical quantity than the value carries. A documented unit has to be the model's unit
  by name or by symbol, or one of the four notations in `_UNIT_SPELLINGS`: `kg/m²` for `mm`, which
  are equal for water and which is what DWD's MOSMIX documentation writes; `-` for a coded value
  whose model symbol is the unhelpful `sign [0..95]`; a Greek mu where the model writes a micro
  sign; and `Bft` for the model's lower-case `bft`. Those four cover all 60 cells that disagree, so
  the check runs without reflowing any of them first, and they are listed rather than tolerated
  wholesale so that a cell naming a different *quantity* fails instead of hiding among them.
  Reverting any of the three wrong-quantity fixes below now fails; the `hectopascal`/`hPa` one does
  not, because that is notation and stays GH-1980's
- A `###` dataset section carrying neither a `#### metadata` nor a `#### parameters` table is
  reported if the model does not declare it. Both halves of the orphan check were derived from
  tables, so such a section named no dataset at all and a page could advertise one no request can
  ask for -- the GH-1971 defect this test exists to report -- and be read by nothing
- Where one `description` cell documents several datasets, and so cannot be compared against any
  one of their model descriptions, those descriptions are at least required to differ from each
  other. A copied entry is the likeliest error that exemption hides: setting
  `cooling_degreehours_18` to the 13-degree sentence passed before and fails now
- A parameter table whose header has no `description` column is reported as that, and so is a row
  carrying *more* cells than its header -- an unescaped `|` in a description, which used to be read
  with every column shifted, so the text compared was whatever sat before the stray pipe. Both are
  the same "opposite of what happened" report the short-row check was added to remove, one level up
  and one direction over
- A `#### metadata` table only names its section while a section is open. A `## Notes` after the
  last `###` closes it, and a metadata table under that was renaming the last real section's
  dataset -- filing every one of its rows under a name the model does not declare -- while
  `_metadata_tables` kept the right name, so the two parsers came out disagreeing on such a page
- A directive name is matched whatever its case, as Sphinx resolves it and as the `metadata`
  heading already is here. `:::{Note}` fell through to the unknown-directive default, was read as
  code, and dropped every table inside it
- A parameter row carrying fewer cells than its header is reported as that. It cannot be read --
  the column wanted may not be there -- and dropping it silently made the presence test say the
  opposite of what happened: a row plainly on the page came out as "declares X, which it does not
  document". Forgetting a trailing `constraints` cell is a likelier slip than omitting a row, so
  the report now names the real one first
- The exemption for a `#### metadata` table naming several datasets rides with the description
  rather than with the dataset name, so a page documenting one of them in its own section as well
  has that section compared. Exempting the name let both go unread -- the silent skip this change
  set exists to close, back in by the side door
- A blank description cell and a `-` are read the same way, since both say "no text here". A `-`
  against a model that carries no description was reported as "the page describes it, the model
  does not", which states the opposite of what happened. Either is still compared where the model
  does carry one
- Under the shared-description exemption, each model description also has to name its own dataset's
  distinguishing token. Asking only that the several differ from each other, and that the docs cell
  list them all, left the 18-degree `cooling_degreehours` free to be described by the 20-degree
  sentence -- satisfying both, while nothing else reads those three. `discover`, the REST API and
  MCP would have reported the wrong reference temperature
- A `#### metadata` table under a prose `###` heading is reported rather than dropped, as the
  parameter rows in that position already were. One naming a real dataset is reported as that
  dataset's second description, so a contradictory blurb under a `## Notes` cannot slip in; one
  naming nothing is reported as a table no section encloses. The page's own resolution-level `##
  metadata` table stays out, since it sits above every section and belongs to no dataset
- `_metadata_tables` takes which section a table belongs to from `_section_datasets`, by position,
  rather than reading the heading itself. Reading it in both places is how the two came to disagree
  again: this one had no notion of the `## datasets` block, so a `#### metadata` table under a
  prose `###` elsewhere was read as a dataset -- reported as one the model does not declare, or,
  where the prose heading reused a real dataset's name, as that dataset's own description drifting.
  Taking the answer from one place is the invariant the rest of the module rests on
- A network skipped because its request class needs a package outside the base install has to be
  named in `NETWORKS_NEEDING_AN_EXTRA`, which holds `dwd/derived` alone. The skip is only a warning
  and nothing escalates it, and landing in `skipped` also exempts that network's pages from both
  directions of `test_docs_cover_every_resolution` -- so on a bare `uv sync`, where pandas is
  absent, its three resolutions went unverified with every test green. Bounded now for the same
  reason the metadata-less networks are
- A `###` heading is read as a dataset only inside the page's `## datasets` block. All 269 dataset
  sections in the tree sit there and `metno/frost` already writes prose under its own `## Notes`,
  so a prose section elsewhere was being reported as "documents a dataset 'Detail' that the model
  does not declare" -- the opposite of what happened. Each `###` still gets an entry either way,
  empty for a prose one, so this walk and the row parser stay index for index in step and rows
  under a prose heading are reported as belonging to no dataset rather than filed under the heading
- The "parses to no parameter row at all" path caps its report per page like the other one. One
  page with an extra header column reported every row of it uncapped -- 12 lines for `aemet` daily,
  hundreds for `dwd/observation` hourly -- which would then have pushed every other page's findings
  past the overall cap, the exact failure the per-page cap was added for
- A `-` description cell says "no text here" for a dataset and for a resolution, as it already did
  for a parameter row. Either was reported as "the page describes it, the model does not" where the
  model describes nothing, which is the inverted report this change set removed one level down.
  Where the model does describe it, a `-` is still compared and still fails
- `_MARKUP_DIRECTIVES` holds the table wrappers -- `{table}`, `{list-table}`, `{csv-table}`,
  `{figure}` and `{toggle}` -- alongside the admonitions and layout containers. `{table}` exists
  only to give a markdown table a caption, so wrapping a `#### parameters` table in one is the
  likeliest next step on these pages, and it would have fallen through to the unknown-directive
  default, been read as code, and taken the table with it. Verified for the colon and backtick
  spellings of `{table}` and for `{figure}`: one row parsed where none was before
- A prose line beginning with a long inline code span is yielded rather than dropped, which is what
  the comment beside it already claimed. Nothing was lost by dropping it -- a heading or a table
  row cannot start with a backtick -- but the two disagreed
- A fence marker inside a code block is literal content, not a fence of its own. Reading it as one
  left the stack permanently open and dropped every line below it -- a whole page, for a
  ```` ```text ```` block showing a `~~~` or an unclosed `:::{note}`. On a resolution page that
  came out as a flood of "declares X, which it does not document"; on a network index, where only
  the glossary test runs, it came out as nothing at all
- The datasets a `###` section names are read by its position rather than by its heading text, so
  two sections sharing a heading no longer collapse into the later one's datasets -- which filed
  the earlier section's rows under the wrong dataset, and disagreed with `_metadata_tables`, which
  reads the same page positionally
- The resolution description is read from under the page's own `## metadata` heading rather than
  from any property table above the first dataset section. A second such table -- under a `##
  Notes` or a `## periods`, say -- would have been compared against the resolution's description
  and sent the author to the wrong table
- A parameter table that no `###` dataset section encloses is reported rather than dropped. Any
  heading of level 1 or 2 closes the section, and this tree carries `## Notes` and the like, so a
  table placed after one was filed under no dataset and read by neither comparison -- the last
  silent skip of the class this change is about. Verified on `metno/frost` 6_hour, whose `## Notes`
  heading swallowed a made-up row without a word
- A page for a resolution the model does not declare is reported. The three comparisons walk the
  model, so a page left behind by a renamed resolution stayed published and stayed linked from its
  network index -- which is all `test_data_coverage` asks of it -- and was read by nothing. The
  networks skipped for a missing optional dependency are excluded from that direction, since a
  network that was never walked declares nothing and its published pages would otherwise all be
  reported -- turning the skip into the failure it exists to avoid
- A `#### metadata` section naming a dataset the model does not declare is reported even when it
  carries no `#### parameters` table. The orphan check read the parameter rows, and the description
  test walks the model's datasets, so neither reached a section left behind when its dataset was
  dropped
- `quality` descriptions are compared like any other parameter's. The presence check requires the
  25 documented `quality` rows to exist and to be keyed by the right `name_original`, so their text
  was the one thing about them that nothing checked. Removing the skip turned up two `dwd/derived`
  hourly rows writing "quality flag" against the model's "Quality flag."
- A parameter row written twice is reported rather than deduped. The parse keys on (dataset, name,
  original name), so a repeated row used to overwrite its twin and leave only the last of them
  compared -- which is the exact shape of two of the defects below, a stale row left in place
  beside the one that replaced it, so with a matching `original name` the next one was invisible
- Only a genuinely missing module excuses a network from the docs tests, and it says so with a
  warning
  naming the network and the module. `dwd/derived` imports pandas, which arrives with the `export`
  extra, so a bare `uv sync` cannot verify its three resolutions -- the reason the clause exists.
  It used to catch every exception, which meant a `metadata.py` that made `build_metadata_model`
  raise, or a typo in a provider's `api.py`, excused that provider from all four tests silently,
  including the one above whose whole purpose is to stop that. The test is read off `__cause__`
  rather than off the exception type, because `Wetterdienst.resolve` re-raises the
  `ModuleNotFoundError` as a plain `ImportError`: catching `ModuleNotFoundError` catches nothing,
  and under a bare `uv sync` the skip would have surfaced as four errors instead. A module name
  inside this package is not excused either, since `resolve` reports any name it cannot import as a
  missing dependency -- so a mistyped intra-package import in a provider's `api.py` would otherwise
  have dropped that provider out of all four tests with nothing but a warning
- All three docs comparisons state how many lines they truncated. The parameter descriptions test
  still sliced its list bare, and it is the one that gained the most coverage here, since the
  heading fix unblocked two whole pages
- The presence report is capped per page as well as overall, and states how many lines it left out.
  A single mistyped dataset `name` row matches nothing and so reports every parameter on both sides
  -- 33 lines for one page, enough to fill a flat 20-line cap and report a corpus-wide problem as a
  local one. A truncated list that does not say it was truncated reads like a complete one
- The docs tests apply `EXCLUDE_PROVIDER_NETWORKS`, which `test_data_coverage` has always applied
  and `test_docs_cover_every_resolution` did not. `dwd/radar` is deliberately undocumented and
  already has a `metadata/` package, so the day it grows a metadata model the two tests in that
  module would have contradicted each other and one would have had to fail
- The docs parsers read only the lines outside a fenced code block, so a `#` comment in a shell or
  Python example is not mistaken for a level-1 heading. One would have closed the dataset section
  it sits in and dropped every row below it out of that dataset, which the descriptions test
  answers by silently comparing nothing -- the failure mode this change set exists to remove. A
  fence closes only on a marker at least as long as the one that opened it, so a ```` ``` ```` line
  inside a ````` ```` `````-opened block is content rather than the end of it, and the open fences
  are a stack, so a code block nested in a directive still hides its own body. What is hidden is
  decided by the directive, not by the marker: a table inside a MyST admonition or layout container
  -- written `:::{note}` or ```` ```{note} ````, both legal -- is published
  documentation and has to be parsed, while `{code-block}`, `{literalinclude}`, `{doctest}`,
  `{eval-rst}` and the `{code-cell}` this repo opens 57 times all hold code. An unlisted directive
  is read as code, because the two mistakes do not cost the same: a code body read as markdown puts
  a `#` comment where a heading goes and makes the descriptions test compare nothing, silently,
  while a container read as code drops its tables, which the presence tests report. The backtick
  spelling is the one this tree writes, four times, in `docs/usage` and on `dwd/phenology`'s index;
  the colon spelling it writes once, in the `dwd/road` warning below -- which is also the only
  fence on any of the 88 resolution pages, so the guard is load-bearing rather than hypothetical.
  A backtick fence's info string may hold no backtick, so a line that merely starts with a long
  inline code span -- the shape these entries use -- is prose, not a fence that nothing closes
- `--if_exists` on `stations`, `values`, `interpolate` and `summarize`, taking `replace` (the
  default, and what the CLI did before), `append`, `fail` or `skip`. `to_target` has taken the
  argument since it was written and the export docs advertise it, but no command passed it, so
  every CLI export replaced: a nightly timer pointed at `duckdb:///obs.duckdb?table=weather` held
  one run's rows rather than a history, and nothing on the command line could change that.
  Appending now accumulates -- two runs of the same query put 550 rows then 1100 into the table.
  Which values a sink takes is the sink's business, so the option offers all four and a refused
  pairing is reported as a line and exit 1 rather than a traceback: `Append mode is not supported
  for file exports.` A test walks the command tree rather than naming the four commands, because
  the gap was a command gaining `--target` without it; `alerts`, `history` and `stripes values`
  are excluded there, their `--target` never reaching a sink. A sink failure that is not about
  `if_exists` at all keeps its traceback and names the target: the likeliest one is appending
  `--shape=wide` output onto a table an earlier run created for a different set of parameters,
  which DuckDB answers with `Binder Error: Table "weather" does not have a column with name
  "precipitation_height"`. Which of the two a failure is cannot be read off its class, because `fail` is reported
  by DuckDB as a `KeyError` and by the SQLAlchemy sinks as pandas' `ValueError`, and those classes
  are also how a sink breaks -- `if_exists` settles it, since outside `fail` neither is ever about
  the target already holding data. Reading them as refusals threw the detail away: exporting a
  stations frame to InfluxDB pops a `date` column only values carry, and the whole report was
  `ERROR date`
- Documentation for running wetterdienst on a schedule, with ready-made units for systemd timers,
  launchd, cron and `docker run` (GH-255, open since 2020). The issue asked for the units and
  proposed generating them with `hickory`; that package last released in August 2020, declares
  `requires_python >=3.6` and schedules a Python *script*, so a CLI invocation would need a wrapper
  around it anyway -- a dead dependency to write two unit files. What the page carries beyond the
  units is what a scheduled run gets wrong. A `DynamicUser=yes` service has no `$HOME` it may write
  to, and the cache directory comes from platformdirs, i.e. from `$HOME`, so without
  `CacheDirectory=` and `WD_CACHE_DIR` the run does not degrade to an uncached one, it fails:
  `PermissionError: [Errno 13] Cache directory ... does not exist and could not be created`. `No
  data available for given constraints` exits 1, indistinguishable from a real failure, so a
  schedule over a quiet station looks like a broken job. A run replaces what the last one wrote
  unless told otherwise, databases included -- a `duckdb://` table is dropped and recreated exactly
  as a `file://` target is rewritten -- so a schedule meant to accumulate passes
  `--if_exists=append`, which this release adds, or writes to a date-stamped name. And a `duckdb:///x.duckdb` path is relative to the working directory,
  because the first `/` after the `//` separates host from path; an absolute one takes four
  slashes. Plus `RandomizedDelaySec`, an off-the-hour cron minute and schedules that match the
  publication cadence, so that not every installation asks the provider at `:00` sharp
- DWD road: a temperature below -60 °C is marked suspect whatever window was asked for. The stopped
  sensors that report `-75.00` °C to the hundredth were already found by the rule that marks a
  sensor holding one value for six hours, but only where the request covered six hours to find them
  in: over one hour of the whole network -- 809 stations, 11 505 temperature readings -- that rule
  marks nothing for the two stations sitting at -75 °C, having five readings where it needs
  twenty-four, and this marks all ten of their readings. Germany's record low air temperature is
  -45.9 °C and a road surface tracks the air rather than running far beneath it, so the line stands
  14 K under that record and 29 K above the world's. `-30.00` and `-25.00` are deliberately left to
  the run rule, both being reachable on a German road in winter, and no line is drawn at the warm
  end, where 79.8 °C is implausible rather than impossible. The reading is kept exactly as DWD
  published it, as everywhere else here. GH-1917

### Changed

- **Breaking**: Every export a sink refuses raises `ExportRefusedError`: a mode it does not do, a
  target already holding data under `if_exists="fail"`, or a format or protocol nothing here
  writes. It replaces a `NotImplementedError`, a `FileExistsError`, two `KeyError`s and, in the
  SQLAlchemy sinks, pandas' own `ValueError` -- five classes for one meaning, none of them
  exclusive to it. Callers matching on the old classes have to match on this one instead, which is
  why this is here rather than in Fixed. What it buys is that nothing has to infer what a failure
  meant. The CLI's export handler tried to, over three rounds of review: `fail` arrives from DuckDB
  as a `KeyError` and from pandas as a `ValueError`, both classes are also simply how a sink
  breaks, and every rule over types and messages let something through -- a `KeyError` from inside
  a sink printed its own argument and nothing else (`ERROR date`, for a stations frame sent to
  InfluxDB, which pops a `date` column only values carry), a bare `NotImplementedError` from scipy
  would have printed an empty `ERROR` line, and `Unknown export file type` reported a traceback or
  a sentence depending on which `--if_exists` the run happened to pass. The handler is two arms
  with nothing to decide now, and `Unknown export file type` names the target it could not write
- The stale MOSMIX and DMO figures the docs carried beside the ones this release measured.
  `docs/data/provider/dwd/index.md` advertised MOSMIX-L at "~115 parameters" and both products at
  "over 5000 stations worldwide", and `dwd/mosmix/index.md` the same two, while
  `docs/data/overview.md` was being corrected to 5649 and 122 in the same change -- the twin one
  file over. Measured: MOSMIX 5649 stations for both datasets, 40 parameters for `small` and 122
  for `large`; DMO 5757 stations and 23 parameters for `icon`, 3688 and 19 for `icon_eu`. The DMO
  bullet also described the long run as "168 h lead time" beside the short one, which reads as one
  grid rather than a second run starting where the first ends
- **Breaking**: DWD DMO declares the elements its runs carry, which is 23 parameters for `icon` and
  19 for `icon_eu` rather than 122 and 40. A request for one of the 99 and 22 that are gone raises
  `NoParametersFoundError` where it used to be built and return an empty frame, so a job pinned to
  one of those names stops at construction rather than quietly producing nothing. The old lists
  were MOSMIX's, copied in when the provider was written -- which is also why `icon` held
  MOSMIX-L's count and `icon_eu` MOSMIX-S's, a split DMO
  does not have: both products carry the same elements per run, and differ in the domain they cover
  and the lead times they cover it for -- `icon` declares more only because it publishes the second,
  3-hourly run as well. Measured over 22 runs across 12 stations, both products, both lead times and
  both station groups: every run carries 21 elements, `dd ff fx3 n neff nh nl nm pppp rad1h radl1
  rads1 rr1 rrs1c t5cm td tn ttt tx w1w2 ww`, with the 3-hourly run substituting `rad3h radl3 rads3
  rr3 rrs3c` for their 1-hourly counterparts. Asking for one of the other 99 and 22 returned an
  empty frame with nothing saying the product never forecasts it -- indistinguishable from a station
  that happens to have no data. `precipitation_height_last_1h` is *added* to `icon_eu`, which serves
  it and did not declare it. Three served elements stay undeclared, for two different reasons:
  `radl1` and `rads1` are 1-hourly radiation *balances* and no canonical parameter describes a net
  flux, while `rad3h` is described exactly by `radiation_global_last_3h` -- except that name is
  already taken by `rads3`, which is a balance and not global radiation, so declaring `rad3h` means
  correcting that first (GH-1977). What this does not fix is which *run* carries what:
  the model has no lead-time axis, so `icon` declares both the 1-hourly and the 3-hourly family and
  four of its 23 are carried only by `lead_time="long"` (`precipitation_height_last_3h`,
  `radiation_global_last_3h`, `radiation_sky_long_wave_last_3h`,
  `water_equivalent_snow_depth_new_last_3h`) while three are carried only by the default
  `lead_time="short"` (`precipitation_height_last_1h`, `radiation_global`,
  `water_equivalent_snow_depth_new_last_1h`). Those still answer with the empty frame this entry is
  otherwise about -- 4 of 23 on the default path rather than 99 of 122, and GH-1976 tracks saying
  so.
  `test_dmo_declares_the_elements_its_runs_carry` reads a run through the same `KMLReader` handle
  the values path parses, and pins each run's element set separately rather than unioning them, so
  an element changing run fails it. It also asserts which lead times each product publishes, read
  off the `all_stations` listing that holds one file per run for the whole product rather than off
  one station's directory, because `icon_eu` gaining a 168 run -- which would arrive at a subset of
  stations first -- would give it the same split and leave it declaring 1-hourly elements its long
  run does not carry
- **Breaking**: `DwdDmoRequest.available_issues` takes the product it is answering for: `dataset`
  (`icon` or `icon_eu`), `station_group` and `lead_time`, all keyword-only, all defaulting to what
  `DwdDmoRequest` itself defaults to -- so what it answers with no arguments is what a request
  built with no arguments accepts. It used to list `icon/single_stations/<id>/kmz/` whatever the
  request would go on to read, and name issues that request then rejected: `icon_eu`'s
  `all_stations` publishes only the `078` lead time, so an issue advertised from a `168` file met
  `IndexError: Unable to find a 168 h forecast within ...`, and a station the shared catalogue
  listed for `icon_eu` without `icon_eu` covering it has no single-station directory, so every
  issue advertised for it resolved to an empty frame with nothing said. Both measured against the
  live server. The directory is named by one function that the values path uses too, so the two
  cannot drift apart again. `wetterdienst issues` and `/api/issues` take `--dataset`/`--lead_time`
  to match, and say so rather than ignoring them where the network is not DMO. Passing
  `lead_time=None` restores the old listing of every lead time together, which is a question about
  the directory rather than about anything that can be requested. GH-1956

- **Breaking**: `Settings.auth` holds `SecretStr` rather than `str`, so code that reads a
  credential off the settings has to ask for it: `reveal(settings.auth.aemet)`, or
  `.get_secret_value()`. Setting them is unchanged -- the env vars, the strings and the pairs all
  read as they did -- and so is every `if not settings.auth.x` check, an empty secret being falsy.
  What changes is reading one back without asking: an f-string or a `str()` of a credential now
  yields `**********` rather than the value, which is the point of the change but is silent where
  the old behaviour was not. The mask is refused as a credential on the way in, so a JSON dump read
  back fails where it is given rather than at the provider later

- **Breaking**: The `mcp` extra requires `fastmcp>=4,<5` (was `>=3.4.4,<4.0.0`), and `ui/mcp.py`
  builds the `OpenAPIProvider`'s in-process ASGI client with `httpx2` rather than `httpx`. FastMCP
  4 moved off httpx entirely and types that provider's `client` as `httpx2.AsyncClient`; an httpx
  client is still taken there by duck typing, but warns and is to be rejected in a later release,
  so the floor now says which library the code is written against. `httpx2` is declared alongside
  the extra (`>=2.12,<3`) rather than leaned on as a transitive dependency of `fastmcp`
- Locked dependencies refreshed to their latest compatible versions -- 74 packages, among them the
  majors cloup 4, fastmcp 4 (mcp 2), plotly 7 and tzfpy 2 -- and the dev toolchain with them (ruff
  0.16.7, ty 0.0.81, zizmor 1.30.1). Three specifiers had to widen to admit them: `cloup<5`,
  `tzfpy<3` and the fastmcp bound above. Plotly 7 leads an HTML export with a doctype where 6.x
  began straight at `<html>`, which is the only change visible in output
- `DwdRadarValues.period` is annotated `Period | None`, which is what it has always held: the
  argument is optional and `parse_enumeration_from_template` returns `None` for it. The annotation
  claimed `Period` and carried a `ty: ignore` to say so, which in turn made both `not self.period`
  guards in the radar API read as dead code to the type checker

### Fixed

- `wsv/pegel` returns no data for a timeseries between measurements rather than raising
  `ColumnNotFoundError`. Pegelonline answers `[]` with HTTP 200 for a series it lists but holds no
  current measurements for, and `pl.read_json` reads that body as a frame with **no columns**, so
  renaming `timestamp` raised out of an ordinary `values.all()` -- from the station list, not from
  anything the caller did wrong. The station now drops out, which is what the neighbouring guards
  already do for no internet, a 404 and a series the station does not publish, and what the wave
  tests rely on when one contributor goes quiet. MELLUMPLATE answered that way for all three of its
  wave series for days, failing `test_wsv_wave_height_comes_back_in_centimetres` and
  `test_wsv_wave_period_is_seconds` on every CI job, which is how it was found (GH-1987)
- `imgw/meteorology` daily writes `mm`/`>=0` for the precipitation and pressure rows its `synop`
  table had as `millimeter`/`-` and `hectopascal`/`-`, which is what the same page's other datasets
  and the same table's `pressure_air_site` already wrote. The monthly page was corrected in the
  same change and the daily twin left alone
- Parameter tables keep the order the model declares them in, which 229 of the 271 documented
  tables carry once the rows they omit are ignored and 196 match exactly -- 224 and 191 on `main`,
  so this change puts five more back -- and which lines a page up one-to-one with its
  `metadata.py`. Sorting `mosmix` hourly and `imgw` monthly alphabetically had broken the
  ascending-window grouping that made `precipitation_height_last_1h, _3h, _6h, _12h, _24h` legible,
  reading it as `_12h, _1h, _24h, _3h, _6h` instead, and the same for the `probability_fog_last_*`,
  `probability_drizzle_last_*` and `wind_gust_max_last_*` families
- Four documented parameters that no request could ask for, and four requestable ones that no page
  documented, found by the presence test above. `dwd/mosmix` hourly documented
  `cloud_base_convective` and `cloud_cover_below_7km` under `small`, which the model declares for
  `large` alone -- the same defect, in the same two parameters, that GH-1971 fixed for `dwd/dmo`
  `icon_eu`, because DMO's tables were copied from MOSMIX's. It also carried a stale `n1` row for
  `cloud_cover_below_1000ft` in both datasets, superseded by the `nl` row appended beside it; the
  model maps `nl` and has never mapped `n1`. `imgw/meteorology` daily documented
  `precipitation_height` under `synop`, which declares `precipitation_height_day` and `_night`
  instead, so the row named something that raises `NoParametersFoundError` -- while
  `imgw/meteorology` monthly `synop` documented none of its four precipitation parameters at all
- Three unit cells disagreeing with the model about the quantity, not just the notation: `dwd/road`
  15_minutes wrote `mm/s` where the model declares `millimeter_per_hour`, and `dwd/observation`
  monthly and annual wrote `Bft` for `wind_gust_max`, which the model declares `meter_per_second`,
  apparently copied from the `wind_force_beaufort` row above it, which really is Beaufort. All
  three now say what the model says. Found by checking every unit cell against
  `UnitConverter.get_unit`: 63 of 2213 disagreed, and the other 60 are notations rather than
  quantities -- `kg/m²` for `mm` (36), `-` for the coded `significant_weather` (16), a Greek mu
  where the model writes a micro sign (5) and `Bft` for `bft` (3), which
  `test_docs_parameter_units_name_the_quantity_the_model_declares` lists and GH-1980 is to settle.
  For the `dwd/road` cell the model is the side under question rather than the page: that module
  labels the BUFR units of the elements it decodes -- it declares `degree_kelvin` for
  `airTemperature`, whose CREX unit is Celsius -- and BUFR gives `intensityOfPrecipitation` as
  `kg m-2 s-1`, which is millimetres per second. GH-1984 carries that, with what would settle it;
  the page follows the model either way, so one label is wrong rather than two statements of it

- The changelog renders as prose again. Three bare ``` and ```` runs written into these entries
  opened real code fences, so `poe docs` warned about a Pygments lexer named `-opened` and nine
  lines of one bullet rendered as an unstyled block with the markup showing, one sentence
  disappearing from the visible text entirely. They are code spans now, with the delimiters
  CommonMark wants
- `dwd/road` 15_minutes carries a warning that its `precipitation_intensity` is labelled `mm/h`
  while the delivered value is almost certainly millimetres per second, with the factor to multiply
  by and a pointer to GH-1984 -- the page has to say what the model says, but not silently. Its
  `water_film_thickness`, labelled `cm` against a BUFR `m`, is named there too
- `dwd/mosmix` hourly describes `large` as a forecast of 122 parameters, which is what the model
  declares, rather than 115. The figure sat in a `#### metadata` description that existed only in
  the markdown, so nothing compared it. It was the fourth copy of the number: GH-1975 corrects the
  other three, in `docs/data/overview.md`, `dwd/index.md` and `mosmix/index.md`, so all four agree
  in this release
- `dwd/observation` hourly writes `hPa`/`>=0` for the `urban_pressure` row it had as
  `hectopascal`/`-`, which is what the same table's `pressure_air_site` already wrote, and puts the
  two rows in the order the model declares them -- the one table this change touched that was among
  the 47 of 271 `main` leaves out of order, five of which this change fixes. `main` carries 69 rows
  that spell a unit out where their own page uses the symbol for it: 57 write `dimensionless`
  against a `-` elsewhere on the page, which is a convention to settle rather than a slip
  (GH-1980), and of the other 12 this change fixes 9 -- 5 on `dwd/mosmix` hourly and 3 on
  `imgw/meteorology` daily, both described above, plus this one -- leaving the 3 on `dwd/dmo`
  hourly to GH-1975, which has that file open
- The three `dwd/derived` `Kuehltage` overrides are described as "Number of days with at least one
  cooling hour", which is what DWD's *Kuehltage* counts, rather than the vaguer "Number of days on
  which cooling was required". The precise wording sat in the docs table, where nothing compared it
  -- that page is one of the two the heading mismatch above had left unchecked. The canonical
  `count_days_cooling_degree` keeps the general wording, because cooling degree days elsewhere are
  defined against a base temperature rather than by counting hours, and because that is exactly how
  the sibling `count_days_heating_degree` is split: a general canonical, with DWD's "number of days
  with daily mean air temperature less than 15 degree Celsius" in the override
- The same parser keys `test_docs_dataset_descriptions_match_the_model` too, which had the
  identical heading bug and so compared nothing on those same two pages. Both now resolve:
  `dwd/mosmix` under `small`/`large` and `dwd/derived` under all three `cooling_degreehours_*`.
  Both are compared now, since this change gives the model the descriptions those pages had been
  carrying alone. `dwd/observation` subdaily `wind_extreme` also gained the `quality_3` and
  `quality_6` rows it declares but never showed, placed where the model declares them, interleaved
  with the gust rows -- so that table reads differently from the four beside it, which put their
  `quality` row last against a model that declares it first. Declaration order is the convention
  this change adopts, and `quality`'s placement is part of the row-order question GH-1980 carries
- **Breaking**: A DuckDB `if_exists="append"` matches columns by name. `INSERT INTO t SELECT * FROM
  origin` matches by position, so two frames carrying the same number of columns under different
  names were both accepted and the second one's values landed under the first one's headings --
  measured on a `--shape=wide` schedule that changed one parameter: `2025-03-23` ended up holding
  both `10.1`, the temperature, and `0.0`, that day's precipitation, in the column named
  `temperature_air_mean_2m`, exit 0 and nothing said. Reachable from the command line only since
  `--if_exists` existed, and reachable by exactly the schedule the docs recommend. `BY NAME`
  refuses it with `Binder Error: Table "weather" does not have a column with name
  "precipitation_height"`. It does not catch every parameter drift, and the docs no longer say it
  does: a frame whose columns are a subset of the table's is accepted, with nulls for the rest, and
  under `--shape=long` the column set never varies, so nothing about `--parameters` reaches the
  insert there at all
- The InfluxDB sink takes `if_exists="append"`, which is the one word for what it actually does:
  every write is points, and a point carrying the timestamp and tags another already has replaces
  that one. Refusing that spelling made the batch export impossible rather than merely awkward --
  `TimeseriesValues.to_target` writes its first station with the `if_exists` it was given and every
  station after it with `append`, so no argument let a multi-station request reach InfluxDB at all.
  The three export examples in the docs did exactly that and had been broken since the day
  `if_exists` was added (02c3b15b, 2025-10-29), which added the guard and the examples together.
  `fail` and `skip` stay refused, because both turn on whether the measurement already exists and
  this sink never asks; the message says so rather than naming the mode alone. `replace` is
  accepted as before and does not clear the measurement, because nothing here issues a delete --
  the modes list says that now instead of implying otherwise, and says which default belongs to
  which class: `replace` on a result, `fail` on `TimeseriesValues`
- DWD DMO: both dataset descriptions were MOSMIX's, word for word. `icon` was described as "Local
  forecast of 115 parameters for worldwide stations, 4 times a day with a lead-time of 240 hours"
  and `icon_eu` as the 40-parameter, 24-times-a-day one -- that is MOSMIX-L and MOSMIX-S, a
  statistical postprocessing that DMO explicitly is not, and "worldwide" cannot be right for a
  limited-area model covering 3688 stations where the global product covers 5757 -- though
  "European" is not right for it either, since 11 of those 3688 sit between 13.25 and 22.52 degrees
  north and 35.6 and 49.12 degrees east, which no sense of the word covers, so the description
  names the set it is published for instead. That set sits inside nothing else here: 132 of the
  3688 are absent from the 5811-row shared catalogue, which is what
  `_with_stations_the_catalogue_omits` recovers, and 189 are absent from `icon`'s 5757, so it is
  smaller than the global product's set without being a subset of it. Read off upstream: products
  are issued at 00 and 12 UTC, `icon` hourly out to 78 hours plus a second run 3-hourly from 78 to
  168 (the long run *starts* where the short one ends -- it is not a 0-168 hour grid),
  `icon_eu` hourly out to 78 only. Neither description names a parameter count any more: both
  counts came from MOSMIX's leaflet, 115 being MOSMIX-L's and 40 MOSMIX-S's, a split DMO does not
  have. 40 did match what `icon_eu` declared before this release, but only because that parameter
  list was MOSMIX-S's verbatim as well. The `icon_eu` parameter table also listed
  `cloud_base_convective` and `cloud_cover_below_7km`, which the model does not define for that
  dataset, so the docs advertised two parameters no request could ask for
- WSV pegel: the wave tests ask each station whether its own values are in the declared unit, rather
  than asking whether two stations agree with each other. Comparing them assumed the same sea at
  both, and they do not carry the same window -- MELLUMPLATE had 98 readings over 1.6 days against LT
  ALTE WESER's 14 347 over ten, so their means were taken over different weather and differed by
  10.5x against an assertion of less than 10, while over the window they share the ratio was 4.6x.
  That failed on every one of the ten CI matrix jobs for days with no unit being wrong, and a
  permanently red matrix is where a real failure goes unnoticed. The bounds now separate the two
  readings of the same number instead: a median of 9.5 cm is 0.095 in metres, so the threshold sits
  near the geometric middle of the hundredfold being guarded against, and no sea state moves a median
  across it. Both wave tests read every station offering the parameter rather than two named ones, so
  a station that stops publishing drops out instead of failing a test about units

- DWD DMO: a station the shared catalogue omits is described from the product's newest run, so it can
  be asked for. 135 of the stations `icon` forecasts for and 132 of `icon_eu`'s are absent from
  `dmo_stationsliste_txt.asc` -- 72 of them with ids it never carries, such as `Y0330`, `G431` and
  `O015` -- and being absent from it they were filtered out of every request, although their
  forecasts are published and fetch with HTTP 200. `Y0353` is Mont Blanc. The run's placemarks carry
  an id, a name and a position in decimal degrees, which is what these stations are now described
  with; they carry no ICAO id, so the catalogue stays the source for the stations it does list rather
  than being replaced, and the added ones report `icao_id` as null, which the catalogue already does
  for the stations it writes as `----`. Both products now advertise exactly what they publish, 5757
  and 3688. The run is read only where the catalogue is missing something, so a catalogue DWD
  completes costs nothing, and once per product per request; a run that cannot be read leaves the
  catalogue as it was and says so, as does one placemark that cannot be, the rest of them still
  describing their stations

- DWD DMO: a run stamp becomes the hour it names whatever that hour is. `DDHHMM` had its day, month
  and minute padded back to two digits before the datetime was parsed, but not its hour, so `3` made
  `...01300`, where `%H` takes the `30` it can see and rejects it as an hour. `00` survived only
  because `%H` could take both its digits and leave `%M` the one it needed. DMO publishes at `00` and
  `12` so no run has ever hit this, and it is fixed because the rule is about the stamp rather than
  about which hours DWD happens to use

- DWD DMO: a station position is read as the degrees and minutes the catalogue writes it in, and the
  seven hardcoded station patches are gone. `dmo_stationsliste_txt.asc` is one format throughout,
  `{degrees}.{minutes:2d}`, and it is the degrees rendering empty at zero that makes the rest look
  irregular: the minutes are right-aligned in two columns, so a lone digit arrives behind a space and
  a negative one behind its own minus sign. `. 5` is 0°05' and `.-6` is -0°06'. Read as plain
  decimals, `.5` became 0°50' -- a station 84 km from where DWD says it is, and nothing raised --
  while `.-6` raised `conversion from str to f64 failed` naming neither column nor station, which is
  what the patches existed to avoid. Of the file's 11 622 position fields, 77 carry no degrees and 21
  of those needed repairing: 14 written with one minute digit, 11 of which landed 50 to 150 km out
  while 3 were a harmless zero, and 7 carrying the sign on the minutes. All 21 now land on the
  coordinate DWD's own KMZ placemarks carry, to 0.000 km for all seven formerly patched stations --
  where the patches were 4 to 28 km out, put London City on the wrong side of Greenwich, and gave
  London Weather Centre a height of 5 m against the 43 m both DWD sources agree on. One field is
  beyond reach: `P0563` (London Luton) is written `.22` where DWD's placemark says -0.37, the sign
  missing rather than misplaced, and nothing distinguishes that from the 39 degreeless fields that
  really are positive -- it is read as written, exactly as before. The MOSMIX catalogue shares the
  format and the conversion but has no such row, so this stays with DMO

- **Breaking**: DWD DMO: a station is advertised only for the product that forecasts for it.
  `dmo_stationsliste_txt.asc` is one list for both DMO products and matches neither: of its 5811
  stations `icon` covers 5622 and `icon_eu` 3556, so a request for `icon_eu` listed 2255 stations
  that could only ever answer with an empty frame -- indistinguishable, from the caller's side,
  from a forecast that is merely missing right now, and from the swallowed listing GH-1947 was
  about. Which stations a product covers is now read from its `single_stations/` directory, whose
  entries are exactly the placemarks that product's `all_stations` run carries, so the correction
  costs one directory listing rather than a 20 MB parse. A listing that cannot be read keeps the
  shared catalogue rather than answering that a product has no stations, and says which it handed
  back; so does a listing that shares no station with the catalogue, which is not a station listing
  however many names it carries. Four of the seven hardcoded station patches are genuinely outside
  `icon_eu` -- Gao, São Gabriel da Cachoeira, Quito and Quito/Mariscal Sucre lie outside a European
  domain -- and are now dropped for it too

- DWD DMO: the directory a product is served from is named by a total mapping rather than one special
  case with a pass-through, so a product added without deciding its upstream spelling is refused where
  the decision is missing instead of 404ing at request time

- DWD swsmos: a body that could not be read is not fetched a second time when the caller has
  disabled the cache. The re-ask exists to get past a cached bad body, and `cache_disable` now says
  whether there is one: it named nothing in `NetworkFilesystemManager`'s registry key when this was
  written -- a request that disabled the cache was served by whatever had been registered first in
  that thread, cache and all -- and GH-1947 put it in that key, so the flag decides what is built
  and asking again would fetch the same bytes down the same wire

- Examples: the DuckDB dump addresses its database file with three slashes rather than four, so
  it opens on Windows. `ConnectionString` takes the database as the URL path with one leading
  slash removed, so exactly one slash belongs between the scheme and the path -- which a POSIX
  path supplies itself and a Windows path does not. The fourth slash was silent on POSIX, where
  the doubled `//` still resolves, and on Windows left DuckDB with `Cannot open file "//C:\..."`,
  reading the leftover slash as a UNC share. The string was always wrong there; the test added in
  GH-1958 is what ran the example on Windows and said so. The same count was wrong in the two
  places that teach it: `to_target`'s own docstring and the PyConDE notebook both showed
  `duckdb://name.duckdb`, which `urlparse` reads as a host rather than a path, so the database fell
  through to the `dwd` default -- data written to an extensionless file named `dwd` in the working
  directory, with no error, and in the notebook's case to a file it then reads back under a
  different name
- Network cache: the on-disk blob directory is separated by the TTL and by the headers that can
  change what a server sends back, and by nothing else. It used to be named for a hash of the whole of `client_kwargs`, which mixes the two
  kinds of thing that go in there: an `Authorization` header decides what a server sends back,
  where a timeout, a proxy and a User-Agent decide nothing about it. The default User-Agent carries
  the version number, so every release renamed the directory and began again from an empty cache --
  and nothing read the old name afterwards or removed it. One developer machine held 129
  directories under 98 distinct hashes and 4.3 GB, of which 115 MB was reachable by the installed
  version; 1.4 GB sat under `ttl-INFINITE-*`, which is a provider saying those bytes never change.
  A credential that rotates does the same on a faster clock, Met Office minting a three-day JWT.
  Directories of the older layout are reclaimed on the first cached download of a process, which is
  safe precisely because no key this version can produce names them. So is a directory a credential
  named that has since rotated, aged out at a month by a marker touched whenever something asks for
  the directory -- the blobs cannot answer that question, an archive read on every run and written
  on none having file times as old as the day it was fetched. Only a directory that carries such a
  suffix is ever aged out: the shared one is named on every run, and reclaiming it for looking idle
  would throw away the main cache rather than a leftover. The in-memory registry key goes on
  separating filesystems by everything one is built from, transport settings included -- `register`
  runs only for a key that is new, so whatever that key omits, the first caller in a thread decides
  for every later one. What it is given to hash changed with the entry below, for the same reason.
  GH-1959
- Network cache: a blob its own TTL has already made useless is dropped, once per directory per
  process. The obvious version of this is destructive, which is why it was taken back out of
  GH-1954: `CacheExpiry.INFINITE` is `False`, `int(False)` is `0`, and fsspec reads an expiry of
  zero as "every entry is expired" -- it removes them all and then `rmtree`s the directory, so the
  first such download in a fresh process would have thrown away the immutable archives `lhmt` and
  both `meteofrance` providers keep there and fetched them again. So a TTL that is not a positive
  number is not swept at all; the expiry is passed explicitly rather than left to fsspec's fallback
  to `self.expiry`; the directory is marked swept before the attempt rather than after, since
  `clear_expired` raises for a half-written entry and a sweep retried on every registration would
  fail every download for that TTL for the life of the process; and the lock is held across the
  sweep rather than around the bookkeeping, which is what keeps a `download_files` thread pool from
  writing rows that the sweep's own snapshot would then drop and orphan -- the leak this closes.
  One lock covers building a caching filesystem as well as sweeping or reclaiming one, because
  building reads the metadata file the other two delete: on POSIX an unlink leaves the open handle
  readable and the race is invisible, where on Windows the builder gets `PermissionError` out of
  fsspec's `CacheMetadata._load`. GH-1955
- Network: two credentials never share a cache directory or a filesystem, whatever shape their
  headers arrive in. Three ways they could, each of which also told the error scrubber there was no
  credential on a request that carried one -- so a failure holding the header went into the retry
  log `stamina` writes. `str()` of a `SecretStr` is `**********`, and `Settings.auth` has held
  credentials as `SecretStr` since GH-1937, so every secret hashed to one value; because that hash
  also names the in-memory filesystem, the second caller was handed the first caller's filesystem,
  built with the first caller's `Authorization` header, which is GH-1947 again. A value is read for
  what it stands for now. `client_kwargs["headers"]` reaches aiohttp as a mapping or as a sequence
  of pairs, and only the mapping was read, so a pair list answered "no credential"; both are read
  now. An iterator is deliberately not read at all -- reading it to name a directory would empty it
  before the request that needs it -- and counts as carrying a credential rather than as carrying
  none
- Network: the cache separates on every header but the ones that cannot change a body, rather than
  on a list of the ones known to carry credentials. That list is written for redaction, where
  missing a name costs a log line; here it costs one caller's body being handed to another, and
  `WD_FSSPEC_CLIENT_KWARGS` is a public setting -- `Accept-Language: de` and `en` shared a
  directory, as would `Cookie` or any header nobody had thought of. An unknown header now costs a
  cache miss, which is a slow answer rather than a wrong one
- met.no Frost: the credential probe builds its own headers rather than writing into the dict
  `Settings` holds. `{**settings.fsspec_client_kwargs}` copies one level, so `setdefault("headers",
  {})[...] = ...` mutated the shared mapping and every later request from that `Settings` -- any
  provider, not only this one -- carried met.no's basic auth
- Network: the log says whether a file was downloaded or read from the cache, rather than saying
  "Downloading file" for both. `File.from_cache` has known which since GH-1947, and it is known
  before the read rather than after, so both the opening and the closing line can say it instead of
  guessing -- and the guess was wrong for every cache hit, which is the one thing a reader of the
  log could already tell was not happening. Said per attempt, so a retry that goes to the network
  after a cached read failed reads as the two different things it is. `download_files` likewise
  announced `Downloading 3 files` before any of the three had been asked for; it now says what it
  is fetching up front and, once they have all been answered, how many of them arrived and how many
  of those the cache answered -- a failure comes back as a `File` carrying the exception rather than
  raising, so counting the list would have said three files arrived where three 404s did. Where
  there is no cache to report on -- `cache_disable`, or the `NO_CACHE` the 1-minute precipitation
  metaindex asks for over a hundred files at a time -- it says `uncached` rather than `0 from
  cache`, which reads as the cache having held none of them. A single file reads as `1 file` rather
  than `1 files`, and the metaindex no longer prints its own count immediately above this one

- DWD mosmix: a `kml/` directory that exists and holds nothing says so, rather than raising past
  the line written for it -- whichever run was asked for. `next` raises `StopIteration` where its
  filter matches nothing, and the `except IndexError` guarding the `LATEST` lookup never caught
  that, so what a caller saw was `RuntimeError: generator raised StopIteration` from inside the
  collection walk (PEP 479 converts it at the generator boundary), naming neither the directory nor
  what was looked for -- or a bare `StopIteration` carrying no message where `get_url_for_date` was
  called directly. Asked for a default instead of guarded by an exception it cannot raise, there is
  nothing to miss. An explicit `issue` failed differently and just as opaquely, building a frame
  whose `url` column was all-null and meeting `invalid series dtype: expected String, got null` in
  the split below it, so an empty listing is now answered before either branch reads it, being one
  thing whichever branch asked. What a run is called is read once, as the ten digits DWD stamps it
  with in a name ending `.kmz`, rather than as the third `_`-separated part of one. Not `.km[lz]`,
  though the directory is named `kml/`: `KMLReader.fetch` hands every download to `ZipFileSystem`,
  which raises `BadZipFile` on a plain KML, so accepting an uncompressed forecast here would
  resolve to a file the reader cannot open -- and would prefer it where DWD published both. That
  wants the reader taught first. MOSMIX-L
  all-stations is the layout that broke on: `MOSMIX_L_2026092203.kmz` carries no station id, so the
  third part was `2026092203.kmz` with the extension still on it, and the alias was `LATEST.kmz`,
  which the filter dropping `LATEST` does not match -- every row then met `conversion from str to
  datetime failed`, and that layout could not be asked for a run at all. MOSMIX-S all-stations was
  never affected: its lead time keeps the run in the third part (`MOSMIX_S_2026092205_240.kmz`) and
  its alias reads as plain `LATEST`. It is on one rule with the others now, rather than on a naming
  that happened to survive. Anything else in the directory is dropped by the same rule, a README as
  much as a checksum published beside a forecast and carrying its run stamp, which would otherwise
  leave two rows matching one run and raise `ValueError: can only call '.item()' if the Series is
  of length 1` in place of that `IndexError`. A station
  whose directory DWD has emptied or retired is how one reaches the empty-directory half, a path
  that no longer exists being answered with no entries rather than an error; the draft adding
  MOSMIX-SNOW is what first met it, that product being published only from November to April. The
  `LATEST` alias is held to the same rule as a dated run, so the default path cannot answer with a
  checksum published beside it either -- today only the listing's sort order keeps it from doing so.
  What none of this changes is who the error takes down with it: nothing between `get_url_for_date`
  and `values.all()` catches, so an emptied directory costs the whole request rather than the one
  station, where `dwd/dmo` returns `None` and keeps the others. That difference is GH-1949. GH-1946

- DWD mosmix: `available_issues` answers a `kml/` directory that holds no run with no issues,
  rather than raising out of `wetterdienst issues` and the `/issues` endpoint, which are what reach
  it. An empty listing built a `url` column of dtype Null and raised `invalid series dtype:
  expected String, got null`; an entry that is not a forecast reached the positional read and
  raised `get index is out of bounds`. Which runs exist has an answer in both cases: none. It reads
  the run by the rule above rather than positionally, so it no longer carries the all-stations
  fault either. Said with a warning naming the directory, because `fs.find` walks with
  `on_error="omit"` and aiohttp's `ClientOSError` is an `OSError`, so a connection reset mid-listing
  -- and the 404 of a station id that does not exist -- arrive looking exactly like an empty
  directory, and a silent `[]` would make either a fact about the station. What that costs a caller
  who is not reading a terminal: `/api/issues` answered a blip with the polars error as an HTTP 400
  and the CLI exited 1, where both now answer `{"issues": []}` and exit 0. Telling them apart needs
  the listing to report what it swallows, which is GH-1947. A directory holding no dated run is
  reported by what is in it -- how many entries, how many of them the `LATEST` alias -- rather than
  by a guess at why, an alias being a forecast and only a dated run being what this lists. GH-1946

- DWD dmo: `available_issues` answers a `kmz/` directory that holds no run with no issues, rather
  than raising out of `wetterdienst issues` and the `/issues` endpoint, which are what reach it. An
  empty listing built a `url` column of dtype Null and raised `invalid series dtype: expected
  String, got null`; an entry that is not a forecast reached `add_date_from_filename` and raised
  `conversion from str to i64 failed ... ["AD"]`. Which runs exist has an answer in both cases:
  none -- as `dwd/mosmix` now does for its own directory, in GH-1946, which this does not depend
  on. Said with a warning naming the directory, because `fs.find` walks with `on_error="omit"`
  and aiohttp's `ClientOSError` is an `OSError`, so a connection reset mid-listing -- and the 404 of
  a station id that does not exist -- arrive looking exactly like an empty directory, and a silent
  `[]` would make either a fact about the station. What that costs a caller who is not reading a
  terminal: `/api/issues` answered a blip with the polars error as an HTTP 400 and the CLI exited 1,
  where both now answer `{"issues": []}` and exit 0; telling them apart needs the listing to report
  what it swallows, which is GH-1947. What counts as a forecast is the six digits a run is stamped
  with *and* the `.kmz` the name ends in: the slice that reads the stamp takes four characters off
  whatever it is given, so `..._210000.txt` strips to `210000` and would have been reported as a run
  that exists, while `.kmz.md5` failed only by stripping to `210000.kmz`, which is luck rather than
  a rule. The positional read itself stays, along with the lead-time substring match and the
  tz-aware issues this method advertises that `get_url_for_date` rejects, which are GH-1948.

- DWD dmo: a run is read by its whole name, where every part of it was read by position or by
  substring and each wrongly. The lead time was matched as a bare `"78"` or `"168"` anywhere in the
  URL, which the station id also satisfies -- 187 of 5811 ids contain `78`, so a request for the
  short lead time kept the long one's files too, two rows carried one run start, and
  `df.get_column("url").item()` raised `can only call '.item()' if the Series is of length 1`; that
  is roughly 3% of DMO stations unable to be read at all, and the rest matched by luck. The run
  stamp was the last `_`-separated part with four characters taken off the end, so a README reached
  the parse and raised `conversion from str to i64 failed ... ["AD"]`, and a `..._210000.txt`
  sidecar strips to a valid `210000` and could be answered with -- handing the reader a file that is
  not a forecast, where a crash would at least have named the listing. And `available_issues`
  returned tz-aware UTC datetimes while this compared against a naive column, so an issue that
  command advertised was rejected by the next one with `could not evaluate comparison between
  series 'date' of dtype: Datetime('us') and ... Datetime('us', 'UTC')`: `wetterdienst issues`
  printed issues in a form `wetterdienst values` could not accept. Named as a whole
  (`_<lead>_<n>_<DDHHMM>.kmz`), the lead time is a field rather than a substring and a name that is
  not a forecast carries no stamp; the issue is converted when it carries a zone, and a filter that
  empties the frame says so rather than reporting `Unable to find None file within`. `available_issues`
  reads by the same rule. An issue between two releases is also floored to the one before it, where
  `hour % 12` sent 1 through 11 *up* to 12: asking for the 03:00 run returned the 12:00 one, issued
  nine hours later, or raised where 12:00 was not yet published while 00:00 sat there unasked for.
  That was unreachable until the comparison above was fixed, every non-`LATEST` issue having raised
  before it decided anything. An issue given in another zone is converted rather than relabelled,
  too: taking its wall-clock hour and stamping UTC on it read `13:00+02:00` as 13:00 UTC, so
  11:00 UTC asked for was answered with 12:00 -- one release too late, and at 11:00 a run not yet
  published, so an `IndexError` where the 00:00 run was sitting there. GH-1948

- DWD mosmix: `LATEST` reads the newest run the listing names, rather than the `LATEST` alias
  beside it, and a forecast is held for as long as its URL allows. The two are the same bytes --
  the server answers one ETag, one content-length and one Last-Modified for both, the alias being a
  link rather than a copy -- but a run named by its timestamp is that run for good, where the alias
  is a name whose content DWD replaces every hour. Holding everything for five minutes meant
  re-downloading `MOSMIX_S`, 36 MB published hourly, up to twelve times an hour for a file that had
  not changed; a named run is held for twelve hours and only the alias, still the fallback for a
  listing that names no run, keeps the short expiry. `dwd/road` and `dwd/dmo` already index the
  named files and skip the alias. What that costs is a distinct URL per run, so the cache gains a
  blob an hour where it reused one: 36 MB an hour and 871 MB a day for MOSMIX-S, against 10.4 GB a
  day over the wire before. Nothing evicts a blob once its expiry has passed, which is GH-1955 and
  is true of every provider here -- the observation zips and the radar files accumulate per URL
  already, and reusing one blob was mosmix's anomaly, from resolving to a name whose content
  changed under it. `dwd/dmo` reads through the same class, so its downloads take the long hold
  too; its names carry the same immutable run stamp. GH-1945

- DWD mosmix: a station whose directory DWD has emptied or retired costs that station and no more.
  `get_url_for_date` raised on a listing that named nothing, and nothing between it and
  `values.all()` catches, so one such station ended a request for fifty and took the forty-nine
  that do publish with it. It answers `None` now and the readers give that station an empty frame,
  which is the split `dwd/dmo` has always made; mosmix raised because its return type said it must.
  A directory that names files but no forecast still raises, being a statement about the product
  rather than about one station -- and so does an empty listing for the all-stations products,
  where one empty directory is every station at once and therefore cannot mean a station retired.
  A run whose cached body is not a zip is dropped from the cache and asked for once more, too:
  fsspec records a cache entry before the copy that fills it finishes, so a download interrupted
  mid-copy leaves a truncated blob that is accepted for the life of the entry -- which held five
  minutes righted itself and held twelve hours would not. GH-1949

- Examples: the DuckDB dump writes outside the repository when it runs under pytest. It is a smoke
  test there rather than an artifact -- one station's values, thrown away -- but it wrote to the
  tracked `examples/provider/dwd/dwd_obs_daily_climate_summary.duckdb`, so every test run left a
  1.3 MB binary modified in the working tree. That has twice been committed by accident alongside
  unrelated work, which is how it was noticed; a test now asserts the file is untouched after the
  example runs.

- Network: the cache says what it did, where it used to decide on a caller's behalf and keep
  quiet. `cache_dir`, `cache_disable` and `use_certifi` all decided what
  `NetworkFilesystemManager.register` built and were then not part of the key it was filed under,
  and `register` runs only for a key that is new -- so the first caller in a thread decided for
  every later one. `CacheExpiry.METAINDEX` being an alias of `TWELVE_HOURS`, any earlier metaindex
  download from any provider was enough to leave a caching filesystem under that key, and a later
  request made with caching disabled, or against a different `WD_CACHE_DIR`, was then served by it.
  All three are in the key now -- which names the instance in memory and nothing on disk, the blobs
  staying where they have always been, since a key that reached the filesystem would strand every
  blob an affected user already has. A listing that could not be read is also no longer answered as
  an empty directory: `fs.find` walks with `on_error="omit"`, which catches `OSError` and returns
  nothing, and aiohttp's `ClientOSError` is one -- so a connection reset was swallowed inside
  fsspec, never reached the retry wrapping the call, and left every provider to decide what an
  empty list meant, which none of them could. It raises now, and the two are told apart where the
  difference is knowable: a directory that is not there is `FileNotFoundError` and stays the `[]`
  callers have always had, and being offline stays `[]` too -- that is the whole library being
  offline rather than this listing failing to read, and every other path here degrades on it
  quietly, a download coming back carrying `NoInternetError` for providers to answer with empty
  frames. That covers a flat listing, which is what this library asks for almost
  everywhere; fsspec does not forward `on_error` to the recursive half of a walk, so a failure
  below the top level of a subtree is still swallowed, which is noted in GH-1947 rather than
  claimed as fixed. And `File` carries `from_cache`, sampled per attempt, because a caller that
  cannot use what it was given needs to know whether asking again could answer differently.
  GH-1947
- DWD swsmos: the run is read once for the request rather than once for every station it answers
  for. One run file holds every road station's whole forecast -- 306 612 rows, 1 836 stations to
  +167 h -- where the collection above it asks for one station at a time, so the run was listed,
  fetched and parsed once per station and all but one station's rows thrown away each time. Five
  stations parsed the same file five times, 2.5 s of a 2.7 s request; twenty-five took 14.1 s, and
  the whole network would have spent a quarter of an hour decompressing one file it already held.
  They now take 0.7 s and 0.8 s: one parse whatever the request asks for, and a 1.08 ms filter over
  the parsed run per station after it -- near-flat rather than flat, 1.98 s of filtering for the
  whole network, where partitioning the run by station would cost 0.065 s once and is the better
  trade only above about sixty stations. The whole
  run is kept where `dwd/road` keeps only its last station group, a run being one file of some
  20 MB however wide the request or long the window, and it needs no key: a group varies from
  station to station, while the run is a property of the query. It is pinned for the length of a
  query and no longer, so a caller keeping the values object and querying it again on a timer is
  answered with the run published since rather than the one it first resolved. A run that cannot be
  fetched is likewise asked for once, and reported once, instead of once per station. This is the
  half of GH-1922 left open when `dwd/road` was fixed, measured rather than assumed to transfer.
  GH-1922

- DWD swsmos: `LATEST` no longer answers with a run up to twelve hours old. How long a run may be
  cached is a property of the URL rather than of the request: a run named by its timestamp is that
  run for good, while `swsmos_LATEST_opendata.csv.bz2` is a name whose content DWD replaces every
  hour -- and the alias was cached by URL for twelve hours like everything else, so "the latest
  run" could be one whose first twelve forecast hours had already happened. Measured against the
  live server at 22:57 UTC: the alias was answered from the 21:00 run while DWD was serving 22:00.
  `LATEST` now resolves to the newest run the directory listing names, which is the same bytes --
  the server returns one ETag for the alias and that file, one content-length and one
  Last-Modified, the alias being a link rather than a copy -- from a URL that cannot change under
  its cache entry, so the answer is the newest run with nothing to expire. The listing is never
  cached, and `dwd/road` likewise indexes the timestamped files and skips the aliases duplicating
  them. The alias remains the fallback for a listing that names no run, held for five minutes,
  which is what `dwd/mosmix` holds its KML for. Found while reviewing the fix above, and older than
  it. GH-1922

- DWD swsmos: a run that cannot be read is reported and skipped, where it used to end the request
  in a traceback. A body that is not the bz2 a run file should be raises out of `bz2.decompress` --
  `ValueError` where it stops early, `OSError` where it was never bz2 -- and nothing between there
  and the caller catches, so a truncated download ended `values.all()` in a traceback where a
  failed download ends it in an empty frame. It is cached for twelve hours as well, so the same
  traceback would have repeated for half a day. It is now warned about and answered the way a
  failed fetch is, and `LATEST` falls back to the run before the newest: the listing is
  deliberately uncached, so it names a run the moment it appears, and a run still being written
  cannot be read -- an hour-old forecast is what `LATEST` should mean in that window rather than
  nothing. What counts as a run is matched exactly (`swsmos_<14 digits>_opendata.csv.bz2`) rather
  than by a `swsmos_` prefix, which also matches a checksum sidecar or a second product published
  beside the runs -- and one of those sorts *after* the run it belongs to, so the newest name would
  have been a file that is not a run. A run that arrives holding nothing takes the same way out:
  `bz2.decompress(b"")` returns `b""` rather than raising, so a zero-byte 200 parsed to a frame of
  no rows and read as a run that simply holds nothing, which became the request's answer while the
  run before it went untried -- the same window, one byte-count away. And a body that could not be
  read is asked for once more past the cache before falling back, since it is held under its URL
  for twelve hours like a good one, so what the cache hands back says nothing about what the server
  has now -- and answering from the run before it without asking would mean an hour of yesterday's
  hour while the run the caller asked for sits complete on the server. `LATEST` means the newest
  run there is, not the newest one a stale cache entry will admit to. The re-ask is not held back by
  `cache_disable`, which does not say what it looks like it says: `NetworkFilesystemManager` keys
  its filesystems by TTL and client kwargs alone and registers one only where that key is new, so a
  request made with caching disabled is served by whatever was registered first in that thread,
  cache and all (GH-1947). Naming the run rather than the alias also means a distinct URL per model
  run, so the cache grows by one 1.9 MB body an hour where it used to refetch one: 45.6 MB a day,
  1.34 GB a month and 16.3 GB a year for a process that keeps asking, against a cache that has no
  eviction at all and already reaches 4.2 GB on its own. Small next to that figure for a quarter,
  and past it thereafter; tracked in GH-1947. A listing
  that names no run at all now says so too, where it used to answer every station with an empty
  frame and no diagnostic: the listing is retried and re-raises, so an empty one means the server
  named nothing, which is a directory reorganised rather than a day without data. Found while
  reviewing the fix above. GH-1922

- A token exchange that meets a server error is asked a second time. `post_file` retried a
  connection that never carried a response, but took every response that did arrive as an answer --
  and a 502 or 503 from a token endpoint is a blip, not an answer. A mint is made once every three
  days and empties a whole Met Office query when it fails, so it is the request least able to afford
  a single-shot failure. A body that stops arriving mid-read is asked again too -- it is the same
  kind of blip, and no subclass of the connection errors that were already named. A 401 is still an
  answer, and a 429 deliberately so: the endpoints that rate-limit are rate-limiting a free account,
  and asking again a tenth of a second later makes that worse rather than better. `download_file`
  is held to the same policy, where it used to retry any failing status -- so a 429 from AEMET or
  met.no Frost is no longer answered by doubling the request rate against a provider that has just
  said it is rate-limiting. AEMET's own retry loop, which waits properly between attempts, is what
  clears that one, and it now sees the 429 after one request rather than two. A missing file is
  still asked for twice, a file index being read minutes before the files it names. GH-1939

- The three paths that do not go through the provider registry say which extra they want, where
  they used to raise a bare `ModuleNotFoundError`: `wetterdienst restapi` without `[restapi]`,
  `.interpolate()` without `[interpolation]`, and the radar HDF5 dump without `[radar]`. Each names
  the package and the command that installs it, as the plotting helpers already did. Where several
  extras install the same package -- `h5py` belongs to both `knmi` and `radar` -- the caller's own
  is the one named, and only where the metadata agrees that it installs it, so a renamed extra
  falls back to what is actually there rather than to a wrong instruction. GH-1938

- A provider that cannot be loaded says which package it is missing. `importlib` raises
  `ModuleNotFoundError` for an absent *dependency* of a module just as readily as for an absent
  module, and `Wetterdienst.resolve` rewrote both into `Module wetterdienst.provider.X not found` --
  so a reader went looking for a provider that was in fact right there, while the package they
  needed went unnamed. The two are now told apart by the name the exception carries, and where an
  extra of this package would install it, the message says which: `pip install wetterdienst[knmi]`.
  The extras are read out of the installed metadata rather than from a list kept in the code, so one
  that gains or loses a package cannot leave a wrong instruction behind, and nothing is suggested
  for a package that belongs to no extra. GH-1929

- Met Office works on a plain `pip install wetterdienst`. Its CEDA token exchange imported `httpx`
  at module level, but `httpx` was declared only by the `restapi` extra and nothing pulls it in
  transitively, so `Wetterdienst("metoffice", "observation")` raised on an installation that had
  not asked for the REST API -- reported as `Module wetterdienst.provider.metoffice.observation not
  found`, since the registry rewrites a `ModuleNotFoundError` and drops the name of what was
  actually missing. The exchange now goes through fsspec's HTTP filesystem like every other request
  the package makes, by way of a new `post_file` in `util/network.py`: the download path could not
  serve it, being a GET through a caching filesystem where a token mint is a POST whose answer must
  never be cached. `httpx` is no longer a dependency of wetterdienst at all -- the REST API never
  imported it, and starlette's test client has moved to `httpx2`. The basic-auth header is written
  by hand rather than through aiohttp's `BasicAuth`, which is deprecated for removal in aiohttp 4,
  and is sent per request so credentials never reach `client_kwargs`, which is hashed into the
  filesystem cache key. A failed exchange is a `File` carrying the exception whichever way it
  failed, the base `ClientError` being caught rather than a list of its subclasses: fsspec holds one
  session and its keep-alive pool for the life of the process while a token is minted days apart, so
  a mint can be handed a connection the server closed hours ago. That one is retried once, where a
  response that did arrive -- a 401 among them -- is an answer and is not. A redirect is not
  followed either: aiohttp would repeat a redirected POST as a GET, turning CEDA's login page into a
  200 whose body parses as nothing, where the 302 says plainly what happened. GH-1929

- The MCP server tells a client which wetterdienst it is talking to. `FastMCP(version=...)` was
  never set, and left unset it reports the installed FastMCP release as the server's own version --
  so a client asking what it had connected to was answered "Wetterdienst 4.0.3". It now answers
  with wetterdienst's version, the same one `GET /api/version` gives

### Security

- Provider credentials are held as `SecretStr`, so that rendering the settings does not print them.
  `Settings.__repr__` and `__str__` serialise the whole model, `auth` included, and a request's
  dataclass repr embeds a `Settings` -- so an API key reached every ordinary way of looking at an
  object on a failure path: a pytest assertion diff, an unhandled traceback, `print(request)`, a
  debugger, a notebook. Nothing logs a `Settings` in normal operation, which is what kept this out
  of sight; what it costs is that anyone pasting such a traceback into an issue, a chat or a CI log
  published every credential they had configured. All four -- AEMET, KNMI, met.no Frost and CEDA --
  now render as `**********`, and `reveal()` is the one way back to a value, called where the
  credential is actually sent. The Met Office token cache is keyed by the secrets themselves rather
  than by what they hold, so it is not somewhere the pair sits in plain text either. GH-1920

- A failed request that carried its credential in a header of another name has that header redacted
  too. The scrubbing added above knew `Authorization`, which is where KNMI's key, met.no Frost's
  basic auth and Met Office's bearer token go -- but AEMET sends its key as `api_key`, leaving the
  one provider with a header of its own the only one whose key still reached a traceback and
  stamina's retry log

- `httpx2` now has a floor of `>=2.12` wherever it is declared -- the dev group, which held
  `>=2.4.0`, and the `mcp` extra, which now declares it -- and the lockfile carries 2.13.0 where it
  held 2.10.0. Six advisories stand against 2.10.0: multipart part header injection through an
  unvalidated file `Content-Type` (CVE-2026-84379, fixed in 2.11.0), conflicting `Content-Length`
  and `Transfer-Encoding` headers being generated together (CVE-2026-84380, 2.11.0), and unbounded
  peak memory when decompressing a streamed response (CVE-2026-84382, 2.12.0). `uv audit` has
  failed on `main` since 2026-09-16 on exactly these, and passes again

- A credential no longer travels in the error a failed download hands back. KNMI sends its API key,
  met.no Frost its basic auth and Met Office its bearer token as an `Authorization` header, and
  aiohttp hangs the request's headers on a `ClientResponseError` -- and on its `args`, which is what
  a `repr` renders -- so the key reached anything that rendered the `File` the download returned.
  It travelled three further ways. The traceback's frames in `util/network.py` hold the caller's
  client kwargs as locals, which is what `pytest --showlocals` prints and what an error reporter
  capturing frame locals sends. `ClientResponseError.history` holds the responses a redirect chain
  passed through, each with its own copy of the header -- the shape a login-page redirect takes.
  And `stamina`'s retry hook logs a `repr` of what failed on the first failure of every retried
  download, rendering the request info before any of this could redact it. None of the four shows
  in `str(error)`, which is what made them easy to miss. The header is now redacted, the history
  and the traceback dropped, and the error scrubbed on its way into the retry as well as out of it
  -- for a request that carried credentials and only for one, an ordinary 404's traceback being
  worth more than it costs. An aiohttp failure that is none of the named ones, a dropped connection
  among them, is answered with a `File` rather than raised through the caller, so it cannot leave
  by way of a traceback either. The token exchange added below is held to the same rule, its own
  frames holding the header and its encoding

## [0.137.0] - 2026-09-18

### Added

- DWD road: a sensor that has stopped is marked suspect. Where an air temperature, a dew point or a
  road surface temperature reports the identical value for 24 readings -- six hours at this
  resolution -- `quality` becomes `1` and the reading is left exactly as DWD published it. The
  threshold is measured rather than chosen: over a day of five station groups and around 700
  stations per quantity, a working sensor's longest run of one value was 14 readings for the air
  temperature, 17 for the dew point and 9 for the road surface, where a broken one held its value
  for 86 to 96 of the day's 96 and reported a single distinct value for the whole day. Only those
  three quantities, because only for those is standing still a fault -- the road surface condition
  and the water film sit at 0 for the whole of a dry day, as does the precipitation type, the
  humidity saturates in fog and the wind falls calm, and a 24-reading rule applied to those would
  have called 547 of 571 stations' surface condition a fault. It adds 12 sensors across the five
  groups that DWD's own flag does not name. This is also what the exact `-75.00`, `-30.00` and
  `-25.00` readings are -- sensors that have stopped, not a sentinel value to recognise, and
  matching them by value would have been worse than useless since -25 and -30 are both reachable in
  a German winter. What it cannot catch is a sensor that moves and is wrong: the difference from a
  station's own air temperature does not separate those, stations with no sign of a fault reaching
  42.0 K above their air where one that is certainly broken sits between 31.8 and 38.9. A run ends
  where the readings stop for more than four times the station's own usual interval, so two
  three-hour plateaus either side of a three-day outage are not a six-hour one -- against the
  station's own cadence rather than a fixed number of minutes, no fixed one separating them when
  99.5% of this network's intervals are its quarter hour and the tail reaches 405. The run is
  counted in readings, so a station publishing on another interval is neither exempt nor tripped
  early. And a road surface at its
  melting point is exempt where the station's own air came near freezing: melting ice holds a road
  at 0.00 C for hours, which is what this network is for, and only the air tells that from a sensor
  stopped at zero -- FN/P717 reads 0.00 all day while its own air reaches 26 C. Within 10 C of
  freezing either side -- brine pinning a road no better at -20 than ice does at +26 -- an ordinary
  thaw running to +6 or +10 with snow still lying -- and not only at 0.00 C,
  German roads being salted and brine depressing the freezing point, so a treated road in the same
  thaw sits at a constant sub-zero value by the same physics. The run must cover the hours as well
  as the readings, the count having been measured at this network's quarter hour, so a station
  reporting more often does not trip on less evidence than that. The question is asked of
  the readings rather than of the rows throughout: a station-minute arriving in two files is one
  minute, where counting it twice put a zero among the intervals and so a zero in their median,
  which ended a run at every reading and answered that nothing anywhere had stopped; and a row
  saying null is the same dropout as a row that never arrived, where reading it as a value ended
  runs an absent row was allowed to span. GH-1917
- DWD road: the `quality` column carries the station's own verdict on its sensors, where it was
  null on every road reading. Each subset ends with `qualityInformationAwsData` (BUFR `0 33 005`), a
  30-bit flag naming which of the station's quantities are suspect, and it was read and thrown away.
  A reading is now `1` where the station checked it and calls it suspect, `0` where it checked and
  does not, and null where nothing is known -- which is the common case rather than the exception,
  817 of 1199 station-minutes measured reporting "no automated meteorological data checks performed"
  and 40 carrying no flag at all. Null and not `0`, those saying the station did not look rather
  than that it looked and was satisfied. Bit 7, "ground temperature data suspect", is the one this
  was verified against: the four stations carrying it in a network-wide file are exactly the four
  whose road surface temperature is impossible -- 65.6 C, 57.8 C, -0.7 C and 0.0 C against an air
  temperature near 12 C -- and no station within 5 K of its own air temperature carries it. The
  other bits follow the flag table's own wording. `road_surface_condition` is left null: the table
  is the WMO's generic one for an automatic weather station and names no state of a road, its
  nearest neighbour being about bare earth, so a reading with nothing to say about it gets a null
  rather than a guess -- and `water_film_thickness` is left null for the same reason, "water
  content" in a generic automatic weather station being the moisture in the ground. Bit 7 is
  mapped because the data confirms that reading of it, not because its wording is close, and
  nothing confirms those two: bit 19 is set nowhere at all, and the stations setting bit 21
  reported the same film as everyone else. A wrong `0` would be worse than a null, telling a
  caller filtering on quality that a suspect reading had been checked and found sound. A parameter
  the station did not report is left null rather than answered 0 as well: one verdict covers the
  station, and a clean bill of health says nothing whatever about the quantities it does not
  measure -- and neither is a flag carrying only the table's own missing marker, the top bit of a
  30-bit flag table, which read as a verdict said the station had checked and was satisfied. The
  numbers are this network's own: `quality` carries whatever a source publishes and the scale
  differs by provider, DWD observation putting `qn` codes there where a larger number means a more
  thorough check, so the canonical description of the column says so now rather than promising one
  meaning. GH-1917
- Export: `file://` targets for `.json`, `.jsonl` and `.nc`. JSON could not be written to a file
  at all; it holds the frame's records, with a list of station ids kept as a list since JSON has
  arrays, rather than the `{"metadata": ..., "values": [...]}` envelope a response carries. JSON
  Lines is the same records one per line, for reading as a stream. NetCDF joins Zarr as the second
  array format, written through xarray with its timestamps as CF units, its gaps as NaN rather
  than the -999 Zarr fills them with, and grouped by the datasets the frame holds. The `export`
  extra carries `h5netcdf`, the engine xarray writes NetCDF with that needs no compiled netCDF
  library
- Interpolation and summary take an `elevation` for the point they answer for, in metres above sea
  level, and bring each station's readings to it before using them. Air temperature falls about
  0.65 K per 100 m and a dew point about 0.2, so a valley station and a summit one say different
  things about the same weather -- around Garmisch the stations within 40 km span 630 m to 2956 m,
  which is 15 K interpolated as though it were horizontal structure, and even the flat country
  around Frankfurt spans 495 m, or 3.2 K. Named as `interpolate(latlon=..., elevation=1500)`, as
  `--elevation` on the CLI and as `elevation` on the REST API. The
  elevation names the point too: two elevations at one place are two answers, and they no longer
  share a station id. A station whose own height the provider does not report is left out of
  an answer about an elevation rather than contributing at its own altitude while its neighbours
  are moved -- thirteen providers have such stations, every one of FMI's, IPMA's and the
  Environment Agency's among them. Where that leaves a parameter with no station at all, the
  request is refused rather than answered empty: `NoStationsWithHeightError` names it and how to
  ask for the readings as they came, which the REST API reports as a 400 and the CLI as a message
  rather than a traceback. Where every quantity asked for falls with height and no station near
  the point reports one, that is settled off the station list without downloading a reading. A
  parameter that kept some stations and still answered nothing is named in the log instead, the
  rest of the result standing: whether the stations it lost would have completed the four an
  interpolation wants is not something a count can say, and the readings that are there stay with
  the caller. Whether a parameter
  was answered is read off the finished frame rather than off the stations collected for it, those
  being different questions -- and the exclusions are named as the reason only where the stations
  they took would have made up what the calculation needs, a parameter that was short of stations
  either way having failed on something an elevation has nothing to do with. Left out, the
  elevation corrects nothing and the result is what it was before: an elevation taken from the
  interpolation itself cancels out of it exactly, so the correction is only possible when a caller
  says where the point is
- Parameter table: `lapse_rate` says how fast a quantity falls with height, in its own unit per
  metre, for the 17 air temperatures measured at 2 m and the dew point. Not for the 5 and 10 cm
  readings -- the grass minimum and its kin -- which are made in the air but governed by the
  ground radiating beneath them. Not for anything measured in or on the
  ground -- soil, concrete, the surface -- which follows the ground rather than the air, nor for
  the comfort indices, nor for pressure, which falls exponentially and wants the barometric
  formula rather than a linear rate

### Changed

- DWD road: the precipitation type is reported as `precipitation_type_flags` rather than
  `precipitation_form`, being a different kind of number. `precipitationType` is BUFR `0 20 021`, a
  30-bit *flag* table with a bit per type of precipitation, where `precipitation_form` everywhere
  else in this library holds a single code from a table of its own -- DWD observation's `wrtr`,
  documented as 0 for no precipitation and 6 for liquid. So rain came back from the road network as
  `33554432`, bit 5 of a 30-bit field, against `wrtr`'s `6` for the same weather, under one
  canonical name. The value is unchanged and still what DWD publishes; what changes is that it no
  longer claims to be comparable with a code it shares nothing with. Decoding it into `wrtr`
  instead would need a correspondence DWD has not published -- the flag table's twenty types would
  have to collapse onto liquid, solid and unknown, and the freezing and depositional ones, glaze
  and rime and clear ice, have no home there at all, which on a road weather network is the
  distinction most worth keeping. The bit layout and how to mask for a type are on the provider's
  docs page. GH-1916
- Dependencies: the `bufr` extra is the whole of what reading BUFR takes. pdbufr requires eccodes,
  but asks for any version at all, and the two were named as separate extras with the docs telling
  you to install both -- neither being any use without the other. The floor is the oldest release
  published as a wheel, named in both extras so that it binds for anyone installing
  `wetterdienst[bufr]` and not only inside this repository's lockfile. It stood at 1.5.2, a 2023
  source tarball, which the minimum-versions job -- resolving every direct dependency to its floor,
  across extras -- had to build, and continues on error if it cannot. It is raised only that far on
  purpose: nothing here needs eccodes 2.x, so an install pinned to 1.x keeps resolving. `pybufrkit`
  is no longer pulled in by `bufr`: nothing in the library imports it, only the radar tests do, and
  they skip on it now rather than failing to collect without it
- Interpolation and summary by station id answer at that station's altitude. Naming a point by a
  station names its height as well, and it is the one case where the elevation is known without
  being given, so `interpolate_by_station_id` and `summarize_by_station_id` correct the quantities
  that fall with height to it. **This changes what those two calls return** where the stations
  drawn on stand at other altitudes -- for the reading uncorrected, pass the station's coordinates
  to `interpolate` or `summarize` instead
- REST API: `/api/summarize` answers a window that ends before it starts with a 400 rather than a
  404, as `/api/interpolate` already did. Both endpoints decide that from one place now, so the
  status a failure carries no longer depends on which of the two it came through
- Dependencies: shapely is required from 2.0.6 rather than 2.0.4. The two releases before it raise
  out of `create_collection` when a geometry is built from coordinates under numpy 2, which is what
  every other dependency here resolves to, so the floor named a combination that does not work

### Fixed

- DWD road: a station group is read once for a request rather than once per station of it. A road
  file holds a whole group where the collection above asks for one station at a time, so every file
  of a group was decoded and built into a frame once per station and all but that station's rows
  thrown away -- three stations of one group over two hours parsed nine files twenty-seven times.
  The files themselves came from the cache; what repeated was the BUFR decode, which is the
  expensive half. The group parsed for the previous station is kept, and one group rather than all
  of them: stations arrive in group order, 1653 of them across 19 groups changing group 21 times,
  so holding the last is worth almost exactly what holding every one would be -- 22 reads against
  19 -- and it bounds what is held to a single group's readings, a month of which is some thirteen
  million rows. Measured on those three stations, 27 parses became 9. GH-1922
- DWD road: a subset that names no station or no minute is one reading lost rather than a file.
  The read is required of nothing but its own structure now, so such a subset arrives like any
  other -- and one null minute makes the whole of pandas' column a float, where 2026 written as
  "2026.0" took the timestamp of every station in the file with it. The keys go through an integer
  on the way to a string, a key at a rank other than the first is read where it actually is, and a
  reading with no station or no minute is dropped
- DWD road: a station with two road sensors is read as having two, and a reading is one sensor's.
  The sensors are a delayed replication inside the station's subset -- `1 09 000` and `0 31 001`
  wrapping the surface temperature, the sub-surface temperatures at their depths, the water film
  and the surface condition -- so the rank on the key names the sensor, where
  `positionOfRoadSensors` reads 0 or missing in all 1199 subsets measured and names nothing. The
  file is read flat to keep it. Only what is inside that replication can arrive twice: of the
  fourteen parameters this dataset maps, three do, and the other eleven -- the air temperature and
  dew point and humidity and visibility, the wind and the precipitation -- come once per station,
  so a row can never hold one sensor's air temperature beside another's road surface. Where two
  sensors report the same quantity they are measuring one road at two points, and they mostly agree
  closely: of 75 stations whose sensors both reported a surface temperature the median disagreement
  was 0.3 K and 97 in 100 sat inside 3 K, so which sensor answers rarely changes the reading. Two of
  the 75 did not, at 22 K and 18 K, and both were a broken sensor rather than a road -- one stuck at
  273.14 K for a day of readings, the other 22 K hot with a normal daily swing. Everything contested
  is taken from the one sensor reporting most of it, so the row is a road rather than an average of
  two, and what is dropped is named in the log at debug -- per file and routine, where the CLI logs
  at info and a month of road data would be thousands of lines. A quantity the chosen sensor does
  not report at all is taken from one that does rather than dropped -- with three sensors the one
  answering a row's contests need not carry every contested quantity, and there is nothing of its
  own for that reading to have been paired against. Where two sensors settle as many contests as
  each other, the one that reported more altogether answers the row, so that a row is wholly one
  sensor's wherever a sensor could supply the whole of it. Which sensor answers a wild
  disagreement is the rank order and nothing better: this library does not judge a reading's
  plausibility here any more than anywhere else. Where two sensors report different quantities they are one
  installation and both are kept: that is the whole of the DD group, whose first sensor carries the
  surface temperature and second the surface condition for 24 of its 25 stations, and answering
  such a row from one sensor would drop the other quantity for nothing. GH-1908
- DWD road: a station's reading is kept whole where it arrives in parts. A road file holds one
  subset per station carrying the descriptors that station has, and `read_bufr` emits an
  observation only where every column asked for is present -- its default, and ours. Asking for
  all fourteen parameters of the dataset and keeping only the complete observations threw away
  every reading of anything not universally fitted: against a file of the DD group the parse
  returned 105 values where the file held 121, the whole of `roadSurfaceTemperature` among the
  missing, on a road weather network. The file is read flat instead -- every key it holds, named by
  its rank -- which is one row per subset and so one row per station and minute, with no column
  list for a descriptor to fall out of. A parameter no subset in the file carries comes back as a
  null column rather than as no column at all
- DWD road: a listing entry is a file when it carries the timestamp the file index reads it by.
  Two entries never do. The listing of a group that exists and holds nothing is the group itself,
  which made the listing non-empty, so `No files found` never said so and a request without dates
  downloaded the directory and handed it to the reader as a BUFR message; and each family a group
  publishes under keeps a `LATEST` alias duplicating its newest file, which a request without
  dates parsed a second time. Both are dropped now. The timestamp is read leniently and from the
  ten digits the format takes, where the pattern used to match a longer run and raise out of the
  file index on a match that would not parse -- taking the request with it, while an entry that
  never matched was simply dropped. A name that is neither a file nor one of those two is one the
  index cannot read, and it is said: a group publishing under two families, as FN does, would
  otherwise lose half its readings to a rename of one of them as quietly as it drops the alias
- DWD road: a file that decodes to nothing is nothing rather than a broken frame. The empty files
  of GH-1526 are turned away by their exact length, which is a guess at a shape rather than a
  reading of one, so a file holding no subsets at some other length reached the parse -- where the
  merge of the two column batches raised `KeyError: 'year'` and the select after it would have
  raised for a column that was not there. A file with no subsets in it, or with no station named in
  them, is now answered in the shape the files that hold readings come back in, so it concatenates
  with them and needs no handling of its own. It says so in the log, at the level its neighbour
  uses for a group that published no file at all
- DWD road: having nothing to answer with is one shape. There were three -- no columns where the
  group published no file, five where the files it published held nothing, and the seven a reading
  has -- handed to a caller that reads the first as "this station had nothing" and would meet
  either of the others with a width it did not expect or a column that is not there. A frame of no
  readings carries the columns a reading does, so the filter has a station id to look for and one
  line answers for the empty case and the populated one alike
- DWD road: a station group with no usable file is an empty result rather than a broken frame.
  The stations report in fifteen-minute batches and four groups are already known to go quiet, so
  a window with no file behind it -- or one holding only the 142-byte empty files of GH-1526 -- is
  an ordinary outcome. The frame standing for "nothing here" carries no columns, and it was
  filtered for a station id before anyone asked whether it held anything, so the collection walk
  raised `ColumnNotFoundError: unable to find column "station_id"; valid columns: []` from its
  middle. It is handed back instead, which is what the rest of the library already reads as "this
  station had nothing". This is what failed `test_pdbufr_examples` on every CI job
- REST API: a BUFR reader missing on the server answers 501 rather than 400. The blanket handler
  read every failure as the caller's, so a deployment installed without the `bufr` extra told the
  client to `pip install wetterdienst[bufr]` on a machine they do not administer, for a request
  that was perfectly well formed -- and `interpolate` and `summarize` called the same thing a 404,
  which reads as "no such network". The install line moves to the server log, where whoever runs
  the instance can act on it
- CI: the test and coverage workflows watch `examples/**`. `tests/examples` runs those files, so a
  change to one is a change both suites cover -- and a pull request touching only an example ran
  neither, while the coverage workflow's header said it takes the same inputs as the test matrix
- BUFR: one question, asked in one place. Reading BUFR takes two halves that fail apart -- pdbufr,
  which reads the messages, and eccodes, the binding to the library that decodes them -- and no
  caller cares which is missing. The codebase asked it four ways, one of them wrong:
  `not ensure_eccodes() and not ensure_pdbufr()` skips only when *both* are missing, so with
  eccodes installed and pdbufr not, the case a skip exists for, tests ran and died on the import --
  and would now error earlier still, `require_bufr` refusing at the request. The four spellings are
  one question now: `bufr_is_available` where an answer will do, `require_bufr` where it has to
  come early, and one `BUFR_AVAILABLE` for the tests that skip on it
- DWD road: a missing BUFR reader is refused at the request rather than at the parse. The values
  class called `ensure_pdbufr()` and threw the answer away, so it guarded nothing: the request went
  through and a bare `ImportError` came back out of the middle of a parse instead
- CLI: a missing optional reader is reported rather than raised. `values`, `interpolate` and
  `summarize` caught `ValueError`, and the `ImportError` naming the extra to install is not one, so
  the sentence saying what to do arrived as the last line of a traceback. The three share one
  handler now, which reports that, a request the provider cannot serve as phrased, and a window
  holding no readings -- the three failures a caller can act on rather than debug. The refusal has
  a type of its own, `BufrReaderMissingError`, so reporting it does not mean reporting every import
  failure that way: a cycle or a typo inside a provider module is a defect and keeps its traceback
- BUFR: asking whether this environment can read BUFR answers, whatever the import does. Each
  probe had a hole of its own: `ensure_eccodes` caught `ModuleNotFoundError` and `RuntimeError`
  but not the plain `ImportError` an eccodes with no compiled library behind it raises, and
  `ensure_pdbufr` caught `ImportError` but re-raised a `RuntimeError` whose message did not say
  "Cannot find the ecCodes library" -- gribapi's phrasing of the day, and no promise. Naming what
  had been seen would have left the next one out in turn, so the catch is anything at all: the
  question is asked from a radar path documented to log and carry on rather than fail a query, and
  from a constant the test suite computes while collecting, where a raise ends the collection
  instead of skipping the tests that want a reader
- BUFR: a reader that is installed and does not work says why, including when it fails as a
  `ModuleNotFoundError` from inside itself -- `No module named 'gribapi.bindings'` is a broken
  install and not an absent one, and reading it as absence hands the caller advice to install what
  they have
- CLI: an empty window is reported once. `get_values` logged "No data available for given
  constraints" and handed the empty frame back, and the CLI logged the identical line again before
  exiting, so a single empty result read as two. Reporting it belongs to the caller -- the CLI says
  it and exits, the REST API returns the empty result -- and the library still notes it at info
  level on the way out of `.all()`
- Interpolation: four stations that surround the target point are a valid group however they are
  ordered. The check drew a polygon through them in the order they are held -- by distance from
  the point, which says nothing about the order around it -- so roughly half of all groups
  described a self-intersecting shape, where `covers` is undefined. Around the point the tests
  interpolate for, 11676 of the 37415 groups that do surround it were rejected, a third of them,
  leaving the interpolation to fall back on more distant stations or to answer nothing at all
  where the leading groups had no data for a timestamp. The convex hull decides now, which is also
  the region `LinearNDInterpolator` can answer for, so a group that passes is one the
  interpolation can use. No interpolated value in the test suite changes: the nearest four are
  accepted either way, and what returns are the groups behind them
- Interpolation: whether four stations surrounding the point exist is answered from the hull of
  all of them rather than by enumerating groups. It is asked once per station collected and the
  groups themselves are not wanted there, while enumerating them costs C(N,4) hulls -- 91390 of
  them for the 40 stations a wide radius reaches, seconds per station, against 0.2 ms for the one
  hull. A request whose parameters never fill up, which is what walks every station in range, is
  the case that paid it
- Interpolation: stations that do not span a triangle are no group. A hull with no width -- four
  stations on a line, or several in one place -- still covers a point lying on it, so such a set
  counted as a valid group, which is what stops the collection of further stations: a set that
  cannot be interpolated at all could end a search that would have found one that can
- Interpolation: four stations on a line come back without a value rather than raising. Their hull
  is a line, which covers a point lying on it, so such a group reaches the interpolator -- where
  scipy answers with a `QhullError` rather than the NaN the guard above expects
- Interpolation: a point the interpolation has no answer for comes back empty rather than as a
  zero. `LinearNDInterpolator` answers NaN outside the stations it was given, and for the
  quantities that carry an occurrence test -- precipitation, new snow -- `NaN >= 0.5` is False, so
  the NaN was reported as a precipitation of exactly none
- Export: a file target renders what the matching format returns. `to_csv` joined a list of
  station ids into one field and the CSV file target did not, so `--target=file://out.csv` on an
  interpolation or a summary died with `CSV format does not support nested data` where
  `--format=csv` wrote the same data out fine. Zarr failed on the same column, so neither could be
  written to an array store either
- Export: station metadata can be filtered by SQL and written to Zarr, NetCDF or CrateDB. All
  three named the `date` column that a values frame has, while a stations frame carries
  `start_date` and `end_date` and no `date`, so `request.all().filter_by_sql(...)` raised
  `ColumnNotFoundError` and stations reached neither array store nor CrateDB. Every timestamp a
  frame carries is handled now, whichever they are. The CLI's `--sql` went through a second copy
  of the filter on `TimeseriesRequest`, which named those two columns itself and so worked but
  called whatever came back UTC; both run the one filter now
- Unit conversion: the mile and the knot are derived from the metres they are defined as, rather
  than from decimals rounded to four figures. `1.609` put kilometre to mile 0.0214% away from the
  metre-to-mile route, `1.151` did the same to the mile and the nautical mile -- the nautical mile
  itself was already exact against metres and kilometres, and only its ratio to the mile moves --
  and `1.944` left knots to metres per second 0.0080% from its kilometres-per-hour route, so
  the same quantity converted differently depending on which unit its source published. That last
  one is on real data: the Met Office publishes wind in knots and the speed target is metres per
  second, so every one of its wind speeds carried the error. A round trip hid all three, both
  directions sharing the rounding, so the tests now check that a conversion agrees whichever route
  it takes

## [0.136.0] - 2026-09-04

### Added

- DWD: new `poi` network (`dwd/poi`) covering DWD's POI ("Point Of Interest") current weather
  reports -- the hourly observations of roughly the last day, published as one
  `<station_id>-BEOB.csv` per station under `weather_reports/poi/`. 39 parameters at `hourly`
  resolution and the `now` period: temperature (2 m and 5 cm), dew point, humidity, sea-level
  pressure, wind and gusts, precipitation over the last 1/3/6/12/24 hours, cloud cover and base,
  visibility, sunshine, snow depth, the coded present and past weather, and the previous day's
  temperature and wind extremes. This is the observed counterpart to `dwd/mosmix`: the two share
  the MOSMIX station catalogue, so a station keeps one id across both and a forecast can be
  compared against what was measured. About 970 of the catalogue's ~5600 stations report, in
  Germany and abroad. Two of the file's 41 columns are left unmapped -- the 24-hour global and
  direct radiation. Both are declared W/m2, which a 24-hour figure cannot be; measured against the
  daily total the hourly column adds up to (itself confirmed against DWD's own 10-minute solar
  data), the 24-hour column comes out proportional with a factor of 1.573 over 29 stations, i.e. a
  real daily total in a unit of ~0.636 MJ/m2 per count that matches nothing the converter knows.
  Sum the hourly column for a daily total

### Changed

- Parameter parsing: a parameter the provider does not have is now logged as a warning naming what
  did not match -- resolution, dataset or parameter -- with the closest name as a "did you mean"
  and the names that would have matched, where it used to be an `info` line saying only that the
  parameter was not found. Half a request silently resolving to less data than was asked for is
  otherwise invisible. `NoParametersFoundError` names the request and the provider too
- Parameter parsing: the parts of a parameter must be strings. A tuple mixing in an enum member,
  `(Resolution.DAILY, "kl")`, now raises a `TypeError` naming the accepted forms instead of an
  `AttributeError` from deep inside the parser
- Lookups on the metadata models (`metadata["daily"]["kl"]`, `metadata.daily.kl`) match the
  source's own name case-insensitively, as looking a parameter up by its `name_original` already
  did in a request, and suggest the closest name when nothing matches
- Provider metadata: `MetadataModel` carries the name it was built with as a `name` field, where
  it used to be stashed on the model's `__name__`. Read `DwdObservationMetadata.name` instead of
  `DwdObservationMetadata.__name__`
- Periods: `periods` is an argument of every request rather than of the three that hand-rolled it,
  and is resolved against the periods the requested datasets declare in the metadata. A dataset
  published under a single period has nothing to choose between, so asking for that period is
  answered and asking for another one raises `NoPeriodsFoundError` naming what is available.
  Left out, the periods are still derived from `start_date`/`end_date` where the provider has a
  release schedule to derive them from -- DWD observation and DWD phenology -- and are otherwise
  every period the requested datasets publish, which for a request naming one dataset is narrower
  than the provider-wide set it used to be. `TimeseriesRequest.available_periods()` reports the
  provider's periods; the per-provider `_available_periods` class attributes it replaces were an
  exact copy of what the metadata already said
- Periods: narrowing the periods of a provider that does not read its data per period -- SMHI,
  MeteoSwiss, met.no Frost and Meteo-France observation declare datasets with more than one period
  but fetch all of them by design -- is logged as a warning saying the request was not narrowed,
  rather than answered with everything in silence

### Fixed

- Interpolation and summarization: a result that came back with no rows is a feature collection
  with no values rather than an `OutOfBoundsError`. The feature's id was read out of the frame's
  first row, so a point and window no station covers -- an ordinary outcome, and one the REST API
  serves as `format=geojson` -- raised `gather indices are out of bounds` from `to_geojson` and
  `to_ogc_feature_collection`, where `to_dict` on the same result answered fine. The id belongs to
  the point rather than to any row: it is the name beside it hashed, which is how the
  interpolation builds it in the first place
- Plots: a parameter is labelled with the unit its values are actually written in. The label
  mapping was keyed on the canonical parameter name alone, while a frame carries `name_original`
  unless `ts_humanize` is on, so nothing matched and the label repeated the name -- `sd_10
  (sd_10)`. The symbol was also always the target unit's, though `ts_convert_units=False` leaves
  the values as the source published them: `10_minutes/solar/sunshine_duration` comes in hours and
  was labelled seconds, a factor of 3600 between the number and its unit. The mapping is keyed by
  resolution and dataset as well as name, since a canonical name is only unique within its dataset
  -- DWD publishes `sunshine_duration` in hours at 10 minutes and in minutes at an hour, and one
  would otherwise have labelled the other. Both affected the value, interpolation and summary
  plots, and the images exported from them
- Dates: a date string covers everything it names instead of only the instant it starts with.
  `2020-05` is the month of May, `2020` the year, and `2020-05-01` a whole day -- which for
  anything measured more often than daily is 24 hours of readings rather than the one at midnight.
  Every one of these formats is documented as supported, and `filter_by_date` matched a single
  date with `==`, so a month or a year of hourly data came back empty: no reading falls exactly on
  the 1st at 00:00. An interval ran to the *first* instant of the span its second half names, so
  `2017-01/2019-12` ended on the 1st of December 2019 and `2010/2020` dropped all of 2020. The
  same reading of the string reached the CLI and REST API, where `--date=2019-12` asked for
  December and got a window of one instant. A date carrying a time still names one instant and is
  matched exactly, however it is written -- `2020-05-01T12`, `2020-05-01t12` or `2020-05-01 12:00`
- Parameter parsing: parameters requested more than once -- a dataset and one of its parameters,
  or the same dataset twice -- are returned once instead of being queried and returned per mention
- Parameter parsing: an iterator of parameters no longer parses as empty. It was consumed by the
  checks that tell `("daily", "kl")` apart from `["daily/kl", "daily/solar"]`
- Parameter parsing: a quality flag requested by name (`daily/kl/quality_wind`) says that quality
  flags come back in the `quality` column next to their parameter, where it used to be dropped as
  if it did not exist. Requesting one as a `ParameterModel` was dropped the same way
- Provider metadata: a misspelled key in a metadata declaration is rejected instead of dropped.
  Only `ParameterModel` forbade extra keys, so `date_requiered` or `grupped` anywhere else was
  silently ignored and the declaration fell back to a default -- a dataset quietly inheriting its
  resolution's `date_required`. Every existing declaration passes unchanged
- Provider metadata: an invalid `periods` or `date_required` on a resolution is reported as the
  validation error it is, naming the value that is wrong, where the validator that cascades those
  two fields down to the datasets used to turn it into a bare `KeyError('periods')`
- CI: the Coolify deploy step has failed on every run since 2026-08-17, so no release or nightly
  has reached the live deployment since. Coolify moved `/api/v1/deploy` from GET to POST and left
  the GET route pointing at a stub that answers `405 This endpoint has changed to a POST request.`,
  which `curl --fail` turned into an exit 22 after the images had already been built and pushed.
  Both deploy calls now use POST. The images were never the problem -- every run pushed its
  manifest and passed `Inspect image` before dying on the last step
- Ranked station values: a station whose record lies entirely outside the requested window no
  longer counts against the station count of `filter_by_rank`. It was checked for data before the
  window was cut and never again after, so it spent one of the ranked slots on an empty frame and
  the walk stopped short of the stations that do cover the window -- a request for a window only
  the more distant stations reach came back with nothing, which reads exactly like no data
  existing at all
- Interpolation and summarization: the values of one station are no longer read together with
  another station's coordinates and distance. Both walks paired the distance-sorted stations frame
  against the values generator by position, but that frame carries a row per station *and* dataset
  while the generator yields one result per station and passes over those that returned nothing,
  so any gap shifted every station after it onto its neighbour's location
- Values: a request that collected nothing returns an empty frame carrying its columns rather than
  one with no columns at all, which wrote an empty file where a header was meant and raised
  `ColumnNotFoundError` from `get_column("date")`. The columns are the ones a populated frame
  would have had, dataset prefixes and all, in whichever shape was asked for. Having no data for
  the constraints given is an ordinary outcome, so it is no longer logged with an exception
  traceback either
- Values: a ranked request no longer reads the whole provider to answer for a window that predates
  it. A station returning nothing inside the window rightly does not count towards `rank`, but
  then nothing bounded the walk either, so a window no station covers read every station there is.
  A station the index says began after the window ended is now skipped without being downloaded.
  Only that direction is read from the index: a station still reporting carries an `end_date` a
  little behind the readings it can already answer for
- Periods: a period no requested dataset publishes is no longer silently turned into *every*
  period. `DwdObservationRequest(parameters=["daily/kl"], periods="future")` intersected the
  request with the available periods, and the empty result then read as "no periods requested", so
  asking for a period that does not exist returned more data than asking for one that does. It
  raises `NoPeriodsFoundError` now, and a period dropped from a request that keeps others is
  logged as a warning naming it
- Periods: `periods` reaches providers that never accepted the argument. It was a per-provider
  constructor field, so `NoaaGhcnRequest(..., periods="historical")` was a `TypeError`, and the
  CLI's `--periods` and the REST API's `periods` were dropped for every provider but DWD
  observation, derived and phenology -- including met.no Frost, whose datasets are published under
  both `historical` and `recent`
- Periods: a period derived from `start_date`/`end_date` is checked against the datasets like a
  requested one is. An interval reaching into today derives `now`, which `daily/kl` has no release
  for, and the request then read no station index at all -- `DwdObservationRequest` for today's
  `daily/kl` reported *no stations*, where asking for `periods="now"` outright raises for the same
  datasets. Where the interval reaches past the newest release a dataset has, that release answers
  for it
- Periods: an explicit period is answered for a dataset published under a single one. The CLI and
  REST API forwarded `periods` only when some requested dataset had more than one, so asking DWD
  derived for `historical` on `monthly/climate_correction_factor` -- a `recent`-only dataset --
  read every period the provider has instead of reporting that the dataset has no historical
  release
- Values: a dataset named more than once in a request -- interleaved with another, as in
  `["daily/kl/temperature_air_mean_2m", "daily/more_precip/precipitation_height",
  "daily/kl/precipitation_height"]` -- is fetched and parsed once instead of once per run of
  consecutive mentions. The station index of NOAA GHCN, Geosphere and MeteoSwiss gained a
  duplicate row per station the same way


## [0.135.0] - 2026-08-31

### Added

- DWD: new `phenology` network (`dwd/phenology`) covering the DWD phenological observation
  network -- the day of the year on which a plant reached a developmental phase, at `annual`
  resolution, reaching back to 1925. 110 datasets, one per plant and reporter group
  (`annual_common_hazel`, `immediate_winter_wheat`, ...), each carrying the phenological phases
  that plant is observed for as parameters (`phenology_flowering_beginning`,
  `phenology_leaf_unfolding_beginning`, `phenology_harvest`, ...). A value is DWD's `Jultag`, the
  day of the year, dated to the 1st of January of the reference year, so the entry date is that
  date plus the value. Both reporter groups are covered -- the ~6600-station *Jahresmelder* and
  the ~1200-station *Sofortmelder* -- with their own station catalogues

### Removed

- `Resolution.UNDEFINED` and `Period.UNDEFINED`, which no provider declared any more. They were
  what the sources without a stated interval were served under, and the last of those went when
  WSV and Hubeau started reporting the interval each station records at. `undefined` was still
  accepted as a key of `ts_geo_station_distance_resolution_factors`, which validates its keys
  against `Resolution` and was the one place the enum was read as a closed vocabulary, so it was a
  setting that could be written and never read. `Resolution.UNDEFINED` also had no `Frequency`
  member of its own name, which is how `create_date_range` looks the interval up, so anything that
  had reached it would have raised a KeyError rather than being served coarsely. `PeriodType` goes
  with `Period.UNDEFINED`, the only thing that read it, as `ResolutionType` did before it, and
  `Frequency.MINUTE_2` goes too, having named a resolution that never existed.
  `periods="undefined"` now raises `InvalidEnumerationError` where it used to parse and then
  match no dataset, which is the one visible change

### Fixed

- Network: the fsspec listings cache silently never hit for `CacheExpiry.INFINITE`. The expiry
  reaches `FileDirCache` as `False`, which diskcache read as an expiry of `now + False == now`, so
  every entry was stored already expired and each listing was refetched. Falsy expiries now mean
  "never expire", matching what the download-side cache has always done with `INFINITE`
- Network: `FileDirCache` could not be unpickled -- its `__reduce__` passed three positional
  arguments to an `__init__` that takes one positional plus keyword-only arguments, and in the
  wrong order
- Network: a listing whose TTL lapsed between fsspec's `in dircache` probe and the following
  lookup raised a `KeyError` out of `ls()`/`find()`. The dircache is now read with a single
  lookup, which also stops a `detail=False` call from caching a name-only listing that later
  `detail=True` reads would receive
- Network: `download_file()` raised `AttributeError: 'NoneType' object has no attribute 'get'`
  when `client_kwargs` was left at its `None` default
- Network: a float timeout in `fsspec_client_kwargs` (e.g. `WD_FSSPEC_CLIENT_KWARGS='{"timeout": 30.5}'`)
  reached aiohttp unwrapped and failed every request with `ValueError: timeout parameter cannot be of
  <class 'float'> type`; only int timeouts were being wrapped in `ClientTimeout`
- Network: a disabled listings cache created (and `mkdir`-ed) a cache directory named `False`,
  `0.0` or `0.01` that nothing readable was ever written to. Those folders are no longer created,
  and any left behind by an earlier version are swept from the cache directory on the next run --
  guarded so that a folder still holding valid entries is kept
- DWD observation: the `climate_urban` URL was pinned to the `recent` directory whatever period was
  requested, so a `now` request for a 10-minute urban dataset was answered with `recent` data ending
  at the previous midnight, and `historical` -- reaching back to each station's first year, 2015 for
  Berlin-Alexanderplatz -- could not be read at all. The 10-minute urban datasets carry a directory
  per period like the non-urban ones, so the requested period now reaches the URL. The hourly urban
  datasets are unchanged: DWD publishes a single `recent` directory for them that already holds the
  full record, and every period keeps mapping onto it
- DWD observation: `describe_fields()` raised an opaque `.item()` length error for the 10-minute
  urban datasets, for which DWD publishes no description PDF at all; it now names the dataset,
  period and URL it looked at
- DWD observation: station `history` returned nothing for the 10-minute urban datasets. It looked
  for them under a `meta_data` directory that only the non-urban high resolutions have, while the
  urban zips carry their `Metadaten_*.txt` files themselves
- DWD observation: where two periods reported the same timestamp, which record survived was decided
  by neither of the two things that should decide it. The periods were read in the iteration order
  of a set, varying from one interpreter run to the next, and the deduplication then ran over a
  frame that `how="align"` had already reordered by value -- so the surviving record was the lower
  reading, or a null wherever one period was missing a measurement the other had. Values now settle
  on the quality-marked historical record, carried through the concatenation as an explicit rank,
  and stations settle on their most current description. This is visible for the first time on the
  10-minute urban datasets, whose three periods used to resolve to the same directory
- The app's `Resolution` type restates the backend enum, and had drifted both ways: it still
  offered `undefined` and `dynamic`, and had never gained `6_minutes`, which Meteo-France is
  served under. A test now holds the two together, as it does for `Frequency`, whose members are
  looked up by resolution name, and for the interpolation radius factors, which are keyed by
  resolution
- Environment Agency: the whole 15-minute resolution was unreachable. Both `15_minutes/data/discharge`
  and `15_minutes/data/groundwater_level` raised `KeyError` while building the station listing,
  which asked a hand-kept map for the EA measure parameter each wetterdienst parameter is taken
  from and that map still spelled them `discharge_instant` and `groundwater_level_instant`, names
  the metadata had long since dropped. The measure parameter and the period are now read off the
  notation the metadata already declares -- `flow-i-900` is flow measured every 900 seconds -- so
  renaming a parameter cannot separate the two again
- Environment Agency: a station is listed once rather than once per matching measure. The listing
  carries a row per measure, so a station recording two of the requested parameters -- or two
  daily statistics of one of them, which share the parameter and the period the listing reports --
  came back duplicated, and `filter_by_rank` then spent rank on the same station twice
- Environment Agency: 15-minute values arrived empty for every window of the last decade and a
  half. The readings endpoint answers a request that names no window with its default page of
  100_000 readings, oldest first, and reports no truncation; at 15 minutes that page runs out
  after some 2.8 years, so the readings of 2008 to 2011 came back whatever was asked for and the
  post-filter dropped all of them. The window is now asked for, and the page raised to the number
  of readings it can hold, so a long window is not silently cut either. Daily was never affected,
  100_000 daily readings being 274 years, and it also stops a 22 MB download per station

## [0.134.0] - 2026-08-22

### Added

- Add the DWD climate indices as four datasets: `annual`/`climate_indices` and
  `monthly`/`climate_indices` count tropical nights and frost, summer, hot and ice days, while
  `annual`/`precipitation_indices` and `monthly`/`precipitation_indices` count the days reaching
  precipitation heights of 0.1 to 20 mm and snow depths of 1 and 5 cm. DWD derives them from the
  daily observations of the same stations and publishes them in the familiar CDC layout, so they
  arrive as metadata alone. Twelve canonical parameters are new with them, named for the index the
  literature knows (`count_days_frost`, `count_days_tropical_night`) rather than for its threshold,
  which the description carries instead
- The two interpolation search radii are settings of their own:
  `ts_geo_station_distance_homogeneous` (40 km, for a quantity that varies slowly across a region,
  such as air temperature) and `ts_geo_station_distance_heterogeneous` (20 km, for one that
  decorrelates within a few tens of kilometres, such as precipitation). They were module constants,
  so widening the search for everything meant naming all 514 parameters individually in
  `ts_geo_station_distance`, which keeps its role as the per-parameter override. The CLI takes
  them as `--interpolation_station_distance_homogeneous` and `--…_heterogeneous` (`--summary_…`
  for `summarize`) and the REST API as query parameters of the same names. A radius that is not
  given is left out rather than passed as the library default, so a server configured through
  `WD_TS_GEO_STATION_DISTANCE_*` keeps its own
- `wetterdienst summarize` reaches the settings that `interpolate` always could:
  `--summary_station_distance` and `--use_nearby_station_distance` had no command options at all,
  so the summary CLI always ran with the defaults

### Changed

- An NWS request asks the observations endpoint for its own window. The endpoint answers an
  unqualified request with its whole retention -- a rolling week of some 180 readings, close to a
  megabyte -- however little of it was wanted, and the frame was trimmed to the request only after
  it arrived. It clips a window to what it still holds rather than refusing one that reaches
  further back, so the readings are the same and a request for one day now downloads one day
- **Breaking**: `skip_empty` works through the CLI and the REST API. Neither surface ever set
  `ts_complete`, and `ts_skip_empty` was silently switched off wherever it was not, so
  `--skip_empty`, `--skip_threshold` and `--skip_criteria` -- and the three REST parameters of the
  same names -- did nothing at all, and `filter_by_rank` never skipped a station over its coverage
  the way it is documented to. The option now stands on its own: it needs neither a gridded frame
  nor `ts_drop_nulls=False`, and their log lines are gone with it. A CLI or REST request that
  passes `--skip_empty` starts skipping stations it used to return
- A station's coverage is the share of the readings the requested window can hold at the
  parameter's resolution that the station delivered, counted from the window and the resolution
  rather than by measuring a frame that had been reindexed onto a grid first. The denominator is
  the same one `ts_complete` produced, so a request that already set both settings keeps its
  answers, with two departures: a reading that does not land on the resolution's grid now counts
  as delivered rather than being dropped and counted as missing, and a request that names no
  window is measured against the span of the station's own series for the dataset in question
  instead of being called fully covered whatever it holds. Readings are counted by the grid slot
  they fall in rather than one by one, so a station reporting more often than the resolution it is
  listed under cannot cover a window twice over and read as complete while half of it holds
  nothing. `subdaily` is measured on what came back instead: it is a bucket rather than an
  interval, and its two providers disagree on one -- DWD takes three Termin readings a day where
  Meteo-France SYNOP reports every three hours -- so counting either as the interval would judge
  the other three times too harshly. A parameter is matched to its metadata case-insensitively, so
  a provider emitting its own casing -- WSV reports `w` where its metadata declares `W` -- is no
  longer read as having sent nothing
- **Breaking**: Eaufrance Hubeau reports under the interval each station transmits at, so its
  single `dynamic` resolution is replaced by `5_minutes`, `6_minutes`, `10_minutes`, `15_minutes`
  and `hourly`, and a request for `dynamic/data/...` no longer resolves. Hubeau publishes the
  interval nowhere -- not in the station referential, not on the observations, and the v2 API
  defines no field for one -- so unlike Pegelonline's declared `equidistance` it is measured from
  the timestamps a station has just published. The network does transmit on a grid: of 3018
  stations reporting over six hours, 2987 resolved to one of the five intervals (5 min for 1643 of
  them, 10 for 903, 15 for 251, 60 for 120, 6 for 33), and re-measuring a 45-station sample over
  48 hours named all 45 the same way. Two hours of the whole network are read at the station list,
  which names every station transmitting at least every fifteen minutes, and the slower and quieter
  ones are then asked about by name over a longer window. A station that has published nothing to
  measure is listed under no resolution rather than under a guessed one, and returns as soon as it
  transmits again; so is one transmitting every 20 or 30 minutes, which no resolution covers, and
  that is reported once. In exchange the interpolation search radius scales by resolution rather
  than falling back to a factor of 1.0, and a station's coverage is measured against the interval
  it actually transmits at. `Resolution.DYNAMIC` goes with it, and with it `ResolutionType`, which
  existed only to spell that one member
- **Breaking**: WSV Pegelonline reports under the interval it actually records at, so its single
  `dynamic` resolution is replaced by `1_minute`, `5_minutes`, `10_minutes`, `15_minutes` and
  `hourly`, and a request for `dynamic/data/...` no longer resolves. Pegelonline publishes an
  `equidistance` on every timeseries in the station listing the provider already downloads, so the
  interval was never something that had to be guessed -- it was simply not read. Each station is
  listed under the resolution it records the requested parameters at, and the 77 of 787 stations
  that record different parameters at different intervals (Passau reads stage every 15 minutes and
  air temperature every 60) appear under each, serving only the parameters that belong there. To
  find a station's resolution, request the parameter at every interval that could carry it and read
  the `resolution` column of the station list. In exchange the interpolation search radius scales
  by resolution like every other provider's rather than falling back to a factor of 1.0, and a
  station's coverage is measured against the interval it actually records at
- **Breaking**: the heterogeneous search radius follows the resolution of the request, so an
  interpolation or summary that already worked returns different values without anything being
  changed by hand: daily precipitation is drawn from 40 km rather than 20, `minute_10` from 15 km
  rather than 20. A quantity that decorrelates fast in space does so less the longer it is
  accumulated -- gauge studies put the correlation length of precipitation at roughly 8 km over ten
  minutes, 27 km over three hours and 33 to 94 km over a day -- and one radius cannot serve both
  ends of that. The factors are `ts_geo_station_distance_resolution_factors`: 0.75 for the minute
  resolutions, 1.0 hourly, 1.5 for `6_hour` and `subdaily`, and 2.0 from daily upwards. Resolutions
  left out keep their factor, every factor set to 1.0 turns the scaling off, and the factors
  multiply whatever `ts_geo_station_distance_heterogeneous` says, so raising that setting moves
  every resolution with it. The table stops at 2.0 rather than following the correlation length up:
  past a day what binds is terrain and not correlation, since the interpolation reads UTM x/y and
  never station height, so 40 km is as far as it may reach -- the same bound the homogeneous radius
  is held to, which is why the two meet at `daily` with the defaults. Precipitation is more
  orographically driven than temperature, not less, so it does not get to reach farther. The
  homogeneous radius does not scale at all, and a radius written out per parameter in
  `ts_geo_station_distance` is used exactly as given, at every resolution. The fine end stops short
  of the 8 km the literature gives, since interpolation needs four surrounding stations and even
  the DWD network rarely has four rain gauges that close -- in a sparse network 15 km may leave a
  request that used to answer with nothing, and raising the factor for that resolution brings it
  back. `summarize` scales too: nothing is blended there, but how far away a measurement still says
  something about the target point is the same question, and it depends on the accumulation period
- **Breaking**: the `"default"` key of `ts_geo_station_distance` is gone, in favour of the two
  radii settings above. It was undocumented and did more than it said: it rebuilt the mapping
  around the given number and so replaced the shorter radius of every heterogeneous parameter
  along with the fallback, giving `{"default": 30}` precipitation, fresh snow and visibility 30 km
  as well. Setting it now raises and names its replacements

### Removed

- **Breaking**: the `ts_complete` setting is gone. It reindexed a series onto the grid its
  resolution implies, spelling every gap out as a null row, and it cost a materialized timestamp
  per reading of the window, a station-local-to-UTC window conversion, and a three-way interlock
  with `ts_drop_nulls` and `ts_shape` that had to be spelled out in three log lines before a
  request could say what it did. The join it built was exact, so a station reporting off the grid
  -- an hourly gauge at seven minutes past, which is how a good third of Hubeau's hourly stations
  report -- came back as a column of nulls; that was worth a warning last release and is not worth
  keeping now. A caller who wants the grid can build it in a few lines of polars over the frame
  they were returned, where the phase is theirs to choose. Nothing in the CLI, the REST API or the
  app ever set it
- **Breaking**: `MetadataModel.timezone_data` is gone, and with it the `timezone_data` key all
  29 providers declared. It named the zone a provider's own `date` labels are stamped in, and
  `ts_complete` was the only thing that ever read it -- to decide which zone to build its grid in.
  The `"dynamic"` value, which meant "read the zone off the station's coordinates" and which NOAA
  GHCN and Hubeau declared, goes with the field; the lookup behind it stays, since ECCC and GHCN
  call it directly while parsing. `metadata.timezone`, the provider's civil timezone, is a
  different field and remains -- DWD reads it to work out which period a request needs. Every
  `date` a request returns is UTC either way, which is what left the field with nothing to say

### Fixed

- The NWS station list holds three American stations it used to leave out, and stops excluding
  American ground for being in the wrong hemisphere. Barking Sands on Kauai and the two US Virgin
  Islands airports are filed by MADIS under a state code rather than a country code, so the
  country column missed them; they are named one by one, because that column cannot be read as a
  state code in general -- `PR` in it is Peru and `GU` is Guatemala, and of its four `VI` rows two
  are American and two are British. All three report, returning 257, 165 and 185 observations over
  the endpoint's rolling week. The list was also narrowed to `longitude < 0 and latitude > 0` on
  top of the country column, which is not where the United States ends: the Aleutians west of
  Amchitka lie beyond the antimeridian, Pago Pago below the equator, and Tinian east of the prime
  meridian. That box is gone, since it decided nationality by hemisphere; the six rows it dropped
  are listed again, but as a correction to the filter and not as data recovered -- of the six,
  Shemya and Pago Pago are stations api.weather.gov knows and both are silent at present, and the
  other four (three duplicate Amchitka rows and Tinian) are not stations it knows at all. That is
  the character of this station list rather than of these six: it is the MADIS METAR table used as
  a proxy, and about a third of what it lists returns nothing. The box guarded nothing else --
  every station MADIS files under the United States carries a usable coordinate pair
- An NWS station of unknown elevation reads as null rather than as standing 9999 m up. MADIS
  writes a missing elevation as 9999 and it was cast to a float and passed on unread, for 31 of
  the 3120 stations -- and height is what interpolation weighs a neighbouring station by
- An NWS request no longer rewrites the settings every other request shares. It stamped its own
  headers onto `Settings.fsspec_client_kwargs` in `__post_init__`, replacing the User-Agent
  wetterdienst builds from its version with a literal `wetterdienst/0.48.0` and adding a
  `Content-Type` that no GET has a use for -- so a DWD request made after an NWS one went out under
  NWS's headers, naming a version eighty-five releases old. api.weather.gov accepts the ordinary
  User-Agent, and the override is gone rather than corrected
- Eaufrance Hubeau serves the overseas departments. Metropolitan station codes begin with the
  letter of their hydrographic basin and the codes of Guadeloupe, Martinique, Guyane, La Réunion
  and Mayotte begin with a digit, and the station list kept only the codes beginning with a letter
  -- excluding all 176 overseas gauges, 86 of them transmitting, for no reason the filter recorded.
  Every station code the referential publishes is well formed, so the filter guarded nothing
- Eaufrance Hubeau lists every station it has rather than the first thousand. The station
  referential answers with a page of 1000 of its 4150 stations and a cursor to the rest, and the
  query named no page size and followed no cursor, so three quarters of the French gauges were
  missing from the station list and unreachable through it -- including by `filter_by_station_id`,
  which filters against that list
- **Breaking**: `ts_shape="wide"` puts one timestamp of one resolution in a row, and stops filling
  rows with values that belong to another. The row used to be keyed on the dataset as well while
  the parameters were joined on the date alone, so a request spanning two datasets emitted every
  timestamp once per dataset and filled all of those rows with all of the datasets' values -- the
  `precipitation_more` row of a `climate_summary` + `precipitation_more` request reported
  `climate_summary_rsk`, and the two rows were identical but for the label. Datasets recorded at
  one resolution share their timestamps and now share a row, which is what the dataset-name column
  prefix was always for; `dataset` is null in that row, since no single name describes it, and
  still carries the name wherever a resolution holds a single dataset.
  Resolutions still get their own rows, because a 15-minute series and an hourly one do not have
  the same timestamps to begin with. The parameter joins are also outer rather than inner, so a
  parameter with no reading at a timestamp leaves a null instead of removing the timestamp from
  the frame: chained inner joins had reduced the result to the timestamps every requested
  parameter happened to share, dropping readings that were asked for and downloaded
- Values of two resolutions are sorted apart in both shapes. The row order was `dataset`,
  `parameter`, `date`, so an hourly and a 10-minute precipitation series -- one dataset name, one
  parameter name -- came back shuffled into each other, one hourly row every six 10-minute ones.
  Resolution leads the sort now, in the long shape as in the wide one
- A Zarr export names its group for what the whole frame holds rather than for whatever its first
  row happens to say: the dataset names present, or the resolutions when a wide row spanning
  several datasets carries no dataset name at all. A frame of two datasets used to be filed under
  whichever of them came first, and one merging them would have gone to the store root, where
  `mode="w"` clobbers every other group already in it
- `ts_geo_station_distance` validates what it is given. A key that is not a canonical parameter is
  rejected rather than kept and never read -- a typo silently left the parameter the user meant at
  its default radius, indistinguishable from having set nothing -- and a negative distance is
  rejected as it already is for `ts_geo_use_nearby_station_distance` next to it. A radius set for a
  parameter that is never interpolated is a warning, since the name is real but nothing reads it.
  The CLI and the REST API report the rejection as a bad parameter and a 400 rather than a
  traceback -- for `interpolate` and `summarize` that now covers every option they validate, such
  as a negative distance, which used to end in a pydantic stack trace
- Settings round-trip through `model_dump()` faithfully: `ts_geo_station_distance` serializes the
  overrides it was given rather than the mapping they were expanded into. Dumping the expansion
  made every heterogeneous parameter come back as an explicit override, which then won over a
  `ts_geo_station_distance_heterogeneous` set alongside it. The expansion is idempotent for the
  same reason -- `TimeseriesRequest` re-validates the settings it is handed, which used to take
  the already-expanded mapping for what the user had written
- Docs: `ts_geo_min_gain_of_value_pairs` is documented with its actual default of 0.1, not 1.2
- `poe docs` builds the documentation again. It ran `make html` in `docs/`, which holds no
  Makefile, so it had failed with "No rule to make target" for as long as that file has been gone.
  It runs sphinx against `docs/conf.py` now, which is what Read the Docs does, and `poe docs:clean`
  removes the build directory

## [0.133.0] - 2026-08-19

### Added

- Every parameter of every provider now carries a description, 1681 of 1681, closing the last 508
  gaps. 271 come from the source itself: MeteoSwiss publishes `ogd-smn_meta_parameters.csv` beside
  the data, MET Norway has a Frost `/elements` endpoint, KNMI writes a `long_name` on every NetCDF
  variable, FMI has an `observableProperty` metadata endpoint, and AEMET and SMHI describe their
  fields in the payloads and listings they already serve (translated here from Spanish and
  Swedish). The remaining 237 are the canonical sentence for the quantity, kept apart in
  `DERIVED_DESCRIPTIONS` so generated text is never mistaken for a source's own wording. Sibling
  prose is now borrowed only within a provider, never across: another source's specifics ("within
  the last 12 hours") need not hold for the one borrowing them
- The provider docs tables carry a `description` column for the 46 pages that had none, and 41 rows
  for parameters that were declared but never listed at all
- `GET /api/version` reports `mcp_enabled` alongside the version. The MCP endpoint sits behind the
  optional `[mcp]` extra, so whether `/mcp` exists is a property of the installation, and a client
  had no way to find out short of probing `/mcp` -- which on the streamable-HTTP transport means
  opening a session rather than asking a question. The index page has always known (it prints the
  endpoint only when mounted); this exposes the same flag over JSON
- 216 more parameters can be interpolated and summarized, 343 of 514 rather than 127. Soil
  temperature under a named cover and depth (114, NOAA GHCNd), forecast probabilities (65, MOSMIX
  and DMO), soil moisture (12, DWD's agrometeorological model), evaporation per crop and soil (6),
  concrete slab temperature (3), humidex and mean radiant temperature, cloud cover in a fixed
  height band, climatological normals, and — at the shorter radius — precipitation intensity and
  visibility. The classification was never about the data being unavailable, only about which names
  had been written into the list by hand. What stays out stays out on purpose: coded observations,
  quality flags, counts, quantities tied to one body of water, a station's own measurement errors,
  directions, which cannot be averaged linearly at all, and the 14 GHCNd soil temperatures whose
  surface cover is recorded as `unknown` — the rest of that family qualifies because the cover is
  part of the name, which is precisely what an unrecorded cover does not give you.
  One cost to know about: `interpolate()` and `summarize()` stop querying stations once *every*
  requested parameter has enough of them, so a whole-dataset request against MOSMIX or DMO now has
  65 probabilities to satisfy and will walk further down the station ranking than it used to.
  Requesting the parameters you actually want keeps it where it was
- DWD hourly solar `true_local_time_offset` (`mess_datum_woz`), a new canonical parameter holding
  how far true local solar time runs ahead of a record's timestamp -- the longitude correction plus
  the equation of time. Solar records are stamped with the UTC instant of a whole true-solar-time
  hour, so the correction sits in the minutes of that timestamp, which wetterdienst rounds to the
  hour so a solar series lines up with every other hourly series. The rounding discarded it and the
  column that also held it was dropped, so it was not reachable at all. At station 00183 it runs 40
  to 71 minutes, its monthly mean tracing the equation of time from 40.4 in February to 69.1 in
  November about a 54.7 minute longitude term
- DWD's two measurement method indicators are returned instead of dropped:
  `cloud_cover_total_measurement_method` (`v_n_i`, hourly cloud_type and cloudiness) and
  `visibility_range_measurement_method` (`v_vv_i`, hourly visibility). DWD writes them as letters
  -- `P` for a human person, `I` for an instrument -- in files that are otherwise numeric, and the
  value column is Float64, so both were declared but silently dropped and a request for them
  returned an empty frame. They are now decoded to 1 for `P` and 2 for `I`. The digits are
  wetterdienst's, not DWD's: they follow the order DWD lists the letters in, and 0 is left unused
  so "not measured" stays distinguishable from either method
- Every DWD parameter now carries a description, 717 of 717 across observation, mosmix, dmo,
  derived, road and swsmos. 25 came from correcting the docs (below), the rest are derived: where a
  source publishes no prose at all, the text is taken from the same canonical parameter at the same
  resolution elsewhere -- the same quantity over the same interval, so the wording transfers -- or
  from the canonical sentence. Those sit in `DERIVED_DESCRIPTIONS`, apart from
  `SOURCE_DESCRIPTIONS` and applied only where nothing else supplies one, so a derived sentence is
  never mistaken for a source's own wording
- Dataset and resolution descriptions on the metadata models: 88 of 148 datasets and 2 resolutions,
  lifted out of the provider docs metadata tables the same way the parameter descriptions were.
  `DatasetModel.description` and `ResolutionModel.description` had been declared but never
  populated, so `metadata["hourly"]["data"].description` returned `None` for every provider.
  `tests/test_docs.py` checks the tables still agree with the model, ignoring the trailing
  `([details](url))` pointer the pages add, which is page formatting rather than description
- Source descriptions for 1057 parameters, in `metadata.source_descriptions` and reported by
  `discover()` -- so by `GET /api/coverage`, the `coverage` MCP tool and `wetterdienst about
  coverage`. These say what a given provider's field means, as against the canonical,
  provider-independent sentence the glossary serves
- 113 DWD observation descriptions come from the English `DESCRIPTION_*_en.pdf` sheets, which are
  more specific than the text the docs carried ("The solar incoming radiation includes the direct
  and the diffuse part ..." against "hourly sum of solar incoming radiation"). DWD CDC is Creative
  Commons BY 4.0, so its wording is reproduced with attribution. A sheet's cell is used only where
  it says at least as much as the curated text: some are terse, a few truncated -- `V_S1_NS` reads
  "cloud cover of 1. laye" and `V_S2_NS` repeats it for the second layer -- and two are left
  untranslated in an otherwise English sheet
- Source descriptions for DWD observation parameters: what a given DWD field means in DWD's own
  words, alongside the canonical, provider-independent sentence the glossary already served. 133
  parameters across the 30 datasets that publish an English description sheet, transcribed into
  `provider/dwd/observation/descriptions.py` and attached to the metadata at import. DWD CDC is
  Creative Commons BY 4.0, so the wording is reproduced with attribution to the Deutscher
  Wetterdienst; the module records the source URL and licence
- `description` now appears in `discover()`, and therefore in `GET /api/coverage`, the `coverage`
  MCP tool and `wetterdienst about coverage`. `ParameterModel.description` had been a declared but
  entirely unused field -- as are `DatasetModel.description` and `ResolutionModel.description`,
  which remain unpopulated
- ECCC monthly and hourly expose the fields that were previously left undeclared, with twelve new
  canonical parameters for them. Monthly gains the day counts
  (`count_days_precipitation_height_ge_1mm` and the six `count_days_valid_*`) and the
  climatological normals (`temperature_air_mean_2m_normal`, `precipitation_height_normal`,
  `snow_depth_new_normal`, `sunshine_duration_normal`); hourly gains `temperature_humidex`. Units
  were taken from the values rather than assumed: each normal matches the range of the quantity it
  is a normal of in the same response, and humidex sits at or above the air temperature in all 233
  paired observations sampled, which is what an apparent temperature does
- CI: new `Minimum dependency versions` job that resolves every direct dependency to the lowest
  version its specifier allows (`UV_RESOLUTION=lowest-direct`) and runs the test suite against it,
  so that declared floors are actually exercised
- Canonical parameter table (`wetterdienst.metadata.parameter_table`) holding the `unit_type` of
  each of the 505 canonical parameter names in one place, plus a test that checks every provider
  declaration against it — that the name is canonical and that the declared `unit` is a unit of
  that quantity. The table is now the single source of `unit_type`; see below
- New canonical parameters `radiation_global_intensity`, `radiation_sky_long_wave_intensity` and
  `radiation_sky_short_wave_diffuse_intensity` for sources that report irradiance (power per area)
  rather than irradiation accumulated over the interval (energy per area)
- Docs: a parameter glossary on the Parameters page, built from the canonical parameter table at
  build time by the local Sphinx extension `docs/_ext/parameter_glossary.py`. Every parameter in
  every provider's metadata table now links to its glossary entry
- `wetterdienst.metadata.unit_type.UnitType`, a literal of the unit types the unit converter
  knows. `CanonicalParameter.unit_type` is typed with it, so a mistyped unit type in the parameter
  table is a type error rather than something only a test can catch. A test pins the literal to
  `UnitConverter` in both directions, since the converter builds its unit types as a runtime dict
  that no static type can be derived from
- Two unit types the audit of the canonical table turned up as missing: `mass_per_volume`
  (g/m³, kg/m³, and mg/l and g/l shared with `concentration`, which is the same quantity under a
  different convention — 1 mg/l is 1 g/m³) and `degree_hour` (°Ch, Kh, °Fh), kept apart from
  `degree_day` so that a quantity accumulated per hour is not reported per day
- New canonical parameter `cooling_degree_day`, the counterpart of `heating_degree_day`
- Parameter discovery across all three interfaces: `GET /api/glossary`, the `glossary` MCP tool and
  `wetterdienst about glossary`. `coverage` answers which parameters a given provider offers; the
  glossary answers what any of them measures and which unit it comes back in — neither of which
  `coverage` reports. Filter with `parameter=` (substring match over the 505 names), `unit_type=`
  (a closed vocabulary, so an unknown one is a 422 or a CLI usage error rather than an empty
  result) and `limit=` to cap the response. The unit reported is the one a values request would
  actually return, including any `ts_unit_targets` override. This is what puts the canonical
  descriptions in front of users rather than only in the docs. A filter matching nothing is an
  empty list over HTTP and a non-zero exit on the CLI, the latter following grep so a shell script
  can tell
- A one-sentence description for all 505 canonical parameters, so the glossary now says what each
  quantity *is* rather than only which unit it comes back in — that soil temperatures are at a
  stated depth under a stated cover, that `wind_movement_24h` is wind run, that
  `radiation_global` is accumulated energy while `radiation_global_intensity` is power. They are
  deliberately provider- and resolution-independent, describing the quantity rather than one
  source's version of it. They appear in the docs glossary today; exposing them through the REST
  API, CLI and MCP is a separate change, since `discover()` reports name, unit type and unit only

### Changed

- The backend image builds with uv 0.12.5 rather than 0.8.4, four minor versions back. 0.8.4 could
  not parse `exclude-newer = "3 days"` and responded by discarding the whole `[tool.uv]` table --
  `warning: Failed to parse pyproject.toml during settings discovery` -- taking `[tool.uv.audit]`
  with it. The build still succeeded, because `uv sync --frozen` installs from the lockfile and
  needs none of those settings, so this was a silent degradation rather than a failure. Dependabot
  will keep the pin current from here, now that it reads `docker/`
- Dependabot's `docker` entry pointed at `/`, where there is no Dockerfile -- both of them live in
  `docker/`. It has therefore never proposed a base-image update for either image; it now reads
  the directory they are actually in
- Locked dependencies refreshed to their latest compatible versions (cryptography 50, fastapi
  0.141.1, starlette 1.6, uvicorn 0.52.3, numpy 2.5.2, zarr 3.3, mcp 1.29, and others), and the dev
  toolchain with them (ruff 0.16.3, ty 0.0.72, zizmor 1.29) -- both still pass with no source
  changes needed
- `uv` now resolves with a three-day cooldown (`tool.uv.exclude-newer = "3 days"`), so a release
  has to survive its first days in the wild before it can enter the lockfile. Yanks and
  publish-day breakage are most often caught in that window. The lockfile records it as a relative
  span (`exclude-newer-span = "P3D"`), not a timestamp, so it does not churn between runs and
  `uv lock --check` stays stable
- Docs: the REST API page's "Web Frontend" section is "Web App", matching what the app has been
  called since it moved to `app/`. The stripes page and the pull-request checklist follow, as do
  the Météo-France comments that explain which caller depends on a populated `start_date`
- Docs: the README states what the project stands for, in the same four lines the app closes with,
  and opens with "Global warming is not an opinion" rather than the Fridays for Future chant -- the
  one claim a weather-data library backs up by existing. Anthropic gets a logo next to JetBrains
  under "Supported by", where it had been a mention in prose
- Docs: the README is rewritten around what a first-time reader needs. One header image rather than
  three, one badge block rather than four, and a table of all 22 providers with their country and
  what each one serves -- which the README never stated, though it is the first question anyone
  asks. The MCP endpoint and the app are named among the features. The extras list is corrected: it
  advertised a `matplotlib` extra that does not exist and omitted `eccodes`, `excel`, `knmi`,
  `radar` and `radarplus`, which do. The Raspberry Pi installation notes move to
  `docs/known_issues.md`, where the other environment-specific issues live, rather than being
  dropped -- the README is the docs landing page, so nothing written only there survives deletion
- 34 more descriptions come from the source. CHMI publishes per-element metadata beside its csv
  archive -- name, unit, sensor height and measurement schedule -- which gives all 25 of its
  parameters, translated from Czech and carrying facts the canonical sentence cannot: its daily
  temperature, humidity, pressure and wind speed are averages of the 06:00, 13:00 and 20:00
  observations, its daily extremes are read at 20:00 and its snow depth at 06:00. DWD's
  `MetElementDefinition.xml` covers nine more codes across swsmos, mosmix and dmo. 190 derived
  descriptions remain
- Resolution descriptions are written where the name underdetermines what arrives, and only there:
  Météo-France synop (SYNOP's native three-hourly interval), MET Norway's 6 hour, and the two
  `dynamic` networks, WSV and Hubeau, where the interval is a property of the station rather than
  the network -- 15 minutes at most gauges, 10 at some, measured across both. `hourly` and `daily`
  say everything about themselves, so they are left empty rather than filled with text that reads
  as information without being any. EA hydrology's resolution description is dropped: it described
  the dataset structure, not the interval, and EA's dataset description already covers that
- 84 more descriptions come from the source rather than from the canonical sentence, after finding
  that three providers document their fields after all. Météo-France publishes a
  `*_descriptif_champs*.csv` beside each resolution (43 parameters, translated from French), the
  Met Office's MIDAS tables are documented by CEDA in English (32), and LHMT lists its fields on
  api.meteo.lt (9, translated from Lithuanian). They say what the canonical sentence cannot: that
  Météo-France's daily precipitation runs 06h to 06h UTC and is attributed to the earlier day, that
  Met Office pressure is uncorrected for altitude, that LHMT returns null for cloud cover it cannot
  determine through fog. 224 derived descriptions remain, DMI (52) and RMI (42) the largest, neither
  of which documents its fields anywhere reachable
- **Breaking**: `discover()` nests its answer so that every level has a place for its description,
  which had nowhere to go before: `{resolution: {"description": ..., "datasets": {dataset:
  {"description": ..., "parameters": [...]}}}}`. The 88 dataset descriptions and 2 resolution
  descriptions were on the model but unreachable over `GET /api/coverage`, the `coverage` MCP tool
  and `wetterdienst about coverage`, which all pass this dict through as their response. Consumers
  reading `data[resolution][dataset]` as a list of parameters now read
  `data[resolution]["datasets"][dataset]["parameters"]`
- The `Parameter` enum is no longer used inside the library. The three places that hard-coded
  parameter names — `TimeseriesRequest.interpolatable_parameters`, interpolation's
  occurrence-based set and the `ts_geo_station_distance` defaults — used it purely to spell a
  lowercased string, and now spell the canonical name directly. All 186 references resolve to the
  same 126/30/30 names as before. Those three lists have since moved into the canonical parameter
  table, see below
- How a parameter behaves in space is declared once, on `CanonicalParameter`, rather than as three
  hand-maintained name lists that had to agree with each other:
  `TimeseriesRequest.interpolatable_parameters`, the `ts_geo_station_distance` defaults in
  `Settings` and `_OCCURRENCE_BASED_PARAMETERS` in `core.interpolate` are all views of the new
  `interpolation` (`"homogeneous"` at the 40 km default radius, `"heterogeneous"` at 20 km, or
  `None` for a quantity that is not interpolated) and `zero_inflated` (whether interpolated values
  are thresholded on occurrence) fields. The two are separate because they are separate facts:
  visibility decorrelates over a few kilometres without being zero-inflated, and a precipitation
  normal is as orographically variable as precipitation while never being zero.
  `_OCCURRENCE_BASED_PARAMETERS` is gone; ask the table, `PARAMETERS[name].zero_inflated`.
  The parameter glossary in the docs now states per parameter whether it can be interpolated and
  from how far away
- **Breaking**, mildly: `TimeseriesRequest.interpolatable_parameters` is a `frozenset` rather than
  a `list`. Every caller in the library only tests membership, but it is a public class attribute,
  so code that indexes or slices it, or relies on its order, needs updating
- **Breaking**: irradiance (`power_per_area`) is now returned in W/m² rather than W/cm², so
  affected values are 10⁴ times larger. W/m² is what WMO specifies and what every source in this
  library actually publishes — MeteoSwiss global radiation now reads 0–1344 W/m² where it used to
  read 0–0.1344 W/cm². Affects the 17 declarations using `power_per_area`: KNMI (10 minutes),
  MeteoSwiss, met.no Frost and RMI. Set `ts_unit_targets={"power_per_area":
  "watt_per_square_centimeter"}` to keep the old output. Irradiation (`energy_per_area`) is
  unchanged and still returned in J/cm², which is the conventional unit for it
- **Breaking**: KNMI (10 minutes), RMI, MeteoSwiss and met.no reported irradiance in W/m² under
  the `radiation_global`, `radiation_sky_long_wave` and `radiation_sky_short_wave_diffuse` names,
  which elsewhere mean irradiation in J/cm². These declarations moved to the new
  `radiation_*_intensity` names. KNMI is the clearest case: its 10-minute `qg` is W/m² while its
  hourly and daily `Q` is J/cm², so one name was covering two quantities that no unit conversion
  relates without the accumulation interval. Queries using the old names against these providers
  need to switch to the `_intensity` names; DWD and every other provider are unaffected
- **Breaking**: Geosphere 10-minute and hourly radiation is now returned as published rather than
  silently rescaled. `cglo` and `chim` are irradiance in W/m², but the parser multiplied them by
  the interval length (600/10000 and 3600/10000) to present them as irradiation in J/cm² under the
  `radiation_global` and `radiation_sky_short_wave_diffuse` names. That conversion is removed and
  the three declarations moved to `radiation_global_intensity` and
  `radiation_sky_short_wave_diffuse_intensity` in W/m². Values are correspondingly 16.67× (10
  minutes) and 2.78× (hourly) larger; multiply by 0.06 and 0.36 respectively to recover the old
  numbers. Daily and monthly are unaffected — they use `cglo_j`, a distinct upstream parameter
  genuinely accumulated over the interval, and keep `radiation_global` in J/cm². This was the only
  in-parser unit conversion left in the library
- **Breaking**: Météo-France synop `visibility_range` was the only declaration of that parameter
  using `length_long`, so it was returned in km while all 15 other declarations return m. It now
  uses `length_medium` and returns m
- Docs: provider metadata tables no longer repeat the `unit type` column. The unit type is a
  property of the canonical parameter, so it is stated once in the glossary; the `unit` column
  stays, because that really is the individual provider's own
- The provider docs tables no longer own that text. It lived only in markdown, where no interface
  could reach it and where the two copies drifted apart in both directions -- three defects found
  during the unit audit were each caught by the *other* source being right. The model is the source
  now and `tests/test_docs.py::test_docs_parameter_descriptions_match_the_model` fails if a table
  disagrees with it
- Raise several dependency floors that were declared lower than what the code actually needs:
  `aiohttp>=3.14.0` (`encode_basic_auth`), `stamina>=25.1.0` (`set_testing` as a context manager),
  `pandas>=2.2.2`, `shapely>=2.0.4` and `h5py>=3.11` (NumPy 2 support),
  `plotly>=6.1.1` with `kaleido>=1.0.0` (static image export), and `click>=8.2`
  (separately captured `stderr` in `CliRunner`)
- Raise the development tooling floors to the versions we develop against, so that the minimum
  versions job only exercises runtime dependency floors

### Removed

- **Breaking**: seven DWD observation parameters that were declared but never returned a value are
  no longer declared, so a request for one now says so instead of answering with an empty frame:
  `cloud_type_layer1..4_abbreviation` (`v_sN_csa`, hourly cloud_type), `weather_text` (`ww_text`,
  hourly weather_phenomena), `end_of_interval` and `true_local_time` (`mess_datum_woz`, hourly
  solar). Each was checked against the archive rather than assumed: `v_sN_csa` is the letter form
  of `v_sN_cs` and matches it exactly across 398,381 records; every `ww` maps to one text across
  443,827 records while two codes share a text, so the text says strictly less than the code;
  `end_of_interval` names a column that does not exist in the solar files at all; and
  `mess_datum_woz` is published as a whole hour, leaving it a fixed one hour from the returned
  timestamp at station 00183 once the solar timestamps are rounded, which is where the sub-hour
  solar correction actually lives. Their canonical entries are dropped too, since no provider can
  express text in a `Float64` value column
- `DwdObservationValues.DROPPABLE_COLUMNS`, which duplicated the parser's drop list and had already
  drifted from it. Dropping happens once, in the parser
- The `magnetic_field_intensity` and `wave_period` unit types. Each existed for exactly one
  parameter, and both of those turned out to be mis-typed: WSV `current` is a bearing in degrees and
  WSV `wave_period` is a duration in seconds, so neither unit type has anything left to describe
- **Breaking**: the `Parameter` enum, exported from the package root. It listed the canonical
  parameter names but could not be used to request them — `parameters=` accepts strings, tuples,
  `ParameterModel` and `DatasetModel`, so passing a member raised
  `AttributeError: 'Parameter' object has no attribute 'strip'`. It appeared in no example and no
  documentation page, and its last internal uses are gone (see Changed). The canonical names live
  in `wetterdienst.metadata.parameter_table`, which also carries each parameter's unit type and
  description, and are discoverable through the new glossary endpoint, MCP tool and
  `wetterdienst about glossary`. Callers who used it to spell a name should use the string directly
- The `unit_type` key from provider metadata declarations — 1575 of them across 29 files. It is a
  property of the measured quantity rather than of the provider, and restating it once per
  declaration is what let the same canonical name pick different output units in different
  providers. `ParameterModel.unit_type` now reads it from the canonical parameter table via the
  parameter's `name`, and `ParameterModel` rejects the key outright so an override cannot creep
  back in. All 1692 parameters resolve to exactly the same `unit_type` as before, so nothing
  changes for users of the library — but a **third-party or custom provider metadata dict that
  still declares `unit_type` will now fail to validate**, and should simply drop the key.
  `discover()` and the REST and CLI responses report `unit_type` exactly as before. It is no
  longer part of `ParameterModel.model_dump()`/`model_dump_json()`, since it is derived from the
  parameter's `name` and emitting it per declaration would reintroduce at the serialization layer
  the duplication this removes; look the name up in `wetterdienst.metadata.parameter_table`
  instead
- **Breaking**: five `Parameter` enum members that no provider declared, so no request could ever
  return them: `HUMIDEX`, `PRECIPITATION_FREQUENCY`, `PRECIPITATION_HEIGHT_LIQUID_MAX`,
  `TIME_WIND_GUST_MAX` and `TIME_WIND_GUST_MAX_1MILE_OR_1MIN`. The dead entries referencing two of
  them in the interpolation membership lists went with them
- Docs: `docs/data/provider/eccc/observation/annual.md`. ECCC's `annual` resolution was dropped
  when observation values moved to the api.weather.gc.ca OGC API, and the docs still described it,
  along with `humidex` under hourly. The ECCC observation overview also still described bulk CSV
  downloads and four resolutions; corrected
- Docs: the `pressure_air_sea` row from IMGW meteorology daily, a parameter that provider no
  longer exposes
- Unused `jsonschema` development dependency

### Fixed

- The whole test suite failed to collect on Python 3.10, the oldest version the project supports:
  `tests/test_citation.py` imported `tomllib`, which is stdlib only from 3.11. The import error
  aborted collection, so 3.10 has been running zero tests rather than failing loudly on one. The
  import is now guarded and falls back to `tomli`, added to the dev group under the same marker
- Fixed nine provider docs rows that named parameters renamed in the code but not in the docs
  (`*_indicator` → `*_index` for DWD, `pressure_air_sl` → `pressure_air_sea_level` for
  Geosphere/NWS, `pressure_air_sh` → `pressure_air_site` for NWS, `flow` → `discharge` for
  Eaufrance)
- Fixed `tests/test_docs.py::test_data_coverage`, which had been passing without checking anything
  because its provider path pointed at `<root>/wetterdienst/provider` instead of `<root>/src/...`
- `CITATION.cff` names the released version again, and is valid CFF 1.2.0 once more. It had lost
  `version` and `date-released`, and carried an empty `identifiers:` key, which parses as null and
  fails the schema — so the file every citation tool reads described no particular release and
  could not be converted at all. It now states 0.132.0 of 2026-08-04 and the Zenodo concept DOI,
  the one that resolves to the latest version. Because nothing generates the file, a test ties it
  to the sources it duplicates: the version in `pyproject.toml`, the release date in this changelog
  and the DOI badge in the README, so a release that forgets it fails rather than ships stale
- `summarize()` searched for stations within 20 km whatever the parameter. It bounded its search
  with `max(ts_geo_station_distance.values())`, and that mapping only holds entries for the
  parameters that get the *shorter* radius — everything else is answered by the default factory and
  so is not in `values()` at all. It now takes the widest radius among the requested parameters, as
  interpolation already did, so a summary of e.g. `temperature_air_mean_2m` reaches the full 40 km
  and finds stations it used to walk past
- **Breaking**: MET Norway's in-band codes are decoded rather than returned as measurements. Frost
  states both in the element descriptions it publishes and then writes them into the value itself:
  snow depth -1 is "no snow", which is a depth of zero rather than an absent one, and cloud cover
  -3 and 9 both mean the cover could not be estimated. Being declared in eighths those two
  converted to -0.375 and 1.125 of the sky, the second looking like a plausible reading rather than
  a code. Snow depth -1 now returns 0, cloud cover -3 and 9 return null. Frost keeps the codes out
  of its own monthly and annual means, so only the elements themselves are touched
- **Breaking**: DWD hourly cloud cover no longer reports -0.125 of the sky. `cloud_cover_total`
  (`v_n`) and `cloud_cover_layer1` to `cloud_cover_layer4` (`v_sN_ns`) carry -1 where the sky could
  not be seen at all, SYNOP's N = 9, and being declared in eighths that converted to -0.125 as a
  fraction. It is returned as null now. DWD's description documents only -999 and says nothing
  about -1, so the reading is from the data: -1 stands in 1.2% of station 00003's hourly
  observations, and fog codes (`ww` 40-49) accompany 69.1% of those against 0.8% of the rest. The
  cloud *type* codes beside them keep their -1, DWD's own value for an automated observation, which
  is dimensionless and so passes through unscaled
- Descriptions no longer leak between resolutions. `build_metadata_model` wrote them into the
  metadata dicts it was given, and providers commonly build one resolution's parameter list from
  another's by comprehension, which reuses the very same dicts: AEMET's annual parameters are its
  monthly ones minus humidity, so annual reported "Monthly mean temperature" and its own seven
  descriptions went nowhere. The dicts are copied now, and a test checks each description lands on
  the parameter it names
- **Breaking**: MET Norway `cloud_cover_total` was declared `percent` while Frost publishes it in
  octas -- its own `unit` field says so, and the values run 0 to 8. A fully overcast sky was
  reported as `8 %`. Now declared `one_eighth`, so it converts like every other cloud cover
- **Breaking**: AEMET daily `dir` is `wind_direction_gust_max`, not `wind_direction`. AEMET
  documents it as the direction of the maximum gust, and its hourly block already separates the two
  as `dmax` and `dv`
- IMGW's monthly `climate` dataset was documented under a stale `data` heading carrying the
  parameter names it had before the dataset was renamed, and DWD derived still labelled
  `count_days_cooling_degree` "Anzahl Kühltage" where the column is `Kuehltage`
- 21 docs rows named a field the provider does not use. DWD MOSMIX and DMO documented low cloud
  cover as `n1` where the element is `nl`, DWD derived used the label "Anzahl Kühltage" where the
  column is `Kuehltage`, and ECCC and IMGW carried names from before their APIs changed. Each was
  a row whose description could not reach the model, so correcting them recovered 25 descriptions
  that already existed
- DWD's layer cloud cover descriptions are correct. Its English sheet truncates `V_S1_NS` to "cloud
  cover of 1. laye" and then repeats that same string for `V_S2_NS`, so the second layer was
  described as the first. The German `Metadaten_Parameter` file inside the data ZIPs has both right
  ("Bedeckungsgrad in der ersten/zweiten Schicht"), and all four layers now read consistently.
  `end_of_interval` and `luftdruck_nn`, which DWD documents in neither language, are described
  plainly; every non-quality DWD observation parameter now has a description
- **Breaking**: DWD's `v_n_i` and `v_vv_i` are named for what they hold. Both are *measurement
  method* indicators -- P for a human observer, I for an instrument, which is why the parser lists
  them among its string parameters -- while `cloud_cover_total_index` and `visibility_range_index`
  both described a coded *value*. They are now `cloud_cover_total_measurement_method` and
  `visibility_range_measurement_method`
- **Breaking**: `visibility_range_class` is renamed `visibility_range_index`. It only existed
  because `visibility_range_index` was occupied by the method indicator above, and its description
  ("Coded indicator of the visibility range") always described DWD subdaily `vk_ter` rather than
  what it was attached to. `cloud_cover_total_index` is removed; no provider declares a coded cloud
  cover
- **Breaking**: four DWD subdaily parameters named the wrong quantity, not merely the wrong unit.
  DWD's own `Metadaten_Parameter_*.txt`, shipped inside every data ZIP, gives each field a
  description and a unit, and for these four it disagreed with what wetterdienst declared:
  - `e_tf_ter` is "Eisansatz bei der Messung der Feuchttemperatur", unit YES/NO -- whether ice had
    formed on the wet bulb thermometer. It was declared `temperature_air_mean_0_05m` in °C, and
    carries only 0 and 1 across 82901 values at station 00003. Now
    `temperature_wet_ice_formation`, dimensionless
  - `ek_ter` is "Terminwerte des Erdbodenzustand", unit CODE -- values 0-9, exactly 10 distinct. It
    was declared `temperature_soil_mean_0_05m` in °C. Now `soil_state_index`, dimensionless
  - `vk_ter` is "Terminwerte Sichtweite", unit CODE -- also 0-9. It was declared `visibility_range`
    in metres, so a request for subdaily visibility returned "5 metres" for visibility class 5. Now
    `visibility_range_class`, dimensionless
  - `tf_ter` is the wet bulb temperature and was declared `temperature_air_mean_2m`. DWD's *hourly*
    moisture dataset already maps the same quantity (`tf_std`) to `temperature_wet_mean_2m`, so the
    two resolutions disagreed with each other. Confirmed against 83994 paired observations: it sits
    a median 1.6 °C below the air temperature and never exceeds it, which is the wet bulb
    signature. Now `temperature_wet_mean_2m`
- Three new canonical parameters for the above: `temperature_wet_ice_formation`,
  `soil_state_index` and `visibility_range_class`, all dimensionless
- **Breaking**: Geosphere `cloud_cover_total` is returned as a fraction rather than a percentage
  passed off as one. It was declared `decimal` while Geosphere documents `bewm_mittel` as `1/100`
  and returns 0-100, so the raw percentage went straight through the `fraction` target unconverted
  and every value was 100x its stated meaning. Geosphere's own `humidity` and
  `sunshine_duration_relative` already declared `percent`, so this was the odd one out within the
  provider. Values now read 0-1
- **Breaking**: DWD road `visibility_range` is returned in metres rather than 1000x too large. It
  was declared `kilometer`, but BUFR `0 20 001 horizontalVisibility` is metres, nothing in the
  parser converts, and the provider's own docs page already said `m`
- **Breaking**: ECCC hourly and monthly return data at all. Both resolutions declared parameters
  the OGC API never publishes -- hourly carried a copy of the *daily* field list
  (`max_temperature`, `snow_on_ground`, the degree days), monthly carried bulk-CSV column headers
  (`"total precip (mm)"`) -- so every request came back empty. Monthly additionally crashed on
  `LOCAL_DATE`, which is `"2023-06"` for that collection against a parser expecting a full
  timestamp. Both now declare the fields ECCC actually serves; the requested field list is derived
  from those declarations rather than hand-maintained per resolution, which is what let hourly
  drift into a copy of daily in the first place. Parameter names change for both resolutions
- **Breaking**: ECCC value requests return the whole period rather than an arbitrary 500 records.
  The OGC endpoint pages at 500 features and a station-year of hourly data is ~8800, so every
  request was silently truncated to a slice of the year -- June 1972 at station 4055 returned 16
  timestamps where it holds 697. Results grow accordingly
- ECCC exposes its whole station network rather than the first 500. The OGC endpoint pages at 500
  by default and ECCC publishes ~8600 stations, so 94% of them could not be requested at all --
  including every station whose data the hourly collection actually holds
- ECCC no longer fails on the daylight-saving fall-back hour, which occurs twice in local time.
  Unreachable while a request returned only part of a year, so it surfaced with the fix above
- ECCC hourly `wind_direction` is returned in degrees rather than tens of degrees, the same source
  encoding already decoded for the daily gust direction
- ECCC stations opened before standard time no longer fail the station listing. `America/Toronto`
  is `-5:17:32` in 1895, an offset that is not a whole number of minutes and that polars rejects;
  the conversion to UTC now happens in Python. A handful of stations publish no timezone at all
  and fall back to UTC. Neither showed up while the listing stopped at 500 rows
- **Breaking**: WSV Pegelonline values are now scaled to the unit the metadata declares. The service
  publishes the unit per *timeseries*, not per parameter, and its stations disagree, so a single
  declaration was silently wrong wherever a station differed. Water level is `cm` at most gauges but
  `m+NN` at 66 of them and `m+PNP` at 2; conductivity `µS/cm` or `mS/cm`; flow speed `m/s` or
  `cm/s`; wave height `cm` or `m`; wave period `s` or `1/100s`. Significant wave height at
  MELLUMPLATE came back as 0.07–1.32 next to 12.66–280.6 at LT ALTE WESER for the same quantity,
  both labelled cm. Affected values change by the corresponding factor. A station publishing a unit
  the provider does not know is now skipped with an error rather than reported under the wrong one.
  Note that the `m+NN` gauges have no gauge zero and so measure against sea level rather than the
  gauge datum even once scaled — the `gauge_zero` station column says which
- **Breaking**: WSV `current` is renamed `flow_direction` and returned in degrees. The source gives
  it the unit `MGN`, degrees relative to magnetic north, which had been read as a magnetic quantity
  and declared as magnetic field strength in A/m; the values are compass bearings of 0–360
- **Breaking**: WSV `wave_period` is returned in seconds. It was declared with a `wave_period` unit
  whose symbol was `1/s`, a frequency rather than a duration, and carried a `TODO` questioning it
- **Breaking**: WSV `clearance_height` is returned in centimetres. It was declared in metres while
  every station publishes centimetres, so values were 100× too large
- **Breaking**: WSV parameter names are humanized like every other provider's. The parser wrote the
  source name lowercased while the humanizing map is keyed on it as declared, so the two never
  matched and values came back as `sigh`, `tp` and `r` rather than `wave_height_sign`,
  `wave_period` and `flow_direction`. Unit conversion keys case-insensitively and was unaffected,
  which is why this went unnoticed. With `ts_humanize=False` the names are now the source's own
  casing (`SIGH`) rather than lowercased (`sigh`)
- WSV `gauge_zero` is populated rather than always null. The station frame built the column as
  `gauge_datum`, which `_base_columns` then dropped, leaving `gauge_zero` null for all 738
  stations. This is the column that says which datum a water level is on, so it matters most for
  exactly the `m+NN` gauges above
- WSV turbidity is checked against the station's own unit like the other scaled parameters. The
  service publishes `TR` as `FNU` at two stations, `TE/F` at two and `NTU` at one; all three name
  the same formazin scale so no value changes, but a turbidity unit that is *not* on that scale is
  now skipped rather than passed through as NTU
- Requesting several parameters at once no longer fails when one of them has no data for the
  station. Concatenating the empty result raised `polars.exceptions.ShapeError: unable to append to
  a DataFrame of width 6 with a DataFrame of width 0`; the empty frame is skipped instead. This
  affected every provider that reports parameters separately rather than grouped. Note that a
  parameter whose *download* fails is indistinguishable from one that simply has no data at this
  point — both surface as an empty frame — so such a parameter is now omitted from the result
  rather than failing the whole request with the `ShapeError` above
- **Breaking**: conductivity conversions between per-centimetre and per-metre units were wrong, 8
  of the 12 pairs by 10²–10⁴. Conductivity is per unit *length*, so a shorter length in the
  denominator means a larger number — 1 S/cm is 100 S/m, not 1/100 of one — and the conversions
  had that inverted on top of mishandling the µ prefix. Since `siemens_per_meter` was the default
  target, every conductivity value the library returned was affected: WSV at station 71160198 read
  0.0021 S/m where the correct figure is 0.2059. Only the two pairs the tests happened to cover
  (µS/m ↔ S/m) were right. All 12 pairs are now checked against 1 µS/cm = 10⁻⁴ S/m
- **Breaking**: conductivity is returned in µS/cm rather than S/m. That is the convention in
  hydrology and water quality and what the sources publish, and S/m is a large enough unit that
  rounding to 4 decimals cost real precision — 8.481 µS/cm came back as `0.0008`, a single
  significant figure, where river values run from single digits to a few thousand µS/cm. Station
  71160198 now reads 8.481–2058.642 µS/cm. Set `ts_unit_targets={"conductivity":
  "siemens_per_meter"}` for the old unit, which now also returns the correct value
- The three new `radiation_*_intensity` parameters are now listed in
  `TimeseriesRequest.interpolatable_parameters`. Without them, `interpolate()` and `summarize()`
  silently dropped the renamed radiation parameters for the affected providers
- Fixed four more provider docs rows that named parameters renamed in the code but not in the docs:
  DWD 1-minute and 5-minute `precipitation_form` → `precipitation_index`, and the `unit` cell of
  DWD DMO hourly `visibility_range`, which repeated the unit type instead of naming the unit
- **Breaking**: ECCC daily `cooling_degree_days` and `heating_degree_days` were mapped onto the
  canonical names `count_days_cooling_degree` and `count_days_heating_degree`, which mean a number
  of days. ECCC publishes the degree day total for the single day the record covers, so the values
  were degree days labelled as a count of days — for station 2 on 1979-11-02 the mean temperature
  is 6.3 °C and the reported value is 11.7, which is `18 - 6.3` and not any count. They now use
  the canonical names `heating_degree_day` and the new `cooling_degree_day`, in °Cd. The values
  are unchanged; queries using the old names against ECCC need to switch. DWD keeps both
  quantities under their own names, and is unaffected. The same two declarations exist in the
  ECCC *hourly* block and were renamed with them, but that block declares the daily field list
  wholesale and the hourly collection publishes none of those fields, so nothing there returns
  data either way — see above
- **Breaking**: ECCC `wind_direction_gust_max` is returned in degrees rather than tens of degrees.
  ECCC publishes `DIRECTION_MAX_GUST` in tens — its own docs call the column
  `Dir of Max Gust (10s deg)` — and the declaration said `degree`, so every bearing came back 10×
  too small: 17–26 across a sample where the true directions are 170–260. Because the wrong values
  still sit inside 0–360, no range check could have caught it. Found while auditing the same file
- DWD `humidity_absolute` (`absf_std`) was declared `dimensionless`. It is a mass of water vapour
  per volume of air, published in g/m³ — station 00433 reads 1.6 to 19.1. It now uses the new
  `mass_per_volume` unit type, so it is labelled g/m³ and can be converted. The values are
  unchanged
- DWD `cooling_degree_hour` (`Kuehlgradstunden`) was declared in degree days while it accumulates
  per hour, so a monthly total of 4179.8 °Ch was reported as 4179.8 °Cd — a figure no month can
  reach. It now uses the new `degree_hour` unit type. The values are unchanged

## [0.132.0] - 2026-08-04

### Changed

- Bump the minimum supported polars version to `>=1.43.0` (from `>=1.15.0`), required by the
  `explode(empty_as_null=...)` and `concat(how="horizontal_extend")` APIs used below

### Fixed

- Resolve polars and pyarrow deprecation warnings surfaced in the test suite: pass explicit
  `empty_as_null=True` to all `explode()` calls, switch `concat(how="horizontal")` to
  `how="horizontal_extend"`, and read Feather exports via `pyarrow.ipc.open_file()` instead of the
  deprecated `pyarrow.feather.read_table`. Also vectorise two per-element `map_elements` calls
  (eaufrance/hubeau, ea/hydrology) that had native polars equivalents
- Type the station response-model `state` field as nullable so the `stations` MCP tool stops rejecting
  MOSMIX/DMO stations. These forecast stations have no state and serialise `state` as `null`, but
  `_Station.state` and `_OgcFeatureProperties.state` were typed non-null, so the derived MCP output
  schema failed validation with `Output validation error: None is not of type 'string'` for every
  `mosmix`/`dmo` station listing (the same schema drift fixed for `values`/`interpolate`/`summarize`)

## [0.131.0] - 2026-08-02

### Added

- Add a DWD SWSMOS network (`dwd`/`swsmos`) exposing the road weather forecast (Straßenwetter-MOS)
  for DWD's ~1800 road weather stations. Each model run provides an hourly forecast out to +167 hours
  (selectable via `issue`, default: the latest run): air, dew-point and road surface temperature,
  liquid precipitation, precipitation probabilities and the road surface condition. This is the
  forecast counterpart to the DWD `road` observation network
- Add the DWD `10_minutes` urban climate (Stadtklima) datasets to the `dwd`/`observation` network,
  served from DWD's `climate_urban/` path (recent period only): `urban_precipitation`,
  `urban_pressure`, `urban_solar`, `urban_temperature_air` (incl. the new
  `temperature_radiant_mean_2m` parameter), `urban_temperature_extreme`, `urban_temperature_soil`,
  `urban_wind` and `urban_wind_extreme`. These complement the existing hourly urban datasets. The
  urban station-description lists are parsed by content because they frequently leave the optional
  date and Bundesland fields blank
- Add an IPMA (Portugal) observation provider (`ipma`/`observation`) backed by the key-less
  `api.ipma.pt` open-data JSON feeds. Provides near-real-time hourly observations (temperature,
  humidity, sea-level pressure, wind speed/direction, precipitation, global radiation) from ~222
  stations. Recent-only (a rolling ~1-day window), so a date range within the last day is required.
  The `-99.0` missing sentinel becomes null and the 8-point wind-direction code is converted to
  degrees
- Add an LHMT (Lithuania) observation provider (`lhmt`/`observation`) backed by the key-less
  `api.meteo.lt` JSON REST API. Provides hourly observations (temperature, humidity, wind
  speed/gust/direction, cloud cover, sea-level pressure, precipitation, snow depth) from ~52
  stations, with historical data back to roughly 2016 fetched per station and day. Settled past days
  are cached indefinitely while the current day uses a short cache
- Add a Met Office (UK) observation provider (`metoffice`/`observation`) backed by the MIDAS Open
  archive on CEDA (UK Open Government Licence). Covers eight datasets across daily and hourly
  resolution (rain, temperature, weather, wind, radiation, soil temperature). Requires a free CEDA
  account (`WD_AUTH__CEDA=<username>:<password>`); the bearer token is minted from those credentials
  and cached in-process until shortly before it expires. Multiple report types per day are collapsed
  to one value per calendar day, multi-day rain accumulations are dropped, and native units are
  normalised (e.g. visibility from decametres to metres)

### Changed

- Sharpen the `interpolate`/`summarize` endpoint descriptions (which become the MCP tool
  descriptions) and the MCP instructions so agents stop routing plain weather questions to them.
  `stations` -> `values` is now stated as the default for weather at a named place even when a
  specific past date is given, and interpolate/summarize are called out as opt-in estimates -- used
  only on explicit request or when no station with data is near the point -- because they add
  inaccuracy

### Fixed

- Type the `interpolate`/`summarize` response-model items to match what the endpoints serialise, so
  their MCP output schemas stop rejecting valid results. `_InterpolatedValuesItemDict` and
  `_SummarizedValuesItemDict` now include the `resolution`/`dataset` keys (always present in the
  rows) and type `value`/`distance_mean`/`distance`/`taken_station_id` as nullable: interpolating or
  summarizing a point with no station in reach serialises `null` for those fields, which the previous
  non-null schema rejected (the same schema drift fixed for `values` in 0.130.0)

## [0.130.0] - 2026-07-30

### Changed

- Raise stale/incorrect dependency lower bounds to honest, still-compatible floors (no change to the
  resolved/tested versions). Most importantly `fastapi>=0.115` (was `>=0.95.1`): the REST endpoints
  use Pydantic query-parameter models, a feature added in FastAPI 0.115, so the old floor advertised
  support the code never had. Also bump `httpx>=0.27`, `uvicorn>=0.30`, `duckdb>=1` (restapi/sql/
  duckdb extras), `xarray>=2024.6`, `fsspec>=2024.6`, `python-dateutil>=2.8.2`, `tabulate>=0.9`,
  `tqdm>=4.64`, `click>=8.1`, and add a lower bound to `sqlalchemy-cratedb>=0.40` (was unbounded
  below). Dev/docs groups are unchanged
- Rewrite the `history`, `summarize` and `interpolate` endpoint descriptions (which become the MCP
  tool descriptions) so small models stop mis-routing plain weather questions to them: they now say
  what each returns and that it is not measured weather -- `history` is station *metadata* history
  (name/location/sensor changes), `summarize`/`interpolate` estimate a value for a point *between*
  stations. Add a "Choosing a tool" note to the MCP instructions pointing weather questions at the
  `stations` -> `values` workflow

### Fixed

- Match station names with `WRatio` (was `token_sort_ratio`) in `filter_by_name`, so a bare place
  name finds its stations: `name="Kiel"` now returns `Kiel-Holtenau`/`Kiel-Kronshagen` instead of
  nothing (`token_sort_ratio` scored the length gap "Kiel" vs "Kiel-Holtenau" at ~47%, below the 0.8
  threshold). `WRatio` is a partial matcher, so a query that is a common sub-token (e.g. `name="Bad"`)
  matches many stations -- set `name_threshold=1.0` (keep only score-100 matches) or use the `sql`
  filter (`sql="name = 'Aach'"`) for an exact name match
- Honor the `rank` argument in `filter_by_name` (it was silently ignored, always returning up to 5
  matches): it now returns the `rank` best matches, best score first (default 1). The `stations`
  REST/CLI listing requests several name candidates by default and passes through an explicit `rank`
- Limit the `stations` listing to the requested `rank` on the REST API (`/api/stations`) and CLI
  (`stations`). A rank filter keeps every station in the frame (the `rank` limit is applied lazily
  during value collection), so a listing that asked for the N closest returned all stations instead
  -- e.g. `rank=3` near Kiel returned all 1284 DWD stations (a ~365 KB response that overwhelmed MCP
  clients). Listings now return the `rank` closest by distance
- Return `404` for the OAuth discovery paths (`/.well-known/oauth-authorization-server`,
  `/.well-known/oauth-protected-resource`) on the REST API so MCP clients treat the open `/mcp`
  server as no-auth instead of attempting (and failing) OAuth Dynamic Client Registration
- Type `value`/`quality` as `float | None` (was `str`) in the `_ValuesItemDict` response model, so
  the `/api/values` OpenAPI schema matches the numbers actually serialised. The MCP `values` tool
  derives its output schema from that model, and the wrong `str` type made FastMCP reject valid
  results with `9.0 is not of type 'string'`. This fixes the real schema instead of the previous
  workaround (`validate_output=False`), so MCP output validation is now enabled again

## [0.129.0] - 2026-07-27

### Added

- Add an optional Model Context Protocol (MCP) endpoint at `/mcp` on the REST API, exposing the data
  endpoints as MCP tools over the streamable-HTTP transport (via [FastMCP](https://gofastmcp.com/)).
  The tools are made agent-friendly (workflow `instructions`, clean tool names, hidden noise
  endpoints, permissive output validation) so even small models can drive them. Enable it with the
  `mcp` extra (`pip install wetterdienst[mcp]`), which is included in the Docker image
- Add DWD weather alerts (CAP warnings) provider (`dwd/alerts`) with Python API, CLI `alerts`
  command and REST `/api/alerts` endpoint: all active warnings, one row per alert, with a GeoJSON
  MultiPolygon geometry, on community (Gemeinde) or district (Landkreis) granularity; a `date`
  selects a historical snapshot from DWD's rolling ~48-hour window
- Parse DWD radar site BUFR products (echo top, reflectivity) into a polars DataFrame on
  `RadarResult.df`, opt-in via the `read_bufr` setting (requires the `eccodes` and `bufr` extras)
- Add RMI (Belgium) observation provider with 10-minute, hourly and daily resolution
  from the automatic weather station (AWS) network (no authentication required)
- Add CHMI (Czechia) observation provider with 10-minute, hourly, daily, monthly and annual
  resolution (no authentication required)
- Add FMI (Finland) observation provider with hourly and daily resolution
  (no authentication required)

### Changed

- Add descriptions to every field of the REST request models (stations, values, interpolate,
  summarize, history, issues). They surface in the REST API's OpenAPI schema (`/docs`) and in the
  generated MCP tool parameters, making both surfaces self-documenting.
- REST API and CLI: the `with_metadata` and `with_stations` options now default to `false` on the
  `stations`, `values`, `interpolate`, `summarize` and `history` commands/endpoints, so output
  contains just the requested data by default. Pass `with_metadata=true` / `with_stations=true`
  (or `--with_metadata=true` / `--with_stations=true`) to include the provider-metadata and station
  blocks as before.
- Reduce DWD MOSMIX/DMO KML parsing memory by streaming the zipped KML instead of
  decompressing it fully in memory (~6.5x lower peak RSS on MOSMIX-S)
- Refresh locked dependencies to their latest compatible versions (polars 1.43.1, pyarrow 25,
  fastapi 0.140.7, uvicorn 0.51, and others). Update the dev toolchain (ruff 0.16, ty 0.0.64) and
  adopt their new checks: ignore `CPY001` (no per-file copyright headers) and `PLR0917`
  (too-many-positional-arguments, sibling of the already-ignored `PLR0913`), fix a
  `log.exception()` call outside an exception handler, wrap implicitly concatenated test URLs, and
  narrow the DWD-derived available-dates set so `min()`/`max()` no longer see `datetime | None`

### Fixed

- Parse NOAA GHCN-hourly (GHCNh) timestamps from the provided ISO date column instead of
  reconstructing them from separate year/month/day/hour/minute fields
- Fix the `about fields` CLI command, which crashed with a `TypeError` because it forwarded
  `resolution` as a separate argument to `describe_fields()`
- Report coverage cleanly for metadata-less standalone networks (`dwd/radar`, `dwd/alerts`):
  `about coverage` and `/api/coverage` now return a clear message instead of crashing with an
  `AttributeError` / HTTP 500

## [0.128.0] - 2026-07-22

### Added

- Add KNMI (Netherlands) observation provider with 10-minute, hourly and daily resolution
  (requires a free KNMI Data Platform API key)
- Add DMI (Denmark) climate data observation provider with hourly, daily, monthly and
  annual resolution (no authentication required)
- Add AEMET (Spain) observation provider with hourly (real-time), daily, monthly and
  annual resolution
- Add SMHI (Sweden) observation provider with 1-minute, hourly, daily and monthly resolution
- Add Météo-France (France) synop network (subdaily, 3-hourly)
- Add Météo-France (France) observation network (6-minute, hourly, daily, monthly)
- Add MeteoSwiss (Switzerland) observation provider with 10-minute, hourly, daily, monthly and annual resolution

### Changed

- Reduce the memory footprint of aggregated value results (`.values.all()`) by storing the
  `station_id`, `resolution`, `dataset` and `parameter` columns as polars `Enum` instead of `String`
  (roughly halves the size of tidy frames); note that the dtype of these columns is now `Enum`. To
  get plain `String` columns back (e.g. for `.str` operations or strict dtype checks), cast them via
  `df.with_columns(pl.col(pl.Enum).cast(pl.String))`

## [0.127.0] - 2026-07-07

### Added

- `[REST API]` The `/api/coverage` endpoint now reports a `date_required` flag per
  provider/network, true if any of its resolutions require a date range for value
  queries (e.g. MET Norway Frost). Lets frontends surface this before submitting a
  query rather than after the query fails.

### Changed

- `[MET Norway Frost]` Value requests now fetch all parameters of a dataset/resolution in
  a single batched request (comma-separated `elements=`) instead of one request per
  parameter, cutting the number of HTTP requests by up to 11x for multi-parameter queries.
  Falls back to the previous per-parameter behavior (including historical time-series
  discovery) if the batched request itself returns a 404.
- `[IMGW]` File listing now prunes IMGW's per-period subfolders (named `YYYY` or
  `YYYY_YYYY`, encoding the exact date range they cover) to only those overlapping the
  requested date range, instead of recursively listing the entire directory tree on every
  request. Cuts the number of HTTP requests from ~33 (meteorology) / ~74 (hydrology) down
  to the 1-2 folders that actually matter for a given query.

### Removed

- `[IMGW]` Removed the hardcoded lat/lon override for hydrology station `150190410`,
  a workaround for a corrupted upstream CSV line from ~2024-02. The station's data has
  been clean upstream for a while, so the override had become a no-op; keeping it around
  risked silently clobbering a legitimate future coordinate change for that station.

### Fixed

- `[IMGW]` Station listing for both meteorology and hydrology no longer fails: the
  upstream station CSVs gained an extra "founding year" column and switched from a
  Windows codepage to UTF-8, which broke column parsing and produced mojibake names.
  Also fixed a station-list column-index bug (hydrology latitude/longitude were reading
  the wrong columns), a missing `return_dtype` on the lat/lon DMS-to-decimal conversion,
  and station rows no longer carrying a `resolution`/`dataset` tag, which made
  `.values.all()` fail outright.
- `[IMGW]` Hydrology value downloads now honor `WD_USE_CERTIFI`/`use_certifi`, matching
  the station list fetch and the meteorology provider. Previously it was silently ignored
  for the actual data downloads.
- `[IMGW]` Hydrology daily requests touching 2023 or later no longer crash with
  `ValueError: month must be in 1..12`. IMGW switched from twelve monthly zips per year
  to one consolidated yearly zip starting 2023, which broke the date-range parsing that
  assumed a `codz_YYYY_MM.zip` filename. Also handles the two different (and, for 2024,
  outright malformed) CSV export quirks IMGW has used for these consolidated files since,
  for both daily and monthly hydrology data: semicolon-separated unquoted rows in 2023,
  and in 2024 every row wrapped in a broken extra pair of quotes with doubled inner quotes.
- `[IMGW]` Meteorology `synop` daily requests no longer crash with
  `TypeError: '<' not supported between instances of 'NoneType' and 'NoneType'`. Unlike
  every other IMGW meteorology dataset, `synop` daily has always been archived one file
  per station per period (e.g. `2024_100_s.zip` for the station whose id ends in `100`)
  rather than one file per month across all stations, going back to at least the 1966-1970
  archive — the URL selection logic never accounted for this, so `synop` daily was
  non-functional for any date range.

## [0.126.0] - 2026-07-07

### Fixed

- `[REST API]` Station listing no longer fails with `StartDateEndDateError` for providers
  with `date_required` datasets (e.g. MET Norway Frost hourly, 10-minute, 6-hour). The
  date requirement only applies to value fetching, not to listing available stations. Also
  fixed a `TypeError` when constructing requests for providers that declare multi-period
  datasets but do not accept a `periods` constructor argument.

## [0.125.0] - 2026-07-06

### Added

- `[MET Norway Frost]` Add new provider `metno/frost` for the Norwegian Meteorological
  Institute's Frost API. Supports 10-minute, hourly, 6-hour, daily, monthly and annual
  resolutions with ~2200 stations across Norway. Authentication via free API key
  (`WD_AUTH__METNO_FROST` env var). Historical synoptic 6-hourly data is retrieved
  via an `availableTimeSeries` fallback that resolves the time-series-specific query
  parameters required by the Frost API.
- `[Settings]` Load `.env` files automatically via `env_file=".env"` and support nested
  env vars via `env_nested_delimiter="__"` (e.g. `WD_TS_UNIT_TARGETS__temperature=degree_fahrenheit`).
- `[Metadata]` Add `auth: bool = False` field to `MetadataModel` so providers requiring
  an API key can declare it. Defaults to `False` for all existing providers.
- `[API]` Add `is_configured() -> bool` and `is_valid() -> bool` classmethods to
  `TimeseriesRequest`. `is_configured` checks whether credentials are present (cheap,
  offline); `is_valid` probes the API to confirm they actually work (should be cached
  by the implementation). Both default to `True` for providers that need no auth.
- `[REST API]` `GET /api/coverage` (no parameters) now returns
  `{provider: {network: {auth: bool, configured: bool, valid: bool}}}` instead of
  `{provider: [network]}`, exposing per-network auth status to API consumers.
- `[REST API]` Add `GET /api/auth?provider=&network=` endpoint that returns
  `{provider, network, auth, configured, valid}` for a specific provider/network,
  allowing clients to re-check credential validity without fetching all coverage.
  `valid` is always `false` when `configured` is `false` (probe cannot run without credentials).

## [0.124.0] - 2026-06-30

### Added

- `[DWD MOSMIX / DMO]` Add `available_issues(station_id, settings)` classmethod to
  `DwdMosmixRequest` and `DwdDmoRequest` that lists the model-run datetimes currently
  available on DWD's OpenData server for a given station (MOSMIX_L single-station KMZ
  files and ICON single-station KMZ files respectively).
- `[CLI]` Add `wetterdienst issues --provider <p> --network <n> --station <id>` command
  that prints available issue datetimes as a JSON array.
- `[REST API]` Add `GET /api/issues?provider=<p>&network=<n>&station=<id>` endpoint
  returning `{"issues": ["<UTC ISO datetime>", ...]}`. Currently supported:
  `provider=dwd, network=mosmix` and `provider=dwd, network=dmo`.

### Fixed

- `[DWD MOSMIX / DMO]` Fix `issue` (and DMO `lead_time`) parameters being silently
  ignored when calling the REST API or `_get_stations_request` directly. The guard used
  `isinstance(api, DwdMosmixRequest)` where `api` is the *class* itself (not an instance),
  so the condition was always `False` and `DwdForecastDate.LATEST` was used regardless of
  the caller's intent. Changed to `issubclass` and added a `None`-guard so that omitting
  `issue` still falls through to the dataclass default (`DwdForecastDate.LATEST`).
- `[Frontend / Meteogram]` Fix x-axis tick labels overlapping massively on narrow mobile
  screens. Tick interval is now chosen based on actual chart pixel width: a 7-day MOSMIX
  forecast on a ~360 px phone uses 24-hour ticks instead of 6-hour ones (28 → 7 labels).
  Day-name annotations above the chart also shorten to weekday-only (`Mo`) when a day
  occupies fewer than 44 px, preventing header collisions on long forecasts.

## [0.123.0] - 2026-06-18

### Fixed

- `[DWD Observation]` Skip periods where all file downloads fail (empty `filenames_and_files`)
  before passing to the parser, preventing a `polars.exceptions.InvalidOperationError` from
  `pl.concat(..., how="align")` caused by a schema-less `LazyFrame` being mixed with valid ones.
- Reduce stamina retry attempts in `download_file` from 3 to 2 to limit worst-case wait time
  per file on persistent network failures.
- Add a default `aiohttp.ClientTimeout(total=30)` to `fsspec_client_kwargs` in `Settings` so
  HTTP connections time out after 30 seconds instead of hanging indefinitely.
- Wrap bare `int` timeouts in `aiohttp.ClientTimeout` inside `HTTPFileSystem.__init__` so that
  aiohttp >= 3.9 (which rejects plain int timeouts) works correctly with `fsspec_client_kwargs`.

## [0.122.0] - 2026-06-07

### Fixed

- Fix `download_file` retry mechanism: the previous `@stamina.retry` decorator was broken
  (the `on=` predicate checked `ClientResponse` instead of an exception, and all errors were
  swallowed before stamina could see them). Replaced with `stamina.retry_context` wrapping the
  `filesystem.cat_file` call directly. Retries are now triggered on `FileNotFoundError`,
  `FSTimeoutError`, `ClientConnectorError`, `ClientResponseError` and `ClientPayloadError`; all exhausted errors are
  returned as `File` objects rather than propagated.
- `[DWD Dmo]` Convert latitude and longitude from degrees and minutes to decimal degrees using `convert_dm_to_dd`.
- Fix station history parsing and add tests

## [0.121.1] - 2026-05-26

### Fixed

- Propagate `Settings.use_certifi` through `NetworkFilesystemManager.get` and the
  download helpers (`download_file`, `download_files`, `list_remote_files_fsspec`) so
  that fsspec's HTTP clients use the certifi certificate bundle when requested. This
  ensures provider code using these helpers respects the global `use_certifi` setting.
  Fixes #1669.
  Thanks to @KonstantinWaser for reporting the issue.

## [0.121.0] - 2026-05-09

### Added

- Interpolation / summarize: greatly expanded the set of interpolatable parameters
  beyond the original six. All continuous, spatially-correlated meteorological fields
  are now supported, organised into two distance classes:
    - **~40 km** (homogeneous / large-scale): all temperature variants at 2 m and 0.05 m
      (mean, max, min, last-24 h, multiday, mean-of-extremes), dew point, wet-bulb,
      wind-chill, surface temperature, soil temperatures (0.02 m – 2 m depth),
      heating/cooling degree aggregates, all humidity variants (`humidity`,
      `humidity_absolute`, `humidity_max`, `humidity_min`, `humidex`), all wind-speed
      variants and gust-max variants, wind movement, Beaufort scale, all sunshine-duration
      variants, global / diffuse / direct / long-wave radiation, all pressure variants
      (site, sea-level, reduced, max, min, tendency, vapour), total / effective / time-
      windowed cloud cover, and evapotranspiration / evaporation fields.
    - **~20 km** (heterogeneous / locally variable): all precipitation-height variants
      (including liquid, droplet, rocker, last-1 h … last-24 h, multiday, significant-
      weather, max), precipitation duration, new-snow depth and its multiday / max
      variants, and new-snow water-equivalent variants.
    - Fixes #1651 (`sunshine_duration` was silently dropped by both `interpolate` and
      `summarize` because it was absent from `interpolatable_parameters`).
- Interpolation: occurrence-threshold zeroing (previously only applied to
  `precipitation_height`) is now applied to **all** zero-inflated accumulation
  parameters: every precipitation-height variant, precipitation duration, new-snow
  depth variants, and new-snow water-equivalent variants. This prevents spurious
  small positive values when the surrounding stations recorded no event.
- Tests: five new unit tests for the occurrence-threshold logic in
  `core/interpolate.py` (`test_occurrence_threshold_*`) and two new remote
  integration tests (`test_interpolation_sunshine_duration_daily`,
  `test_interpolation_snow_depth_new_daily`).

- CLI: `--start-date` / `--end-date` options added to the `values`, `interpolate`, and
  `summarize` commands as a user-friendly alternative to the `--date` ISO-8601 interval
  syntax. Passing only `--start-date` treats it as a single-point date; passing only
  `--end-date` likewise. `--date` and `--start-date`/`--end-date` are mutually exclusive
  and raise a `UsageError` when combined.
- CLI: comprehensive `help` text added to all options across the `values`, `stations`,
  `interpolate`, and `summarize` commands, including `--provider`, `--network`,
  `--parameters`, `--periods`, all station-filtering options, `--format`, `--target`,
  `--shape`, `--humanize`, `--convert_units`, `--unit_targets`, `--skip_empty`,
  `--skip_criteria`, `--skip_threshold`, `--drop_nulls`, `--with_metadata`,
  `--with_stations`, `--pretty`, and `--issue`.

### Fixed

- Station name filtering (`filter_by_name`, `--name`) was case-sensitive, causing
  lowercase queries like `"darmstadt"` to return no results. Fixed by adding
  `processor=fuzz_utils.default_process` to the rapidfuzz call.
- NOAA GHCN hourly: adapted to upstream format changes — the station list CSV now
  contains non-integer values in the `WMO_ID` column (e.g. `"open"`), and the
  per-station PSV files renamed the station identifier column from `Station_ID` to
  `STATION`.
- DWD observation requests no longer raise `MetaFileNotFoundError` when a period's
  station description file is absent on the server (e.g. `10_minutes/precipitation/now`).
  The missing period is skipped with a warning and remaining periods are still returned.
- No internet connection no longer raises an error; instead, an empty result is
  returned. `ClientConnectorError` (TCP/DNS failures) is caught in `download_file`
  and stored as `NoInternetError` in the `File` object. All provider call sites
  return empty `DataFrame`/`LazyFrame` values accordingly. Fixes #1624.
- `NetworkFilesystemManager` now uses `threading.local()` instead of a class-level
  `dict` so each thread in `ThreadPoolExecutor`-based parallel downloads gets its
  own `WholeFileCacheFileSystem` instance, eliminating a race condition in the
  in-memory metadata cache that caused `TypeError: cannot unpack non-iterable bool
  object` at `fsspec/implementations/cached.py:716`.
- Reverted the directory-listing cache from `shelved-cache` + `cachetools` back to
  `diskcache`. `shelved-cache` wraps Python's `dbm`/`shelve`, which is not safe for
  concurrent access; parallel pytest-xdist workers sharing the same cache directory
  caused `_dbm.error` cascades and cascading test failures. `diskcache` uses SQLite
  and is both thread- and process-safe.
- `FileDirCache` mapping semantics corrected: `__getitem__` now raises `KeyError` on a
  cache miss (previously returned `None`) and short-circuits when `use_listings_cache`
  is `False`; `__contains__` uses a proper existence check so falsy cached values (e.g.
  an empty directory listing `[]`) are no longer misreported as absent; `__len__`
  delegates to the underlying cache directly instead of materialising all keys.

### Security

- `diskcache` advisory GHSA-w8v5-vhqr-4h9v (CVE-2025-69872, pickle deserialization)
  acknowledged and suppressed in `pysentry` and `dependency-review`. Exploitation
  requires write access to the local user cache directory, which is not a realistic
  attack vector for this project.
- `lxml` upgraded to 6.1.0, resolving GHSA-vfmq-68hx-4jfw (local file read via
  `resolve_entities`).

### Changed

- Station name filtering now uses `token_sort_ratio` instead of `token_set_ratio`,
  making word-order variations (e.g. `"Koeln Bonn"` → `"Köln/Bonn"`) match correctly.
  Zero regressions across all 1281 stations; 149 stations now resolve to their correct
  match when searched by exact name.
- Default fuzzy-match threshold for `filter_by_name` lowered from `0.9` to `0.8`,
  allowing single-character typos and common shorthands to match while maintaining
  100% precision.
- `name_threshold` is now exposed in the CLI (`--name-threshold`) for the `stations`
  and `values` commands, and wired through `StationsRequest` / `ValuesRequest` models
  so the REST API `/api/stations` and `/api/values` endpoints honour it automatically.
  All previously stale `0.9` defaults in stripes endpoints updated to `0.8`.

## [0.120.0] - 2026-04-11

### Added

- Add DWD Derived data for hourly climate (duett), daily soil, and monthly soil datasets,
  including parameters for evapotranspiration, soil moisture, soil temperature, frost/thaw depth,
  radiation, sunshine duration, and heating/cooling degree days, thanks @mspils and @jb-at-bdr

### Changed

- ECCC observation: migrate data retrieval from legacy CSV bulk download to
  the `api.weather.gc.ca` OGC API. Updates parameter metadata to match new
  column naming, rewrites wide-to-long pivoting to handle `*_flag` quality
  columns, and expands timezone mapping to include daylight saving variants.

### Fixed

- DWD `describe_fields`: adapt to updated PDF location and format. Description
  PDFs moved from the period subdirectory (e.g. `daily/kl/recent/`) to the
  dataset directory (`daily/kl/`). The PDF content now uses a structured table
  format with column name and description on the same line. The German section
  header changed from `Parameter` to `CSV Inhaltsbeschreibung`.

## [0.119.0] - 2026-02-17

### Added

- New API endpoint for climate stripes data

### Changed

- Improve interpolation and summary
- DWD DMO: Remove unnecessary validation for minimum dataframe length in date extraction
- Rename API endpoint /stripes/values to /stripes/image
- Migrate from `diskcache` to `cachetools` and `shelved-cache` for caching functionality. The new
  implementation uses `shelved_cache.PersistentCache` wrapping `cachetools.TTLCache` for improved
  maintainability while preserving all existing functionality and API compatibility.

### Fixed

- Update API endpoint for geosphere data retrieval

## [0.118.0] - 2026-02-01

### Added

- Implement station history retrieval; added API and request support to query historical station
  snapshots and lifecycle events (created, updated, decommissioned) by station id and dataset.
- Add `use_certifi` setting to use certifi certificate bundle instead of system certificates for
  HTTPS connections. Default is `False` for backward compatibility. Can be enabled via
  `Settings(use_certifi=True)` or environment variable `WD_USE_CERTIFI=true`.

### Changed

- Move code to src directory
- Filter By Rank: Sort stations by distance and station id
- Soften validation for numbers and integers in UI core request models

## [0.117.0] - 2026-01-03

### Added

- Restapi: Add /api/version endpoint to get current version of wetterdienst backend (used in frontend)

## [0.116.0] - 2025-12-09

### Changed

- Improve polars code, thanks @SeeBastion524

### Fixed

- Allow concatenation of station data with varying columns, thanks @jb-at-bdr
- Adjust data type of "name" column, thanks @jb-at-bdr

## [0.115.0] - 2025-11-24

### Added

- Add classifier for python 3.14
- Add new data of DWD Derived, thanks @jb-at-bdr

### Changed

- Update docker image to use python 3.14

### Fixed

- Cast value in interpolate function to float

  @ninjeanne reported that wetterdienst lately quirks when running interpolation. This issue is related to one of the
  new polars versions > 1.33.1. A shorthand fix would be to cast the value coming from the scipy interpolate function to
  a float.

## [0.114.3] - 2025-11-07

### Fixed

- \[DWD Obs\] Fix encoding issue

## [0.114.2] - 2025-11-05

### Fixed

- \[DWD DMO\] Fix path for `icon_eu` and minor fixes

## [0.114.1] - 2025-11-01

### Fixed

- Fix global import of duckdb exception in `to_target` method

## [0.114.0] - 2025-10-31

### Added

- \[DWD Obs\] Use utf8 encoding for parsing data
- Add `if_exists` argument to `to_target`
- Use more polars-native methods

### Fixed

- \[DWD Road\]: Skip empty files

### Changed

- Bump polars minimum to 1.15.0

## [0.113.0] - 2025-09-21

### Added

- Make Mosmix and DMO a lot faster for multiple stations requests

### Changed

- Bump pypdf to <7
- Make pypdf optional

## [0.112.0] - 2025-09-06

### Changed

- Switch back to `WholeFileCacheFileSystem` for caching
- Improve more things on caching
- Update uv.lock
- Polars: Set format and timezone on datetime conversion

## [0.111.0] - 2025-08-03

### Added

- Make humidity interpolatable
- Improve interpolation configuration
- Set missing `return_dtype` in fileindex function
- Set `return_dtype` for polars functions

### Changed

- Pin zarr to `>=3.1;python_version>=3.11`
- Docker: Copy uv bin from uv image
- Pin lxml to <7

### Fixed

- Parse parameters only if any are given
- Fix export for interpolated values to csv
- Round timestamps of hourly solar data to nearest hour
- Fix several polars issues
- Docker: Install chromium to fix png export

## [0.110.0] - 2025-07-23

### Added

- Make retry of `download_file` more robust
- Overhaul docs switching to `sphinx` and `myst-parser`
- Improve exception handling in restapi
- Improve download of files

### Changed

- Drop upper version pins for fsspec and tzdata
- Introduce `wetterdienst.model`, streamline others
- Bump minimum kaleido version to `0.2.2`

### Fixed

- Export: Fix influx tags and fields
- \[NOAA GHCN hourly\] Fix metadata creation
- Include resolution column in wide format
- Disallow `polars==1.31.0` due to issues

## [0.109.0] - 2025-06-03

### Changed

- Split `coordinates` and `bbox` into separate arguments
- Bump dependencies

## [0.108.0] - 2025-04-25

### Added

- Improve restapi look and add impressum
- Add uvloop and httptools for speed via `uvicorn[standard]`

### Changed

- Use dataclass everywhere
- Refactor query method
- Adjust retry of function `download_file`

### Fixed

- Fix numerous radar tests

## [0.107.0] - 2025-03-25

### Changed

- Refactor `download_file`

### Fixed

- Fix false attribute parsing by pydantic model in cli
- Fix datetime parsing for generic radar data

## [0.106.0] - 2025-03-05

### Fixed

- Improve parameter unpacking in `ParameterSearch.parse`
- Fix docker manifest

## [0.105.0] - 2025-03-01

### Added

- Add user agent to default `fsspec_client_kwargs`
- Adjust apis to track resolution and dataset (allows querying data for different resolutions and datasets in one
  request)

### Changed

- Improve date parsing across multiple apis
- Cleanup docker image
- Improve numerous apis

### Fixed

- \[WSV Pegel\] Fix characteristic values and improve date parsing

## [0.104.0] - 2025-02-15

### Changed

- Reduce the margin of the stations plot
- Make pydantic models for uis simpler
- Migrate from `sklearn+numpy` to `pyarrow` for location querying
- Remove command from Docker file
- Improve workflow for Docker
- Get rid of columns enumeration
- \[NOAA GHCN\] Improve date parsing and other fixes

## [0.103.0] - 2025-02-02

### Added

- Stripes: Replace matplotlib by plotly
- Explorer: Add download button for plot
- Split up plotting extras into `plotting` and `matplotlib`
- Interpolation/Summary: Add dataset to DataFrame
- Add plotting capabilities

### Changed

- Update docker image extras

### Removed

- Remove unused cachetools dependency

### Fixed

- Fix benchmark code
- Make fastexcel a polars extra
- Drop click-params dependency
- Make pyarrow a polars extra

## [0.102.0] - 2025-01-17

### Added

- Add cmd to docker image

### Changed

- Use `to_list()[0]` instead of `first()`

## [0.101.0] - 2025-01-13

### Added

- Move more details into `MetadataModel`

### Changed

- \[DWD Obs\] Make the download function more flexible using threadpool
- \[DWD Obs\] Cleanup parser function
- \[DWD Obs\] Improve fileindex and metaindex

### Fixed

- \[DWD Obs\] Reduce unnecessary file index calls during retrieval of data for stations with multiple files

## [0.100.0] - 2025-01-06

### Added

- Add logo for restapi
- **Breaking:** Add dedicated unit converter

  Attention: Many units are changed to be more consistent with typical meteorological units. We now use `°C` for
  temperatures. Also, length units are now separated in `length_short`, `length_medium` and `length_long` to get more
  reasonable decimals. For more information, see the new units chapter (usage/units) in the documentation.

### Changed

- Add reasonable upper bounds for dependencies

### Fixed

- Filter out invalid underscore prefixed files

## [0.99.0] - 2024-12-30

### Added

- Add setting `ts_complete=False` that allows to prevent building a complete time series

### Changed

- Docs: Change to markdown using mkdocs
- Settings: Switch to `pydantic_settings` for settings management
- Improve wetterdienst api class
- Dissolve wetterdienst notebook into examples
- Use `duckdb.sql` and ask only for WHERE clause
- Update restapi annotations
- Use `Settings` in restapi/cli core functions
- Restapi/Cli: Use pydantic models for request parameters
- Rename `dropna` to `drop_nulls`
- Change default of `drop_nulls` to True
- Replace occurrences of `dt.timezone.utc` by `ZoneInfo("UTC")`
- Improve release workflow using `uv build` and `uv publish`
- Improve docker-publish workflow to use `uv build`

## [0.98.0] - 2024-12-09

### Added

- Add support for Python 3.13

### Changed

- **Breaking:** Add new metadata model: Requests now use `parameters` instead of `parameter` and `resolution` e.g.
  `parameters=[("daily", "kl")]` instead of `parameter="kl", resolution="daily"`

### Deprecated

- Deprecate Python 3.9

## [0.97.0] - 2024-10-06

### Fixed

- DWD Road: Use correct 15 minute resolution

## [0.96.0] - 2024-10-04

### Changed

- Bump polars to `>=1.0.0`
- Change `DWDMosmixValues` and `DWDDmoValues` to follow the core `_collect_station_parameter` method
- Allow only single issue retrieving with `DWDMosmixRequest` and `DWDDmoRequest`

## [0.95.1] - 2024-09-04

### Fixed

- Fix `state` column in station list creation for DWD Observation

## [0.95.0] - 2024-08-27

### Changed

- Make fastexcel non-optional
- Remove upper dependency bounds

## [0.94.0] - 2024-08-10

### Added

- DWD Road: Add new station groups, log warning if no data is available, especially if the station group is one of the
  temporarily unavailable ones

### Fixed

- Explorer: Fix DWD Mosmix request kwargs setup

## [0.93.0] - 2024-08-06

### Fixed

- Fix multiple Geosphere parameter and unit enums
- Explorer: Fix wrap `(parameter, dataset)` in iterator
- Adjust parameter typing of apis

## [0.92.0] - 2024-07-31

### Changed

- Rename parameters
    - units in parameter names are now directly following the number
    - temperature parameters now use meter instead of cm and also have a unit
    - e.g. TEMPERATURE_AIR_MEAN_2M, CLOUD_COVER_BETWEEN_2KM_TO_7KM, PROBABILITY_PRECIPITATION_HEIGHT_GT_0_0MM_LAST_6H

### Fixed

- Bump pyarrow version to <18
- Fix EaHydrology station list parsing
- Rename `EaHydrology` to `EAHydrology`
- Fix propagation of settings through `EAHydrology` values

## [0.91.0] - 2024-07-14

### Fixed

- Fix DWD Road api

## [0.90.0] - 2024-07-14

### Changed

- Bump `environs` to <12

### Fixed

- Explorer: Fix json export

## [0.89.0] - 2024-07-03

### Fixed

- EaHydrology: Fix date parsing
- Hubeau: Use correct frequency unit
- Fix group by unpack

## [0.88.0] - 2024-06-14

### Added

- Allow passing `--listen` when running the explorer to specify the host and port

## [0.87.0] - 2024-06-06

### Added

- Add precipitation version

### Changed

- Rename warming stripes to climate stripes
- Replace custom Settings class with pydantic model

## [0.86.0] - 2024-06-01

### Changed

- Interpolation/Summary: Require start and end date
- Enable interpolation and summarization for all services

### Fixed

- Fix multiple issues with interpolation and summarization

## [0.85.0] - 2024-05-29

### Fixed

- Fix `dropna` argument for DWD Mosmix and DMO
- Adjust DWD Mosmix and DMO kml reader to parse all parameters
- Fix `to_target(duckdb)` for stations
- Fix init of `DwdDmoRequest`

## [0.84.0] - 2024-05-15

### Fixed

- Fix DWD Obs station list parsing again

## [0.83.0] - 2024-04-26

### Added

- Allow `wide` shape with multiple datasets

## [0.82.0] - 2024-04-25

### Fixed

- Adjust column specs for DWD Observation station listing
- Maintain order during deduplication
- Change threshold in `filter_by_name` to 0.0...1.0

## [0.81.0] - 2024-04-09

### Added

- Warming stripes: Add option to enable/disable showing only active stations

## [0.80.0] - 2024-04-08

### Added

- Migrate explorer to streamlit
- UI: Add warming stripes

### Changed

- Explorer: Disable higher than daily resolutions for hosted version

## [0.79.0] - 2024-03-21

### Fixed

- Fix parsing of DWD Observation stations where name contains a comma

## [0.78.0] - 2024-03-09

### Added

- Docker: Install more extras

### Fixed

- Cli/Restapi: Return empty values if no data is available

## [0.77.1] - 2024-03-08

### Fixed

- Fix setting NOAA GHCN-h date to UTC

## [0.77.0] - 2024-03-08

### Changed

- Refactor index caching -> Remove monkeypatch for fsspec

## [0.76.1] - 2024-03-03

### Fixed

- NOAA GHCN Hourly: Fix date parsing

## [0.76.0] - 2024-03-02

### Added

- Add NOAA GHCN Hourly API (also known as ISD)

## [0.75.0] - 2024-02-25

### Changed

- Remove join outer workaround for polars and use `outer_coalesce` instead
- Allow duckdb for Python 3.12 again
- Update REST API index layout
- Bump polars to 0.20.10
- Docker: Bump to Python 3.12
- Docker: Reduce image size

## [0.74.0] - 2024-02-22

### Added

- Restapi: Add health check endpoint

## [0.73.0] - 2024-02-09

### Changed

- Set upper version bound for Python to 4.0
- Make pandas optional

### Fixed

- Add temporary workaround for bugged line in IMGW Hydrology station list
- Fix parsing of dates in NOAA GHCN api

## [0.72.0] - 2024-01-13

### Added

- Allow for passing kwargs to the `to_csv` method

### Fixed

- Fix issue when using `force_ndarray_like=True` with pint UnitRegistry

## [0.71.0] - 2024-01-03

### Added

- CI: Add support for Python 3.12

### Fixed

- Fix issue with DWD DMO api

## [0.70.0] - 2023-12-30

### Added

- Docker: Enable interpolation in wetterdienst standard image

### Changed

- Replace partial with lambda in most places
- IMGW: Use ttl of 5 minutes for caching

### Fixed

- IMGW Meteorology: Drop workaround for mixed up station list to fix issue
- WSV Hydrology: Fix issue with station list characteristic values
- DWD Observation: Remove redundant replace empty string in parser
- NWS Observation: Read json data from bytes
- EA Hydrology: Read json data from bytes

## [0.69.0] - 2023-12-18

### Added

- Restapi: Unify station parameter and add alias
- Interpolation: Make maximum station distance per parameter configurable via settings

### Fixed

- Result: Convert date to string only if dataframe is not empty
- Restapi: Move restapi from /restapi to /api

## [0.68.0] - 2023-12-01

### Added

- Add example for comparing Mosmix forecast and Observation data

### Fixed

- Fix parsing of DWD Observation 1 minute precipitation data

## [0.67.0] - 2023-11-17

### Changed

- **Breaking:** Use start_date and end_date instead of from_date and to_date
- Use artificial station id for interpolation and summarization
- Rename taken station ids columns for interpolation and summarization

## [0.66.1] - 2023-11-08

### Fixed

- Add workaround for issue with DWD Observation station lists

## [0.66.0] - 2023-11-07

### Added

- Add lead time argument - one of short, long - for DWD DMO to address two versions of icon

### Changed

- Rework dict-like export formats and tests with extensive support for typing
- Improve radar access
- Style restapi landing page
- Replace timezonefinder by tzfpy

### Fixed

- Fix DWD DMO access again

## [0.65.0] - 2023-10-24

### Changed

- Cleanup error handling
- Make cli work with DwdDmoRequest API
- Cleanup cli docs

### Fixed

- Fix DWD Observation API for 5 minute data

## [0.64.0] - 2023-10-12

### Added

- Export: Add support for InfluxDB 3.x

### Changed

- Remove direct tzdata dependency
- Replace pandas read_fwf calls by polars substitutes

## [0.63.0] - 2023-10-08

### Added

- \[Streamlit\] Add sideboard with settings
- \[Streamlit\] Add station information json
- \[Streamlit\] Add units to DataFrame view and plots
- \[Streamlit\] Add JSON download

### Fixed

- Return data correctly sorted

## [0.62.0] - 2023-10-07

### Changed

- Raise minimum version of polars to 0.19.6 due to breaking changes

### Fixed

- Fix multiple issues with DwdObservationRequest API

## [0.61.0] - 2023-10-06

### Added

- Make parameters TEMPERATURE_AIR_MAX_200 and TEMPERATURE_AIR_MIN_200 summarizable/interpolatable
- Add streamlit app for DWD climate stations
- Add sql query function to streamlit app

### Fixed

- Fix imgw meteorology station list parsing
- Improve streamlit app plotting capabilities
- Fix DWD DMO api

## [0.60.0] - 2023-09-16

### Added

- Add implementation for DWD DMO

## [0.59.3] - 2023-09-11

### Fixed

- Fix DWD solar date string correction

## [0.59.2] - 2023-09-06

### Fixed

- Fix documentation and unit conversion for Geosphere 10minute radiation data

## [0.59.1] - 2023-07-18

### Fixed

- Fix Geosphere parameter names

## [0.59.0] - 2023-07-30

### Changed

- Revise type hints for parameter and station_id

### Fixed

- Fix Geosphere Observation parsing of dates in values -> thanks to @mhuber89 who discovered the bug and delivered a fix

## [0.58.1] - 2023-07-26

### Fixed

- Fix bug with Geosphere parameter case

## [0.58.0] - 2023-07-10

### Added

- Add retry to functions
- Add IMGW Hydrology API
- Add IMGW Meteorology API

### Changed

- Rename FLOW to DISCHARGE and WATER_LEVEL to STAGE everywhere

## [0.57.1] - 2023-06-28

### Fixed

- Fix pyarrow dependency

## [0.57.0] - 2023-05-15

### Added

- Sources: Add DWD Road Weather data

### Changed

- **Breaking:** Backend: Migrate from pandas to polars

  Switching to Polars may cause breaking changes for certain user-space code heavily using pandas idioms, because
  Wetterdienst now returns a [Polars DataFrame](https://pola-rs.github.io/polars/py-polars/html/reference/dataframe/).
  If you absolutely must use a pandas DataFrame, you can cast the Polars DataFrame to pandas by using the `.to_pandas()`
  method.

## [0.56.2] - 2023-05-11

### Fixed

- Fix Unit definition for RADIATION_GLOBAL

## [0.56.1] - 2023-05-10

### Fixed

- Fix JOULE_PER_SQUARE_METER definition from kilojoule/m2 to joule/m2

## [0.56.0] - 2023-05-02

### Fixed

- Update docker images
- Fix now and now_local attributes on core class

## [0.55.2] - 2023-04-20

### Fixed

- Fix precipitation index interpolation

## [0.55.1] - 2023-04-17

### Fixed

- Fix setting empty values in DWD observation data
- Fix DWD Radar composite path

## [0.55.0] - 2023-03-19

### Changed

- Drop Python 3.8 support

### Fixed

- Explorer: Fix function calls

## [0.54.1] - 2023-03-13

### Fixed

- Fix DWD Observations 1 minute fileindex

## [0.54.0] - 2023-03-06

### Changed

- SCALAR: Improve handling skipping of empty stations, especially within .filter_by_rank function
- Make all parameter levels equal for all weather services to reduce complexity in code
- Change `tidy` option to `shape`, where `shape="long"` equals `tidy=True` and `shape="wide"` equals `tidy=False`
- Naming things: All things "Scalar" are now called "Timeseries", with settings prefix `ts_`
- Drop some unnecessary enums
- Rename Environment Agency to ea in subspace

### Fixed

- CLI: Fix cli arguments with multiple items separated by comma (,)
- Fix fileindex/metaindex for DWD Observation
- DOCS: Fix precipitation height unit
- DOCS: Fix examples with "recent" period

## [0.53.0] - 2023-02-07

### Added

- CLI: Add command line options `wetterdienst --version` and `wetterdienst -v` to display version number

### Changed

- SCALAR: Change tidy option to be set to True if multiple different entire datasets are queried (in accordance with
  exporting results to json where multiple DataFrames are concatenated)
- Further cleanups
- Change Settings to be provided via initialization instead of having a singleton

## [0.52.0] - 2023-01-19

### Added

- Add Geosphere Observation implementation for Austrian meteorological data

### Changed

- RADAR: Clean up code and merge access module into api

### Fixed

- DWD MOSMIX: Fix parsing station list
- DWD MOSMIX: Fix converting degrees minutes to decimal degrees within the stations list. The previous method did not
  produce correct results on negative lat/lon values.

## [0.51.0] - 2023-01-01

### Added

- Update wetterdienst explorer with clickable stations and slightly changed layout

### Fixed

- Improve radar tests and certain dict comparisons
- Fix problem with numeric column names in method gain_of_value_pairs

## [0.50.0] - 2022-12-03

### Added

- Interpolation/Summary: Now the queried point can be an existing station laying on the border of the polygon that it's
  being checked against
- UI: Add interpolate/summarize methods as subspaces

### Changed

- Geo: Change function signatures to use latlon tuple instead of latitude and longitude
- Geo: Enable querying station id instead of latlon within interpolate and summarize
- Geo: Allow using values of nearby stations instead of interpolated values

### Fixed

- Fix timezone related problems when creating full date range

## [0.49.0] - 2022-11-28

### Added

- Add NOAA NWS Observation API
- Add Eaufrance Hubeau API for French river data (flow, stage)

### Fixed

- Fix bug where duplicates of acquired data would be dropped regarding only the date but not the parameter
- Fix NOAA GHCN access issues with timezones and empty data

## [0.48.0] - 2022-11-11

### Added

- Add example to dump DWD climate summary observations in zarr with help of xarray

### Fixed

- Fix DWD Observation urban_pressure dataset access (again)

## [0.47.1] - 2022-10-23

### Fixed

- Fix DWD Observation urban_pressure dataset access

## [0.47.0] - 2022-10-14

### Added

- Add support for reading DWD Mosmix-L all stations files

## [0.46.0] - 2022-10-14

### Added

- Add summary of multiple weather stations for a given lat/lon point (currently only works for DWDObservationRequest)

## [0.45.2] - 2022-10-11

### Fixed

- Make DwdMosmixRequest return data according to start and end date

## [0.45.1] - 2022-10-10

### Fixed

- Fix passing an empty DataFrame through unit conversion and ensure set of columns

## [0.45.0] - 2022-09-22

### Added

- Add interpolation of multiple weather stations for a given lat/lon point (currently only works for
  DWDObservationRequest)

### Fixed

- Fix access of DWD Observation climate_urban datasets

## [0.44.0] - 2022-09-18

### Added

- Add DWD Observation climate_urban datasets

### Changed

- Slightly adapt the conversion function to satisfy linter
- Adjust Docker images to fix build problems, now use python 3.10 as base
- Adjust NOAA sources to AWS as NCEI sources currently are not available
- Make explorer work again for all services setting up Period enum classes instead of single instances of Period for
  period base

### Fixed

- Fix parameter names:
    - we now use consistently INDEX instead of INDICATOR
    - index and form got mixed up with certain parameters, where actually index was measured/given but not the form
    - global radiation was mistakenly named radiation_short_wave_direct at certain points, now it is named correctly

## [0.43.0] - 2022-09-05

### Added

- Add DWD Observation climate_urban datasets

### Changed

- Use lxml.iterparse to reduce memory consumption when parsing DWD Mosmix files
- Fix Settings object instantiation
- Change logging level for Settings.cache_disable to INFO

## [0.42.1] - 2022-08-25

### Fixed

- Fix DWD Mosmix station locations

## [0.42.0] - 2022-08-22

### Changed

- Move cache settings to core wetterdienst Settings object

### Fixed

- Fix two parameter names

## [0.41.1] - 2022-08-04

### Fixed

- Fix correct mapping of periods for solar daily data which should also have Period.HISTORICAL besides Period.RECENT

## [0.41.0] - 2022-07-24

### Fixed

- Fix passing through of empty dataframe when trying to convert units

## [0.40.0] - 2022-07-10

### Changed

- Update dependencies

## [0.39.0] - 2022-06-27

### Changed

- Update dependencies

## [0.38.0] - 2022-06-09

### Added

- Add DWD Observation 5 minute precipitation dataset
- Add test to compare actually provided DWD observation datasets with the ones we made available with wetterdienst

### Fixed

- Fix one particular dataset which was not correctly included in our DWD observations resolution-dataset-mapping

## [0.37.0] - 2022-06-06

### Fixed

- Fix EA hydrology access
- Update ECCC observation methods to acquire station listing

## [0.36.0] - 2022-05-31

### Fixed

- Fix using shared FSSPEC_CLIENT_KWARGS everywhere

## [0.35.0] - 2022-05-29

### Added

- Add option to skip empty stations (option tidy must be set)
- Add option to drop empty rows (value is NaN) (option tidy must be set)

## [0.34.0] - 2022-05-22

### Added

- Add UKs Environment Agency hydrology API

## [0.33.0] - 2022-05-14

### Fixed

- Fix acquisition of DWD weather phenomena data
- Set default encoding when reading data from DWD with pandas to 'latin1'
- Fix typo in `EcccObservationResolution`

## [0.32.4] - 2022-05-14

### Fixed

- Fix acquisition of historical DWD radolan data that comes in archives

## [0.32.3] - 2022-05-12

### Fixed

- Fix creation of empty DataFrame for missing station ids
- Fix creation of empty DataFrame for annual data

## [0.32.2] - 2022-05-10

### Fixed

- Revert ssl option

## [0.32.1] - 2022-05-09

### Fixed

- Circumvent DWD server ssl certificate problem by temporary removing ssl verification

## [0.32.0] - 2022-04-24

### Added

- Add implementation of WSV Pegelonline service

### Changed

- Clean up code at several places

### Fixed

- Fix ECCC observations access

## [0.31.1] - 2022-04-03

### Fixed

- Change integer dtypes in untidy format to float to prevent loosing information when converting units

## [0.31.0] - 2022-03-29

### Changed

- Improve integrity of dataset, parameter and unit enumerations with further tests
- Change source of hourly sunshine duration to dataset sun
- Change source of hourly total cloud cover (+indicator) to dataset cloudiness

## [0.30.1] - 2022-03-03

### Fixed

- Fix naming of sun dataset
- Fix DWD Observation monthly test

## [0.30.0] - 2022-02-27

### Fixed

- Fix monthly/annual data of DWD observations

## [0.29.0] - 2022-02-27

### Added

- Add datasets EXTREME_WIND (subdaily) and MORE_WEATHER_PHENOMENA (daily)
- Add support for Python 3.10

### Changed

- Simplify parameters using only one enumeration for flattened and detailed parameters
- Rename dataset SUNSHINE_DURATION to SUN to avoid complications with similar named parameter and dataset
- Rename parameter VISIBILITY to VISIBILITY_RANGE

### Removed

- Drop Python 3.7 support

## [0.28.0] - 2022-02-19

### Added

- Extend explorer to use all implemented APIs

### Fixed

- Fix cli/restapi: return json and use NULL instead of NaN

## [0.27.0] - 2022-02-16

### Added

- Add support for Python 3.10

### Fixed

- Fix missing station ids within values result
- Add details about time interval for NOAA GHCN stations
- Fix falsely calculated station distances

### Removed

- Drop support for Python 3.7

## [0.26.0] - 2022-02-06

### Added

- Add Wetterdienst.Settings to manage general settings like tidy, humanize,...
- Instead of "kind" use "network" attribute to differ between different data products of a provider

### Changed

- Rename DWD forecast to mosmix

### Fixed

- Change data source of NOAA GHCN after problems with timeouts when reaching the server
- Fix problem with timezone conversion when having dates that are already timezone aware

## [0.25.1] - 2022-01-30

### Fixed

- Fix cli error with upgraded click ^8.0 where default False would be converted to "False"

## [0.25.0] - 2022-01-30

### Fixed

- Fix access to ECCC stations listing using Google Drive storage
- Remove/replace caching entirely by fsspec (+monkeypatch)
- Fix bug with DWD intervals

## [0.24.0] - 2022-01-24

### Added

- Add NOAA GHCN API

### Fixed

- Fix radar index by filtering out bz2 files

## [0.23.0] - 2021-11-21

### Fixed

- Add missing positional dataset argument for _create_empty_station_parameter_df
- Timestamps of 1 minute / 10 minutes DWD data now have a gap hour at the end of year 1999 due to timezone shifts

## [0.22.0] - 2021-10-01

### Added

- Introduce core Parameter enum with fixed set of parameter names. Several parameters may have been renamed!
- Add FSSPEC_CLIENT_KWARGS variable at wetterdienst.util.cache for passing extra settings to fsspec request client

## [0.21.0] - 2021-09-10

### Changed

- Start migrating from `dogpile.cache` to `filesystem_spec`

## [0.20.4] - 2021-08-07

### Added

- Enable selecting a parameter precisely from a dataset by passing a tuple like [("precipitation_height", "kl")]
  or [("precipitation_height", "precipitation_more")], or for cli/restapi use "precipitation_height/kl"
- Rename `wetterdienst show` to `wetterdienst info`, make version accessible via CLI with `wetterdienst version`

### Fixed

- Bug when querying an entire DWD dataset for 10_minutes/1_minute resolution without providing start_date/end_date,
  which results in the interval of the request being None
- Test of restapi with recent period
- Get rid of pandas performance warning from DWD Mosmix data

## [0.20.3] - 2021-07-15

### Fixed

- Bugfix acquisition of DWD radar data
- Adjust DWD radar composite parameters to new index

## [0.20.2] - 2021-06-26

### Fixed

- Bugfix tidy method for DWD observation data

## [0.20.1] - 2021-06-26

### Changed

- Update readme on sandbox developer installation

### Fixed

- Bugfix show method

## [0.20.0] - 2021-06-23

### Added

- Change cli base to click
- Add support for wetterdienst core API in cli and restapi
- Export: Use InfluxDBClient instead of DataFrameClient and improve connection handling with InfluxDB 1.x
- Export: Add support for InfluxDB 2.x
- Add show() method with basic information on the wetterdienst instance

### Fixed

- Fix InfluxDB export by skipping empty fields

## [0.19.0] - 2021-05-14

### Changed

- Make tidy method a abstract core method of Values class

### Fixed

- Fix DWD Mosmix generator to return all contained dataframes

## [0.18.0] - 2021-05-04

### Added

- Add origin and si unit mappings to services
- Use argument "si_units" in request classes to convert origin units to si, set to default
- Improve caching behaviour by introducing optional `WD_CACHE_DIR` and `WD_CACHE_DISABLE` environment variables. Thanks,
  @meteoDaniel!
- Add baseline test for ECCC observations
- Add DWD Observation hourly moisture to catalogue

## [0.17.0] - 2021-04-08

### Added

- Add capability to export data to Zarr format
- Add Wetterdienst Explorer UI. Thanks, @meteoDaniel!
- Add MAC ARM64 support with dependency restrictions
- Add support for stations filtering via bbox and name
- Add support for units in distance filtering

### Changed

- Rename station_name to name
- Rename filter methods to .filter_by_station_id and .filter_by_name, use same convention for bbox, filter_by_rank (
  previously nearby_number), filter_by_distance (nearby_distance)

### Fixed

- Radar: Verify HDF5 responses instead of returning invalid data
- Mosmix: Use cached stations to improve performance

## [0.16.1] - 2021-03-31

### Changed

- Make .discover return lowercase parameters and datasets

## [0.16.0] - 2021-03-29

### Added

- Add capability to export to Feather- and Parquet-files to I/O subsystem
- Add `--reload` parameter to `wetterdienst restapi` for supporting development
- Add Environment and Climate Change Canada API

### Changed

- Use direct mapping to get a parameter set for a parameter
- Rename DwdObservationParameterSet to DwdObservationDataset as well as corresponding columns
- Merge metadata access into Request
- Repair CLI and I/O subsystem
- Improve spreadsheet export
- Increase I/O subsystem test coverage
- Make all DWD observation field names lowercase
- Make all DWD forecast (mosmix) field names lowercase
- Rename humanize_parameters to humanize and tidy_data to tidy

### Deprecated

- Deprecate support for Python 3.6

### Fixed

- Radar: Use OPERA as data source for improved list of radar sites

## [0.15.0] - 2021-03-07

### Added

- Add StationsResult and ValuesResult to allow for new workflow and connect stations and values request
- Add accessor .values to Stations class to get straight to values for a request
- Add top-level API

### Fixed

- Fix issue with Mosmix station location

## [0.14.1] - 2021-02-21

### Fixed

- Fix date filtering of DWD observations, where accidentally an empty dataframe was returned

## [0.14.0] - 2021-02-05

### Added

- DWD: Add missing radar site "Emden" (EMD, wmo=10204)

### Changed

- Change key STATION_HEIGHT to HEIGHT, LAT to LATITUDE, LON to LONGITUDE
- Rename "Data" classes to "Values"
- Make arguments singular

### Fixed

- Mosmix stations: fix longitudes/latitudes to be decimal degrees (before they were degrees and minutes)

## [0.13.0] - 2021-01-21

### Added

- Create general Resolution and Period enumerations that can be used anywhere
- Create a full dataframe even if no values exist at requested time
- Add further attributes to the class structure
- Make dates timezone aware
- Restrict dates to isoformat

## [0.12.1] - 2020-12-29

### Fixed

- Fix 10minutes file index interval range by adding timezone information

## [0.12.0] - 2020-12-23

### Changed

- Move more functionality into core classes
- Add more attributes to the core e.g. source and timezone
- Make dates of internal data timezone aware, set start date and end date to UTC
- Add issue date to Mosmix class that actually refers to the Mosmix run instead of start date and end date
- Use Result object for every data related return
- In accordance with typical naming conventions, DWDObservationSites is renamed to DWDObservationStations, the same is
  applied to DWDMosmixSites
- The name ELEMENT is removed and replaced by parameter while the actual parameter set e.g. CLIMATE_SUMMARY is now found
  under PARAMETER_SET

### Removed

- Remove StorageAdapter and its dependencies
- Methods self.collect_data() and self.collect_safe() are replaced by self.query() and self.all() and will deprecate at
  some point

## [0.11.1] - 2020-12-10

### Fixed

- Bump `h5py` to version 3.1.0 in order to satisfy installation on Python 3.9

## [0.11.0] - 2020-12-04

### Added

- Upgrade Docker images to Python 3.8.6
- Radar data: Add non-RADOLAN data acquisition

### Changed

- Change wherever possible column type to category
- Increase efficiency by downloading only historical files with overlapping dates if start_date and end_date are given
- Use periods dynamically depending on start and end date

### Fixed

- InfluxDB export: Fix export in non-tidy format (#230). Thanks, @wetterfrosch!
- InfluxDB export: Use "quality" column as tag (#234). Thanks, @wetterfrosch!
- InfluxDB export: Use a batch size of 50000 to handle larger amounts of data (#235). Thanks, @wetterfrosch!
- Update radar examples to use `wradlib>=1.9.0`. Thanks, @kmuehlbauer!
- Fix inconsistency within 1 minute precipitation data where historical files have more columns
- Improve DWD PDF parser to extract quality information and select language. Also, add an example at
  `example/dwd_describe_fields.py` as well as respective documentation.
- Move intermediate storage of HDF out of data collection
- Fix bug with date filtering for empty/no station data for a given parameter

## [0.10.1] - 2020-11-14

### Fixed

- Upgrade to dateparser-1.0.0. Thanks, @steffen746, @noviluni and @Gallaecio! This fixes a problem with timezones on
  Windows. The reason is that Windows has no zoneinfo database and `tzlocal` switched from `pytz` to
  `tzinfo`. https://github.com/earthobservations/wetterdienst/issues/222

## [0.10.0] - 2020-10-26

### Added

- CLI: Obtain "--tidy" argument from command line
- Extend MOSMIX support to equal the API of observations
- DWDObservationData now also takes an individual parameter independent of the pre-configured DWD datasets by using
  DWDObservationParameter or similar names e.g. "precipitation_height"
- Newly introduced coexistence of DWDObservationParameter and DWDObservationParameterSet to address parameter sets as
  well as individual parameters

### Changed

- DWDObservationSites now filters for those stations which have a file on the server
- Imports are changed to submodule thus now one has to import everything from wetterdienst.dwd
- Renaming of time_resolution to resolution, period_type to period, several other relabels

## [0.9.0] - 2020-10-09

### Added

- Rename `DWDStationRequest` to `DWDObservationData`
- Add `DWDObservationSites` API wrapper to acquire station information
- Move `discover_climate_observations` to `DWDObservationMetadata.discover_parameters`
- Add PDF-based `DWDObservationMetadata.describe_fields()`

### Changed

- Large refactoring
- Make period type in DWDObservationData and cli optional
- Activate SQL querying again by using DuckDB 0.2.2.dev254. Thanks, @Mytherin!

### Fixed

- Fix coercion of integers with nans
- Fix problem with storing IntegerArrays in HDF

## [0.8.0] - 2020-09-25

### Added

- Add TTL-based persistent caching using dogpile.cache
- Add `example/radolan.py` and adjust documentation
- Export dataframe to different data sinks like SQLite, DuckDB, InfluxDB and CrateDB
- Query results with SQL, based on in-memory DuckDB
- Split get_nearby_stations into two functions, get_nearby_stations_by_number and get_nearby_stations_by_distance
- Add MOSMIX client and parser. Thanks, @jlewis91!
- Add basic HTTP API

## [0.7.0] - 2020-09-16

### Added

- Add test for Jupyter notebook
- Add function to discover available climate observations (time resolution, parameter, period type)
- Make the CLI work again and add software tests to prevent future havocs
- Use Sphinx Material theme for documentation

### Fixed

- Fix typo in enumeration for TimeResolution.MINUTES_10

## [0.6.0] - 2020-09-07

### Changed

- Enhance usage of get_nearby_stations to check for availability
- Output of get_nearby_stations is now a slice of meta_data DataFrame output

## [0.5.0] - 2020-08-27

### Added

- Add RADOLAN support
- Change module and function naming in accordance with RADOLAN

## [0.4.0] - 2020-08-03

### Added

- Extend DWDObservationData to take multiple parameters as request
- Add documentation at readthedocs.io
- \[cli\] Adjust methods to work with multiple parameters

## [0.3.0] - 2020-07-26

### Added

- Add option for data collection to tidy the DataFrame (properly reshape) with the "tidy_data" keyword and set it to be
  used as default

### Changed

- Establish code style black
- Setup nox session that can be used to run black via nox -s black for one of the supported Python versions

### Fixed

- Fix integer type casting for cases with nans in the column/series
- Fix humanizing of column names for tidy data

## [0.2.0] - 2020-07-23

### Added

- \[cli\] Add geospatial filtering by distance.
- \[cli\] Filter stations by station identifiers.
- \[cli\] Add GeoJSON output format for station data.
- Improvements to parsing high resolution data by setting specific datetime formats and changing to concurrent.futures

### Changed

- Change column name mapping to more explicit one with columns being individually addressable
- Add full column names for every individual parameter
- More specific type casting for integer fields and string fields

### Fixed

- Fix na value detection for cases where cells have leading and trailing whitespace

## [0.1.1] - 2020-07-05

### Added

- \[cli\] Add geospatial filtering by number of nearby stations.
- Simplify release pipeline
- Small updates to readme

### Changed

- Parameter, time resolution and period type can now also be passed as strings of the enumerations e.g. "
  climate_summary" or "CLIMATE_SUMMARY" for Parameter.CLIMATE_SUMMARY
- Enable selecting nearby stations by distance rather than by number of stations

### Fixed

- Change updating "parallel" argument to be done after parameter parsing to prevent mistakenly not found parameter
- Remove find_all_match_strings function and extract functionality to individual operations

## [0.1.0] - 2020-07-02

### Added

- Initial release
- Update README.md
- Update example notebook
- Add Gh Action for release
- Rename library

[Unreleased]: https://github.com/earthobservations/wetterdienst/compare/v0.137.0...HEAD
[0.137.0]: https://github.com/earthobservations/wetterdienst/compare/v0.136.0...v0.137.0
[0.136.0]: https://github.com/earthobservations/wetterdienst/compare/v0.135.0...v0.136.0
[0.135.0]: https://github.com/earthobservations/wetterdienst/compare/v0.134.0...v0.135.0
[0.134.0]: https://github.com/earthobservations/wetterdienst/compare/v0.133.0...v0.134.0
[0.133.0]: https://github.com/earthobservations/wetterdienst/compare/v0.132.0...v0.133.0
[0.132.0]: https://github.com/earthobservations/wetterdienst/compare/v0.131.0...v0.132.0
[0.131.0]: https://github.com/earthobservations/wetterdienst/compare/v0.130.0...v0.131.0
[0.130.0]: https://github.com/earthobservations/wetterdienst/compare/v0.129.0...v0.130.0
[0.129.0]: https://github.com/earthobservations/wetterdienst/compare/v0.128.0...v0.129.0
[0.128.0]: https://github.com/earthobservations/wetterdienst/compare/v0.127.0...v0.128.0
[0.127.0]: https://github.com/earthobservations/wetterdienst/compare/v0.126.0...v0.127.0
[0.126.0]: https://github.com/earthobservations/wetterdienst/compare/v0.125.0...v0.126.0
[0.125.0]: https://github.com/earthobservations/wetterdienst/compare/v0.124.0...v0.125.0
[0.124.0]: https://github.com/earthobservations/wetterdienst/compare/v0.123.0...v0.124.0
[0.123.0]: https://github.com/earthobservations/wetterdienst/compare/v0.122.0...v0.123.0
[0.122.0]: https://github.com/earthobservations/wetterdienst/compare/v0.121.1...v0.122.0
[0.121.1]: https://github.com/earthobservations/wetterdienst/compare/v0.121.0...v0.121.1
[0.121.0]: https://github.com/earthobservations/wetterdienst/compare/v0.120.0...v0.121.0
[0.120.0]: https://github.com/earthobservations/wetterdienst/compare/v0.119.0...v0.120.0
[0.119.0]: https://github.com/earthobservations/wetterdienst/compare/v0.118.0...v0.119.0
[0.118.0]: https://github.com/earthobservations/wetterdienst/compare/v0.117.0...v0.118.0
[0.117.0]: https://github.com/earthobservations/wetterdienst/compare/v0.116.0...v0.117.0
[0.116.0]: https://github.com/earthobservations/wetterdienst/compare/v0.115.0...v0.116.0
[0.115.0]: https://github.com/earthobservations/wetterdienst/compare/v0.114.3...v0.115.0
[0.114.3]: https://github.com/earthobservations/wetterdienst/compare/v0.114.2...v0.114.3
[0.114.2]: https://github.com/earthobservations/wetterdienst/compare/v0.114.1...v0.114.2
[0.114.1]: https://github.com/earthobservations/wetterdienst/compare/v0.114.0...v0.114.1
[0.114.0]: https://github.com/earthobservations/wetterdienst/compare/v0.113.0...v0.114.0
[0.113.0]: https://github.com/earthobservations/wetterdienst/compare/v0.112.0...v0.113.0
[0.112.0]: https://github.com/earthobservations/wetterdienst/compare/v0.111.0...v0.112.0
[0.111.0]: https://github.com/earthobservations/wetterdienst/compare/v0.110.0...v0.111.0
[0.110.0]: https://github.com/earthobservations/wetterdienst/compare/v0.109.0...v0.110.0
[0.109.0]: https://github.com/earthobservations/wetterdienst/compare/v0.108.0...v0.109.0
[0.108.0]: https://github.com/earthobservations/wetterdienst/compare/v0.107.0...v0.108.0
[0.107.0]: https://github.com/earthobservations/wetterdienst/compare/v0.106.0...v0.107.0
[0.106.0]: https://github.com/earthobservations/wetterdienst/compare/v0.105.0...v0.106.0
[0.105.0]: https://github.com/earthobservations/wetterdienst/compare/v0.104.0...v0.105.0
[0.104.0]: https://github.com/earthobservations/wetterdienst/compare/v0.103.0...v0.104.0
[0.103.0]: https://github.com/earthobservations/wetterdienst/compare/v0.102.0...v0.103.0
[0.102.0]: https://github.com/earthobservations/wetterdienst/compare/v0.101.0...v0.102.0
[0.101.0]: https://github.com/earthobservations/wetterdienst/compare/v0.100.0...v0.101.0
[0.100.0]: https://github.com/earthobservations/wetterdienst/compare/v0.99.0...v0.100.0
[0.99.0]: https://github.com/earthobservations/wetterdienst/compare/v0.98.0...v0.99.0
[0.98.0]: https://github.com/earthobservations/wetterdienst/compare/v0.97.0...v0.98.0
[0.97.0]: https://github.com/earthobservations/wetterdienst/compare/v0.96.0...v0.97.0
[0.96.0]: https://github.com/earthobservations/wetterdienst/compare/v0.95.1...v0.96.0
[0.95.1]: https://github.com/earthobservations/wetterdienst/compare/v0.95.0...v0.95.1
[0.95.0]: https://github.com/earthobservations/wetterdienst/compare/v0.94.0...v0.95.0
[0.94.0]: https://github.com/earthobservations/wetterdienst/compare/v0.93.0...v0.94.0
[0.93.0]: https://github.com/earthobservations/wetterdienst/compare/v0.92.0...v0.93.0
[0.92.0]: https://github.com/earthobservations/wetterdienst/compare/v0.91.0...v0.92.0
[0.91.0]: https://github.com/earthobservations/wetterdienst/compare/v0.90.0...v0.91.0
[0.90.0]: https://github.com/earthobservations/wetterdienst/compare/v0.89.0...v0.90.0
[0.89.0]: https://github.com/earthobservations/wetterdienst/compare/v0.88.0...v0.89.0
[0.88.0]: https://github.com/earthobservations/wetterdienst/compare/v0.87.0...v0.88.0
[0.87.0]: https://github.com/earthobservations/wetterdienst/compare/v0.86.0...v0.87.0
[0.86.0]: https://github.com/earthobservations/wetterdienst/compare/v0.85.0...v0.86.0
[0.85.0]: https://github.com/earthobservations/wetterdienst/compare/v0.84.0...v0.85.0
[0.84.0]: https://github.com/earthobservations/wetterdienst/compare/v0.83.0...v0.84.0
[0.83.0]: https://github.com/earthobservations/wetterdienst/compare/v0.82.0...v0.83.0
[0.82.0]: https://github.com/earthobservations/wetterdienst/compare/v0.81.0...v0.82.0
[0.81.0]: https://github.com/earthobservations/wetterdienst/compare/v0.80.0...v0.81.0
[0.80.0]: https://github.com/earthobservations/wetterdienst/compare/v0.79.0...v0.80.0
[0.79.0]: https://github.com/earthobservations/wetterdienst/compare/v0.78.0...v0.79.0
[0.78.0]: https://github.com/earthobservations/wetterdienst/compare/v0.77.1...v0.78.0
[0.77.1]: https://github.com/earthobservations/wetterdienst/compare/v0.77.0...v0.77.1
[0.77.0]: https://github.com/earthobservations/wetterdienst/compare/v0.76.1...v0.77.0
[0.76.1]: https://github.com/earthobservations/wetterdienst/compare/v0.76.0...v0.76.1
[0.76.0]: https://github.com/earthobservations/wetterdienst/compare/v0.75.0...v0.76.0
[0.75.0]: https://github.com/earthobservations/wetterdienst/compare/v0.74.0...v0.75.0
[0.74.0]: https://github.com/earthobservations/wetterdienst/compare/v0.73.0...v0.74.0
[0.73.0]: https://github.com/earthobservations/wetterdienst/compare/v0.72.0...v0.73.0
[0.72.0]: https://github.com/earthobservations/wetterdienst/compare/v0.71.0...v0.72.0
[0.71.0]: https://github.com/earthobservations/wetterdienst/compare/v0.70.0...v0.71.0
[0.70.0]: https://github.com/earthobservations/wetterdienst/compare/v0.69.0...v0.70.0
[0.69.0]: https://github.com/earthobservations/wetterdienst/compare/v0.68.0...v0.69.0
[0.68.0]: https://github.com/earthobservations/wetterdienst/compare/v0.67.0...v0.68.0
[0.67.0]: https://github.com/earthobservations/wetterdienst/compare/v0.66.1...v0.67.0
[0.66.1]: https://github.com/earthobservations/wetterdienst/compare/v0.66.0...v0.66.1
[0.66.0]: https://github.com/earthobservations/wetterdienst/compare/v0.65.0...v0.66.0
[0.65.0]: https://github.com/earthobservations/wetterdienst/compare/v0.64.0...v0.65.0
[0.64.0]: https://github.com/earthobservations/wetterdienst/compare/v0.63.0...v0.64.0
[0.63.0]: https://github.com/earthobservations/wetterdienst/compare/v0.62.0...v0.63.0
[0.62.0]: https://github.com/earthobservations/wetterdienst/compare/v0.61.0...v0.62.0
[0.61.0]: https://github.com/earthobservations/wetterdienst/compare/v0.60.0...v0.61.0
[0.60.0]: https://github.com/earthobservations/wetterdienst/compare/v0.59.3...v0.60.0
[0.59.3]: https://github.com/earthobservations/wetterdienst/compare/v0.59.2...v0.59.3
[0.59.2]: https://github.com/earthobservations/wetterdienst/compare/v0.59.1...v0.59.2
[0.59.1]: https://github.com/earthobservations/wetterdienst/compare/v0.59.0...v0.59.1
[0.59.0]: https://github.com/earthobservations/wetterdienst/compare/v0.58.1...v0.59.0
[0.58.1]: https://github.com/earthobservations/wetterdienst/compare/v0.58.0...v0.58.1
[0.58.0]: https://github.com/earthobservations/wetterdienst/compare/v0.57.1...v0.58.0
[0.57.1]: https://github.com/earthobservations/wetterdienst/compare/v0.57.0...v0.57.1
[0.57.0]: https://github.com/earthobservations/wetterdienst/compare/v0.56.2...v0.57.0
[0.56.2]: https://github.com/earthobservations/wetterdienst/compare/v0.56.1...v0.56.2
[0.56.1]: https://github.com/earthobservations/wetterdienst/compare/v0.56.0...v0.56.1
[0.56.0]: https://github.com/earthobservations/wetterdienst/compare/v0.55.2...v0.56.0
[0.55.2]: https://github.com/earthobservations/wetterdienst/compare/v0.55.1...v0.55.2
[0.55.1]: https://github.com/earthobservations/wetterdienst/compare/v0.55.0...v0.55.1
[0.55.0]: https://github.com/earthobservations/wetterdienst/compare/v0.54.1...v0.55.0
[0.54.1]: https://github.com/earthobservations/wetterdienst/compare/v0.54.0...v0.54.1
[0.54.0]: https://github.com/earthobservations/wetterdienst/compare/v0.53.0...v0.54.0
[0.53.0]: https://github.com/earthobservations/wetterdienst/compare/v0.52.0...v0.53.0
[0.52.0]: https://github.com/earthobservations/wetterdienst/compare/v0.51.0...v0.52.0
[0.51.0]: https://github.com/earthobservations/wetterdienst/compare/v0.50.0...v0.51.0
[0.50.0]: https://github.com/earthobservations/wetterdienst/compare/v0.49.0...v0.50.0
[0.49.0]: https://github.com/earthobservations/wetterdienst/compare/v0.48.0...v0.49.0
[0.48.0]: https://github.com/earthobservations/wetterdienst/compare/v0.47.1...v0.48.0
[0.47.1]: https://github.com/earthobservations/wetterdienst/compare/v0.47.0...v0.47.1
[0.47.0]: https://github.com/earthobservations/wetterdienst/compare/v0.46.0...v0.47.0
[0.46.0]: https://github.com/earthobservations/wetterdienst/compare/v0.45.2...v0.46.0
[0.45.2]: https://github.com/earthobservations/wetterdienst/compare/v0.45.1...v0.45.2
[0.45.1]: https://github.com/earthobservations/wetterdienst/compare/v0.45.0...v0.45.1
[0.45.0]: https://github.com/earthobservations/wetterdienst/compare/v0.44.0...v0.45.0
[0.44.0]: https://github.com/earthobservations/wetterdienst/compare/v0.43.0...v0.44.0
[0.43.0]: https://github.com/earthobservations/wetterdienst/compare/v0.42.1...v0.43.0
[0.42.1]: https://github.com/earthobservations/wetterdienst/compare/v0.42.0...v0.42.1
[0.42.0]: https://github.com/earthobservations/wetterdienst/compare/v0.41.1...v0.42.0
[0.41.1]: https://github.com/earthobservations/wetterdienst/compare/v0.41.0...v0.41.1
[0.41.0]: https://github.com/earthobservations/wetterdienst/compare/v0.40.0...v0.41.0
[0.40.0]: https://github.com/earthobservations/wetterdienst/compare/v0.39.0...v0.40.0
[0.39.0]: https://github.com/earthobservations/wetterdienst/compare/v0.38.0...v0.39.0
[0.38.0]: https://github.com/earthobservations/wetterdienst/compare/v0.37.0...v0.38.0
[0.37.0]: https://github.com/earthobservations/wetterdienst/compare/v0.36.0...v0.37.0
[0.36.0]: https://github.com/earthobservations/wetterdienst/compare/v0.35.0...v0.36.0
[0.35.0]: https://github.com/earthobservations/wetterdienst/compare/v0.34.0...v0.35.0
[0.34.0]: https://github.com/earthobservations/wetterdienst/compare/v0.33.0...v0.34.0
[0.33.0]: https://github.com/earthobservations/wetterdienst/compare/v0.32.4...v0.33.0
[0.32.4]: https://github.com/earthobservations/wetterdienst/compare/v0.32.3...v0.32.4
[0.32.3]: https://github.com/earthobservations/wetterdienst/compare/v0.32.2...v0.32.3
[0.32.2]: https://github.com/earthobservations/wetterdienst/compare/v0.32.1...v0.32.2
[0.32.1]: https://github.com/earthobservations/wetterdienst/compare/v0.32.0...v0.32.1
[0.32.0]: https://github.com/earthobservations/wetterdienst/compare/v0.31.1...v0.32.0
[0.31.1]: https://github.com/earthobservations/wetterdienst/compare/v0.31.0...v0.31.1
[0.31.0]: https://github.com/earthobservations/wetterdienst/compare/v0.30.1...v0.31.0
[0.30.1]: https://github.com/earthobservations/wetterdienst/compare/v0.30.0...v0.30.1
[0.30.0]: https://github.com/earthobservations/wetterdienst/compare/v0.29.0...v0.30.0
[0.29.0]: https://github.com/earthobservations/wetterdienst/compare/v0.28.0...v0.29.0
[0.28.0]: https://github.com/earthobservations/wetterdienst/compare/v0.27.0...v0.28.0
[0.27.0]: https://github.com/earthobservations/wetterdienst/compare/v0.26.0...v0.27.0
[0.26.0]: https://github.com/earthobservations/wetterdienst/compare/v0.25.1...v0.26.0
[0.25.1]: https://github.com/earthobservations/wetterdienst/compare/v0.25.0...v0.25.1
[0.25.0]: https://github.com/earthobservations/wetterdienst/compare/v0.24.0...v0.25.0
[0.24.0]: https://github.com/earthobservations/wetterdienst/compare/v0.23.0...v0.24.0
[0.23.0]: https://github.com/earthobservations/wetterdienst/compare/v0.22.0...v0.23.0
[0.22.0]: https://github.com/earthobservations/wetterdienst/compare/v0.21.0...v0.22.0
[0.21.0]: https://github.com/earthobservations/wetterdienst/compare/v0.20.4...v0.21.0
[0.20.4]: https://github.com/earthobservations/wetterdienst/compare/v0.20.3...v0.20.4
[0.20.3]: https://github.com/earthobservations/wetterdienst/compare/v0.20.2...v0.20.3
[0.20.2]: https://github.com/earthobservations/wetterdienst/compare/v0.20.1...v0.20.2
[0.20.1]: https://github.com/earthobservations/wetterdienst/compare/v0.20.0...v0.20.1
[0.20.0]: https://github.com/earthobservations/wetterdienst/compare/v0.19.0...v0.20.0
[0.19.0]: https://github.com/earthobservations/wetterdienst/compare/v0.18.0...v0.19.0
[0.18.0]: https://github.com/earthobservations/wetterdienst/compare/v0.17.0...v0.18.0
[0.17.0]: https://github.com/earthobservations/wetterdienst/compare/v0.16.1...v0.17.0
[0.16.1]: https://github.com/earthobservations/wetterdienst/compare/v0.16.0...v0.16.1
[0.16.0]: https://github.com/earthobservations/wetterdienst/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/earthobservations/wetterdienst/compare/v0.14.1...v0.15.0
[0.14.1]: https://github.com/earthobservations/wetterdienst/compare/v0.14.0...v0.14.1
[0.14.0]: https://github.com/earthobservations/wetterdienst/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/earthobservations/wetterdienst/compare/v0.12.1...v0.13.0
[0.12.1]: https://github.com/earthobservations/wetterdienst/compare/v0.12.0...v0.12.1
[0.12.0]: https://github.com/earthobservations/wetterdienst/compare/v0.11.1...v0.12.0
[0.11.1]: https://github.com/earthobservations/wetterdienst/compare/v0.11.0...v0.11.1
[0.11.0]: https://github.com/earthobservations/wetterdienst/compare/v0.10.1...v0.11.0
[0.10.1]: https://github.com/earthobservations/wetterdienst/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/earthobservations/wetterdienst/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/earthobservations/wetterdienst/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/earthobservations/wetterdienst/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/earthobservations/wetterdienst/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/earthobservations/wetterdienst/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/earthobservations/wetterdienst/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/earthobservations/wetterdienst/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/earthobservations/wetterdienst/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/earthobservations/wetterdienst/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/earthobservations/wetterdienst/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/earthobservations/wetterdienst/releases/tag/v0.1.0

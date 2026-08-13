# Migration plan: canonical parameter model

Status: **complete**. All eight steps done; see Final state below for what is left over.
Author: drafted 2026-08-04, last updated 2026-08-12.

Replace the flat `Parameter` enum with a central parameter table that owns the properties of the
*quantity*, and reduce provider metadata declarations to the facts a provider actually knows.

## Problem

`Parameter` (`src/wetterdienst/metadata/parameter.py:8`) is 712 lines of `NAME = "NAME"`. It carries
no information beyond the string. The only thing binding it to reality is
`tests/test_api.py:139::test_metadata_parameter_names`, which asserts that every provider's
`parameter.name` is a member — and nothing else.

Everything that a canonical parameter *means* is instead declared per provider, in every
`provider/*/metadata.py`, once per occurrence:

```python
{
    "name": "temperature_air_mean_2m",
    "name_original": "tt_10",
    "unit_type": "temperature",   # implied by the name, restated at every site
    "unit": "degree_celsius",
}
```

`unit_type` is a property of the physical quantity, not of the provider. Because it is declared
1617 times instead of 484, nothing compares declaration #1 against declaration #47, and they have
drifted.

## Evidence

Measured across the 31 provider/network combos that expose a `metadata` model
(`dwd/radar` and `dwd/alerts` have none). Reproduce with all optional extras installed —
`Wetterdienst.discover()` reports a missing optional dependency as `Module ... not found`, which
silently drops `dwd/derived` and `metoffice/observation` from a bare environment:

| | count |
| --- | --- |
| parameter declarations in provider `metadata.py` files | 1692 |
| distinct canonical names in use | 501 |
| names in the `Parameter` enum | 487 (all used; the 5 dead ones were removed) |
| declarations carrying a `description` | 0 |
| names where providers disagree on `unit_type` **or** `unit` | 24 |
| names where providers disagree on `unit_type` alone | 4 |

Counts re-measured 2026-08-04 (providers added since the first draft). Note that 17 of the 501
names are `quality*` names that no provider-facing test saw before, because
`DatasetModel.__iter__` filters them out; the table covers them.

`temperature_air_mean_2m` alone is declared 72 times, all 72 with `"unit_type": "temperature"`.
Repo-wide, 1133 `unit_type` lines restate what the name already determines.

### The 4 real conflicts

`unit_type` selects the *output* unit via `UnitConverter.targets`
(`src/wetterdienst/model/unit.py:128`), so a disagreement silently changes what users get back.

```
visibility_range
  dwd/observation   hourly/visibility    length_medium  -> returns m
  dwd/road          15_minutes/data      length_medium  -> returns m
  meteofrance/synop subdaily/data        length_long    -> returns km

radiation_global
  dwd/observation   10_minutes/solar     energy_per_area -> J/cm²
  dwd/mosmix        hourly/small         energy_per_area -> J/cm²
  knmi/observation  10_minutes/data      power_per_area  -> W/cm²

radiation_sky_long_wave
  dwd/observation   10_minutes/solar     energy_per_area -> J/cm²
  meteoswiss/obs.   10_minutes/data      power_per_area  -> W/cm²

radiation_sky_short_wave_diffuse
  dwd/observation   10_minutes/solar     energy_per_area -> J/cm²
  metoffice/obs.    hourly/radiation     energy_per_area -> J/cm²
  meteoswiss/obs.   10_minutes/data      power_per_area  -> W/cm²
```

`visibility_range` is a straightforward inconsistency: same quantity, two `unit_type` buckets that
happen to share the underlying `_length` list but pick different target indices.

The radiation ones are a modelling question the current design lets us dodge: irradiation (J/cm²)
and irradiance (W/cm²) are different quantities sharing one canonical name. This needs a decision,
not just a fix (see Open decisions).

The remaining 20 conflicting names differ only in `unit`, which is correct and expected — `unit` is
the *source's* unit (DWD ships hPa, another provider ships Pa).

## Design

A central table keyed by canonical name, holding what is true of the quantity:

- `name` — canonical snake_case name (the existing vocabulary)
- `unit_type` — the quantity's unit type, feeding `UnitConverter.targets`
- `description` — one sentence, written once

### Representation

A frozen dataclass per entry, not a pydantic model:

```python
@dataclass(frozen=True, slots=True)
class CanonicalParameter:
    name: str
    unit_type: str
    description: str | None = None
```

Rationale:

- The table is hand-written source, not external input. Pydantic's value is validating untrusted
  dicts, which is why `ParameterModel` (`src/wetterdienst/model/metadata.py:35`) is a `BaseModel` —
  it is built from provider dicts via `model_validate`. The table has no such boundary.
- 484 entries are constructed at import time. A frozen slots dataclass is cheap; running pydantic
  validation 484 times per interpreter start to validate literals we wrote ourselves is not.
- `frozen=True` makes entries hashable, so they work as dict keys and set members — useful for the
  reverse lookups in steps 3 and 5.
- It matches existing practice: `TimeseriesRequest` and `ParameterSearch` are both dataclasses.

The one thing pydantic would have given us — checking that `unit_type` is a real key of
`UnitConverter.targets` — is better done once as a module-level assertion or a test than 484 times
at import.

`ParameterModel` stays a pydantic `BaseModel`. It sits at the provider-dict boundary and keeps its
current role; it just gains its `unit_type` from the table instead of from the dict.

Provider metadata keeps what only the provider knows:

- `name` — foreign key into the table
- `name_original` — the source's own code (`tt_10`, `tre200s0`)
- `unit` — the source's unit

After migration a declaration reads:

```python
{"name": "temperature_air_mean_2m", "name_original": "tt_10", "unit": "degree_celsius"},
```

`unit` stays **mandatory** even for providers that already ship canonical units. Defaulting a unit
silently is how data ends up wrong by a factor of ten with no error.

There is no per-provider `unit_type` override. A source reporting a different physical quantity
gets its own canonical name (see the `radiation_*_intensity` names added in step 2), because an
override would let one name mean two unit types -- exactly what the table exists to prevent.

## Steps

Each step is independently shippable. Step 1 changes no behaviour and is the one that pays for
itself immediately.

### 1. Introduce the table + check (additive) — **done**

- `src/wetterdienst/metadata/parameter_table.py` holds `CanonicalParameter` and the 501-entry
  `PARAMETER_TABLE`, with `PARAMETERS` as the name-keyed lookup. The `unit_type` column was
  generated from what providers already declare; 497 of 501 names were unanimous.
- The check lives in `tests/test_api.py::test_metadata_parameter_table`, **not** in
  `build_metadata_model()`. Validating 1692 declarations on every import is startup cost paid
  by every user to catch a mistake only a contributor can make; a test catches it at the same
  point in time for free. `test_parameter_table_unit_types` separately checks that every
  canonical `unit_type` is a key of `UnitConverter.targets`.
- The check asserts three things per declaration: the name is in the table, the declared
  `unit_type` matches the canonical one, and the declared `unit` is a unit of that unit type.
  The last one is the reason a name/unit mismatch cannot slip through unnoticed.
- No per-declaration escape hatch. A `unit_type_override` flag was tried and dropped: it lets a
  name mean two different unit types, which is the thing the table exists to prevent. Step 2
  resolved the deviations instead, so there is nothing left to opt out of.
- Provider metadata is otherwise unchanged and keeps declaring `unit_type`.
- `tests/test_api.py` now shares one `ALL_METADATA` list across the metadata tests, and that
  list gained `DwdDerivedMetadata`, which the two existing tests had been missing.

### 2. Resolve the conflicts — **done**

Open decision 1 resolved as **split into distinct names**. KNMI settled it: its 10-minute `qg`
is W/m² and its hourly/daily `Q` is J/cm², so one canonical name was covering irradiance and
irradiation — two quantities that no unit conversion relates without the accumulation
interval. Forcing one `unit_type` would have required a W/m² -> J/cm² conversion that
`UnitConverter` cannot express, and should not.

- Added `radiation_global_intensity`, `radiation_sky_long_wave_intensity` and
  `radiation_sky_short_wave_diffuse_intensity` (all `power_per_area`) to the table and to the
  `Parameter` enum. The `_intensity` suffix keeps the pair inside the `radiation_*` family and
  follows the `precipitation` / `precipitation_intensity` unit types that already exist.
- Repointed the 17 deviating declarations onto the new names: `knmi/observation` (1, the
  10-minute one only), `meteoswiss/observation` (13), `metno/frost` (2), `rmi/observation`
  (1 in the shared `_COMMON` list, covering three resolutions).
- Open decision 2 resolved as `length_medium`: `meteofrance/synop` `visibility_range` was the
  only `length_long` declaration of 16, so it returned km where everyone else returns m.
- Updated the 19 affected rows in `docs/data/provider/`, plus the frontend glossaries.
- `CHANGELOG.md` records both as breaking, since the affected providers' output changes.

Repo-wide there are now 0 names on which providers disagree about `unit_type` (504 names,
1692 declarations).

### 3. Remove `unit_type` from provider dicts — **done**

Shipped as removal, not as the optional step this originally described. Making it optional only
buys the ability to migrate provider by provider; doing all of it in one mechanical pass makes that
worthless, and an optional-but-still-declarable key leaves a provider free to re-declare a
`unit_type` the table already owns — the exact drift the table exists to prevent.

- `ParameterModel.unit_type` is now a property reading `PARAMETERS[self.name].unit_type`. It is
  resolved on access, not at import, so nothing is validated per declaration at startup.
- `ParameterModel` gained `extra="forbid"`, so a leftover or re-added `unit_type` fails loudly
  instead of being silently ignored (pydantic's default is `extra="ignore"`, which would have made
  the removal unverifiable). This is schema validation at the provider-dict boundary, which is
  what `ParameterModel` was already doing for every other field — not semantic validation, which
  stays in tests.
- 1575 declarations removed across 29 files (1543 standalone lines, 32 inline in single-line
  dicts). The count is lower than the 1692 declarations because several providers share parameter
  lists across resolutions.
- Verified by snapshotting `(name, name_original, unit_type, unit, description)` for all 1692
  parameters across all 31 metadata models before and after: byte-identical. That is the whole
  proof that the deletion changed nothing.
- The `unit_type` match assertion in `test_metadata_parameter_table` is gone — it compared the
  table against itself once the value was derived. What remains is the name-in-table check and the
  unit-belongs-to-unit-type check. Two new tests cover the property: that declaring a `unit_type`
  is rejected, and that an uncanonical name raises on access naming the parameter.
- `docs/contribution/services.md` — the metadata example new providers copy — had to lose it too,
  and gained prose on why a provider declares `name`/`name_original`/`unit` and nothing else.
- `discover()` (`model/request.py`) still emits `unit_type`, now derived. It is public output and
  answers "what unit will I get back", so it stays.
- `test_metadata_parameter_names` is *not* redundant after all, contrary to the original note here.
  Nothing forces the table lookup at build time by design, so an uncanonical name would otherwise
  go unnoticed until something reads `unit_type`. Keep it until step 5.

### 4. Backfill descriptions — **done**

All 504 written, in one pass rather than group by group. As predicted, no docs work was needed:
the glossary renders `description` as soon as it is set.

- Provider- and resolution-independent by design: "mean air temperature at 2 m above ground", not
  "daily mean of air temperature". The 474 names that already had a docs description were a
  reference, not a source -- most of those are resolution-specific ("annual mean of cloud cover",
  "daily mean of cloud cover" for the same name) and could not be reused verbatim.
- Three families (temperature 175, probability 65, quality 17) were composed from their parts
  rather than typed out, because spelling out 257 near-identical sentences by hand invites
  inconsistency rather than avoiding it. The composition still has to add what the name does not
  say: a depth in metres, a threshold, an averaging window. The rest were written individually.
- `test_parameter_table_descriptions` keeps it honest: every entry has one, each is a capitalised
  sentence ending in a period, and **no two entries share a description**. That last check is the
  useful one -- a repeated sentence means at least one parameter is not describing itself.
- **The correction worth remembering**: the first draft reported 504/504 coverage while silently
  mis-describing 14 parameters, because the `quality` composer had no prefix guard and acted as a
  catch-all for anything the earlier composers declined. `temperature_soil_max_bare_muck_1_8m`
  came out as "Quality flag published by the source for ...". Coverage counts prove nothing when
  the fallback always succeeds; gating each composer strictly turned the 14 into visible misses.
  A greedy `.+` in the soil-cover regex was the second half of it, splitting `bare_muck_1` / `8m`.
- Descriptions do **not** reach the REST API, CLI or MCP yet. `discover()`
  (`model/request.py`) reports name, `name_original`, `unit_type` and `unit`, and the canonical
  description is not among them -- that is step 8's job, not a gap in this one.

### Docs glossary (done alongside step 2)

- `docs/data/parameters.md` used to print the flat enum at build time. It now contains a single
  `{parameter-glossary}` directive, implemented by the local Sphinx extension
  `docs/_ext/parameter_glossary.py`, which builds a `glossary` from the table at build time.
  Nothing generated is committed, so the glossary cannot drift from the table and needs no
  sync test. (A committed-file-plus-generator-script approach was built first and replaced.)
- Every provider parameter table in `docs/data/provider/` lost its `unit type` column -- that is
  a property of the canonical name now, not of the provider -- and its parameter names became
  ``{term}`name` `` cross-references into the glossary. `unit` stays, because it really is the
  source's own. 147 tables across 79 files.
- The Sphinx `glossary` directive was chosen after checking that the alternatives do not work:
  an `attrs_inline` span id inside a table cell (`[name]{#id}`) is not resolvable cross-file,
  which a throwaway Sphinx build confirmed with `myst.xref_missing` warnings. `{term}` resolves
  cleanly under `-W` and generates the relative link itself.
- `test_docs_parameters_link_to_glossary` keeps the provider tables honest: every documented
  parameter must be canonical and linked. It checks the **`name` column only**, so the
  `original name` and `unit` columns are still unverified — and measurably stale: comparing
  `(name, name_original)` against the live metadata models finds **56 mismatched rows across 11
  pages** (worst: `wsv/pegel/dynamic.md` 21, `eccc/observation/daily.md` 11, `imgw/meteorology`
  11 across daily+monthly; ECCC's whole table still carries CSV-era original names from before the
  OGC migration). All of it predates this work. Extending the test to compare the full row against
  the metadata model would surface them, but it fails until the rows are fixed, so the fix and the
  test have to land together — its own piece of work, tracked here rather than done in passing.

This surfaced pre-existing docs drift, see Known docs drift below.

### 5. Retire the enum — **done**

Removed outright rather than deprecated in place, because the investigation turned up that it was
already unusable:

- `_PARAMETER_TYPE_SINGULAR` is `str | tuple | ParameterModel | DatasetModel`, so `parameters=`
  never accepted a `Parameter` member. Passing one raised
  `AttributeError: 'Parameter' object has no attribute 'strip'`.
- It appeared in **zero** docs pages and **zero** examples. Every `Parameter.X` in those is
  `DwdRadarParameter`, a different enum and an explicit non-goal.
- So its only possible use was spelling a name the caller then had to `.name.lower()` themselves.

That made a deprecation cycle hard to justify for 710 lines of `NAME = "NAME"` nobody could use.

**Deriving the enum from the table, as this note originally proposed, was rejected.** Drift was
already prevented by `test_parameter_table_matches_enum`, so deriving bought nothing, and the
functional `Enum` API would have destroyed the static typing and autocomplete that were the only
reason to prefer the enum over a plain string. The recommendation was written before that test
existed.

The internal migration landed first and separately: all 186 references in
`model/request.py` (126), `settings.py` (30) and `core/interpolate.py` (30) now spell the canonical
name directly, verified byte-identical across all three derived values.

- `test_internal_parameter_lists_are_canonical` replaces the typo-safety the enum provided. A
  misspelled string fails quietly -- a parameter silently never interpolated, or silently keeping
  the default 40 km radius -- so this one matters more than it looks. Confirmed against an
  injected typo.
- `test_metadata_parameter_names` **was** redundant after all, correcting the note added at step 3.
  `test_metadata_parameter_table` asserts the same membership over a superset (it covers the
  quality parameters `DatasetModel.__iter__` filters out) and reports a better message. Verified by
  injecting a non-canonical name and watching the surviving test catch it.
- `test_parameter_table_matches_enum` went with the enum; there is nothing left to sync against.

## Aftermath

Steps 1-5 make the vocabulary *consistent*. These three make it *correct*, *documented* and
*discoverable*. None of them blocks the others; 6 is the one with actual correctness at stake.

### 6. Audit every parameter/unit pairing for sanity — **done**

Step 1's check proves **internal consistency, not correctness**. It asserts the declared `unit` is
*a* unit of the canonical `unit_type` — so a provider that ships Pa but declares `hectopascal`
passes cleanly and is wrong by 100x. Nothing in the repo can currently catch that.

Worse, the drift we did find was only findable because providers *disagreed*. `visibility_range`
was caught because 15 declarations said `length_medium` and one said `length_long`. A parameter
declared by exactly one provider has nothing to disagree with, and a parameter where *all*
providers are wrong the same way looks unanimous. Unanimity was the signal used to generate the
table's `unit_type` column in step 1 (497 of 501 names were unanimous), so any shared error was
inherited by the table itself.

#### Pass 1 findings (2026-08-10) — **read, 6 defects found, all fixed in #1809 and #1810**

All 504 canonical `name -> unit_type` rows read. The column is sound for `temperature` (177),
`fraction` (97), `precipitation` (39), `length_short/medium/long`, `speed`, `angle`, `pressure`,
`energy_per_area`, `power_per_area`, `significant_weather`, `time`, `volume_per_time` and
`concentration`. Five defects, every one of them in a name declared by a **single provider** --
exactly the blind spot predicted above, since unanimity was the signal used to build the column and
one declaration has nothing to disagree with.

1. **`wave_height_max` / `wave_height_sign` (wsv/pegel) -- 100x wrong at one station.**
   Pegelonline publishes wave height in **cm at LT ALTE WESER (9460041)** and **m at MELLUMPLATE
   (9420010)**, per-timeseries. The metadata declares one fixed `centimeter`. Measured: significant
   wave height comes back as 0.07-1.32 at MELLUMPLATE and 12.66-280.6 at ALTE WESER, both labelled
   cm, for the same quantity. The unit is a property of the *timeseries*, not the parameter, so no
   single declaration can be right -- this needs the parser to read `timeseries[].unit`.
2. **`wave_period` (wsv/pegel) -- mixed scale and a dimensionally wrong unit.**
   Published as `s` at MELLUMPLATE and `1/100s` at ALTE WESER. Declared as unit `wave_period` whose
   symbol is `1/s` -- a *frequency*, not a period. `model/unit.py` carries
   `# TODO: check if this is correct` on that entry; it is not. Measured 1.59-4.05 at one station
   and 211-577 at the other, in one series.
3. **`current` (wsv/pegel) -- wrong quantity entirely.**
   `R` is `RICHTUNGSTROM` with unit `MGN`, i.e. current *direction* in degrees relative to magnetic
   north. `MGN` was read as a magnetic unit and mapped to `magnetic_field_intensity` /
   `magnetic_field_strength` (A/m). Values are 2.44-359.4, a compass bearing. Should be `angle`, and
   the canonical name should say direction. `magnetic_field_intensity` exists **only** for this one
   parameter, so it goes away with the fix.
4. **`humidity_absolute` (dwd/observation) -- g/m3 labelled dimensionless.**
   DWD `absf_std` is absolute humidity in g/m3; measured 10.1-14.5 at Berlin-Tempelhof in July,
   which is the g/m3 range. Declared `dimensionless`/`dimensionless`, so values come back
   unlabelled. The docs row even carries a `>=0,<=100` constraint, suggesting it was taken for a
   percentage. Needs a mass-per-volume unit: `concentration` is dimensionally right
   (1 g/m3 == 1 mg/l exactly) but is otherwise used for substances dissolved in water.
5. **`cooling_degree_hour` (dwd/derived) -- degree-hours declared as degree-days.**
   `Kuehlgradstunden` is a degree-*hour* sum, declared `degree_celsius_day`. It sits directly beside
   `Anzahl Kuehlstunden` and `Kuehltage`, so the source clearly distinguishes hours from days. The
   `degree_day` unit list has no hour variant, so there is currently no correct unit to declare.

Separately, and not a unit problem: requesting several wsv parameters at once where one has no data
raises `polars.exceptions.ShapeError: unable to append to a DataFrame of width 6 with a DataFrame of
width 0` from `model/values.py:355`. Reproduced with
`parameters=[('dynamic','data',p) for p in ('wave_period','current','wave_height_sign')]`.

#### Pass 1 resolution

**#1809 (wsv, breaking)** — findings 1, 2, 3 plus one only visible once the conversion table was
built, and the `ShapeError`. The three wsv findings turned out to be one root cause, not three:
pegelonline publishes the unit **per timeseries**, and its stations disagree — `W` is cm at 670
gauges, `m+NN` at 66 and `m+PNP` at 2; `LF` is µS/cm or mS/cm; `VA` m/s or cm/s; `SIGH`/`MAXH` cm or
m; `TP` s or 1/100s. No single declaration can be right. Values are now scaled to the declared unit
using the station's own reported unit, read from the station listing the request already downloads;
an unknown source unit is skipped with an error rather than reported under the wrong one. The extra
find: **`clearance_height` was declared metre while every station publishes cm** — 100x wrong
everywhere, with no per-station variance to hint at it, so only the table surfaced it.
`magnetic_field_intensity` and `wave_period` are left with no parameters and are removed.

The `m+NN` datum question is deliberately **left open**: those 66 gauges have no gauge zero, so even
correctly scaled they measure against sea level rather than the gauge datum. That is a modelling
question about what `stage` means, not a scaling bug; `gauge_zero` says which datum applies.

**#1810 (breaking)** — findings 4 and 5, plus a **sixth found while checking 5**: ECCC daily and
hourly `cooling_degree_days`/`heating_degree_days` were mapped onto `count_days_*`, which mean a
number of days. ECCC publishes the degree-day total for the single day the record covers — station 2
on 1979-11-02 has mean 6.3 °C and value 11.7, which is `18 - 6.3` and cannot be a count (fractional,
and greater than the one day requested). The existing test fixture already carried 11.7 beside 6.3;
the evidence was in the repo and had simply never been read that way. DWD keeps both quantities
under separate names (`Monatsgradtage` vs `Anzahl Heiztage`), which is what the canonical names were
built for — only ECCC conflated them.

Two unit types were added despite the non-goal, both because no existing type could express the
quantity: `mass_per_volume` (shares its unit list with `concentration`, differing only in default
target — mg/l for water chemistry, g/m³ for vapour in air, and 1 mg/l *is* 1 g/m³, exactly the
`length_short`/`medium`/`long` pattern) and `degree_hour` (kept apart from `degree_day` so an
hourly accumulation is not converted to and reported per day). Net across both PRs the count is
unchanged at 23, since #1809 removes two. **No values change in #1810** — only labels, and ECCC's
names.

Noticed and **not** fixed: ECCC's *hourly* resolution declares the daily parameter set
(`max_temperature`, `snow_on_ground`, the degree days), none of which appear in ECCC hourly CSVs.
The block looks copied from daily. Pre-existing, and wants its own investigation.

Two passes, in this order:

1. **The canonical column** — read all 504 `name -> unit_type` rows top to bottom and judge them.
   This is one focused sitting, needs no network, and is the higher-leverage half: a wrong
   `unit_type` picks the wrong output unit for *every* provider reporting that name.
2. **The per-provider `unit`** — is it really what the source ships? 1692 declarations is too many
   to check by hand, so prioritise:
   - names declared by **exactly one provider** (no cross-check possible, so no existing signal),
   - the **24 names where providers disagree on `unit`** — expected and usually legitimate, since
     `unit` is the source's own, but it is also where a transcription error would hide,
   - anything whose unit was inferred rather than read out of the source's documentation.

**`unit` is the unit at the point of declaration, not the unit the source publishes.** This trips
up the obvious audit method and cost one wrong "fix" already. Geosphere's API publishes 10-minute
and hourly `cglo`/`chim` in W/m², and the metadata declares `energy_per_area` /
`joule_per_square_centimeter` -- which looks exactly like the KNMI defect and is not one, because
`provider/geosphere/observation/api.py:119` already converts W/m² to J/cm² in the parser
(`* 600 / 10000` for 10 minutes, `* 3600 / 10000` for hourly). The declaration describes the value
after that conversion and is correct. Renaming it to `radiation_global_intensity` made the parser
convert to J/cm², label the result W/m², and then convert again to W/cm².

So the audit cannot compare a declaration against the source's documentation alone -- it has to
trace the parser first. Two `curl`s of the upstream metadata are not evidence.

This also exposes a genuine inconsistency worth resolving on its own: the same physical situation
(source reports irradiance, we want irradiation) is handled two ways. Geosphere pre-converts in the
parser using the accumulation interval and declares the derived unit; KNMI, MeteoSwiss, met.no and
RMI declare the source's own unit and now carry the quantity in the name. Both work. Having both is
what makes the metadata unreadable in isolation, and picking one belongs in this step.

Geosphere's is the **only** in-parser unit conversion in the whole `provider/` tree, so removing it
would eliminate the exception rather than start a migration. Two things had to be settled first,
and both now are — **this sub-item is done**, in the required order:

- ~~**`UnitConverter.targets["power_per_area"]` is `watt_per_square_centimeter`.**~~ Changed to
  `watt_per_square_meter` in #1801, which is what WMO specifies and what every source in this
  library publishes. This had to land first: removing the conversion beforehand would have briefly
  shipped Geosphere radiation in W/cm², worse than either end state.
- ~~**What users lose.**~~ Resolved in #1802 in favour of honesty over comparability. Geosphere
  10-minute/hourly `cglo`/`chim` now carry `radiation_*_intensity` names in W/m² and are no longer
  directly comparable with DWD 10-minute solar in J/cm². Daily and monthly are untouched: they use
  `cglo_j`, a *distinct upstream parameter* genuinely accumulated over the interval, which the
  conversion never touched. Confirmed against live data at station 4821 for 2022-06-01..02 before
  the change: 82851 W/m² x 0.06 = 4971.06 and 13795 W/m² x 0.36 = 4966.2, both inside the range the
  old J/cm² test asserted — so the parser was doing exactly what the metadata now declares.

There is no longer any in-parser unit conversion in the `provider/` tree. What remains open in this
step is the audit itself, both passes.

Worth considering as a cheap standing guard: a plausibility range per `unit_type` (or per name),
asserted against fetched values in the remote tests. It will not catch a subtly wrong unit, but it
catches the order-of-magnitude class -- which is the class that actually burns users -- and unlike
this audit it keeps working after the audit is over.

#### Pass 2 progress (2026-08-11) — **started, disagreement set cleared**

Inventory over all **1692** declarations: 504 distinct canonical names, **23** where providers
disagree on `unit`, **437** declared by exactly one provider.

The 23 disagreements are mostly legitimate -- sources genuinely publish K vs °C, hPa vs Pa, knots
vs m/s -- and `unit` exists precisely to record that. The risk is the **minority-of-one**
declaration, which has nothing to disagree with. Method: fetch live values from each provider,
convert to the shared target, and compare. Agreement proves nothing; an order-of-magnitude gap is
a lead.

Cleared so far, all **correct**:

- `snow_depth` smhi `meter` -- converts to max 127 cm against dwd 75 cm and geosphere 123 cm
- `snow_depth` noaa/ghcn daily `millimeter` (`snwd`) -- max 294.9 cm; the hourly declaration is cm
  and is a different upstream field, so the split is intentional
- `stage` eaufrance `millimeter` -- median 29.8 cm against wsv 124 cm
- `discharge` eaufrance `liter_per_second` -- medians differ from wsv by ~1000x, but that is small
  French streams against the Rhine and Elbe, not a unit error: per-station medians run 0.003 to
  469 m³/s as a **continuum**, with none of the two-cluster signature that exposed wsv's `W`

Checked and dismissed: dwd hourly `visibility_range` reaches 99990 m in the historical archive,
which looks like an unfiltered sentinel but occurs 2 times in 414100 rows (0.0005%) -- noise in
DWD's archive rather than a systematic code.

#### Documentation audit (2026-08-11)

Chosen over plausibility ranges because it costs no CI flakiness. 88% of the 437 single-provider
names sit in two providers -- **noaa 192** and **dwd 191** -- so this is two jobs, not twenty
(geosphere 17, eccc 12, wsv 11, imgw 8, then single digits).

**DWD: automated against DWD's own description sheets.** `provider/dwd/observation/fields.py`
already parses them for `about fields`, and the parsed description carries the unit inline
("daily mean of temperature °C"). Diffing that against every declaration gives **140 of 235
declarations checked, zero real defects**. The four apparent mismatches were artefacts of the
unit-token regex -- "J /cm^2" with a space, and "minute" spelled out -- not declaration errors.

Coverage is 30 of 58 datasets. The other 28 have no description sheet in either language: all
`urban_*`, all `subdaily/*`, `daily/weather_phenomena{,_more}`, `monthly/weather_phenomena` and
all of `annual/*`. Those need the station-description TXT files or manual reading.

Worth noting on the way past: the description URLs use hyphens
(`DESCRIPTION_obsgermany-climate-daily-kl_en.pdf`), not the underscores the obvious guess produces
-- a 404 that cost a detour and is worth checking `about fields` against.

**NOAA: the tenths question answered.** GHCN-daily publishes several elements in tenths (PRCP in
tenths of mm, TMAX/TMIN in tenths of °C), which is exactly the class of error this audit exists to
find. The parser scales them: daily `temperature_air_max_2m` returns 15.7-49.3 °C and
`precipitation_height` 0-406.9 mm, not 157-493 and 0-4069. The remaining 192 NOAA names are mostly
GHCNh and still need their element list diffed.

**NOAA: audited in full, 224 declarations, zero defects.** GHCN-daily is the riskiest provider in
the repo for this class of bug -- it publishes many elements in *tenths*, the scaling lives in a
hand-maintained `DAILY_PARAMETER_MULTIPLICATION_FACTORS` table separate from the `unit`
declaration, and NOAA is the only declarer for 192 names, so nothing cross-checks it.

Diffing the readme's tenths list against that table: **146 declared elements documented as tenths,
all 148 table entries accounted for, nothing unscaled and nothing over-scaled.** Declared units
diffed against the readme separately: no mismatches either.

Three false positives on the way, each worth recording because each would have been a wrong bug
report:

- `SN*#`/`SX*#` are soil temperature, `SN` plus a *soil-type digit* and a *depth digit*. Expanding
  `*` and `#` as "any character" matches `SNOW` and `SNWD`, which the readme documents as plain mm
  -- they looked like unscaled tenths and are not
- `MNPN`/`MXPN` looked over-scaled: their "(tenths of degrees C)" sits on a continuation line
  indented with a **tab**, which a spaces-only continuation rule drops
- `MDTX` reads "tenths of **degress** C" -- a typo in NOAA's readme, so a `"degrees c"` substring
  match misses it

`MDSF` (multiday snowfall) has **no unit at all** in the readme; `millimeter` is inferred from
`SNOW` and is the only sensible reading, but it is inferred rather than documented.

GHCNh needs no scaling: hourly temperature returns -30 to 50 °C and station pressure 940-1034 hPa
against raw values. The "⁰C to tenths" in the metadata comments means reporting *precision*, not
units of a tenth -- a distinction that would have been a 10x error if read the other way.

**The tail (54 names).** Verified:

- **wsv (11)** -- checked against pegelonline's own per-timeseries `unit` field: `CL`/`O2` mg/l,
  `PH` `--` (dimensionless), `GRU` m+NHN, `WR` Grad, `Q` m³/s, `WT`/`LT` °C, `WG` m/s, `HL` %. All
  match. Every WSV parameter is now either verified or was fixed in #1809
- **knmi `temperature_air_mean_0_1m` <- 10-minute `tg`** -- looked like a mis-mapping, because
  daily `TG` is the 1.5 m mean and maps to `temperature_air_mean_2m`. The same letters mean
  different things in the two datasets. Confirmed against live data: 0.1 m spans 3.1-30.2 °C
  against 2 m's 7.0-26.0 over the same period -- colder on clear nights, warmer in daytime sun,
  which is the near-ground signature and not something a mislabelled 2 m sensor could produce
- **geosphere (17), imgw (8), metoffice, nws, meteoswiss (1 each)** -- soil/concrete temperatures
  in °C, snow in cm, stage in cm, precipitation in mm, wind in m/s, radiation in kJ/m² and W/m².
  Consistent on inspection; none carries the shape of a scale error

#### ECCC monthly is broken, like ECCC hourly — **found 2026-08-11, not fixed**

The 11 stale `quality_*` names (`'total precip flag'`, with spaces) turned out to be the thread
end of a dead resolution. ECCC monthly fetches successfully and then **crashes**:

```
InvalidOperationError: conversion from `str` to `datetime[μs]` failed in column 'local_date'
```

`LOCAL_DATE` is `'2023-06'` for monthly -- year and month -- while the parser applies
`%Y-%m-%d %H:%M:%S`. Two independent breakages, either one fatal:

1. the date format never parses
2. `name_original` is the bulk-CSV spelling (`'total precip (mm)'`) while the API returns OGC names
   (`TOTAL_PRECIPITATION`, `COOLING_DEGREE_DAYS`), so no parameter would match even if it did

So ECCC has **two** non-functional resolutions: hourly (declares the daily field list, which the
hourly collection does not publish) and monthly (above). Only daily works. Both predate this
migration and both want their own fix.

**Still open in pass 2** (updated 2026-08-11, after the documentation audit below):

- **dwd, 95 declarations in 28 datasets that ship no description sheet in either language** -- all
  `urban_*`, all `subdaily/*`, `daily/weather_phenomena{,_more}`, `monthly/weather_phenomena` and
  all of `annual/*`. These need the station-description TXT files or manual reading; the automated
  diff cannot reach them
- **four disagreement minorities never individually checked**: knmi `precipitation_duration` in
  hours, dwd/road `visibility_range` in km, geosphere `cloud_cover` as decimal, and the
  Pa/kJ/knots/km-h minorities. Each is plausible on its face -- the sources really do differ -- but
  plausible is what `clearance_height` looked like too

Everything else in pass 2 is done: the other disagreement minorities, noaa in full (224/224), dwd
where documented (140/235), and the 54-name tail.

#### Pass 2 minorities resolved (2026-08-11) — 2 of 4 were defects, fixed in #1815

- **geosphere `cloud_cover_total`** declared `decimal` while Geosphere documents `bewm_mittel` as
  `1/100` and returns 0-100. The `fraction` target *is* `decimal`, so nothing converted and a
  percentage was reported as a 0-1 fraction. Corroborated across all nine other declarations of the
  name, which land at 0.64-0.88 after conversion while geosphere sat at 67. Its own `humidity` and
  `sunshine_duration_relative` already said `percent`
- **dwd/road `visibility_range`** declared `kilometer`; BUFR `0 20 001` is metres, nothing in the
  parser converts, ten other providers say metres, and the provider's own docs page said `m`
- **knmi `precipitation_duration`** is correct. This was the near-miss: KNMI's legacy ASCII export
  documents `DR` in *0.1 hour*, which would make it 10x wrong, but this provider reads the NetCDF
  dataset API and that file declares `units = h`. Answering from the well-known ASCII convention
  would have broken a correct declaration
- **the Pa/kJ/knots/km-h group** is correct; each lands alongside the majority on the shared target

**Both defects had a docs page that already carried the right unit.** The metadata had drifted away
from documentation that was right all along, in both cases. That makes the provider docs tables a
cheap independent cross-check that this audit has not been using systematically -- and a candidate
for a test, since `test_docs.py` currently validates only the *name* column.

#### Open, different class: sentinel codes reaching the output

DWD hourly and subdaily `cloud_cover_total` (`v_n`) returns raw `-1` in 189 of 93467 recent values
(0.2%), which converts to a cloud cover of **-0.125 eighths** -- not a possible value. DWD's own
English description sheet documents only `missing value = -999` for this field and says nothing
about `-1`, so what it means is a question for DWD's German conventions rather than something to
guess at. Unlike the `99990` in hourly visibility (2 rows in 414100, archive noise), this recurs
consistently. Worth a decision; deliberately not fixed here.

#### The 95 undocumented DWD declarations — sources found (2026-08-11)

The description PDFs are not the only documentation, and the gap is closed by two sources:

1. **`Metadaten_Parameter_*.txt`, shipped inside every data ZIP.** A proper semicolon table --
   `Parameter;Parameterbeschreibung;Einheit` -- one per station, present for datasets that have no
   PDF at all. Better than the PDFs for this purpose: structured rather than prose, so the unit
   comes out of a column instead of a regex over a sentence.
2. **`climate_urban/` root holds the urban DESCRIPTION PDFs.** The urban datasets appeared
   undocumented only because they live under `observations_germany/climate_urban/`, not
   `.../climate/`, and their sheets sit at the tree root rather than per dataset. My earlier
   listing returned zero files, which should have been read as a wrong URL rather than as missing
   documentation.

Audited via the ZIP route: **84 of the 95** declarations (all subdaily, annual, weather_phenomena
and 10-minute urban). The remaining 11 are the six hourly `urban_*` datasets, whose ZIPs carry no
`Metadaten_Parameter` but which have English PDFs at the `climate_urban` root.

#### Three wrong *quantities* in subdaily — found by that route, **not fixed**

Not unit errors. The declaration names a physical quantity where DWD publishes a flag or a code,
which is why no unit-level check could have caught them:

| declared | DWD `Metadaten_Parameter` | live values |
| --- | --- | --- |
| `temperature_air_mean_0_05m` °C <- `E_TF_TER` | "Eisansatz bei der Messung der Feuchttemperatur", **YES/NO** | only 0.0 and 1.0 |
| `temperature_soil_mean_0_05m` °C <- `EK_TER` | "Terminwerte des Erdbodenzustand", **CODE** | 0-9, exactly 10 distinct |
| `visibility_range` m <- `VK_TER` | "Terminwerte Sichtweite", **CODE** | 0-9, exactly 10 distinct |

`visibility_range` converts to metres, so a user asking for subdaily visibility gets "5 metres" for
what is a visibility class.

**Resolved 2026-08-11**: named and fixed in #1815 as `temperature_wet_ice_formation`,
`soil_state_index` and `visibility_range_class`, all dimensionless, following the table's
convention for coded values. A fourth defect surfaced while checking them -- `tf_ter` is the wet
bulb temperature declared as `temperature_air_mean_2m`, contradicting DWD's own hourly dataset
which maps the same quantity to `temperature_wet_mean_2m`; that one needed no new name.

The hourly `urban_*` datasets were audited against the PDFs at the `climate_urban` tree (11
declarations, all correct), so **all 95 are now done**.

`visibility_range_index` was deliberately not reused for `vk_ter`. Note that **`visibility_range_index` is not
the answer for `VK_TER`**: it currently means DWD's `v_vv_i`, "visibility index, noting how the
measurement is taken" (P = person, I = instrument) -- a *method* indicator. Reusing it would put
two quantities under one name, which is the thing the table exists to prevent. Same shape as the
irradiance/irradiation split in step 2, and the same kind of decision as `DAYS_WITH_*`, `NORMAL_*`
and `humidex`.

### 7. Add the source's own parameter descriptions — **done**, inverted

Distinct from step 4. Step 4 writes **one canonical sentence per quantity**, provider-independent
("what is `temperature_air_mean_2m`"). This step records **what a given provider's `name_original`
means in that provider's own words** ("what is DWD's `TT_TU`") — measurement method, instrument,
sampling, caveats. Both are wanted; they answer different questions.

The slot already exists: `ParameterModel.description` (`model/metadata.py`) is declared and
**nothing in `src/` reads or writes it** — 0 of 1692 declarations populate it, and no consumer
looks. So this step fills a field that is currently dead, and step 4 fills the table's.

DWD is the obvious starting point and is further along than it looks. `wetterdienst about fields`
(`ui/cli.py:777`) already fetches and parses the DWD description PDFs at runtime, via
`provider/dwd/observation/fields.py` and `util/pdf.py`. The extraction is written. What is missing
is that the result is (a) fetched over the network on every call, (b) DWD-observation only, (c)
dumped as `pformat(dict(...))` rather than attached to the parameters, and so (d) invisible to the
docs, the REST API and MCP.

**Open question — where the text lives.** Two options:

- *Baked into `metadata.py`*: available offline, rendered into the provider docs tables (whose
  `description` column already exists, hand-written, on the dwd pages), and served by REST/MCP for
  free. Costs a large one-time transcription and the text goes stale silently when upstream
  revises a PDF.
- *Fetched at runtime*, as `about fields` does today: never stale, but network-dependent, only
  works where a machine-readable source exists, and cannot appear in built docs.

Baking in is probably right — it is transcription of upstream prose, not generation from our own
data, so it is not the committed-generated-artifact pattern we avoid elsewhere. But note the
licensing dimension: reproducing DWD's PDF text wholesale in the repo is a redistribution question,
not just an engineering one, and should be checked against their terms before bulk transcription.
Paraphrasing sidesteps it at the cost of fidelity.

### 8. Expose parameter discovery in the CLI, REST API and MCP — **done**

`coverage` (`ui/restapi.py:297`, `ui/cli.py` `about coverage`) already answers the **structural**
question: which providers, networks, resolutions, datasets and parameter *names* exist. What no
interface answers is the **semantic** one: what does this parameter mean, and what unit will I get
back? Today a user has to read the docs glossary to find out.

The table makes this trivial to serve, and the plumbing is mostly free:

- **REST**: one endpoint over `PARAMETER_TABLE` — name, `unit_type`, the `UnitConverter.targets`
  output unit, the canonical description (step 4), and optionally which providers declare it plus
  their `name_original` and source `unit` (step 7).
- **MCP**: nearly free. `ui/mcp.py` generates tools from the REST OpenAPI schema, so a new endpoint
  becomes a tool by adding it to the friendly-name map and keeping it out of the exclusion list.
  The endpoint docstring becomes the tool description.
- **CLI**: the only one needing real wiring. It belongs in the existing `about` group, next to
  `coverage` and `fields`.

**Naming.** `glossary` is the recommendation, for a specific reason rather than symmetry with the
docs: the obvious alternative, `parameters`, collides with the `parameters` request field that
every other command and endpoint already takes, and for an LLM driving the MCP tools that collision
is a live failure mode -- we have already been bitten by tool descriptions that read ambiguously
(see the MCP small-model notes). `glossary` reads unambiguously as "look up what a term means" and
cannot be confused with `coverage` ("what is available"). CLI spelling would be
`wetterdienst about glossary`.

This is shippable **before** step 4. With no descriptions yet it still answers "what unit will I
get back", which is the question the four `unit_type` conflicts in step 2 show users cannot
currently answer. Descriptions then enrich it in place.

## Open decisions

1. ~~**Radiation: one name or two?**~~ Resolved in step 2: two names, `radiation_*` for
   irradiation and `radiation_*_intensity` for irradiance.
2. ~~**`visibility_range`: `length_medium` (m) or `length_long` (km)?**~~ Resolved: `length_medium`.
3. ~~**Table format.**~~ Resolved: Python module, alphabetically sorted.
4. **Should the table also own a canonical `unit`?** Out of scope here — `UnitConverter.targets`
   already serves that role, and merging the two concepts is a separate change.
5. ~~**Where do source descriptions live** (step 7) — baked in or fetched at runtime?~~ Resolved:
   baked into `metadata/source_descriptions.py` and applied by `build_metadata_model`. The
   redistribution question that blocked it had a published answer all along — DWD CDC is CC BY 4.0
   (`https://opendata.dwd.de/climate_environment/CDC/Terms_of_use.txt`), which permits
   redistribution and adaptation with attribution. It was parked three times before anyone looked
   it up.
6. ~~**Name of the discovery command** (step 8).~~ Resolved: `glossary`, shipped in #1806.

## Final state (2026-08-12)

All eight steps done, across six merged PRs: #1809 (wsv), #1810 (unit types), #1811 (conductivity),
#1814 (eccc hourly/monthly), #1815 (six declarations), #1816 (descriptions), on top of the earlier
#1801-#1808.

| | |
| --- | --- |
| declarations audited | ~1690, every one |
| defects found and fixed | 12 |
| canonical parameters added | 15 (505 -> 520) |
| parameter descriptions served | 1057, via `discover()` -> REST, MCP, CLI |

**What the audit actually caught**, in the order the layers were peeled back. Pass 1 read the
canonical `unit_type` column and found six, all in single-provider names -- the predicted blind
spot, since unanimity was the signal used to build the column. Pass 2 read the per-provider `unit`
and found six more, of which four were the *wrong quantity* rather than the wrong unit: a yes/no
ice flag declared as a temperature, a ground-state code as a soil temperature, a visibility class
as metres, a wet bulb reading as air temperature. No unit-level check could have caught those, and
no cross-provider comparison either, since all four are DWD-only names.

**The two methods that did the work.** Cross-provider comparison of live values, which finds any
name at least two providers declare; and the sources' own documentation, which is the only thing
that reaches the 437 single-provider names. The second only became possible after noticing that
DWD ships `Metadaten_Parameter_*.txt` inside every data ZIP -- a structured
`Parameter;Parameterbeschreibung;Einheit` table, present for the 28 datasets that have no
description PDF at all.

**Three false-positive traps**, each of which would have been a wrong bug report, recorded so they
are not re-derived: `SN*#`/`SX*#` expand over digits, not any character, or they swallow `SNOW` and
`SNWD`; NOAA continues a line with a tab, so a spaces-only rule drops "(tenths of degrees C)"; and
`MDTX` says "degress", so a substring match on "degrees" misses it.

### Left over

- **`DatasetModel.description` (0/148) and `ResolutionModel.description` (0/78)** are still dead
  slots. The same inversion applies and there is no licensing question at all -- the provider docs
  pages already carry that text, written here.
- **28 DWD datasets** document their fields only inside the ZIPs, in German. Translating is
  adaptation rather than transcription, which is a decision rather than a task.
- **`visibility_range_index` and `cloud_cover_total_index`** are attached to DWD's `v_vv_i` and
  `v_n_i`, which are *measurement method* indicators (P = person, I = instrument), while both
  descriptions say "coded value". Fixing it means renaming existing parameters.
- **DWD cloud cover returns a raw `-1`** in 0.2% of values, which converts to -0.125 eighths -- not
  a possible value. DWD's English sheet documents only `-999` as missing and says nothing about
  `-1`, so what it means is a question for their German conventions rather than something to guess.
- **ECCC hourly and monthly are repaired but thin**: `DAYS_WITH_*` and `NORMAL_*` are declared now,
  `WEATHER_ENG_DESC` is not, because it is free text and the value schema casts to `Float64`.
- **`test_api_ea_hydrology` fails on every job of every run.** EA rate-limits the matrix, which
  hits it from every job at once. #1812 fixed this with a backoff and a scoped `xfail`, and #1813
  stopped eight providers reporting a failed download as "no data"; both were **closed unmerged**
  by maintainer decision on 2026-08-12. The work is recoverable at `e84de100` and `6602af18`.

### Worth keeping from the process

- **Verify in both directions.** Every fix here was checked for the thing it should *not* break as
  well as the thing it should: a 404 stays routine while a timeout raises; absence stays absence
  while an outage becomes an error. One-directional checks passed on several changes that were
  wrong.
- **A regression test that passes before the fix is worthless.** The ECCC and WSV tests were each
  run against the unfixed code and confirmed to fail with the original error.
- **CI catching a local pass is the good case.** ECCC value requests were truncated to 500 records;
  it passed locally because the arbitrary slice happened to contain the sampled month, and failed
  on every CI job because it did not. The test was right and the fetch was wrong.
- **Docs and model drifted in both directions.** Twice the docs were right and the metadata wrong;
  once the reverse. Both copies existing is the defect; the guard added in #1816 is the fix.

## Non-goals

- Changing the canonical name vocabulary itself. Existing names stay as they are (step 2 added
  three new names, but renamed none).
- Changing `UnitConverter` or the set of unit types.
- Touching `provider/dwd/radar/metadata/parameter.py`, which is a separate radar-specific enum and
  unrelated to this vocabulary.

## Known docs drift (surfaced, then closed off)

Superseded by #1816: the docs no longer own the parameter descriptions, and
`test_docs_parameter_descriptions_match_the_model` fails if a table disagrees with the model. The
*name* column was already pinned; the description column is now too. What follows is the drift that
was found before that guard existed.

Linking the provider tables required every documented parameter to exist in the table. 13 rows
did not. 9 were renames the docs had missed and were repointed at the current name (dwd
`*_indicator` -> `*_index`, geosphere/nws `pressure_air_sl` -> `pressure_air_sea_level`, nws
`pressure_air_sh` -> `pressure_air_site`, eaufrance `flow` -> `discharge`).

The remaining 4 documented parameters that no provider declares any more were held in a
`KNOWN_STALE_DOC_PARAMETERS` list until the appendix removal below deleted them outright:

- `eccc/observation/annual.md` -- `precipitation_frequency`, `precipitation_height_liquid_max`.
  The whole page was stale: eccc's metadata has daily, hourly and monthly, no annual.
- `eccc/observation/hourly.md` -- `humidex`.
- `imgw/meteorology/daily.md` -- `pressure_air_sea`.

Three of these (`humidex`, `precipitation_frequency`, `precipitation_height_liquid_max`) were
also in the appendix list of enum names no provider declares, which is consistent: they were
dropped from provider metadata and left behind in both the enum and the docs.

Separately, `test_data_coverage` in `tests/test_docs.py` had been passing vacuously since its
`PROVIDER` path pointed at `<root>/wetterdienst/provider` rather than `<root>/src/...`, so its
loop body never ran. Fixed, which then required skipping non-directories in the same walk.

## Risks

- Step 2 changes output units for a small number of provider/parameter combinations. It is a fix,
  but it is a breaking change for anyone relying on the current (inconsistent) behaviour, so it
  belongs in a minor release with a clear changelog entry.
- Step 5 touches public API and needs a deprecation period.
- Steps 3 and 4 are large mechanical diffs. Keep them separate from steps 1 and 2 so the
  behavioural changes stay reviewable.

## Appendix: enum names with no provider declaration — **removed**

These five were members no provider declared, so no request could ever return them:

```
humidex
precipitation_frequency
precipitation_height_liquid_max
time_wind_gust_max
time_wind_gust_max_1mile_or_1min
```

Removed from `Parameter` together with the four dead entries that referenced two of them in the
interpolation membership lists (`settings.py`, `core/interpolate.py`, `model/request.py` x2).
The enum is now 487 members, all of them declared by at least one provider.

The docs rows for three of them went too, which resolved the stale-docs list above:
`humidex` (eccc hourly) and `pressure_air_sea` (imgw daily) were dropped as rows, and
`docs/data/provider/eccc/observation/annual.md` was deleted outright -- `git log` on
`provider/eccc/observation/metadata.py` shows PR #1616 (the api.weather.gc.ca OGC migration)
deliberately dropped both the `annual` resolution and `hmdx`, and the docs were never updated.
The eccc network index lost its `annual.md` toctree entry and its overview prose was corrected
(it still described bulk CSV downloads and four resolutions).
`KNOWN_STALE_DOC_PARAMETERS` in `tests/test_docs.py` is gone, since nothing is stale any more.

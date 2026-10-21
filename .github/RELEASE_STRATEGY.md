# Release Strategy

This repository uses a **monorepo structure** with separate release workflows for backend and app.

## Release Types

### Backend (Python Package)
- **Tag format**: `v{major}.{minor}.{patch}` (e.g., `v0.117.0`)
- **Trigger**: GitHub Release with tag matching `v*.*.*`
- **Workflows**: 
  - `.github/workflows/release.yml` - Publishes to PyPI
  - `.github/workflows/docker-publish.yml` - Publishes Docker image to GHCR
- **Docker image**: `ghcr.io/earthobservations/wetterdienst:0.117.0`
- **Command**: `gh release create v0.117.0 --title "v0.117.0" --notes "..."`

### App (Nuxt Application)
- **Tag format**: `app-v{major}.{minor}.{patch}` (e.g., `app-v0.28.0`; the app stays 0.x, see `docs/usage/compatibility.md`)
- **Trigger**: GitHub Release with tag matching `app-v*.*.*`
- **Workflows**: 
  - `.github/workflows/app-release.yml` - Creates GitHub Release artifact
  - `.github/workflows/docker-publish-app.yml` - Publishes Docker image to GHCR
- **Docker image**: `ghcr.io/earthobservations/wetterdienst-app:0.28.0`
- **Deployment**: Railway.com (auto-deploy from main branch)
- **Command**: `gh release create app-v0.28.0 --title "App v0.28.0" --notes "..."`

> Releases up to and including 0.12.1 originally used the `frontend-` tag prefix and the
> `wetterdienst-frontend` image. The 13 historical tags were renamed to `app-v*` on the remote
> and their GitHub Releases repointed at the new tags, so `frontend-v*` no longer resolves
> anywhere. Release asset *filenames* were left as published (e.g. `frontend-v0.12.1.tar.gz`).

## Docker Images

### Backend Image
- **Triggered by**: `v*.*.*` tags
- **Registry**: `ghcr.io/earthobservations/wetterdienst`
- **Tags**: 
  - `0.117.0` (specific version)
  - `0.117` (major.minor)
  - `nightly` (daily builds)

### App Image
- **Triggered by**: `app-v*.*.*` tags
- **Registry**: `ghcr.io/earthobservations/wetterdienst-app`
- **Example**: Tag `app-v0.28.0` creates Docker tags:
  - `0.28.0` (specific version - without "app-" prefix)
  - `0.28` (major.minor)
  - `nightly` (daily builds)

**Key point**: Backend releases only build backend images, app releases only build app images.

## Creating Releases

### Release notes are not the changelog

The two are different documents with different jobs, and a release needs both:

- The **`CHANGELOG.md` section** is the record: what changed, what it means for a caller, and
  `(GH-####)`. Terse by convention — see the changelog bullet under Conventions in `AGENTS.md`.
- The **GitHub release body** is the narrative: what this release is about, which breaking changes
  need action and what to do instead, and why anything surprising was done. This is where the
  reasoning belongs, and it is the only place it is written for a reader deciding whether to upgrade.

Do **not** pass `--notes-file CHANGELOG.md`. That publishes the whole file — 3300+ lines — rather
than the section for the version being released.

### Backend Release
```bash
# 1. Update version in pyproject.toml
# 2. Add the release's CHANGELOG.md section: a "## [x.y.z] - YYYY-MM-DD" heading under the
#    [Unreleased] one, then at the foot of the file add the [x.y.z] compare link and repoint
#    [Unreleased] at the new version (tests/test_changelog.py enforces both)
# 3. Update version and date-released in CITATION.cff (tests/test_citation.py enforces this)
# 3b. Refresh the contract baselines: the OpenAPI document, the CLI options, the Python surface, the
#    MCP tools and the parameters of every dataset as of this release, which later pull requests are
#    checked against (tests/ui/test_openapi_baseline.py and tests/baselines/test_baselines.py enforce
#    that x-release in each is the version of pyproject.toml, and that no ACCEPTED_BREAKS entry is
#    left that the refreshed baseline does not need). Empty every ACCEPTED_BREAKS (tests/ui/openapi_diff.py
#    and tests/baselines/{cli,surface,mcp,parameters}.py) in the same commit
uv run poe contracts:baseline
# 4. Commit changes
git commit -am "chore(backend): release 0.118.0"
git push

# 5. Create and push tag
git tag v0.118.0
git push origin v0.118.0

# 6. Create GitHub release, with the narrative as its body
#    Write it to a scratch file first -- it is prose, not a paste of the changelog section
gh release create v0.118.0 --title "v0.118.0" --notes-file /tmp/v0.118.0-notes.md

#    For a release with nothing to explain, the commit list will do:
#    gh release create v0.118.0 --title "v0.118.0" --generate-notes
```

### App Release
```bash
# 1. Update version in app/package.json (optional)
# 2. Commit changes
git commit -am "chore(app): release 1.1.0"
git push

# 3. Create and push tag
git tag app-v1.1.0
git push origin app-v1.1.0

# 4. Create GitHub release
gh release create app-v1.1.0 --title "App v1.1.0" --notes "Release notes..."
```

### The contract checks

Three contracts are held by snapshots, so that a change to one is a diff in the pull request that makes it:

| Contract | Snapshot | Regenerate after an intended change |
| --- | --- | --- |
| the OpenAPI document of the REST API | `tests/ui/openapi.snapshot.json` | `uv run poe openapi:snapshot` |
| the `--help` of every command | `tests/ui/cli/help.snapshot.txt` | `uv run poe cli:snapshot` |
| the public surface of the Python API | `tests/public_surface.snapshot.json` | `uv run poe surface:snapshot` |

`uv run poe contracts:snapshot` does all three. A snapshot shows a change; it does not refuse one. So each contract
is also checked against what the **last release** offered: a baseline is that surface as released, a test fails when
the code no longer offers something the baseline does, and additions always pass.

| Baseline | File | What must still be offered |
| --- | --- | --- |
| the OpenAPI document | `tests/ui/openapi.baseline.json` | paths, operations, parameters and their types, enum members, members of requests and answers, statuses, headers; a request must not be asked more of: a new required parameter, a changed default, a tighter bound, a new pattern |
| the command line | `tests/baselines/cli.baseline.json` | commands, every spelling of every option, its type, choices, range, default, `nargs`, `multiple`, flag and required-ness, and the exit codes |
| the Python surface | `tests/baselines/surface.baseline.json` | what `tests/public_surface.snapshot.json` holds: `__all__`, `Period`, `Resolution`, the fields of `Settings` and `Options`, the signatures of `Wetterdienst` and `TimeseriesRequest`, the registry's networks and request constructors, and the request class each provider package exports |
| the MCP tools | `tests/baselines/mcp.baseline.json` | each tool and each argument of it, with type, enum members, default and bounds |
| the parameters of the datasets | `tests/baselines/parameters.baseline.json` | each provider/network/resolution/dataset/parameter name, which must still be there or be renamed (`wetterdienst.metadata.renamed`), and each rename entry |

The tests are `tests/ui/test_openapi_baseline.py` and `tests/baselines/test_baselines.py`; what is compared is
described in `tests/ui/openapi_diff.py` and in the module of each surface under `tests/baselines`.

- **A break is not made by regenerating the snapshot.** The baseline stays the surface of the last release, so it
  fails whether or not the snapshot moved. A break that is meant (before 1.0, or an error such as a wrong media type)
  is named in the `ACCEPTED_BREAKS` of that surface, with its reason, together with a **Breaking** entry in the
  changelog that says what to do instead. From 1.0 a break of `/api/v1` is not made: it is `/api/v2`, and a rename of
  a parameter keeps the old name (a removal is a major).
- **At a release** the baselines are refreshed in the release commit (step 3b above): `uv run poe contracts:baseline`
  writes each with `x-release` set to the version of `pyproject.toml`, and every `ACCEPTED_BREAKS` is emptied, as the
  baselines now hold what those entries changed. A test per surface fails a release that forgot to refresh, and one
  that left an entry the baseline no longer needs (`test_no_accepted_break_is_stale`).
- The OpenAPI document, the MCP tools and the help depend on the versions of FastAPI, pydantic, FastMCP and click:
  where the installed ones are not the locked ones, the OpenAPI, MCP and `--help` comparisons are skipped (as the
  snapshots are).

## The v1.0.0 tag day

The checklist for the release that makes 0.x into 1.0.0, in the order to do it. It is what #2625 (the library),
#2561 (REST, CLI, MCP) and the issues under them promise for the tag; every file named is in the repository. The
release steps above (and `chore: release 0.162.0 and app 0.27.0`, the commit that did them last) are the
mechanics; this list adds what only 1.0.0 needs. The app stays 0.x (`docs/usage/compatibility.md`, "The web app and
the image"), so its release after this one is `app-v0.28.0`, not `app-v1.0.0`.

### 0. What must be true first

- [ ] #3128 is down to the two shims below: `Settings(ts_*)` was removed in 0.160.0, and
  `StationsResult._df_all`, `_stations_filter` and `_rank` are private (`src/wetterdienst/model/result.py`).
- [ ] The compatibility page (`docs/usage/compatibility.md`), the migration note (`docs/usage/migrating.md`) and the
  links from `README.md` and `docs/usage/index.md` exist (#3130); the three contract checks exist (#3131):
  `tests/ui/test_openapi_baseline.py`, `tests/ui/cli/help.snapshot.txt`, `tests/baselines/test_baselines.py`.
- [ ] The decisions the page leaves open are made and written down (see "Decisions" below). The alias for renames and
  the floor of Python are made and are on the page.
- [ ] No pull request that changes a frozen surface is open or planned for the tag: the `ACCEPTED_BREAKS` of
  `tests/ui/openapi_diff.py` and `tests/baselines/{cli,surface,mcp,parameters}.py` are empty, apart from the one
  step 1 adds.
- [ ] The newest completed **Tests** run on `main` (`.github/workflows/tests.yml`) is read job by job. The matrix is
  `continue-on-error`, so a red job does not block anything and the run reports success: what must be green is the
  `Offline selection` jobs, `Lint`, `Typecheck`, `Docs`, `Unused` and `Vulnerable`. A red matrix job is
  acceptable only when it is an upstream outage or a missing credential (`WD_AUTH__METNO_FROST`, `WD_AUTH__AEMET`,
  `WD_AUTH__KNMI`, `WD_AUTH__CEDA` are secrets of this repository, not of a fork) and a rerun the same day does not
  clear it; anything else is read as a regression.
- [ ] `App E2E` and `App Tests` are green on `main`.
- [ ] `uv run poe docs` passes (warnings are errors), and the scheduled `Check the external links` job of the
  `Docs` workflow (`uv run poe "docs:linkcheck"`, needs the internet) has no broken link: a timeout of a site that
  blocks bots is not one (`linkcheck_ignore` in `docs/conf.py` names those that are refused), a moved page is fixed.

### 1. The pre-tag pull request: remove the two announced shims

Both are dated "removed 1.0.0" in `docs/usage/compatibility.md` (table "Deprecated today") and
`docs/usage/migrating.md`, so this is the last change to a surface before the baselines are taken. It is a
**Breaking** change, so it goes in as an ordinary PR with an issue (#3128 is it) and merges before the release PR.

- [ ] `src/wetterdienst/api.py`: delete `Wetterdienst.__new__` (the `DeprecationWarning`), and the imports it leaves
  unused (`warnings`, `StandaloneRequest` if nothing else uses them; `uv run poe lint` says). `Wetterdienst(...)`
  is then a plain call of an empty class. The Python-surface baseline skips underscore names, so
  `tests/baselines/surface.baseline.json` does not see this removal.
- [ ] `src/wetterdienst/ui/cli.py`: delete the `stripes.add_command(_Command("values", ...))` block and the comment
  above it at the end of the file. `_Command` stays: it is the `command_class` of `_Group`.
- [ ] `tests/test_api.py`: replace `test_the_constructor_form_is_deprecated_and_still_returns_the_class` with a test
  that `Wetterdienst("dwd", "observation")` raises `TypeError`. `tests/test_docs.py`
  (`test_the_documentation_resolves_a_network_with_resolve`) stays: it keeps the form out of the docs and examples.
- [ ] `tests/ui/cli/test_cli_stripes.py`: replace `test_stripes_values_is_the_deprecated_name_of_the_image` with a
  test that `stripes values` exits 2 with "No such command". `tests/ui/cli/test_cli.py`
  (`writes_directly` has `"stripes values"`) and `tests/ui/test_surface_parity.py` (`_NO_COMMAND` says
  `stripes values` is the deprecated name of the image) lose that name.
- [ ] `tests/baselines/cli.py`: `ACCEPTED_BREAKS` gets
  `"wetterdienst stripes values was removed"` with the reason (announced since 0.159.0, GH-3035, removed at 1.0.0 as
  `docs/usage/compatibility.md` says). The finding text is the one `breaking_changes` writes for a removed command;
  run `uv run pytest tests/baselines` to see it if it differs.
- [ ] `uv run poe "contracts:snapshot"`: rewrites `tests/ui/cli/help.snapshot.txt` (the `values` line under
  `stripes` goes). The OpenAPI snapshot and the MCP baseline do not change: `stripes_values` is the REST tool, not
  the command.
- [ ] `docs/usage/compatibility.md`: "Deprecated today" has no rows; replace the paragraph "Both are removed at 1.0.0,
  with the tag. ..." by one that says they were removed in 1.0.0, that `wetterdienst stripes values` is "No such
  command", and keep "the name is **never reused**".
- [ ] `docs/usage/migrating.md`: the intro paragraph "Two things still work in 0.162.0 and are removed at 1.0.0" (line
  19), the `Wetterdienst(provider, network)` row of "The request" (line 44) and the `stripes values` row of
  "Command line" (line 246) say "removed in 1.0.0" and what to write instead, with `1.0.0, GH-3128` as the release.
- [ ] `docs/usage/python-api.md` (line 72, "`Wetterdienst(provider, network)` is deprecated and removed in 1.0.0")
  becomes a statement that it was removed, or goes.
- [ ] `src/wetterdienst/ui/deprecation.py` (module docstring: "Before the tag a deprecation names the version that
  removes it") and `tests/public_surface.py` ("From 1.0 ...") are written in the present tense of 1.0.
- [ ] `CHANGELOG.md`, `[Unreleased]`, **Removed** or **Breaking** entries (a few lines each, `(GH-3128)`, what to
  use instead): `Wetterdienst(provider, network)` is a `TypeError`, write `Wetterdienst.resolve(provider, network)`
  (`resolve_standalone` for `dwd/radar` and `dwd/alerts`); `wetterdienst stripes values` is "No such command", write
  `wetterdienst stripes image`.
- [ ] `uv run poe format`, `uv run poe lint`, `uv run poe typecheck`, `uv run poe "test:offline"`, `uv run poe docs`.
- [ ] Land it. Close nothing yet: #3128 closes with the tag.

### 2. The release pull request, `chore: release 1.0.0`

The files `chore: release 0.162.0 and app 0.27.0` touched, plus the 1.0 ones. Backend only; the app is step 6.

- [ ] `pyproject.toml`: `version = "1.0.0"`, and `uv.lock`: the `wetterdienst` entry (`uv lock`; commit nothing else
  it changes).
- [ ] `pyproject.toml`: `"Development Status :: 4 - Beta"` becomes `"Development Status :: 5 - Production/Stable"`.
- [ ] `CITATION.cff`: `version: 1.0.0` and `date-released` (`tests/test_citation.py` holds both to
  `pyproject.toml` and `CHANGELOG.md`).
- [ ] `CHANGELOG.md`: cut `## [1.0.0] - YYYY-MM-DD` out of `[Unreleased]`, add the `[1.0.0]` compare link
  (`v0.162.0...v1.0.0`, or the last 0.x) and point `[Unreleased]` at `v1.0.0...HEAD` (`tests/test_changelog.py`).
  The section opens with an entry that says 1.0.0 is the first release that carries the promise of
  `docs/usage/compatibility.md`.
- [ ] `README.md`: delete the `> [!WARNING]` block ("This library is a work in progress! Breaking changes should be
  expected until a 1.0 release, ..."). Keep its last sentence's links somewhere: the "Upgrade" bullet further down
  already links Compatibility and Migrating, so nothing else is needed. If a notice is wanted, one line: "From 1.0.0
  the surfaces listed in [Compatibility](...) are stable; see [Migrating from 0.139.0](...) to upgrade."
- [ ] `.github/RELEASE_STRATEGY.md`: the two "currently" lines under "Version Management" (backend `1.0.0`, app still
  `0.27.0` until step 6).
- [ ] `uv run poe "contracts:baseline"` (OpenAPI, CLI, Python surface, MCP, parameters): `x-release` becomes `1.0.0`.
  **Empty every `ACCEPTED_BREAKS`** (`tests/ui/openapi_diff.py`, `tests/baselines/{cli,surface,mcp,parameters}.py`),
  including the entry step 1 added; `test_no_accepted_break_is_stale` fails the release otherwise.
- [ ] `docs/usage/compatibility.md`: "The baselines are those of 0.162.0 until the next release" becomes 1.0.0 (nothing
  tests this sentence; the last release commit did it by hand), and the statements that are dated by the tag change
  as follows:

  | Line (today) | Says | Becomes |
  | --- | --- | --- |
  | 7 to 9 | "Wetterdienst is 0.x until the 1.0.0 tag, and until then any release may break any surface below ... This page is the promise that 1.0.0 makes." | "Wetterdienst is 1.x: a break of a frozen surface takes a major release. Releases before 1.0.0 broke surfaces freely; [Migrating](migrating.md) lists what." This page is the promise 1.0.0 made. |
  | 19 | "every release; from 1.0.0 as semantic versioning says" | "every release, as semantic versioning says" |
  | 27 | column "Frozen from 1.0" | "Frozen" |
  | 73 | "and from 1.0 it is the rule" (a correction of data is marked Breaking) | "and it is the rule" |
  | 80 | "From 1.0.0 a break of a frozen surface takes a **major** release" | "A break of a frozen surface takes a **major** release" |
  | 215 | "From 1.0.0 a break of `/api/v1` is not made" | "A break of `/api/v1` is not made" |
  | 266 | "**Until 1.0 a rename is a hard break, with a hint.**" | "**A rename made in a 0.x release is a hard break, with a hint.**" |
  | 274 | "**From 1.0 a rename keeps the old name as an alias.** ..." (the alias is built, `wetterdienst.metadata.aliases`; no alias is declared yet) | "**A rename keeps the old name as an alias.**" |
  | 304 | "The alias is held by `tests/metadata/test_aliases.py`, with an alias declared in the test, since none is declared yet: ..." | unchanged: it stays true until the first real alias is declared |
  | 346 | "from 1.0 it is made only in a major release" | "it is made only in a major release" |
  | 375 | "and that a removal after 1.0 is in a major release" | "and that a removal is in a major release" |
  | 386 | "(until 1.0; after it the old name is an alias with a warning ...)" | "(for the names renamed in 0.x; since then the old name is an alias ...)" |
  | 398 | "From 1.0 it is made in a **minor** release, ..." (raising the floor of Python: the decision is written) | unchanged: it is not dated by the tag |

  The same wording is in `docs/usage/restapi.md` (line 110, "From 1.0.0 an endpoint or a parameter of `/api/v1` is
  removed only ..."), and `docs/usage/migrating.md` (lines 6 and 22 "frozen from 1.0", line 136 "after 1.0");
  `grep -rn "1\.0" docs/usage` finds them.
- [ ] `docs/usage/migrating.md`: the title and intro move from "0.139.0 to 0.162.0" to "0.139.0 to 1.0.0" (lines 3, 4,
  132, 134, 250 name 0.162.0), "`app-v0.27.0` goes with 0.162.0" (line 16) names the app of step 6, and the "Two
  things still work" paragraph is gone with step 1. `docs/usage/index.md` ("Migrating from 0.139.0") keeps its text.
- [ ] `uv run poe format`, `lint`, `typecheck`, `"test:offline"`, `docs`; `uv run poe "contracts:baseline"` a second time
  changes nothing.
- [ ] The Offline jobs of the PR are green; land it (squash).

### 3. Tag and publish the backend

- [ ] Fresh `main`, the release commit is `HEAD`, the checkout is clean. Compare with `git log -1`.
- [ ] `git tag v1.0.0 && git push origin v1.0.0`. The tag starts `.github/workflows/docker-publish.yml`
  (trigger: a `v*.*.*` tag push).
- [ ] Write the narrative of the release to a scratch file (not the changelog, see "Release notes are not the
  changelog"): what 1.0.0 promises and links Compatibility, which breaking changes since 0.139.0 need action and the
  link to Migrating, the two shims removed in it, that the app is 0.x and paired (step 6).
- [ ] `gh release create v1.0.0 --title "v1.0.0" --notes-file <scratch file>`. The published release starts
  `.github/workflows/release.yml` (build, then `uv publish` by trusted publishing).
- [ ] `release.yml` finished: `pip index versions wetterdienst` (or the PyPI page) lists 1.0.0; in a fresh
  environment `uvx --from wetterdienst==1.0.0 wetterdienst --version` prints 1.0.0 and `wetterdienst info` runs.
- [ ] Docker: the `Release Docker Backend` run for the tag finished; `ghcr.io/earthobservations/wetterdienst:1.0.0`
  and `:1.0` exist (the workflow's tags are `{{version}}`, `{{major}}.{{minor}}` and `nightly`; there is no `:1`) and
  `docker run --rm ghcr.io/earthobservations/wetterdienst:1.0.0 wetterdienst --version` prints 1.0.0.
  `docs/usage/docker.md` and `README.md` pull the image without a tag: check that `:latest` points to the same digest
  as `:1.0.0` (`docker buildx imagetools inspect`); `latest` is not in the workflow's tag list and comes from the
  default of `docker/metadata-action`, which this checklist could not verify.
- [ ] Read the Docs built `v1.0.0` and `stable` points to it (`.readthedocs.yml`; the links in `README.md` use
  `latest` and need no change).
- [ ] The GitHub release is archived on Zenodo with a new version DOI (`CITATION.cff` and the README badge use the
  concept DOI, so nothing to change; the Zenodo integration is not configured in this repository, so check the
  record).

### 4. The app against the tagged backend

The e2e suite of `.github/workflows/app-e2e.yml` starts the backend from `src/` of the checkout, not from PyPI, so the
run on `main` proves the commit, not the published wheel.

- [ ] Run the workflow on the tag: `gh workflow run app-e2e.yml --ref v1.0.0` (it has `workflow_dispatch`); green.
- [ ] And once against the published wheel, on a machine: `uvx --from "wetterdienst[restapi]==1.0.0" wetterdienst
  restapi --listen 0.0.0.0:7890`, then `cd app && pnpm install && BACKEND_URL=http://localhost:7890 pnpm test:e2e`
  (`app/tests/e2e/global-setup.ts` reads `BACKEND_URL` and checks `/health`; Playwright starts the app itself).
  `pnpm test:ci` and `pnpm lint` pass as on `main`.
- [ ] The app reads `/api/version` (`app/app/app.vue`) and calls the `/api` alias; `curl localhost:7890/api/version`
  reports `version` 1.0.0 and `api_version` `v1`, and the app footer shows it.

### 5. Close the issues

- [ ] Close #3128 (the shims, step 1; the result fields were done before), #3130 (compatibility page and migration
  note), #3131 (contract checks) and #2625 (the library tracker), each with a comment that names the release and the
  test or file that holds it. #2561 (REST, CLI, MCP tracker) closes with them once its list says nothing
  is left: its remaining items were #3129 (closed), #3130, #3131, the CORS stance of #2778 and the exit codes,
  which `docs/usage/compatibility.md` and `docs/usage/cli.md` freeze as 0, 1 and 2.
- [ ] Stays open, none of it blocks the tag: #2606 (the backend security review) until the threat model PR #2778 is
  rechecked against the code and merged (its status comment says it blocks closing, not the tag), and #2607 (the app
  review); #2621 (docs samples, numbers and links: this list and the link check are a part of it, not all); #2628
  (its deferred findings are additive); #3134 (additions after v1), #3136 and #3137 (provider data checks).
- [ ] Move the milestone `v1.0.0` to closed once the above are closed, and open a milestone for 1.1.

### 6. The app release, after its backend is on PyPI and GHCR

An app that ships against a backend it was not run with is how app 0.21.0 got a 422 from 0.155.0; the app is
released after step 3, never in the same PR as the backend.

- [ ] `app/package.json` `version` `0.28.0`; `CHANGELOG_APP.md` gets its `## [0.28.0] - YYYY-MM-DD` section cut from
  `[Unreleased]`; `.github/RELEASE_STRATEGY.md` "currently" line for the app; `docs/usage/migrating.md` line 16 names
  `app-v0.28.0` with 1.0.0. Land it.
- [ ] `git tag app-v0.28.0 && git push origin app-v0.28.0` (starts `docker-publish-app.yml`), then
  `gh release create app-v0.28.0 --title "App v0.28.0" --notes-file <scratch file>` (starts `app-release.yml`, which
  attaches `app-v0.28.0.tar.gz`). The notes say it is paired with backend 1.0.0.
- [ ] `ghcr.io/earthobservations/wetterdienst-app:0.28.0` and `:0.28` exist, and `compose.yml --profile full` (or the
  `docker run` pair in `docs/usage/app.md`) starts the two images against each other.
- [ ] Railway deploys from `main` by itself (see "Railway Deployment"); check that `https://wetterdienst.eobs.org`
  shows the backend 1.0.0 in its footer.

### 7. After the tag

- [ ] `[Unreleased]` of `CHANGELOG.md` is empty and its compare link reads `v1.0.0...HEAD`.
- [ ] The `ACCEPTED_BREAKS` stay empty, and the first change that needs one is a major (`/api/v2`) or an
  announced exception (a correction of data, an ended upstream source).
- [ ] Announce: the release body is the text; link it from the places the project has (the issue trackers above).

### Decisions the maintainer has to make first

Not decided anywhere this checklist could read, and each changes a line above.

- **The app number**: `docs/usage/compatibility.md` says the app stays 0.x. The examples of this file used
  `app-v1.0.0` and are changed to 0.x here; if the app is to be 1.0 as well, step 6 and the compatibility page change.
- **Whether a 0.x release goes between step 1 and step 2**: the page says the shims go "with the tag"; a release in
  between would ship their removal as 0.x. This list assumes none.

## Version Management

- **Backend**: Version in `pyproject.toml` (currently `0.164.0`)
- **App**: Version in `app/package.json` (currently `0.29.0`; the package is also marked `private`)
- Both can be versioned independently
- Consider semantic versioning for both

## Railway Deployment

Railway automatically deploys from the `main` branch. App releases create versioned artifacts but don't automatically deploy to Railway. To trigger Railway deployment:

1. **Option A**: Manual deployment from Railway dashboard
2. **Option B**: Use Railway CLI: `railway up`
3. **Option C**: Configure Railway webhook in app-release.yml (commented out)

## Why Monorepo?

✅ **Kept together because**:
- Shared development workflow (E2E tests start backend locally)
- App proxies `/api` to backend - tight coupling
- Atomic API changes with app updates
- Simplified dependency management

✅ **Separate releases because**:
- Different deployment targets (PyPI vs Railway)
- Independent versioning needs
- App can update without backend release
- Clear changelog separation
- **No cross-contamination**: Backend releases don't trigger app Docker builds and vice versa


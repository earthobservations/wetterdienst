# GitHub Actions workflows

Every `*.yml` file in this directory is one workflow; `install.sh` is the dependency installer the
Python jobs share. The sections below say what the path filters and the app workflows read.

## Path filters

Every `push`/`pull_request` workflow is filtered down to the files that can actually change its
outcome, so a pull request that only touches the app, the notebooks or the Docker setup does not
start the Python test matrix. Each workflow also lists its own file, so a change to a workflow is
always exercised by that workflow.

The filters are drawn from what the commands behind them read, not from what looks related: `ruff`
is restricted to the four trees named in `include` in `pyproject.toml`, `ty` and `deptry` only ever
look at `src/wetterdienst`, and `uv audit` only at the resolved dependency set. The test matrix is
the widest of them, because the suite reaches outside `src/` and `tests/`: `tests/test_docs.py`
checks the provider pages under `docs/data/provider` against the metadata model,
`tests/test_citation.py` ties `CITATION.cff` to `README.md` and `CHANGELOG.md`,
`tests/test_docs.py` ties the extras `docker/Dockerfile` installs to `docs/usage/docker.md`, and
`app/tests/e2e/i18n-coverage.spec.ts` checks the app translation catalogs under `app/i18n` and the
app home page against a running backend, so the Python suite no longer reads either.

Being drawn that tightly, the filters have to be maintained with the code: a test that starts
reading a tree nobody listed will simply stop being run on changes to it. When you teach a test to
read something new, add it here.

The one deliberate exception is `codeql.yml`. Code scanning is a merge requirement in the repository
ruleset, and that requirement is reported per pull request - a run that never happens leaves the
pull request waiting for a result rather than passing it, so CodeQL keeps running unconditionally.

## Pinning

Every `uses:` line is pinned to the full commit SHA of a release, with the release tag in a trailing
comment (`uses: actions/checkout@<sha> # v7.0.1`), and the base images of `docker/` carry their
digest after the tag (`python:3.15-slim-trixie@sha256:...`). A tag is something the owner of an
action can move to other code; a commit and a digest are not. Dependabot (`github-actions` and
`docker` in `.github/dependabot.yml`) reads the comment and the tag and proposes the next release
with its new SHA and digest, so the pin does not freeze the version. zizmor's `unpinned-uses` rule
is on and fails a new action that is referenced by a tag or a branch. When you add an action,
resolve the tag with `gh api repos/<owner>/<repo>/git/ref/tags/<tag>` (an annotated tag has to be
dereferenced to its commit) and write the SHA and the tag. The one thing left on a tag is the
`mcr.microsoft.com/playwright` job container of `app-accessibility.yml`, which Dependabot does not
read and which is kept in step with `@playwright/test` by hand.

`vulnerable.yml` is path-filtered for pull requests (only the manifest and the lock change what
`uv audit` finds) and also runs weekly on `main`, because an advisory is published against a lock
that does not change.

## Docs CI

`docs.yml` builds the Sphinx pages (`docs/conf.py`) with warnings as errors and the notebook pages not
executed, so a broken toctree, a link to a missing anchor or a failing directive is a red check on the pull
request that made it; the page filter is `docs/**`, the README and changelog the pages include, `src/**` (the API
pages and the parameter glossary are written from it) and the dependency files. A second job checks the external
links (`poe "docs:linkcheck"`) on a weekly schedule and on request only: a site that is down for an hour is not a
reason to fail a pull request. The code samples are run by `tests/test_docs_samples.py` (the command line and
REST samples offline, the Python ones under the `remote` marker), which `tests.yml` and `coverage.yml` start on a
change to `docs/**`.

## Timeouts

Every job carries a `timeout-minutes`, in place of GitHub's six hours: a hung run leaves its check
pending, which blocks a landing, until the next push cancels it or six hours of runner time are spent.
The limits sit at 2x or more of the longest passing run in the job durations of recent runs: a
test-matrix leg has taken up to 57 minutes on a passing run and 84 on a failing one (150 allowed), the
Python 3.15 leg of the offline selection up to 27 (60), the minimum-versions job up to 53 (120), the
backend image's smoke build up to 30 (60), the coverage job up to 52 (120), the accessibility scan up to
50 and growing (120), the daily Docker cleanup 31 (90); lint, unused, typecheck and the pages build take
a few minutes and have 15 to 30, the link check 45. The time spent queued for a runner does not count.
When a job legitimately outgrows its limit, raise it in the workflow and here.

## Credentials

A secret goes in the `env:` of the step that reads it, never of the job or the workflow: `uv sync`,
the package managers and third-party actions run code that is not ours and would be handed it. The
provider keys (`WD_AUTH__*`) are therefore on the test steps of `tests.yml` and `coverage.yml`
only. In `release.yml` the `build` job runs the project's build code and has no `id-token`; the
`publish` job has it and runs only `uv publish` on the artifact `build` uploaded.

## App CI

The app has two workflows, split along what each of them reads.

### `app-tests.yml`

Runs on changes to `app/**`.

**Jobs:**
1. **typecheck** - `nuxt typecheck`
2. **lint** - ESLint and Oxlint checks
3. **unit-tests** - Vitest unit and component tests

### `app-e2e.yml`

Runs on changes to `app/**` *and* to the backend - `src/wetterdienst/**`, `pyproject.toml`,
`uv.lock` - because the Playwright suite drives the app against a real backend started from the
working tree. A REST API change that breaks the app is caught here, which is why this is the one
workflow whose filter spans both sides of the repository.

**E2E Test Flow:**
1. Install Node.js, pnpm, and Playwright with Firefox
2. Setup Python and install backend with uv
3. Start backend API server on port 7890
4. Run E2E tests against live backend
5. Upload test artifacts (Playwright report)
6. Cleanup backend process

**Caching:**
- pnpm store cached for faster installs
- Playwright's Firefox is installed on every run, it is not cached

**Artifacts:**
- Playwright HTML report (retained for 7 days)

### `app-accessibility.yml`

The axe scan of every page (`app/tests/e2e/accessibility.spec.ts`), **on request only**: it takes ten
minutes and more, so `app-e2e.yml` leaves it out (`playwright.config.ts` ignores it unless `A11Y=1`).
It runs from the Actions tab (*Run workflow*), or on a pull request that carries the `a11y` label - when
the label is added and on every push after it. A pull request without the label gets a skipped job.

It has no path filter, and it is not, and must not be made, a required check. It needs no backend: the
spec answers every `/api/*` request itself. It runs in the Playwright image the baseline was recorded in
(`mcr.microsoft.com/playwright`, tag to be kept in step with `@playwright/test`), builds and serves the
production build, scans, holds the
app to `app/tests/e2e/accessibility/baseline.json` (a violation outside it fails the run, and so does a
baseline entry that is no longer found), and writes the baseline's size and this run's result to the
run's summary page; the scans' results are uploaded as an artifact, to re-record the baseline from. See
`app/ACCESSIBILITY.md`.

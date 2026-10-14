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
`tests/test_citation.py` ties `CITATION.cff` to `README.md` and `CHANGELOG.md`, and
`app/tests/e2e/i18n-coverage.spec.ts` checks the app translation catalogs under `app/i18n` and the
app home page against a running backend, so the Python suite no longer reads either.

Being drawn that tightly, the filters have to be maintained with the code: a test that starts
reading a tree nobody listed will simply stop being run on changes to it. When you teach a test to
read something new, add it here.

The one deliberate exception is `codeql.yml`. Code scanning is a merge requirement in the repository
ruleset, and that requirement is reported per pull request - a run that never happens leaves the
pull request waiting for a result rather than passing it, so CodeQL keeps running unconditionally.

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
3. Start backend API server on port 3000
4. Run E2E tests against live backend
5. Upload test artifacts (Playwright report)
6. Cleanup backend process

**Caching:**
- pnpm store cached for faster installs
- Playwright browsers cached automatically

**Artifacts:**
- Playwright HTML report (retained for 7 days)

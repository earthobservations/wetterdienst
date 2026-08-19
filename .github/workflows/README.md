Check out the guide that was used to create the CI environment including setting up the yaml files:

- https://medium.com/@cjolowicz/hypermodern-python-d44485d9d769
- https://cjolowicz.github.io/posts/hypermodern-python-01-setup/

- https://docs.github.com/en/actions/creating-actions/creating-a-docker-container-action
- https://docs.github.com/en/actions/creating-actions/dockerfile-support-for-github-actions
- https://docs.github.com/en/actions/guides/publishing-docker-images

## Path filters

Every `push`/`pull_request` workflow is filtered down to the files that can actually change its
outcome, so a pull request that only touches the app, the notebooks or the Docker setup does not
start the Python test matrix. Each workflow also lists its own file, so a change to a workflow is
always exercised by that workflow.

The filters are drawn from what the commands behind them read, not from what looks related: `ruff`
is restricted to the four trees named in `include` in `pyproject.toml`, `ty` and `deptry` only ever
look at `src/wetterdienst`, and `uv audit` only at the resolved dependency set. The test matrix is
the widest of them, because `tests/test_docs.py` checks the provider pages under
`docs/data/provider` against the metadata model and `tests/test_citation.py` ties `CITATION.cff` to
`README.md` and `CHANGELOG.md`.

The one deliberate exception is `codeql.yml`. Code scanning is a merge requirement in the repository
ruleset, and that requirement is reported per pull request - a run that never happens leaves the
pull request waiting for a result rather than passing it, so CodeQL keeps running unconditionally.

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

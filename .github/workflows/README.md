Check out the guide that was used to create the CI environment including setting up the yaml files:

- https://medium.com/@cjolowicz/hypermodern-python-d44485d9d769
- https://cjolowicz.github.io/posts/hypermodern-python-01-setup/

- https://docs.github.com/en/actions/creating-actions/creating-a-docker-container-action
- https://docs.github.com/en/actions/creating-actions/dockerfile-support-for-github-actions
- https://docs.github.com/en/actions/guides/publishing-docker-images

## Frontend CI

The frontend has its own dedicated workflow:

### `frontend-tests.yml`

Runs on changes to `frontend/**` directory.

**Jobs:**
1. **lint** - ESLint and Oxlint checks
2. **unit-tests** - Vitest unit and component tests (63 tests)
3. **e2e-tests** - Playwright E2E tests with real backend (32 tests)

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

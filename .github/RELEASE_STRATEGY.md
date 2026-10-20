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
- **Tag format**: `app-v{major}.{minor}.{patch}` (e.g., `app-v1.0.0`)
- **Trigger**: GitHub Release with tag matching `app-v*.*.*`
- **Workflows**: 
  - `.github/workflows/app-release.yml` - Creates GitHub Release artifact
  - `.github/workflows/docker-publish-app.yml` - Publishes Docker image to GHCR
- **Docker image**: `ghcr.io/earthobservations/wetterdienst-app:1.0.0`
- **Deployment**: Railway.com (auto-deploy from main branch)
- **Command**: `gh release create app-v1.0.0 --title "App v1.0.0" --notes "..."`

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
- **Example**: Tag `app-v1.0.0` creates Docker tags:
  - `1.0.0` (specific version - without "app-" prefix)
  - `1.0` (major.minor)
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

## Version Management

- **Backend**: Version in `pyproject.toml` (currently `0.162.0`)
- **App**: Version in `app/package.json` (currently `0.27.0`; the package is also marked `private`)
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


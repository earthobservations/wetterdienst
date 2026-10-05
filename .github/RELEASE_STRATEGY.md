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

## Version Management

- **Backend**: Version in `pyproject.toml` (currently `0.139.0`)
- **App**: Version in `app/package.json` (currently `0.18.0`; the package is also marked `private`)
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


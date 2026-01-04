# Release Strategy

This repository uses a **monorepo structure** with separate release workflows for backend and frontend.

## Release Types

### Backend (Python Package)
- **Tag format**: `v{major}.{minor}.{patch}` (e.g., `v0.117.0`)
- **Trigger**: GitHub Release with tag matching `v*.*.*`
- **Workflows**: 
  - `.github/workflows/release.yml` - Publishes to PyPI
  - `.github/workflows/docker-publish.yml` - Publishes Docker image to GHCR
- **Docker image**: `ghcr.io/earthobservations/wetterdienst:0.117.0`
- **Command**: `gh release create v0.117.0 --title "v0.117.0" --notes "..."`

### Frontend (Nuxt Application)
- **Tag format**: `frontend-v{major}.{minor}.{patch}` (e.g., `frontend-v1.0.0`)
- **Trigger**: GitHub Release with tag matching `frontend-v*.*.*`
- **Workflows**: 
  - `.github/workflows/frontend-release.yml` - Creates GitHub Release artifact
  - `.github/workflows/docker-publish-frontend.yml` - Publishes Docker image to GHCR
- **Docker image**: `ghcr.io/earthobservations/wetterdienst-frontend:1.0.0`
- **Deployment**: Railway.com (auto-deploy from main branch)
- **Command**: `gh release create frontend-v1.0.0 --title "Frontend v1.0.0" --notes "..."`

## Docker Images

### Backend Image
- **Triggered by**: `v*.*.*` tags
- **Registry**: `ghcr.io/earthobservations/wetterdienst`
- **Tags**: 
  - `0.117.0` (specific version)
  - `0.117` (major.minor)
  - `nightly` (daily builds)

### Frontend Image
- **Triggered by**: `frontend-v*.*.*` tags
- **Registry**: `ghcr.io/earthobservations/wetterdienst-frontend`
- **Example**: Tag `frontend-v1.0.0` creates Docker tags:
  - `1.0.0` (specific version - without "frontend-" prefix)
  - `1.0` (major.minor)
  - `nightly` (daily builds)

**Key point**: Backend releases only build backend images, frontend releases only build frontend images.

## Creating Releases

### Backend Release
```bash
# 1. Update version in pyproject.toml
# 2. Update CHANGELOG.md
# 3. Commit changes
git commit -am "Bump version to 0.118.0"
git push

# 4. Create and push tag
git tag v0.118.0
git push origin v0.118.0

# 5. Create GitHub release
gh release create v0.118.0 --title "v0.118.0" --notes-file CHANGELOG.md
```

### Frontend Release
```bash
# 1. Update version in frontend/package.json (optional)
# 2. Commit changes
git commit -am "Frontend: Bump version to 1.1.0"
git push

# 3. Create and push tag
git tag frontend-v1.1.0
git push origin frontend-v1.1.0

# 4. Create GitHub release
gh release create frontend-v1.1.0 --title "Frontend v1.1.0" --notes "Release notes..."
```

## Version Management

- **Backend**: Version in `pyproject.toml` (currently `0.117.0`)
- **Frontend**: Version in `frontend/package.json` (currently marked as `private`, no version)
- Both can be versioned independently
- Consider semantic versioning for both

## Railway Deployment

Railway automatically deploys from the `main` branch. Frontend releases create versioned artifacts but don't automatically deploy to Railway. To trigger Railway deployment:

1. **Option A**: Manual deployment from Railway dashboard
2. **Option B**: Use Railway CLI: `railway up`
3. **Option C**: Configure Railway webhook in frontend-release.yml (commented out)

## Why Monorepo?

✅ **Kept together because**:
- Shared development workflow (E2E tests start backend locally)
- Frontend proxies `/api` to backend - tight coupling
- Atomic API changes with frontend updates
- Simplified dependency management

✅ **Separate releases because**:
- Different deployment targets (PyPI vs Railway)
- Independent versioning needs
- Frontend can update without backend release
- Clear changelog separation
- **No cross-contamination**: Backend releases don't trigger frontend Docker builds and vice versa


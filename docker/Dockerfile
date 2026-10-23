FROM python:3.15-slim-trixie@sha256:044d5bd747976e21f8bc4d746c3479b19a84bb8ae6261b802acdd26b29036c93 AS build

COPY --from=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /bin/

ENV UV_NO_DEV=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_EDITABLE=1
ENV UV_PROJECT_ENVIRONMENT=/usr/local

# Compiler and HDF5 headers: some dependencies have no wheel for Python 3.15 yet and are built
# from source (GH-2568); the slim image has neither
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libhdf5-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*

# Set working directory for build
WORKDIR /app

# Copy dependency files
COPY uv.lock pyproject.toml ./

# Install the dependencies first, without the project (GH-2952): this layer depends on the two files
# above only, so a change in src/ leaves it cached and does not compile h5py, duckdb and the others
# again (they have no wheel for Python 3.15 yet, GH-2568). The cache mount does not travel with the
# layer cache of the CI, the layer itself does.
RUN --mount=type=cache,id=uv,target=/root/.cache/uv \
    uv sync --frozen --active --no-install-project \
    --extra bufr --extra cratedb --extra duckdb --extra export --extra influxdb --extra interpolation --extra knmi --extra plotting --extra postgresql --extra radar --extra radarplus --extra restapi --extra mcp

# Copy source code
COPY src ./src
COPY README.md LICENSE.md ./

# Install wetterdienst itself with all extras using uv
RUN --mount=type=cache,id=uv,target=/root/.cache/uv \
    uv sync --frozen --active \
    --extra bufr --extra cratedb --extra duckdb --extra export --extra influxdb --extra interpolation --extra knmi --extra plotting --extra postgresql --extra radar --extra radarplus --extra restapi --extra mcp

# Dev stage: editable install so uvicorn --reload picks up source changes.
# Installs the same extras and OS packages as the final stage for feature parity.
FROM python:3.15-slim-trixie@sha256:044d5bd747976e21f8bc4d746c3479b19a84bb8ae6261b802acdd26b29036c93 AS dev

COPY --from=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /bin/

ENV UV_NO_DEV=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/usr/local

# Install chromium -> required for kaleido png export, curl for health checks, and the ecCodes
# library (with its definitions, libeccodes-data) that the eccodes bindings of the `bufr` extra
# load to decode BUFR -- the lock installs the bindings only. The dev stage installs in place, so it
# also has the compiler and the HDF5 headers (which bring the HDF5 library h5py links to) that the
# build stage has
RUN apt-get update && \
    apt-get install -y --no-install-recommends chromium curl libeccodes0 libeccodes-data \
    build-essential libhdf5-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY uv.lock pyproject.toml ./

# Dependencies before the source, as in the build stage (GH-2952)
RUN --mount=type=cache,id=uv,target=/root/.cache/uv \
    uv sync --frozen --active --no-install-project \
    --extra bufr --extra cratedb --extra duckdb --extra export --extra influxdb --extra interpolation --extra knmi --extra plotting --extra postgresql --extra radar --extra radarplus --extra restapi --extra mcp

COPY src ./src
COPY README.md LICENSE.md ./

RUN --mount=type=cache,id=uv,target=/root/.cache/uv \
    uv sync --frozen --active \
    --extra bufr --extra cratedb --extra duckdb --extra export --extra influxdb --extra interpolation --extra knmi --extra plotting --extra postgresql --extra radar --extra radarplus --extra restapi --extra mcp

EXPOSE 7890
CMD ["wetterdienst", "restapi", "--listen", "0.0.0.0:7890", "--reload"]

# Final stage
FROM python:3.15-slim-trixie@sha256:044d5bd747976e21f8bc4d746c3479b19a84bb8ae6261b802acdd26b29036c93

# Install chromium -> required for kaleido png export, curl for health checks, and the ecCodes
# library (with its definitions, libeccodes-data) that the eccodes bindings of the `bufr` extra
# load to decode BUFR -- the lock installs the bindings only. libhdf5-310 and libhdf5-hl-310 are the
# HDF5 libraries that h5py, built from source in the build stage, links to
RUN apt-get update && \
    apt-get install -y --no-install-recommends chromium curl libeccodes0 libeccodes-data \
    libhdf5-310 libhdf5-hl-310 && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from build stage
COPY --from=build /usr/local/lib/python3.15/site-packages /usr/local/lib/python3.15/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

# Run unprivileged: the server parses what the network gives it, and starts a Chromium for every
# chart (kaleido runs it without its sandbox), so a flaw in either should not be root's (GH-2770).
# The home directory is where the cache goes, /home/wetterdienst/.cache/wetterdienst; a volume
# kept across runs is mounted there, or anywhere with WD_CACHE_DIR pointing to it. The directory
# is made here, with ~/.cache above it (Chromium and matplotlib keep theirs there), owned by the
# user, so that a new named volume mounted there takes its owner
# (a volume that an earlier, root image filled keeps root as its owner: chown it to 10001 once, see
# docs/usage/docker.md; until then the cache is kept in a temporary directory, GH-2860)
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin wetterdienst && \
    install -d -o wetterdienst -g wetterdienst /home/wetterdienst/.cache /home/wetterdienst/.cache/wetterdienst
USER wetterdienst
WORKDIR /home/wetterdienst

# Expose port 7890
EXPOSE 7890

# Default command: start restapi on port 7890
CMD ["wetterdienst", "restapi", "--listen", "0.0.0.0:7890"]

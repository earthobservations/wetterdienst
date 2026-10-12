FROM python:3.14-slim-trixie AS build

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/

ENV UV_NO_DEV=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_EDITABLE=1
ENV UV_PROJECT_ENVIRONMENT=/usr/local

# Set working directory for build
WORKDIR /app

# Copy dependency files
COPY uv.lock pyproject.toml ./

# Copy source code
COPY src ./src
COPY README.md LICENSE.md ./

# Install wetterdienst with all extras using uv
RUN --mount=type=cache,id=uv,target=/root/.cache/uv \
    uv sync --frozen --active \
    --extra bufr --extra cratedb --extra duckdb --extra export --extra influxdb --extra interpolation --extra knmi --extra plotting --extra postgresql --extra radar --extra radarplus --extra restapi --extra mcp

# Dev stage: editable install so uvicorn --reload picks up source changes.
# Installs the same extras and OS packages as the final stage for feature parity.
FROM python:3.14-slim-trixie AS dev

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/

ENV UV_NO_DEV=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/usr/local

# Install chromium -> required for kaleido png export, curl for health checks, and the ecCodes
# library (with its definitions, libeccodes-data) that the eccodes bindings of the `bufr` extra
# load to decode BUFR -- the lock installs the bindings only
RUN apt-get update && \
    apt-get install -y --no-install-recommends chromium curl libeccodes0 libeccodes-data && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY uv.lock pyproject.toml ./
COPY src ./src
COPY README.md LICENSE.md ./

RUN --mount=type=cache,id=uv,target=/root/.cache/uv \
    uv sync --frozen --active \
    --extra bufr --extra cratedb --extra duckdb --extra export --extra influxdb --extra interpolation --extra knmi --extra plotting --extra postgresql --extra radar --extra radarplus --extra restapi --extra mcp

EXPOSE 3000
CMD ["wetterdienst", "restapi", "--listen", "0.0.0.0:3000", "--reload"]

# Final stage
FROM python:3.14-slim-trixie

# Install chromium -> required for kaleido png export, curl for health checks, and the ecCodes
# library (with its definitions, libeccodes-data) that the eccodes bindings of the `bufr` extra
# load to decode BUFR -- the lock installs the bindings only
RUN apt-get update && \
    apt-get install -y --no-install-recommends chromium curl libeccodes0 libeccodes-data && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from build stage
COPY --from=build /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

# Run unprivileged: the server parses what the network gives it, and starts a Chromium for every
# chart (kaleido runs it without its sandbox), so a flaw in either should not be root's (GH-2770).
# The home directory is where the cache goes, /home/wetterdienst/.cache/wetterdienst; a volume
# kept across runs is mounted there, or anywhere with WD_CACHE_DIR pointing to it. The directory
# is made here, with ~/.cache above it (Chromium and matplotlib keep theirs there), owned by the
# user, so that a new named volume mounted there takes its owner
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin wetterdienst && \
    install -d -o wetterdienst -g wetterdienst /home/wetterdienst/.cache /home/wetterdienst/.cache/wetterdienst
USER wetterdienst

# Expose port 3000
EXPOSE 3000

# Default command: start restapi on port 3000
CMD ["wetterdienst", "restapi", "--listen", "0.0.0.0:3000"]

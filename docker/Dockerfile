FROM python:3.14-slim-trixie AS build

COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /bin/

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
    --extra bufr --extra cratedb --extra duckdb --extra export --extra influxdb --extra interpolation --extra plotting --extra postgresql --extra radar --extra radarplus --extra restapi

# Final stage
FROM python:3.14-slim-trixie

# Install chromium -> required for kaleido png export, and curl for health checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends chromium curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from build stage
COPY --from=build /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

# Expose port 3000
EXPOSE 3000

# Default command: start restapi on port 3000
CMD ["wetterdienst", "restapi", "--listen", "0.0.0.0:3000"]

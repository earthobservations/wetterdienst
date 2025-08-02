FROM python:3.13-slim-bookworm AS build

COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /bin/

# Copy wheel that was generated in the previous step (./.github/workflows/docker-publish.yml).
# If you want to build the Docker image locally, you need to build the wheel first e.g. with `uv build`.
COPY dist/wetterdienst-*.whl /tmp/

# Install wetterdienst using latest wheel package from `/tmp` folder.
RUN --mount=type=cache,id=pip,target=/root/.cache/pip \
    true \
    && WHEEL=$(ls -r /tmp/wetterdienst-*-py3-none-any.whl | head -n 1) \
    && uv pip install --system ${WHEEL}[bufr,cratedb,duckdb,explorer,export,influxdb,interpolation,plotting,postgresql,radar,radarplus,restapi]

# Final stage
FROM python:3.13-slim-bookworm

# Copy installed pip packages from build stage
COPY --from=build /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

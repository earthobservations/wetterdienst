FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

# Install build prerequisites.
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN \
    --mount=type=cache,id=apt,sharing=locked,target=/var/cache/apt \
    --mount=type=cache,id=apt,sharing=locked,target=/var/lib/apt \
    true \
    && apt-get update \
    && apt-get install --no-install-recommends --no-install-suggests --yes \
      git build-essential ca-certificates \
      python-is-python3 python3-h5py python3-dev python3-pip python3-venv python3-wheel

# Use Python 3.11.
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 0

# Use venv to circumvent "externally managed environment" error
# Source: https://pythonspeed.com/articles/activate-virtualenv-dockerfile/
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install wradlib.
RUN python -m pip install --prefer-binary wradlib

# Install Wetterdienst.

# Use `poetry build --format=wheel` to build wheel packages into `dist` folder.
COPY dist/wetterdienst-*.whl /tmp/

# Install package.
# Pick latest wheel package from `/tmp` folder.
RUN --mount=type=cache,id=pip,target=/root/.cache/pip \
    true \
    && pip install --prefer-binary versioningit \
    && WHEEL=$(ls -r /tmp/wetterdienst-*-py3-none-any.whl | head -n 1) \
    && pip install --use-pep517 --prefer-binary ${WHEEL}[export,influxdb,cratedb,postgresql,radar,bufr,restapi,explorer,radar,radarplus]

# Uninstall build prerequisites again.
RUN true \
    && apt-get --yes remove --purge git build-essential python3-dev python3-pip python3-venv python3-wheel \
    && apt-get --yes autoremove

# Purge /tmp directory
RUN rm /tmp/*

# Copy selftest.sh to the image
COPY .github/release/selftest.sh /usr/local/bin

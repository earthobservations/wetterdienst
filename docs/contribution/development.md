# Development sandbox

## Introduction

Whether you are working on an issue, trying to implement a new feature, or adding
a new weather service, you'll need a proper sandbox environment. The following
procedure outlines how to setup such an environment.

This setup procedure will outline how to install the library and the minimum
dependencies required to run the whole test suite.

If, for some reason, you are not available to install all the packages, just
leave out some of the ``extras`` dependency groups.

### Acquire sources and prerequisites

To develop on the Wetterdienst library, you will first have to acquire the
sources. The following instructions will guide you through the process of
cloning the repository and installing the prerequisites.

```bash
git clone https://github.com/earthobservations/wetterdienst
cd wetterdienst

# Prerequisites
## Mac
brew install git python uv
## Linux
sudo apt install git python3 python3-venv uv
## Windows
# install via chocolatey or manually

# Regarding `uv` the following page lists all releases:
# - https://github.com/astral-sh/uv/releases
```

Install required dependencies using `uv`:

*with help of [poe](https://github.com/nat-n/poethepoet)

```bash
uv sync --all-extras --all-groups
```

## Run tests

For running the whole test suite, you will need to have Firefox and
geckodriver installed on your machine:

```bash
uv run poe test
```

If this does not work for some reason and you would like to skip ui-related
tests on your machine, please invoke the test suite with:

```bash
uv run poe test -m "not ui"
```

In order to run only specific tests, invoke:

```bash
# Run tests by module name or function name.
uv run poe test -k test_cli

# Run tests by tags.
uv run poe test -m "not (remote or slow)"
```

## Build OCI images

Before building OCI images, you will need a recent wheel package. In order to
build one from the current working tree, run:

```bash
uv build
```

To build the OCI images suitable to run on Docker, Podman, Kubernetes, and friends,
invoke:

```bash
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
export BUILDKIT_PROGRESS=plain

docker build \
  --tag=local/wetterdienst \
  --file=.github/release/Dockerfile \
  .
```

In order to build images for other platforms than ``linux/amd64``, use the
``--platform`` option, For ARM 64-bit:

```bash
docker build \
  --tag=local/wetterdienst \
  --file=.github/release/Dockerfile \
  --platform=linux/arm64 \
  .
```

For ARM 32-bit:

```bash
docker build \
  --tag=local/wetterdienst \
  --file=.github/release/Dockerfile \
  --platform=linux/arm/v7 \
  .
```

## Contributing

1. Before committing your changes, please als run those steps in order to make
   the patch adhere to the coding standards used here.

   ```bash
   uv run poe format  # black code formatting
   uv run poe lint    # lint checking
   ```

1. Push your changes and submit them as pull request.

1. Wait for our feedback. We'll probably come back to you in a few days and let you know
   if there's anything that may need some more polishing.

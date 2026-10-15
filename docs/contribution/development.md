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

Install required dependencies using `uv` (task shortcuts are provided via
[poe](https://github.com/nat-n/poethepoet)):

```bash
uv sync --all-extras --all-groups
```

## Run tests

To run the whole test suite, which includes the tests that need the internet:

```bash
uv run poe test
```

In order to run only specific tests, invoke:

```bash
# Run tests by module name or function name.
uv run poe test -k test_cli

# Run tests by tags.
uv run poe test -m "not (remote or slow)"
```

`-m "not remote"` is the offline selection and the suite holds itself to it: every test that is
not marked `remote` runs with non-local names and addresses refused, so one that reaches upstream
fails at once, naming what it tried to reach, rather than passing on a warm cache. A new test
that needs the internet therefore wants `@pytest.mark.remote`; one that only needs an object a
request would have downloaded is better built from a `StationsResult` over a literal frame, as
the provider tests do.

What the guard catches is a connection being made, not one already open or made before the
per-test fixture is in place -- `tests/conftest.py` says what that leaves out. `poe test:offline`
runs the selection on its own, which is how CI asks the question: everything `-m "not remote"`
selects, less `explorer`, which no job here runs and which nothing in the tree is marked with. It
runs serially, two of those tests being marked `cflake`.

## Build OCI images

The image is built from the sources in the working tree (`docker/Dockerfile` installs them with
`uv sync` against `uv.lock`), so no wheel is needed first. To build an OCI image suitable to run on
Docker, Podman, Kubernetes, and friends, invoke:

```bash
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
export BUILDKIT_PROGRESS=plain

docker build \
  --tag=local/wetterdienst \
  --file=docker/Dockerfile \
  .
```

In order to build images for other platforms than ``linux/amd64``, use the
``--platform`` option, For ARM 64-bit:

```bash
docker build \
  --tag=local/wetterdienst \
  --file=docker/Dockerfile \
  --platform=linux/arm64 \
  .
```

The published image is built for `linux/amd64` and `linux/arm64` only.

## Contributing

1. Before committing your changes, please also run those steps in order to make
   the patch adhere to the coding standards used here.

   ```bash
   uv run poe format  # ruff formatting and autofixes
   uv run poe lint    # lint checking
   ```

1. Push your changes and submit them as pull request.

1. Wait for our feedback. We'll probably come back to you in a few days and let you know
   if there's anything that may need some more polishing.

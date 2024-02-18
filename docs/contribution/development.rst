###################
Development sandbox
###################


************
Introduction
************

Whether you are working on an issue, trying to implement a new feature, or adding
a new weather service, you'll need a proper sandbox environment. The following
procedure outlines how to setup such an environment.

This setup procedure will outline how to install the library and the minimum
dependencies required to run the whole test suite.

If, for some reason, you are not available to install all the packages, just
leave out some of the ``extras`` dependency groups.


*********************************
Acquire sources and prerequisites
*********************************

.. code-block:: bash

    git clone https://github.com/earthobservations/wetterdienst
    cd wetterdienst

    # Prerequisites
    brew install git python rye

    # Other OS
    # You can also get installers and/or release archives for Linux, macOS
    # and Windows at
    #
    # - https://rye.astral.sh/


************
Using Poetry
************

.. code-block:: bash

    rye pin 3.12
    rye install --with=test,dev,docs --extras=sql --extras=export --extras=restapi --extras=explorer --extras=interpolation
    poetry shell


*********
Using pip
*********

.. code-block:: bash

    python3 -m venv .venv
    source .venv/bin/activate

    # Install package in "editable" mode.
    pip install --editable=".[sql,export,restapi,explorer,interpolation]"


*********
Run tests
*********

For running the whole test suite, you will need to have Firefox and
geckodriver installed on your machine::

    poe test

If this does not work for some reason and you would like to skip ui-related
tests on your machine, please invoke the test suite with::

   poe test -m "not ui"

In order to run only specific tests, invoke::

    # Run tests by module name or function name.
    poe test -k test_cli

    # Run tests by tags.
    poe test -m "not (remote or slow)"


****************
Build OCI images
****************

Before building OCI images, you will need a recent wheel package. In order to
build one from the current working tree, run::

    pip install build
    python -m build --wheel

To build the OCI images suitable to run on Docker, Podman, Kubernetes, and friends,
invoke::

    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    export BUILDKIT_PROGRESS=plain

    docker build \
        --tag=local/wetterdienst \
        --file=.github/release/Dockerfile \
        .

In order to build images for other platforms than ``linux/amd64``, use the
``--platform`` option, For ARM 64-bit::

    docker build \
        --tag=local/wetterdienst \
        --file=.github/release/Dockerfile \
        --platform=linux/arm64 \
        .

For ARM 32-bit::

    docker build \
        --tag=local/wetterdienst \
        --file=.github/release/Dockerfile \
        --platform=linux/arm/v7 \
        .


************
Contributing
************

1. Before committing your changes, please als run those steps in order to make
   the patch adhere to the coding standards used here.

   .. code-block:: bash

       poe format  # black code formatting
       poe lint    # lint checking
       poe export  # export of requirements (for Github Dependency Graph)

2. Push your changes and submit them as pull request.

   That's it, you're almost done! We'd already like to thank you for taking the time to contribute.

3. Wait for our feedback. We'll probably come back to you in a few days and let you know
   if there's anything that may need some more polishing.

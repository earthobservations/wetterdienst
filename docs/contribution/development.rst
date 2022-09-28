Development
###########

Whether you work on an issue, try to implement a new feature or work on adding a new weather service, you'll need a
proper working environment. The following describes how to setup such an environment and how to enable you to
satisfy our code quality rules which would ultimately fail on Github CI and block a PR.

1. Clone the library and install the environment.

   This setup procedure will outline how to install the library and the minimum
   dependencies required to run the whole test suite. If, for some reason, you
   are not available to install all the packages, just leave out some of the
   "extras" dependency tags.

.. code-block:: bash

    git clone https://github.com/earthobservations/wetterdienst
    cd wetterdienst

    # Prerequisites
    brew install --cask firefox
    brew install git python geckodriver

    # Option 1: Basic
    git clone https://github.com/earthobservations/wetterdienst
    cd wetterdienst
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --requirement=requirements.txt
    python setup.py develop

    # (Option 2: Install package with extras)
    pip install ".[sql,export,restapi,explorer,interpolation]"

    # Option 3: Install package with extras using poetry.
    poetry install --extras=sql --extras=export --extras=restapi --extras=explorer --extras=interpolation
    poetry shell

2. For running the whole test suite, you will need to have Firefox and
   geckodriver installed on your machine. Install them like::

       # macOS
       brew install --cask firefox
       brew install geckodriver

       # Other OS
       # You can also get installers and/or release archives for Linux, macOS
       # and Windows at
       #
       # - https://www.mozilla.org/en-US/firefox/new/
       # - https://github.com/mozilla/geckodriver/releases

   If this does not work for some reason and you would like to skip ui-related
   tests on your machine, please invoke the test suite with::

       poe test -m "not ui"

3. Edit the source code, add corresponding tests and documentation for your
   changes. While editing, you might want to continuously run the test suite
   by invoking::

       poe test

   In order to run only specific tests, invoke::

       # Run tests by module name or function name.
       poe test -k test_cli

       # Run tests by tags.
       poe test -m "not (remote or slow)"

4. Before committing your changes, please als run those steps in order to make
   the patch adhere to the coding standards used here.

.. code-block:: bash

    poe format  # black code formatting
    poe lint    # lint checking
    poe export  # export of requirements (for Github Dependency Graph)

5. Push your changes and submit them as pull request

   That's it, you're almost done! We'd already like to thank you for your commitment!

6. Wait for our feedback. We'll probably come back to you in a few days and let you know if there's anything that may
   need some more polishing.

.. note::

    If you need to extend the list of package dependencies, invoke:

    .. code-block:: bash

        # Add package to runtime dependencies.
        poetry add new-package

        # Add package to development dependencies.
        poetry add --dev new-package

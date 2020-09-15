###########
Development
###########


************
Introduction
************
We originally started rebuilding rdwd_ in Python as a starting project,
but soon got accompanied by others to make this work as flawless as we can.

We are always looking for others to join and bring in their own ideas so
please consider writing us! Below you can find more about contribution and the
most recent changelog of the library.

.. _rdwd: https://github.com/brry/rdwd>


************
Contribution
************
As we are currently keeping development simple, so don't worry to much about style. If
you want a PR to be merged, describe what you changed at best precision and we guarantee
a fast merge.

Otherwise, if you have an idea of a problem or even better a solution just
let us know via an issue (you could also describe problem with words so we can figure
out how to solve it with a suitable programming solution).

For working on the code base, please clone the repository and install development
dependencies.

.. code-block:: bash

    git clone https://github.com/earthobservations/wetterdienst
    cd wetterdienst

    pip install .
    # or
    poetry install

Before committing, run the black code formatter and the linter to test for appropriate formatting.
This will inform you in case of problems with tests and your code format.

.. code-block:: bash

    nox -s tests
    nox -s black
    nox -s lint

In order to run the tests more **quickly**::

    poetry install --extras=excel
    poetry shell
    pytest -vvvv -m "not (remote or slow)"

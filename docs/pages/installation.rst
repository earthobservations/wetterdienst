#####
Setup
#####

Wetterdienst can be used by either installing it on
your workstation or within a Docker container.


******
Native
******
The installation of ``wetterdienst`` can happen via PyPi or directly from GitHub. The GitHub
version will always include most recent changes that may not have been released to PyPI.

PyPI

.. code-block:: bash

  pip install wetterdienst

GitHub

.. code-block:: bash

  pip install git+https://github.com/earthobservations/wetterdienst


******
Docker
******

We have a Docker image available that let's you run the library dockerized. To use
Wetterdienst in a Docker container, you just have to build the image from this project

.. code-block:: bash

    docker build -t "wetterdienst" .

To run the tests in the given environment, just call

.. code-block:: bash

    docker run -ti -v $(pwd):/app wetterdienst:latest poetry run pytest -vvvv tests

from the main directory. To work in an iPython shell, invoke

.. code-block:: bash

    docker run -ti -v $(pwd):/app wetterdienst:latest poetry run ipython

Command line script
===================

The ``wetterdienst`` command is also available through Docker:

.. code-block:: bash

    docker run -ti -v $(pwd):/app wetterdienst:latest poetry run wetterdienst --help

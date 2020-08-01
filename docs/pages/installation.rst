Installation
############


The installation of wetterdienst can happen via PyPi or directly from Github. The Github
version will always include most recent changes that may not have been released to PyPi.

PyPi

.. code-block::

  pip install wetterdienst

Github

.. code-block::

  pip install git+https://github.com/earthobservations/wetterdienst

If you think that any constraints we have set for the library in the pyproject.toml
may have to be updated/improved, please come back to us via mail or place an issue on
Github.

Docker
******

We have a Docker image available that let's you run the library dockerized. To use
Wetterdienst in a Docker container, you just have to build the image from this project

.. code-block::

    docker build -t "wetterdienst" .

To run the tests in the given environment, just call

.. code-block::

    docker run -ti -v $(pwd):/app wetterdienst:latest poetry run pytest tests

from the main directory. To work in an iPython shell call

.. code-block::

    docker run -ti -v $(pwd):/app wetterdienst:latest poetry run ipython

Command line script
*******************

You can download data as csv files after building docker container.
Currently, only the `collect_dwd_data` is supported by this service.

.. code-block::

    docker run \
        -ti -v $(pwd):/app wetterdienst:latest poetry run python wetterdienst/run.py \
        collect_dwd_data "[1048]" "kl" "daily" "historical" /app/dwd_data/ False False True False True True


The `wetterdienst` command is also available through Docker:

.. code-block::

    docker run -ti -v $(pwd):/app wetterdienst:latest poetry run wetterdienst

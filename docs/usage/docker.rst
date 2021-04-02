Docker
******

Get wetterdienst-standard

.. code-block:: bash

    docker pull ghcr.io/earthobservations/wetterdienst-standard

Get wetterdienst-full

.. code-block:: bash

    docker pull ghcr.io/earthobservations/wetterdienst-full

Run wetterdienst cli:

.. code-block:: bash

    docker run -it --rm ghcr.io/earthobservations/wetterdienst-standard wetterdienst --version

Run wetterdienst HTTP service:

.. code-block:: bash

    docker run -it --rm --publish=7890:7890 ghcr.io/earthobservations/wetterdienst-standard wetterdienst service --listen 0.0.0.0:7890

Run wetterdienst UI service:

.. code-block:: bash

    docker run -it --rm --publish=7890:7890 ghcr.io/earthobservations/wetterdienst-full wetterdienst ui --listen 0.0.0.0:7890

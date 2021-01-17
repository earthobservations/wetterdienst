Docker
******

Get wetterdienst-standard

.. code-block:: bash

    docker pull ghcr.io/earthobservations/wetterdienst-standard

Get wetterdienst-full

.. code-block:: bash

    docker pull ghcr.io/earthobservations/wetterdienst-full

Run wetterdienst shell:

.. code-block:: bash

    docker run -ti ghcr.io/earthobservations/wetterdienst-standard

Run wetterdienst service:

.. code-block:: bash

    docker run -ti ghcr.io/earthobservations/wetterdienst-standard poetry run wetterdienst service


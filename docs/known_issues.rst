Known Issues
############

Besides the officially listed issues on the wetterdienst repository, there are other issues regarding
running wetterdienst listed below that may be environment specific and are not likely fixable on our side.

LINUX ARM (Raspberry Pi)
************************

Running wetterdienst on Raspberry Pi, you need to install **numpy**
and **lxml** prior to installing wetterdienst running the following
lines:

.. code-block:: bash

    sudo apt-get install libatlas-base-dev
    sudo apt-get install python3-lxml
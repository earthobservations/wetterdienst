.. _explorer-ui:

Wetterdienst Explorer
#####################

Navigator for wetterdienst provided open data.


Introduction
************

Welcome to Wetterdienst Explorer, your friendly web-based GUI for the
Wetterdienst weather service library for Python. This web UI can easily be
self-hosted.

The implementation is still in its infancy, so we are happy about further
contributions.


Screenshot
**********

.. figure:: https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/img/wetterdienst_explorer.png
    :name: Wetterdienst Explorer UI screenshot
    :target: https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/img/wetterdienst_explorer.png


Features
********

Coverage
========

Wetterdienst Explorer currently covers access to:

- Weather observation data from all providers that are implemented. Historical, recent and near real time.


Usage
*****

Invoke service
==============

Install Wetterdienst and invoke the user interface::

    # Install Wetterdienst with Explorer extension
    pip install --user wetterdienst[explorer]

    # Run Wetterdienst Explorer UI
    wetterdienst explorer

    # Navigate to web UI
    open http://localhost:7891


Invoke using Docker
===================

Run the Wetterdienst user interface using Docker::

    docker run -it --rm --publish=7891:7891 ghcr.io/earthobservations/wetterdienst-full wetterdienst explorer --listen 0.0.0.0:7891


Serve Wetterdienst Explorer at non-root URL
===========================================

If you are wrapping up Wetterdienst behind a reverse HTTP proxy, use the
``DASH_URL_BASE_PATHNAME`` environment variable to configure the HTTP base URL
the service is mounted on::

    export DASH_URL_BASE_PATHNAME=/explorer/
    wetterdienst explorer --listen=localhost:8891

The gist of a corresponding Nginx configuration snippet is::

    server {
      server_name wetterdienst.example.org;
      location ~ ^/explorer {
        proxy_set_header   Host $host;
        proxy_pass http://localhost:8891;
      }
    }


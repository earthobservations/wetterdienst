.. _explorer-ui:

#####################
Wetterdienst Explorer
#####################

Navigator for wetterdienst provided open data.


************
Introduction
************

Welcome to Wetterdienst Explorer, your friendly web-based GUI for the
Wetterdienst weather service library for Python. This web UI can easily be
self-hosted.

The implementation is still in its infancy, so we are happy about further
contributions.


**********
Screenshot
**********

.. figure:: https://user-images.githubusercontent.com/453543/113444787-dcc2f680-93f4-11eb-8ca5-ad71c2e15007.png
    :name: Wetterdienst Explorer UI screenshot
    :target: https://user-images.githubusercontent.com/453543/113444866-febc7900-93f4-11eb-827a-5af0e5e624de.png


********
Features
********

Coverage
========

Wetterdienst Explorer currently covers access to:

- Weather observation data from all providers that are implemented. Historical, recent and near real time.


*****
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


*******
Backlog
*******

* Fix x-axis labels in graph figure
* Implement different figure types for different data types
* Provide more information for weather station (location, avail.) on the front-end
* Display extremes of actual visualisation
* Support overlays
* Zoom map to selected station
* Enable select station by click on an icon on map (requires ipyleaflet)

Known Bugs
==========

* `_gdbm.error: [Errno 11] Resource temporarily unavailable: '/root/.cache/wetterdienst/metaindex.dbm'`
  Sometimes there are problems with a wetterdienst cache. You can work around
  this bug by switching between sudo and not sudo call.

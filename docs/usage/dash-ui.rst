.. _dash-ui:

###########
Dash Web UI
###########

Navigator for DWD open weather data.


************
Introduction
************

Welcome to Wetterdienst UI, your friendly web-based GUI for the Wetterdienst
weather service library for Python. This web UI can easily be self-hosted.

The implementation is still in its infancy, so we are happy about further
contributions.


**********
Screenshot
**********

.. figure:: https://user-images.githubusercontent.com/453543/113444787-dcc2f680-93f4-11eb-8ca5-ad71c2e15007.png
    :name: Wetterdienst UI screenshot
    :target: https://user-images.githubusercontent.com/453543/113444866-febc7900-93f4-11eb-827a-5af0e5e624de.png


********
Features
********

Coverage
========
Wetterdienst UI currently covers access to:

- Weather observation data from DWD. Historical, recent and near real time.


*****
Usage
*****

Invoke service
==============

Install Wetterdienst and invoke the user interface::

    # Install Wetterdienst
    pip install --user wetterdienst[ui]

    # Run Wetterdienst UI
    wetterdienst ui

    # Navigate to web UI
    open http://localhost:7890


Invoke using Docker
===================

Run the Wetterdienst user interface using Docker::

    docker run -it --rm --publish=7890:7890 ghcr.io/earthobservations/wetterdienst-full wetterdienst ui --listen 0.0.0.0:7890


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

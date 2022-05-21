EA (Environment Agency)
***********************

Hydrology
=========

Overview
________

The data as offered by EA Hydrology through ``wetterdienst`` includes:

- flow
- groundwater stage

in resolutions 15 minutes, 6 hours and daily.

.. ipython:: python

    import json
    from wetterdienst.provider.environment_agency.hydrology import EaHydrologyRequest

    meta = EaHydrologyRequest.discover(flatten=False)

    # Selection of daily historical data
    print(json.dumps(meta, indent=4, ensure_ascii=False))

ECCC (Environment and Climate Change Canada)
********************************************

- Historical Weather Observations
    - Historical (last ~180 years)
    - Hourly, daily, monthly, (annual) resolution
    - Time series of stations in Canada

.. ipython:: python

    import json
    from wetterdienst.provider.eccc.observation import EcccObservationRequest

    meta = EcccObservationRequest.discover()

    # Selection of daily historical data
    print(json.dumps(meta, indent=4, ensure_ascii=False))

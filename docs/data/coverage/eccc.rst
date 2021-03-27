ECCC (Environment and Climate Change Canada)
********************************************

- Historical Weather Observations
    - Historical (last ~180 years)
    - Hourly, daily, monthly, (annual) resolution
    - Time series of stations in Canada

.. ipython:: python

    from wetterdienst.provider.eccc.observation import EcccObservationRequest

    observations_meta = EcccObservationRequest.discover()

    # Selection of daily historical data
    print(observations_meta)

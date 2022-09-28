###############
Python examples
###############

.. contents::
    :local:
    :depth: 1


************************************
DWD: Historical weather observations
************************************

Get available parameters for daily historical data of DWD:

.. ipython:: python
    :okwarning:

    from wetterdienst import Resolution, Period
    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    observations_meta = DwdObservationRequest.discover(
        filter_=Resolution.DAILY,
    )

    # Available parameter sets
    print(observations_meta)

    # Available individual parameters
    observations_meta = DwdObservationRequest.discover(
        filter_=Resolution.DAILY, flatten=False
    )

    print(observations_meta)

Get stations for daily historical precipitation:

.. ipython:: python
    :okwarning:

    from wetterdienst import Resolution, Period
    from wetterdienst.provider.dwd.observation import DwdObservationDataset

    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.PRECIPITATION_MORE,
        resolution=Resolution.DAILY,
        period=Period.HISTORICAL
    )

    print(stations.all().df.head())

Get data for a dataset:

.. ipython:: python
    :okwarning:

    from wetterdienst import Resolution, Period
    from wetterdienst.provider.dwd.observation import DwdObservationDataset

    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.PRECIPITATION_MORE,
        resolution=Resolution.DAILY,
        period=Period.HISTORICAL
    )

    print(next(stations.all().values.query()))

Get data for a parameter:

.. ipython:: python
    :okwarning:

    from wetterdienst import Resolution, Period
    from wetterdienst.provider.dwd.observation import DwdObservationParameter

    observation_data = DwdObservationRequest(
        parameter=DwdObservationParameter.DAILY.PRECIPITATION_HEIGHT,
        resolution=Resolution.DAILY,
        period=Period.HISTORICAL
    )

    print(next(stations.all().values.query()))

Get data for a parameter from another dataset:

.. ipython:: python
    :okwarning:

    from wetterdienst import Resolution, Period
    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    observation_data = DwdObservationRequest(
        parameter=[("precipitation_height", "precipitation_more")],
        resolution=Resolution.DAILY,
        period=Period.HISTORICAL
    )

    print(next(stations.all().values.query()))

*********************
DWD: MOSMIX forecasts
*********************

Get stations for MOSMIX-SMALL:

.. ipython:: python
    :okwarning:

    from wetterdienst import Resolution, Period
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType

    stations = DwdMosmixRequest(parameter="large", mosmix_type=DwdMosmixType.LARGE)

    print(stations.all().df.head())

Get data for MOSMIX-LARGE:

.. ipython:: python
    :okwarning:

    from wetterdienst import Resolution, Period
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType

    stations = DwdMosmixRequest(parameter="large", mosmix_type=DwdMosmixType.LARGE).filter_by_station_id(
        station_id=["01001", "01008"]
    )

    print(stations.values.all().df.head())

Code Snippets
*************

.. contents::
    :local:
    :depth: 1

DWD (German Weather Service)
============================

Historical Weather Observations
-------------------------------

Get available parameters for daily historical data of DWD:

.. ipython:: python

    from wetterdienst import Wetterdienst, Resolution, Period

    API = Wetterdienst("dwd", "observation")

    observations_meta = API.discover(
        resolution=Resolution.DAILY,
    )

    # Available parameter sets
    print(observations_meta)

    # Available individual parameters
    observations_meta = API.discover(
        resolution=Resolution.DAILY, flatten=False
    )

    print(observations_meta)

Get stations for daily historical precipitation:

.. ipython:: python

    from wetterdienst import Wetterdienst, Resolution, Period
    from wetterdienst.provider.dwd.observation import DwdObservationDataset

    API = Wetterdienst(provider="dwd", kind="observation")

    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.PRECIPITATION_MORE,
        resolution=Resolution.DAILY,
        period=Period.HISTORICAL
    )

    print(stations.all().df.head())



Get data for a parameter set:

.. ipython:: python

    from wetterdienst import Wetterdienst, Resolution, Period
    from wetterdienst.provider.dwd.observation import DwdObservationDataset

    API = Wetterdienst(provider="dwd", kind="observation")

    stations = API(
        parameter=DwdObservationDataset.PRECIPITATION_MORE,
        resolution=Resolution.DAILY,
        period=Period.HISTORICAL
    )

    print(next(stations.all().values.query()))

Get data for a parameter:

.. ipython:: python

    from wetterdienst import Wetterdienst, Resolution, Period
    from wetterdienst.provider.dwd.observation import DwdObservationParameter

    API = Wetterdienst(provider="dwd", kind="observation")

    observation_data = API(
        parameter=DwdObservationParameter.DAILY.PRECIPITATION_HEIGHT,
        resolution=Resolution.DAILY,
        period=Period.HISTORICAL
    )

    print(next(stations.all().values.query()))

Mosmix
------

Get stations for Mosmix:

.. ipython:: python

    from wetterdienst import Wetterdienst, Resolution, Period
    from wetterdienst.provider.dwd.forecast import DwdMosmixType

    API = Wetterdienst(provider="dwd", kind="forecast")

    stations = API(parameter="large", mosmix_type=DwdMosmixType.LARGE)

    print(stations.all().df.head())

Get data for Mosmix-L:

.. ipython:: python

    from wetterdienst import Wetterdienst, Resolution, Period
    from wetterdienst.provider.dwd.forecast import DwdMosmixType

    API = Wetterdienst(provider="dwd", kind="forecast")

    stations = API(parameter="large", mosmix_type=DwdMosmixType.LARGE).filter(
        station_id=["01001", "01008"]
    )

    print(stations.values.all().df.head())

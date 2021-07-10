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

    from wetterdienst import Wetterdienst, Resolution, Period

    API = Wetterdienst("dwd", "observation")

    observations_meta = API.discover(
        filter_=Resolution.DAILY,
    )

    # Available parameter sets
    print(observations_meta)

    # Available individual parameters
    observations_meta = API.discover(
        filter_=Resolution.DAILY, flatten=False
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

Get data for a dataset:

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

Get data for a parameter from another dataset:

.. ipython:: python

    from wetterdienst import Wetterdienst, Resolution, Period

    API = Wetterdienst(provider="dwd", kind="observation")

    observation_data = API(
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

    from wetterdienst import Wetterdienst, Resolution, Period
    from wetterdienst.provider.dwd.forecast import DwdMosmixType

    API = Wetterdienst(provider="dwd", kind="forecast")

    stations = API(parameter="large", mosmix_type=DwdMosmixType.LARGE)

    print(stations.all().df.head())

Get data for MOSMIX-LARGE:

.. ipython:: python

    from wetterdienst import Wetterdienst, Resolution, Period
    from wetterdienst.provider.dwd.forecast import DwdMosmixType

    API = Wetterdienst(provider="dwd", kind="forecast")

    stations = API(parameter="large", mosmix_type=DwdMosmixType.LARGE).filter_by_station_id(
        station_id=["01001", "01008"]
    )

    print(stations.values.all().df.head())

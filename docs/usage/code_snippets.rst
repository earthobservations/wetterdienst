Code Snippets
*************

.. contents::
    :local:
    :depth: 1

DWD (German Weather Service)
============================

Historical Weather Observations
-------------------------------

Get available parameters for daily historical data:

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationMetadata, DWDObservationResolution, DWDObservationPeriod

    observations_meta = DWDObservationMetadata(
        resolution=DWDObservationResolution.DAILY,
        period=DWDObservationPeriod.HISTORICAL
    )

    # Available parameter sets
    print(
        observations_meta.discover_parameter_sets()
    )

    # Available individual parameters
    print(
        observations_meta.discover_parameters()
    )

Get stations for daily historical precipitation:

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationStations, DWDObservationParameterSet, DWDObservationResolution, DWDObservationPeriod

    stations = DWDObservationStations(
        parameter=DWDObservationParameterSet.PRECIPITATION_MORE,
        resolution=DWDObservationResolution.DAILY,
        period=DWDObservationPeriod.HISTORICAL
    )

    print(stations.all().df.head())



Get data for a parameter set:

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationStations, DWDObservationParameterSet, DWDObservationResolution, DWDObservationPeriod

    stations = DWDObservationStations(
        parameter=DWDObservationParameterSet.PRECIPITATION_MORE,
        resolution=DWDObservationResolution.DAILY,
        period=DWDObservationPeriod.HISTORICAL
    )

    print(next(stations.all().values.query()))

Get data for a parameter:

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationStations, DWDObservationParameter, DWDObservationResolution, DWDObservationPeriod

    observation_data = DWDObservationStations(
        parameter=DWDObservationParameter.DAILY.PRECIPITATION_HEIGHT,
        resolution=DWDObservationResolution.DAILY,
        period=DWDObservationPeriod.HISTORICAL
    )

    print(next(stations.all().values.query()))

Mosmix
------

Get stations for Mosmix:

.. ipython:: python

    from wetterdienst.dwd.forecasts import DWDMosmixStations, DWDMosmixType

    stations = DWDMosmixStations(mosmix_type=DWDMosmixType.LARGE)

    print(stations.all().df.head())

Get data for Mosmix-L:

.. ipython:: python

    from wetterdienst.dwd.forecasts import DWDMosmixStations, DWDMosmixType

    stations = DWDMosmixStations(
        mosmix_type=DWDMosmixType.LARGE
    ).filter(station_id=["01001", "01008"])

    print(stations.values.all().df.head())

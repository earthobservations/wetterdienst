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

    print(stations.all().head())



Get data for a parameter set:

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationValues, DWDObservationParameterSet, DWDObservationResolution, DWDObservationPeriod

    observation_data = DWDObservationValues(
        station_id=stations.all().STATION_ID[0],
        parameter=DWDObservationParameterSet.PRECIPITATION_MORE,
        resolution=DWDObservationResolution.DAILY,
        period=DWDObservationPeriod.HISTORICAL
    )

    print(observation_data.all().head())

Get data for a parameter:

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationValues, DWDObservationParameter, DWDObservationResolution, DWDObservationPeriod

    observation_data = DWDObservationValues(
        station_id=stations.all().STATION_ID[0],
        parameter=DWDObservationParameter.DAILY.PRECIPITATION_HEIGHT,
        resolution=DWDObservationResolution.DAILY,
        period=DWDObservationPeriod.HISTORICAL
    )

    print(observation_data.all().head())

Mosmix
------

Get stations for Mosmix:

.. ipython:: python

    from wetterdienst.dwd.forecasts import DWDMosmixStations

    stations = DWDMosmixStations()

    print(stations.all().head())

Get data for Mosmix-L:

.. ipython:: python

    from wetterdienst.dwd.forecasts import DWDMosmixValues, DWDMosmixType

    forecast_data = DWDMosmixValues(
        station_id=stations.all().STATION_ID[0],
        mosmix_type=DWDMosmixType.LARGE
    )

    print(forecast_data.all().head())

Code Snippets
*************

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
        parameter_set=DWDObservationParameterSet.PRECIPITATION_MORE,
        resolution=DWDObservationResolution.DAILY,
        period=DWDObservationPeriod.HISTORICAL
    )

    print(stations.all().head())



Get data for a parameter set:

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationData, DWDObservationParameterSet, DWDObservationResolution, DWDObservationPeriod

    observation_data = DWDObservationData(
        station_ids=stations.all().STATION_ID[0],
        parameters=DWDObservationParameterSet.PRECIPITATION_MORE,
        resolution=DWDObservationResolution.DAILY,
        periods=DWDObservationPeriod.HISTORICAL
    )

    print(observation_data.all().head())

Get data for a parameter:

.. ipython:: python

    from wetterdienst.dwd.observations import DWDObservationData, DWDObservationParameter, DWDObservationResolution, DWDObservationPeriod

    observation_data = DWDObservationData(
        station_ids=stations.all().STATION_ID[0],
        parameters=DWDObservationParameter.DAILY.PRECIPITATION_HEIGHT,
        resolution=DWDObservationResolution.DAILY,
        periods=DWDObservationPeriod.HISTORICAL
    )

    print(observation_data.all().head())

Mosmix
------

Get stations for Mosmix-S:

.. ipython:: python

    from wetterdienst.dwd.forecasts import DWDMosmixStations

    stations = DWDMosmixStations()

    print(stations.all().head())

Get data for Mosmix-S:

.. ipython:: python

    from wetterdienst.dwd.forecasts import DWDMosmixData, DWDMosmixType

    forecast_data = DWDMosmixData(
        station_ids=stations.all().STATION_ID[0],
        mosmix_type=DWDMosmixType.SMALL
    )

    print(forecast_data.all().head())

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

    from wetterdienst.dwd.observations import DwdObservationMetadata, DwdObservationResolution, DwdObservationPeriod

    observations_meta = DwdObservationMetadata(
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.HISTORICAL
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

    from wetterdienst.dwd.observations import DwdObservationRequest, DwdObservationParameterSet, DwdObservationResolution, DwdObservationPeriod

    stations = DwdObservationRequest(
        parameter=DwdObservationParameterSet.PRECIPITATION_MORE,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.HISTORICAL
    )

    print(stations.all().df.head())



Get data for a parameter set:

.. ipython:: python

    from wetterdienst.dwd.observations import DwdObservationRequest, DwdObservationParameterSet, DwdObservationResolution, DwdObservationPeriod

    stations = DwdObservationRequest(
        parameter=DwdObservationParameterSet.PRECIPITATION_MORE,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.HISTORICAL
    )

    print(next(stations.all().values.query()))

Get data for a parameter:

.. ipython:: python

    from wetterdienst.dwd.observations import DwdObservationRequest, DwdObservationParameter, DwdObservationResolution, DwdObservationPeriod

    observation_data = DwdObservationRequest(
        parameter=DwdObservationParameter.DAILY.PRECIPITATION_HEIGHT,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.HISTORICAL
    )

    print(next(stations.all().values.query()))

Mosmix
------

Get stations for Mosmix:

.. ipython:: python

    from wetterdienst.dwd.forecasts import DwdMosmixRequest, DwdMosmixType

    stations = DwdMosmixRequest(mosmix_type=DwdMosmixType.LARGE)

    print(stations.all().df.head())

Get data for Mosmix-L:

.. ipython:: python

    from wetterdienst.dwd.forecasts import DwdMosmixRequest, DwdMosmixType

    stations = DwdMosmixRequest(
        mosmix_type=DwdMosmixType.LARGE
    ).filter(station_id=["01001", "01008"])

    print(stations.values.all().df.head())

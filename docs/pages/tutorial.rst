########
Tutorial
########


=============
Prerequisites
=============
Import modules necessary for general functioning.

.. ipython:: python

    import warnings
    warnings.filterwarnings("ignore")
    from wetterdienst.dwd.observations import DWDObservationMetadata,
        DWDObservationSites, DWDObservationData, DWDObservationPeriod, DWDObservationResolution,
        DWDObservationParameterSet, DWDObservationParameter
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from matplotlib import cm


========
Metadata
========

Which parameters are available?

=====================
Daily historical data
=====================
.. ipython:: python

    observations_meta = DWDObservationMetadata(
        resolution=DWDObservationResolution.DAILY,
        period=DWDObservationPeriod.HISTORICAL
    )

    # Selection of daily historical data
    print(
        observations_meta.discover_parameter_sets()
    )

    # Individual parameters
    print(
        observations_meta.discover_parameters()
    )


================
Get station list
================
.. ipython:: python

    sites_hdp = DWDObservationSites(
        parameter=DWDObservationParameterSet.PRECIPITATION_MORE,
        resolution=DWDObservationResolution.DAILY,
        period=PeriodType.HISTORICAL
    )

    print("Number of stations with available data: ", sites_hdp.all().sum())
    print("Some of the stations:")
    sites_hdp.all().head()

==========
Query data
==========
For a parameter set
.. ipython:: python
    observation_data = DWDObservationData(
        station_ids=[sites_hdp.all()["STATION_ID"][0])
        parameters=DWDObservationParameterSet.PRECIPITATION_MORE,
        resolution=DWDObservationResolution.DAILY,
        periods=DWDObservationPeriod.HISTORICAL
    )

    print(observation_data.collect_safe())

For a parameter
.. ipython:: python
    observation_data = DWDObservationData(
        station_ids=[sites_hdp.all()["STATION_ID"][0])
        parameters=DWDObservationParameter.DAILY.PRECIPITATION_HEIGHT,
        resolution=DWDObservationResolution.DAILY,
        periods=DWDObservationPeriod.HISTORICAL
    )

    print(observation_data.collect_safe())
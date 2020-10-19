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
        DWDObservationSites, DWDObservationData, DWDObsPeriodType, DWDObsTimeResolution,
        DWDObsParameterSet, DWDObsParameter
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
        time_resolution=DWDObsTimeResolution.DAILY,
        period_type=DWDObsPeriodType.HISTORICAL
    )

    # Selection of daily historical data
    print(
        observations_meta.discover_parameters()
    )


================
Get station list
================
.. ipython:: python

    sites_hdp = DWDObservationSites(
        parameter=DWDObsParameterSet.PRECIPITATION_MORE,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL
    )

    print("Number of stations with available data: ", sites_hdp.all().sum())
    print("Some of the stations:")
    sites_hdp.all().head()

==========
Query data
==========
.. ipython:: python
    observation_data = DWDObservationData(
        station_ids=[sites_hdp.all()["STATION_ID"][0])
        parameter=DWDObsParameterSet.PRECIPITATION_MORE,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL
    )

    print(observation_data.collect_safe())

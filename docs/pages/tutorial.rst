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
    from wetterdienst import DWDObservationMetadata, DWDObservationSites, PeriodType, TimeResolution, Parameter
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from matplotlib import cm


========
Metadata
========

Which parameters are available?


Daily historical data
=====================
.. ipython:: python

    observations_meta = DWDObservationMetadata(
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL
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
        parameter=Parameter.PRECIPITATION_MORE,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL
    )

    print("Number of stations with available data: ", sites_hdp.all()["HAS_FILE"].sum())
    print("Some of the stations:")
    sites_hdp.all().head()

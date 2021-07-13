NOAA (National Oceanic and Atmospheric Administration)
******************************************************

Global Historical Climatology Network
=====================================

Overview
________

NOAA Global Historical Climatology Network is a collection of **hourly** weather data put together from multiple weather
services around the world, even those where at this moment no data is publicly offered. Resolution is fixed on hourly,
because this is the most common and maintainable resolution with most observations practiced all over the world.

.. ipython:: python

    from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest

    meta = NoaaGhcnRequest.discover(flatten=False)

    # Selection of daily historical data
    print(meta)

Special Parameters
__________________

The dataset originally doesn't contain **average daily temperature**, which is why this data is calculated by
wetterdienst with

.. math::

    tmean = (tmax + tmin) / 2

so those values are not actually averages but means.

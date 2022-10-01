GHCN
####

Global Historical Climatology Network

Overview
********

NOAA Global Historical Climatology Network is a collection of **hourly** weather data put together from multiple weather
services around the world, even those where at this moment no data is publicly offered. Resolution is fixed on hourly,
because this is the most common and maintainable resolution with most observations practiced all over the world.

Special Parameters
******************

The dataset originally doesn't contain **average daily temperature**, which is why this data is calculated by
wetterdienst with

.. math::

    tmean = (tmax + tmin) / 2

so those values are not actually averages but means.

Structure
*********

.. toctree::
   :maxdepth: 1

   ghcn/daily

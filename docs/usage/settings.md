.. settings:

Settings
########

Overview
********

Wetterdienst holds core settings in its Settings class. Settings has four layers from which to be sourced:

* Settings arguments e.g. Settings(ts_shape="long")

* environment variables e.g. `WD_TS_SHAPE="wide"`

* local .env file in the same folder (same as above)

* default arguments set by `wetterdienst`

The arguments are overruled in the above order meaning:

* Settings argument overrules environmental variable

* environment variable overrules .env file

* .env file overrules default argument

The following settings are available:

.. list-table:: General
   :widths: 20 70 10
   :header-rows: 1

   * - name
     - description
     - default
   * - cache_disable
     - switch of caching
     - False
   * - cache_dir
     - set the directory where the cache is stored
     - platform specific / "wetterdienst"
   * - fsspec_client_kwargs
     - pass arguments to fsspec, especially for querying data behind a proxy
     - {}

.. list-table:: Timeseries
   :widths: 20 70 10
   :header-rows: 1

   * - name
     - description
     - default
   * - ts_humanize
     - rename parameters to more meaningful names
     - True
   * - ts_shape
     - reshape the returned data to a `long/tidy format`_, one of "long", "wide", if two datasets are requested,
       parameter names are prefixed with the dataset name
     - "long"
   * - ts_si_units
     - convert values to SI units
     - True
   * - ts_skip_empty
     - skip empty stations, requires setting `ts_shape="long"`, empty stations are defined via `ts_skip_threshold` and
       `ts_skip_criteria`
     - True
   * - ts_skip_threshold
     - use with `skip_empty` to define when a station is empty, with 1.0 meaning no
       values per parameter should be missing and e.g. 0.9 meaning 10 per cent of values can be missing
     - 0.95
   * - ts_skip_criteria
     - statistical criteria on which the percentage of actual values is calculated with options "min", "mean",
       "max", where "min" means the percentage of the lowest available parameter is taken, while "mean" takes the
       average percentage of all parameters and "max" does so for the parameter with the most percentage, requires
       setting `ts_shape="long"`
     - "min"
   * - ts_dropna
     - drop all empty entries thus reducing the workload, requires setting `ts_shape="long"`
     - True
   * - ts_interpolation_station_distance
     - maximum distance to the farthest station which is used for interpolation, if the distance is exceeded, the
       station is skipped
     - 40.0
   * - ts_interpolation_use\_
       nearby_station_until_km
     - distance to the nearest station which decides whether the data is used directly from this station or if
       data is being interpolated
     - 1

Python
******

You can import and show Settings like

.. ipython:: python

    from wetterdienst import Settings

    settings = Settings.default()  # default settings, ignoring env variables
    print(settings)

or modify them for your very own request like

.. ipython:: python

    from wetterdienst import Settings

    settings = Settings(ts_shape="wide")
    print(settings)

The evaluation of environment variables can be skipped by using ``ignore_env``:

.. ipython:: python

    from wetterdienst import Settings
    Settings(ignore_env=True)

and to set it back to standard

.. ipython:: python

    from wetterdienst import Settings

    settings = Settings(ts_shape="wide")
    settings = settings.reset()

If your system is running behind a proxy e.g. like `here <https://github.com/earthobservations/wetterdienst/issues/524>`_
you may want to use the `trust_env` setting like

.. ipython:: python

    from wetterdienst import Settings

    settings = Settings(fsspec_client_kwargs={"trust_env": True})

to allow requesting through a proxy.

.. _long/tidy format: https://vita.had.co.nz/papers/tidy-data.pdf

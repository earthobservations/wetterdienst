#################
Behind the scenes
#################

Details
-------
- The ``DWDStationRequest`` class can combine multiple periods/date ranges
  for any number of stations and parameters of one time resolution.
- It wraps ``collect_climate_observations_data``, which in turn combines
  ``create_file_list_for_climate_observations``, ``download_climate_observations_data_parallel``
  and ``parse_climate_observations_data`` for multiple stations.

    - ``create_file_list_for_climate_observations``
        - is used with the help of the metadata to retrieve file paths to
          files for a set of parameters + station id
        - here also **create_new_file_index** can be used

    - ``download_climate_observations_data_parallel``
        - is used with the created file paths to download and store the data
          (second os optionally, in a hdf)

    - ``parse_climate_observations_data``
        - is used to get the data into the Python environment in
          shape of a pandas DataFrame.
        - the data will be ready to be analyzed by you!


Additionally, the following functions allow you to reset the cache of the file/meta index:

- **reset_file_index_cache:**
    - reset the cached file index to get latest list of files (only required for
      constantly running system)

- **reset_meta_index_cache:**
    - reset the cached meta index to get latest list of files (only required for
      constantly running system)

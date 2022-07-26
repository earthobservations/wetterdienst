Minute_5
########

.. dropdown:: Metadata

    .. list-table::
       :widths: 20 80
       :stub-columns: 1

       * - original name
         - 5_minutes
       * - url
         - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/5_minutes/>`_

.. dropdown:: Datasets
    :open:

    .. dropdown:: Precipitation

        .. dropdown:: Metadata

            .. list-table::
               :widths: 20 80
               :stub-columns: 1

               * - original name
                 - precipitation
               * - url
                 - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/5_minutes/precipitation/>`_
               * - description file
                 - missing, simple descriptions within `DWD parameter listing`_
               * - description
                 - missing

            .. _DWD parameter listing: https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx

        .. dropdown:: Parameters
            :open:

            .. dropdown:: precipitation_height
                :open:

                .. list-table::
                   :widths: 20 80
                   :stub-columns: 1

                   * - original name
                     - rs_05
                   * - description file
                     - missing, taken from `DWD parameter listing`_
                   * - description
                     - precipitation height of last 5min
                   * - origin unit
                     - :math:`mm`
                   * - SI unit
                     - :math:`m^3 / m^2`
                   * - constraints
                     - :math:`\geq{0}`

            .. dropdown:: precipitation_height_droplet
                :open:

                .. list-table::
                   :widths: 20 80
                   :stub-columns: 1

                   * - original name
                     - rth_05
                   * - description file
                     - missing, taken from `DWD parameter listing`_
                   * - description
                     - precipitation height of last 5min measured with droplet
                   * - origin unit
                     - :math:`mm`
                   * - SI unit
                     - :math:`m^3 / m^2`
                   * - constraints
                     - :math:`\geq{0}`

            .. dropdown:: precipitation_height_rocker
                :open:

                .. list-table::
                   :widths: 20 80
                   :stub-columns: 1

                   * - original name
                     - rwh_05
                   * - description file
                     - missing, taken from `DWD parameter listing`_
                   * - description
                     - precipitation height of last 5min measured with rocker
                   * - origin unit
                     - :math:`mm`
                   * - SI unit
                     - :math:`m^3 / m^2`
                   * - constraints
                     - :math:`\geq{0}`

            .. dropdown:: precipitation_form
                :open:

                .. list-table::
                   :widths: 20 80
                   :stub-columns: 1

                   * - original name
                     - rs_ind_05
                   * - description file
                     - missing, taken from `DWD parameter listing`_
                   * - description
                     - precipitation form of last 5min, codes taken from 10_minutes dataset

                       .. list-table::
                          :widths: 20 80
                          :stub-columns: 1

                          * - code
                            - meaning
                          * - 0
                            - no precipitation
                          * - 1
                            - precipitation has fallen
                          * - 3
                            - precipitation has fallen and heating of instrument was on

                   * - origin unit
                     - :math:`dimensionless`
                   * - SI unit
                     - :math:`dimensionless`
                   * - constraints
                     - :math:`\in [0, 1, 3]`

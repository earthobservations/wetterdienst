Minute_1
########

.. dropdown:: Metadata

    .. list-table::
       :widths: 20 80
       :stub-columns: 1

       * - original name
         - 1_minute
       * - url
         - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/1_minute/>`_

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
                 - `here <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/1_minute/precipitation/>`_
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
                     - rs_01
                   * - description file
                     - missing, taken from `DWD parameter listing`_
                   * - description
                     - precipitation height of last 1min
                   * - origin unit
                     - :math:`mm`
                   * - SI unit
                     - :math:`m^3 / m^2`
                   * - constraints
                     - :math:`\geq{0}`

                ----

            .. dropdown:: precipitation_height_droplet
                :open:

                .. list-table::
                   :widths: 20 80
                   :stub-columns: 1

                   * - original name
                     - rth_01
                   * - description file
                     - missing, taken from `DWD parameter listing`_
                   * - description
                     - precipitation height of last 1min measured with droplet
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
                     - rwh_01
                   * - description file
                     - missing, taken from `DWD parameter listing`_
                   * - description
                     - precipitation height of last 1min measured with rocker
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
                     - rs_ind_01
                   * - description file
                     - missing, taken from `DWD parameter listing`_
                   * - description
                     - precipitation index, codes taken from 10_minutes dataset

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

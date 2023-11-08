Services
########

The core of wetterdienst is to provide data but as we don't collect the data ourselves we rely on consuming data of
already existing services - mostly governmental services. To simplify the implementation of weather services we created
enumerations and classes that should be used in order to adapt whatever API is offered by a service to the general
scheme of wetterdienst with some handful of attributes to define each API and streamline internal workflows. The
following paragraphs describe how we can/may/should implement a new weather service in wetterdienst as far as our own
experience goes. We'll give examples based on the DwdObservationRequest implementation.


Step 1: Enumerations
********************

The basis for the implementation of a new service are enumerations. A weather service requires 5 enumerations:
- parameter enumeration
- unit enumeration
- dataset enumeration
- resolution enumeration
- period enumeration

Parameter enumeration
=====================

The parameter enumeration could look like this:

.. code-block:: python

    from wetterdienst import Resolution
    from wetterdienst.util.parameter import DatasetTreeCore

    class DwdObservationParameter(DatasetTreeCore):
        # the string "MINUTE_1" has the match the name of a resolution, here Resolution.MINUTE_1
        class MINUTE_1(DatasetTreeCore):
            # precipitation
            class PRECIPITATION(Enum):
                QUALITY = "qn"
                PRECIPITATION_HEIGHT = "rs_01"
                PRECIPITATION_HEIGHT_DROPLET = "rth_01"
                PRECIPITATION_HEIGHT_ROCKER = "rwh_01"
                PRECIPITATION_INDEX = "rs_ind_01"

            PRECIPITATION_HEIGHT = PRECIPITATION.PRECIPITATION_HEIGHT
            PRECIPITATION_HEIGHT_DROPLET = PRECIPITATION.PRECIPITATION_HEIGHT_DROPLET
            PRECIPITATION_HEIGHT_ROCKER = PRECIPITATION.PRECIPITATION_HEIGHT_ROCKER
            PRECIPITATION_INDEX = PRECIPITATION.PRECIPITATION_INDEX

            class ANOTHER_DATASET(Enum):
                QUALITY = "qn"
                # this parameter can't be accessed via MINUTE_1.PRECIPITATION_HEIGHT
                # but has to be queried with something like
                # parameter=(MINUTE_1.ANOTHER_DATASET.PRECIPITATION_HEIGHT, MINUTE_1.ANOTHER_DATASET)
                PRECIPITATION_HEIGHT = "rs_01"

.. hint::

    Here `MINUTE_1` represents the resolution of the data and it has to match one of the resolution names of the core
    resolution (here it matches Resolution.MINUTE_1). It has to match as we access the possible parameters e.g. via
    the requested resolution.

As the DWD observations are offered in datasets, `DwdObservationParameter` has two layers of parameters:

- flat layer of all available parameters for a given resolution with favorites for parameters if two of the same name
  exist in different datasets
- deep layer of a dataset and its own parameters

Here we have a dataset `PRECIPITATION` in `MINUTE_1` resolution, which has four parameters and one quality column.
Those parameters are flattened out by adding links to them on the resolution level. This way we can now access
parameters as follows:

.. code-block:: python

    # PRECIPITATION_HEIGHT of PRECIPITATION dataset
    DwdObservationRequest(
        parameter=DwdObservationParameter.MINUTE_1.PRECIPITATION_HEIGHT
    )

    # same as above
    DwdObservationRequest(
        parameter=DwdObservationParameter.MINUTE_1.PRECIPITATION.PRECIPITATION_HEIGHT
    )

    # PRECIPITATION_HEIGHT of the exact PRECIPITATION dataset, assuming that there would be another dataset with the
    # same parameter
    DwdObservationRequest(
        parameter=(DwdObservationParameter.MINUTE_1.PRECIPITATION.PRECIPITATION_HEIGHT, DwdObservationParameter.MINUTE_1.PRECIPITATION)
    )

.. hint::

    The values of the enumerations should represent the original name of the parameter to create renaming mappings.

Unit enumeration
================

The unit enumeration has to match the parameter enumeration except that it should only have deep levels. For the above
example it should look like:

.. code-block:: python

    from wetterdienst.util.parameter import DatasetTreeCore
    from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum

    class DwdObservationUnit(DatasetTreeCore):
        # the string "MINUTE_1" has the match the name of a resolution, here Resolution.MINUTE_1
        class MINUTE_1(DatasetTreeCore):
            # precipitation
            class PRECIPITATION(UnitEnum):
                QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
                PRECIPITATION_HEIGHT = (
                    OriginUnit.MILLIMETER.value,
                    SIUnit.KILOGRAM_PER_SQUARE_METER.value,
                )
                PRECIPITATION_HEIGHT_DROPLET = (
                    OriginUnit.MILLIMETER.value,
                    SIUnit.KILOGRAM_PER_SQUARE_METER.value,
                )
                PRECIPITATION_HEIGHT_ROCKER = (
                    OriginUnit.MILLIMETER.value,
                    SIUnit.KILOGRAM_PER_SQUARE_METER.value,
                )
                PRECIPITATION_INDEX = (
                    OriginUnit.DIMENSIONLESS.value,
                    SIUnit.DIMENSIONLESS.value,
                )

Each parameter is represented by a tuple with the original unit and the SI unit. General conversations are easily
possible with the pint unit system and for other more complex conversions we may have to define special mappings.

Other enumerations
==================

The remaining enumerations are simple enumerations. The only thing that has to be considered here is that all the names
are matching the ones from the parameter enumeration, the resolution enumeration and the period enumeration:

.. code-block:: python

    from enum import Enum
    from wetterdienst import Resolution, Period

    class DwdObservationDataset(Enum):
        # 1_minute
        PRECIPITATION = "precipitation"

    class DwdObservationResolution(Enum):
        # 1_minute
        MINUTE_1 = Resolution.MINUTE_1.value

    class DwdObservationPeriod(Enum):
        # 1_minute
        HISTORICAL = Period.HISTORICAL.value

Step 2: Request class
*********************

The request class represents a request and carries all the required attributes as well as the values class that is
responsible for acquiring the data later on. The implementation is based on `TimeseriesRequest` from `wetterdienst.core`.

Attributes:

.. code-block:: python

    @property
    @abstractmethod
    def provider(self) -> Provider:
        """Optional enumeration for multiple resolutions"""
        pass

    @property
    @abstractmethod
    def kind(self) -> Kind:
        """Optional enumeration for multiple resolutions"""
        pass

    @property
    @abstractmethod
    def _resolution_base(self) -> Optional[Resolution]:
        """Optional enumeration for multiple resolutions"""
        pass

    @property
    @abstractmethod
    def _resolution_type(self) -> ResolutionType:
        """Resolution type, multi, fixed, ..."""
        pass

    @property
    @abstractmethod
    def _period_type(self) -> PeriodType:
        """Period type, fixed, multi, ..."""
        pass

    @property
    @abstractmethod
    def _period_base(self) -> Optional[Period]:
        """Period base enumeration from which a period string can be parsed"""
        pass

    @property
    @abstractmethod
    def _parameter_base(self) -> Enum:
        """parameter base enumeration from which parameters can be parsed e.g.
        DWDObservationParameter"""
        pass

    @property
    @abstractmethod
    def _data_range(self) -> DataRange:
        """State whether data from this provider is given in fixed data chunks
        or has to be defined over start and end date"""
        pass

    @property
    @abstractmethod
    def _has_datasets(self) -> bool:
        """Boolean if weather service has datasets (when multiple parameters are stored
        in one table/file)"""
        pass

    @property
    def _unique_dataset(self) -> bool:
        """If ALL parameters are stored in one dataset e.g. all daily data is stored in
        one file"""
        if self._has_datasets:
            raise NotImplementedError("define if only one big dataset is available")
        return False

    @property
    @abstractmethod
    def _unit_base(self):
        pass

    @property
    @abstractmethod
    def _values(self):
        """Class to get the values for a request"""
        pass

`TimeseriesRequest` has one abstract method that has to be implemented: the `_all` which manages to get a listing of
stations for the requested datasets/parameters. The listing includes:

- station_id
- start_date
- end_date
- height
- name
- state
- latitude
- longitude

The names can be mapped using the `Columns` enumeration.

Step 3: Values class
*********************

The values class is based on `TimeseriesValues` and manages the acquisition of actual data. The
class is also part of the `TimeseriesRequest` being accessed via the `_values` property. It has to implement the
`_collect_station_parameter` method that takes care of getting values of a parameter/dataset for a station id.

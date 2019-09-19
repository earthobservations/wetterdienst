from typing import List

from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.additionals.functions import check_parameters


class DWDRequest:

    def __init__(self,
                 statid: List[int],
                 parameter: Parameter,
                 time_resolution: TimeResolution,
                 period_type: PeriodType):
        assert isinstance(statid, list)
        if not all([isinstance(s, int) for s in statid]):
            try:
                statid = [int(s) for s in statid]
            except ValueError as e:
                print("Not all statids could be parsed to integers."
                      f"Error: {str(e)}")
        assert isinstance(parameter, Parameter)
        assert isinstance(time_resolution, TimeResolution)
        assert isinstance(period_type, PeriodType)
        assert check_parameters(parameter=parameter,
                                time_resolution=time_resolution,
                                period_type=period_type)

        self.statid = statid
        self.parameter = parameter
        self.time_resolution = time_resolution
        self.period_type = period_type

    # Todo: request could be used to define already what kind of data exists. This could be kind of a callback
    # by other functions

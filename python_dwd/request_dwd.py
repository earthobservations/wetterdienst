from typing import List, Union, Optional
from pandas import Timestamp
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.additionals.functions import check_parameters


class DWDRequest:

    def __init__(self,
                 station_id: List[Union[int, str]],
                 parameter: Parameter,
                 period_type: PeriodType,
                 time_resolution: Optional[TimeResolution] = None,
                 start_date: Optional[Union[str, Timestamp]] = None,
                 end_date: Optional[Union[str, Timestamp]] = None):
        assert isinstance(station_id, list)
        station_id = [int(s) for s in station_id]
        assert isinstance(parameter, Parameter)
        assert isinstance(period_type, PeriodType)
        assert time_resolution is None or (start_date is None and end_date is None), \
            "Define either a time_resolution or both the start_ and end_date and leave the other one empty!"
        if time_resolution:
            assert isinstance(time_resolution, TimeResolution)

            assert check_parameters(parameter=parameter,
                                    time_resolution=time_resolution,
                                    period_type=period_type), \
                "parameter, time_resolution and period_type do not present a possible combination"

        if start_date and end_date:
            if not isinstance(start_date, Timestamp):
                start_date = Timestamp(start_date)

            if not isinstance(end_date, Timestamp):
                end_date = Timestamp(end_date)

            assert start_date <= end_date, "end_date must at least be start_date or later!"

        self.station_id = station_id
        self.parameter = parameter
        self.period_type = period_type
        self.time_resolution = time_resolution
        self.start_date = start_date
        self.end_date = end_date


    # Todo: request could be used to define already what kind of data exists. This could be kind of a callback
    # by other functions


if __name__ == "__main__":
    dwdrequest = DWDRequest(station_id=[1048],
                            parameter=Parameter.CLIMATE_SUMMARY,
                            period_type=PeriodType.NOW,
                            time_resolution=TimeResolution.DAILY)

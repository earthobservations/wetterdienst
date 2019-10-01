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
        if not isinstance(station_id, list):
            raise TypeError("Error: station_id is not of type list")
        try:
            station_id = [int(s) for s in station_id]
        except ValueError as e:
            raise ValueError(f"Error: one or more statid(s) couldn't be converted to integers. {str(e)}")
        if not isinstance(parameter, Parameter):
            raise TypeError("Error: parameter is not an instance of the Parameter enumeration.")
        if not isinstance(period_type, PeriodType):
            raise TypeError("Error: period_type is not an instance of the PeriodType enumeration.")
        if not (time_resolution or (start_date and end_date)):
            raise ValueError(
                "Define either a time_resolution or both the start_ and end_date and leave the other one empty!")
        if time_resolution:
            if not isinstance(time_resolution, TimeResolution):
                raise TypeError("Error: time_resolution is not an instance of the TimeResolution enumeration.")
            if not check_parameters(parameter=parameter,
                                    time_resolution=time_resolution,
                                    period_type=period_type):
                raise ValueError(
                    "Error: parameter, time_resolution and period_type do not present a possible combination")
        if start_date and end_date:
            try:
                start_date, end_date = Timestamp(start_date), Timestamp(end_date)
            except ValueError as e:
                raise ValueError(f"Error: start_date/end_date couldn't be parsed to Timestamp. {str(e)}")

            if not start_date <= end_date:
                raise ValueError("Error: end_date must at least be start_date or later!")

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
                            period_type=PeriodType.HISTORICAL,
                            start_date="1991-01-01",
                            end_date="1981-01-01")

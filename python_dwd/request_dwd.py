from typing import List, Union, Optional, Callable
from pandas import Timestamp
from python_dwd.enumerations.parameter_enumeration import Parameter, PARAMETER_WORDLISTS
from python_dwd.enumerations.period_type_enumeration import PeriodType, PERIODTYPE_WORDLISTS
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution, TIMERESOLUTION_WORDLISTS
from python_dwd.additionals.functions import check_parameters

STRING_TO_ENUMERATION_MAPPING = {
    "parameter": Parameter,
    "period_type": PeriodType,
    "time_resolution": TimeResolution
}

STRING_TO_WORDLIST_MAPPING = {
    "parameter": PARAMETER_WORDLISTS,
    "period_type": PERIODTYPE_WORDLISTS,
    "time_resolution": TIMERESOLUTION_WORDLISTS
}


def extract_numbers_from_string(string: str,
                                number_type: str,
                                decimal: str) -> Union[List[Union[float, int]], None]:
    """

    Args:
        string (str) : the string from which the number should be extracted
        number_type (int, float) : the type that should be casted on the number
        decimal (str) - the type of decimal that is used (either "," or ".")

    Returns:
        list of numbers - the extracted numbers in a list

    """

    if not isinstance(string, str):
        raise TypeError(f"Error: 'string' expected to be str, instead is {type(string)}.")
    if number_type not in ["float", "int"]:
        raise TypeError(f"Error: 'number_type' should be one of float/int, not {str(number_type)}")
    if decimal not in [".", ",", ""]:
        raise ValueError(f"Error: 'decimal' neither ',', '', nor '.', instead is {str(decimal)}.")

    # Keep decimal in string/remove others
    digits_string = "".join([s if s.isdigit() or s == decimal else " " for s in string]).strip()

    # Any number needs at least one digit. Decimals at the edge are removed (e.g. "1234." -> "1234")
    possible_numbers = [string.strip(decimal) for string in digits_string.split(" ")
                        if len(string) > 0 and any([s.isdigit() for s in string])]

    # numbers = []
    #
    # for number in possible_numbers:
    #     try:
    #         if number_type == "float":
    #             numbers.append(float(number))
    #         else:
    #             numbers.append(int(number))
    #     except ValueError:
    #

    return [float(number) if number_type == "float" else int(number) for number in possible_numbers]


class FuzzyExtractor:
    """ The FuzzyExtractor is used to get parameter values in a shape that our functions can work with. It mainly works
    with a pair of parameter name and corresponding values, where the parameter name defines which kind of result we
    to receive and the parameter value which is tried to reshape to this expectation so that the following functions
    won't show problems with the parameters.

    Args:
        parameter_name (str) - the parameter name which is used to identify the objective of the extraction
        parameter_value (list, str, int) - the value itself which has to be remodeled to get the expected shape

    """
    def __init__(self,
                 parameter_name: str,
                 parameter_value: Union[List[Union[int, str]], str, int]):
        if not isinstance(parameter_name, str):
            raise TypeError(f"Error: parameter_name {str(parameter_name)} should be of type str but instead "
                            f"is of type {type(parameter_name)}.")

        if not isinstance(parameter_value, (list, str, int)):
            raise TypeError(f"Error: parameter_name {parameter_name} should be of type str but instead "
                            f"is of type {type(parameter_name)}.")

        if isinstance(parameter_value, list):
            if not parameter_value:
                raise ValueError(f"Error: parameter {parameter_name} is of type list but holds no data.")
            # try:
            #     parameter_value = [int(par_val) for par_val in parameter_value]
            # except ValueError:
            #     raise ValueError(f"Error: one or more values of parameter {parameter_name} could not be converted to "
            #                      f"integers.")

        assert parameter_name in ["station_id", "parameter", "period_type",
                                  "time_resolution", "start_date", "end_date"], \
            "Error: Unknown parameter can not be parsed."

        self.parameter_name = parameter_name
        self.parameter_value = parameter_value

        # self.extract_parameter_from_value()

    def extract_parameter_from_value(self):
        parameter_value = self.parameter_value

        if self.parameter_name == "station_id":
            return self.extract_station_id(parameter_value)

        if self.parameter_name in ["parameter", "period_type", "time_resolution"]:
            parameter_value = self.clean_string(parameter_value)

            for par in STRING_TO_ENUMERATION_MAPPING[self.parameter_name]:

                wordlist = STRING_TO_WORDLIST_MAPPING[self.parameter_name][par]

                cond1 = len(wordlist) == len(parameter_value)

                cond2 = self.find_any_one_word_from_wordlist(parameter_value, wordlist)

                if cond1 and cond2:
                    return par

        if self.parameter_name in ["start_date", "end_date"]:
            return Timestamp(parameter_value)

        # if self.parameter_name == "parameter":
        #     return self.extract_parameter(cleaned_parameter_value)
        # if self.parameter_name == "period_type":
        #     return self.extract_period_type(cleaned_parameter_value)
        # if self.parameter_name == "time_resolution":
        #     return self.extract_time_resolution(cleaned_parameter_value)
        # if self.parameter_name in ["start_date", "end_date"]:
        #     return self.extract_date(cleaned_parameter_value)

    @staticmethod
    def extract_station_id(parameter_value):
        if all([isinstance(par_val, int) for par_val in parameter_value]):
            return parameter_value

        # Input is expected to be list
        station_id = []

        for par_val in parameter_value:
            extracted_station_ids = extract_numbers_from_string(string=par_val, number_type="int", decimal="")

            if len(extracted_station_ids) > 1:
                raise ValueError(f"Error: the string {par_val} holds more then one number. This is not supported as"
                                 "it's unclear which number to take as station id.")

            station_id.extend(extracted_station_ids)

        return station_id

    @staticmethod
    def extract_parameter(parameter_value):
        pass

    @staticmethod
    def extract_period_type(parameter_value):
        pass

    # @staticmethod
    # def extract_time_resolution(parameter_value):
    #     for time_res in TimeResolution:
    #         wordlist = TIMERESOLUTION_WORDLISTS[time_res]
    #
    #         cond1 = len(wordlist) == len(parameter_value)
    #
    #         cond2 = self.find_an
    #
    #         if cond1 and cond2:
    #             return time_res

    @staticmethod
    def extract_date(parameter_value):
        pass

    @staticmethod
    def clean_string(string):
        return string.strip().lower().split("_")

    @staticmethod
    def find_any_one_word_from_wordlist(string_list, word_list):
        return all([any([any([(word in string) if not word.isdigit() else word == string
                        for word in wl]) for string in string_list])
                   for wl in word_list])


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


if __name__ == "__main__":
    dwdrequest = DWDRequest(station_id=[1048],
                            parameter=Parameter.CLIMATE_SUMMARY,
                            period_type=PeriodType.HISTORICAL,
                            start_date="1991-01-01",
                            end_date="1981-01-01")

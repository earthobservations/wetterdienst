from typing import List, Union, Optional
from pandas import Timestamp
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.additionals.functions import check_parameters, cast_to_list

PARAMETER_WORDLIST_MAPPING = {
    Parameter.TEMPERATURE_SOIL:     [["soil", "boden", "ground"], ["temp"]],
    Parameter.TEMPERATURE_AIR:      [["air", "luft"], ["temp"]],
    Parameter.PRECIPITATION:        [["prec", "nied"]],
    Parameter.TEMPERATURE_EXTREME:  [["extr"], ["temp"]],
    Parameter.WIND_EXTREME:         [["extr"], ["wind"]],
    Parameter.SOLAR:                [["sol"]],
    Parameter.WIND:                 [["wind"]],
    Parameter.CLOUD_TYPE:           [["cloud", "wolke"], ["typ"]],
    Parameter.CLOUDINESS:           [["cloud", "bewölkung", "bewölkung"]],
    Parameter.SUNSHINE_DURATION:    [["sun", "sonne"]],
    Parameter.VISBILITY:            [["vis", "sicht"]],
    Parameter.WATER_EQUIVALENT:     [["wat", "was"], ["eq"]],
    Parameter.PRECIPITATION_MORE:   [["more", "mehr"], ["prec", "nied"]],
    Parameter.PRESSURE:             [["press", "druck"]],
    Parameter.CLIMATE_SUMMARY:      [["kl", "cl"]]
}

TIMERESOLUTION_WORDLIST_MAPPING = {
    TimeResolution.MINUTE_1:    [["1"], ["min"]],
    TimeResolution.MINUTE_10:   [["10"], ["min"]],
    TimeResolution.HOURLY:      [["hour", "stünd"]],
    TimeResolution.DAILY:       [["day", "tag", "daily", "täg"]],
    TimeResolution.MONTHLY:     [["month", "monat"]],
    TimeResolution.ANNUAL:      [["year", "jahr", "annual", "jähr"]]
}

PERIODTYPE_WORDLIST_MAPPING = {
    PeriodType.HISTORICAL:  [["hist"]],
    PeriodType.RECENT:      [["rec", "akt"]],
    PeriodType.NOW:         [["now", "jetzt"]]
}


def strip_and_lower_string(string):
    return string.strip().lower()


# def extract_numbers_from_string(string: str,
#                                 decimal: str) -> Optional[List[float]]:
#     """ Function to extract a number from a string. Therefor the function is using the internal
#     str.isdigit() function. The function allows multiple numbers to be extracted. Especially
#     the decimal is important for the detection as multiple signs (".", ",") could be troubling
#     the function. Numbers are returned as floats and further transformations have to be done
#     outside the function.
#
#     Args:
#         string (str) : the string from which the number should be extracted
#         decimal (str) - the type of decimal that is used (either "," or ".")
#
#     Returns:
#         list of numbers - the extracted numbers in a list
#
#     """
#
#     if not isinstance(string, str):
#         raise TypeError(f"Error: 'string' expected to be str, instead is {type(string)}.")
#     if decimal not in [".", ",", ""]:
#         raise ValueError(f"Error: 'decimal' neither ',', '', nor '.', instead is {str(decimal)}.")
#
#     # Keep decimal in string/remove others
#     digits_string = "".join([s if s.isdigit() or s == decimal else " " for s in string]).strip()
#
#     # Any number needs at least one digit. Decimals at the edge are removed (e.g. "1234." -> "1234")
#     possible_numbers = [string.strip(decimal) for string in digits_string.split(" ")
#                         if len(string) > 0 and any([s.isdigit() for s in string])]
#
#     return [float(number) for number in possible_numbers]


def find_any_one_word_from_wordlist(string_list, word_list):
    return all([any([any([(word in string) if not word.isdigit() else word == string
                    for word in wl]) for string in string_list])
               for wl in word_list])


def parse_parameter_from_value(string, parameter_to_wordlist_mapping):
    string_splitted = string.split("_")

    for parameter, wordlist in parameter_to_wordlist_mapping:
        cond1 = len(wordlist) == len(string)

        cond2 = find_any_one_word_from_wordlist(string_splitted, wordlist)

        if cond1 and cond2:
            return parameter


def parse_date(string):
    try:
        return Timestamp(string)
    except ValueError:
        pass


def parse_station_id_to_list_of_ints(station_id: Union[str, int, List[str], List[int]]) -> List[int]:
    """
    A function to parse either a str, an int or a list of any of both to a list of int, which is required for further
    selection of stations that should be returned later on.
    :param station_id: the value representing the station_id as given in possible dtypes
    :return: list of integers with the station_ids
    :raises ValueError: if conversion to float/int does not work depending on input dtypes
    """
    try:
        station_id = station_id.split(" ")
    except AttributeError:
        try:
            station_id = list(station_id)
        except TypeError:
            station_id = [station_id]
    finally:
        station_id = [int(float(id_)) for id_ in station_id]

    return station_id


class DWDStationRequest:
    """
    The DWDStationRequest class represents a request for station data as provided by the DWD service
    """
    def __init__(self,
                 station_id: List[int],
                 parameter: Union[str, Parameter],
                 period_type: Union[str, PeriodType],
                 time_resolution: Union[None, str, list, TimeResolution] = None,
                 start_date: Union[None, str, Timestamp] = None,
                 end_date: Union[None, str, Timestamp] = None):

        if not (time_resolution or (start_date and end_date)):
            raise ValueError("Define either a 'time_resolution' or both the 'start_date' and 'end_date' and "
                             "leave the other one empty!")

        self.station_id = parse_station_id_to_list_of_ints(station_id)

        self.parameter = parameter if isinstance(parameter, Parameter) \
            else parse_parameter_from_value(parameter, PARAMETER_WORDLIST_MAPPING)

        self.period_type = period_type if isinstance(period_type, PeriodType) \
            else parse_parameter_from_value(period_type, PERIODTYPE_WORDLIST_MAPPING)

        self.time_resolution = None if not time_resolution else \
            [parse_parameter_from_value(time_res, TIMERESOLUTION_WORDLIST_MAPPING)
             for time_res in cast_to_list(time_resolution)]

        self.start_date = parse_date(start_date)
        self.end_date = parse_date(end_date)

        if self.start_date:
            self.time_resolution = [*TimeResolution]

        assert self.start_date <= self.end_date, "Error: end_date must at least be start_date or later!"

        for time_res in self.time_resolution:
            if not check_parameters(parameter=self.parameter,
                                    time_resolution=time_res,
                                    period_type=self.period_type):
                self.time_resolution.remove(time_res)
                print(f"Combination of: parameter {self.parameter.value}, time_resolution {time_res.value}, "
                      f"period_type {self.period_type.value} not available and removed.")

        if not self.time_resolution:
            raise ValueError("Error: no combination for parameter, time_resolution and period_type could be found.")

    def __eq__(self, other):
        return [self.station_id,
                self.parameter,
                self.period_type,
                self.time_resolution,
                self.start_date,
                self.end_date] == other

    def __str__(self):
        return ", ".join([self.station_id.value,
                          self.parameter.value,
                          self.period_type.value,
                          "& ".join(self.time_resolution),
                          self.start_date.value,
                          self.end_date.value])

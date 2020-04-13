from typing import List, Union, Optional
from pandas import Timestamp
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.additionals.functions import check_parameters


PARAMETER_WORDLISTS = {
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

TIMERESOLUTION_WORDLISTS = {
    TimeResolution.MINUTE_1:    [["1"], ["min"]],
    TimeResolution.MINUTE_10:   [["10"], ["min"]],
    TimeResolution.HOURLY:      [["hour", "stünd"]],
    TimeResolution.DAILY:       [["day", "tag", "daily", "täg"]],
    TimeResolution.MONTHLY:     [["month", "monat"]],
    TimeResolution.ANNUAL:      [["year", "jahr", "annual", "jähr"]]
}

PERIODTYPE_WORDLISTS = {
    PeriodType.HISTORICAL:  [["hist"]],
    PeriodType.RECENT:      [["rec", "akt"]],
    PeriodType.NOW:         [["now", "jetzt"]]
}


def clean_string(string):
    return string.strip().lower()


def extract_numbers_from_string(string: str,
                                decimal: str) -> Optional[List[float]]:
    """ Function to extract a number from a string. Therefor the function is using the internal
    str.isdigit() function. The function allows multiple numbers to be extracted. Especially
    the decimal is important for the detection as multiple signs (".", ",") could be troubling
    the function. Numbers are returned as floats and further transformations have to be done
    outside the function.

    Args:
        string (str) : the string from which the number should be extracted
        decimal (str) - the type of decimal that is used (either "," or ".")

    Returns:
        list of numbers - the extracted numbers in a list

    """

    if not isinstance(string, str):
        raise TypeError(f"Error: 'string' expected to be str, instead is {type(string)}.")
    if decimal not in [".", ",", ""]:
        raise ValueError(f"Error: 'decimal' neither ',', '', nor '.', instead is {str(decimal)}.")

    # Keep decimal in string/remove others
    digits_string = "".join([s if s.isdigit() or s == decimal else " " for s in string]).strip()

    # Any number needs at least one digit. Decimals at the edge are removed (e.g. "1234." -> "1234")
    possible_numbers = [string.strip(decimal) for string in digits_string.split(" ")
                        if len(string) > 0 and any([s.isdigit() for s in string])]

    return [float(number) for number in possible_numbers]


def find_any_one_word_from_wordlist(string_list, word_list):
    return all([any([any([(word in string) if not word.isdigit() else word == string
                    for word in wl]) for string in string_list])
               for wl in word_list])


def extract_parameter_from_value(string, parameter_to_wordlist_mapping):
    string_splitted = string.split("_")

    for parameter, wordlist in parameter_to_wordlist_mapping:
        cond1 = len(wordlist) == len(string)

        cond2 = find_any_one_word_from_wordlist(string_splitted, wordlist)

        if cond1 and cond2:
            return parameter


def parse_date(string):
    try:
        return Timestamp(string)
    except:
        pass


def extract_station_id(parameter_value):
    if all([isinstance(par_val, int) for par_val in parameter_value]):
        return parameter_value

    if all([isinstance(par_val, float) for par_val in parameter_value]):
        return [int(par_val) for par_val in parameter_value]

    station_id = []  # Input is expected to be list

    for par_val in parameter_value:
        extracted_station_ids = extract_numbers_from_string(string=par_val, decimal="")

        if len(extracted_station_ids) == 0 or len(extracted_station_ids) > 1:
            raise ValueError(f"Error: the string {par_val} holds zero or more then one number. This is not "
                             f"supported as it's unclear which number to take as station id.")

        station_id.extend(extracted_station_ids)

    return station_id


class ClimateRequest:
    def __init__(self,
                 station_id: List[int],
                 parameter: Union[str, Parameter],
                 period_type: Union[str, PeriodType],
                 time_resolution: Union[None, str, list, TimeResolution] = None,
                 start_date: Union[None, str, Timestamp] = None,
                 end_date: Union[None, str, Timestamp] = None):
        if not isinstance(station_id, list):
            try:
                station_id = [station_id]
            except ValueError:
                raise TypeError("Error: station_id is not of type list")

        if not isinstance(parameter, (str, Parameter)):
            raise TypeError("Error: parameter is not an instance of str or the Parameter enumeration.")

        if not isinstance(period_type, (str, PeriodType)):
            raise TypeError("Error: period_type is not an instance of str or the PeriodType enumeration.")

        if not (time_resolution or (start_date and end_date)):
            raise ValueError(
                "Define either a time_resolution or both the start_ and end_date and leave the other one empty!")
        if time_resolution:
            if not isinstance(time_resolution, (str, TimeResolution)):
                raise TypeError("Error: time_resolution is not an instance of str or the TimeResolution enumeration.")

            if not isinstance(time_resolution, list):
                try:
                    time_resolution = [time_resolution]
                except ValueError:
                    raise TypeError("Error: time_resolution can't be converted to a list.")

        if start_date and end_date:
            start_date = FuzzyExtractor("start_date", start_date).extract_parameter_from_value()
            end_date = FuzzyExtractor("end_date", end_date).extract_parameter_from_value()

            if not start_date <= end_date:
                raise ValueError("Error: end_date must at least be start_date or later!")

            time_resolution = [*TimeResolution]

        self.station_id = FuzzyExtractor("station_id", station_id).extract_parameter_from_value()
        self.parameter = FuzzyExtractor("parameter", parameter).extract_parameter_from_value()
        self.period_type = FuzzyExtractor("period_type", period_type).extract_parameter_from_value()
        self.time_resolution = [FuzzyExtractor("time_resolution", time_res).extract_parameter_from_value()
                                for time_res in time_resolution]
        self.start_date = start_date
        self.end_date = end_date

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

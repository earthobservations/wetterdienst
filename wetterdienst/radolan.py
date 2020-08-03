""" Functions for DWD RADOLAN collection """
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.period_type_enumeration import PeriodType


def get_radolan_data(
        time_resolution: TimeResolution,
        period_type: PeriodType
):
    if time_resolution not in (TimeResolution.HOURLY, TimeResolution.DAILY):
        raise ValueError("RADOLAN is only offered in hourly and daily resolution.")

    if period_type not in (PeriodType.HISTORICAL, PeriodType.RECENT):
        raise ValueError("RADOLAN is only offered for the historical and recent period.")

    pass

# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from abc import abstractmethod
from datetime import datetime
from typing import Optional, List, Union

import dateutil.parser
import pandas as pd
import pytz

from wetterdienst import Resolution, Period
from wetterdienst.core.core import Core
from wetterdienst.exceptions import StartDateEndDateError
from wetterdienst.metadata.period import PeriodType
from wetterdienst.metadata.resolution import ResolutionType, Frequency
from wetterdienst.util.enumeration import parse_enumeration_from_template


class ScalarCore(Core):
    """Core for time series related classes """

    @property
    def resolution(self) -> Optional[Resolution]:
        """ Resolution accessor"""
        return self._resolution

    @resolution.setter
    def resolution(self, res) -> None:
        # TODO: add functionality to parse arbitrary resolutions for cases where
        #  resolution has to be determined based on returned data
        if self._resolution_type in (ResolutionType.FIXED, ResolutionType.UNDEFINED):
            self._resolution = res
        else:
            self._resolution = parse_enumeration_from_template(
                res, self._resolution_base, Resolution
            )

    @property
    @abstractmethod
    def _resolution_base(self) -> Optional[Resolution]:
        """ Optional enumeration for multiple resolutions """
        pass

    @property
    @abstractmethod
    def _resolution_type(self) -> ResolutionType:
        """ Resolution type, multi, fixed, ..."""
        pass

    # TODO: implement for source with dynamic resolution
    @staticmethod
    def _determine_resolution(dates: pd.Series) -> Resolution:
        """ Function to determine resolution from a pandas Series of dates """
        pass

    @property
    def frequency(self) -> Frequency:
        """Frequency for the given resolution, used to create a full date range for
        mering"""
        return Frequency[self.resolution.name]

    @property
    @abstractmethod
    def _period_type(self) -> PeriodType:
        """ Period type, fixed, multi, ..."""
        pass

    @property
    @abstractmethod
    def _period_base(self) -> Optional[Period]:
        """ Period base enumeration from which a period string can be parsed """
        pass

    @abstractmethod
    def _parse_period(self, period: List[Period]):
        """ Method for parsing period depending on if multiple are given """
        pass

    def __init__(
        self,
        resolution: Resolution,
        period: Union[Period, List[Period]],
        start_date: Optional[Union[str, datetime]],
        end_date: Optional[Union[str, datetime]],
    ) -> None:
        self.resolution = resolution
        self.period = self._parse_period(period)

        if start_date or end_date:
            # If only one date given, set the other one to equal
            if not start_date:
                start_date = end_date

            if not end_date:
                end_date = start_date

            start_date = dateutil.parser.isoparse(str(start_date))
            if not start_date.tzinfo:
                start_date = start_date.replace(tzinfo=pytz.UTC)

            end_date = dateutil.parser.isoparse(str(end_date))
            if not end_date.tzinfo:
                end_date = end_date.replace(tzinfo=pytz.UTC)

            # TODO: replace this with a response + logging
            if not start_date <= end_date:
                raise StartDateEndDateError(
                    "Error: 'start_date' must be smaller or equal to 'end_date'."
                )

        self.start_date = start_date
        self.end_date = end_date

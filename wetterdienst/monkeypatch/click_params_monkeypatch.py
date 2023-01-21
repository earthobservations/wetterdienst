# """Wetterdienst - Open weather data for humans"""
# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from click_params.base import ListParamType


def convert(self, value, param, ctx):
    if isinstance(value, list):
        return value

    if self._ignore_empty and value == "":
        return []
    value = self._strip_separator(value)
    errors, converted_list = self._convert_expression_to_list(value)
    if errors:
        self.fail(self._error_message.format(errors=errors), param, ctx)

    return converted_list


def activate():
    ListParamType.convert = convert

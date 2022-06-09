# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum
from typing import Optional, Type, Union

from numpy.distutils.misc_util import as_list

from wetterdienst.exceptions import InvalidEnumeration


def parse_enumeration_from_template(
    enum_: Union[str, Enum], intermediate: Type[Enum], base: Optional[Type[Enum]] = None
) -> Optional[Enum]:
    """
    Function used to parse an enumeration(string) to a enumeration based on a template

    :param enum_:           Enumeration as string or Enum
    :param intermediate:    intermediate enumeration from which the enumeration is
                            parsed
    :param base:            base enumeration to which the intermediate one is casted

    :return:                Parsed enumeration from template
    :raises InvalidParameter: if no matching enumeration found
    """
    if enum_ is None:
        return None

    enum_name = None

    # Attempt to decode parameter either as string or Enum item.
    if isinstance(enum_, str):
        enum_name = enum_
    else:
        try:
            enum_name = enum_.name
        except AttributeError:
            pass

    try:
        enum_parsed = intermediate[enum_name.upper()]
    except (KeyError, AttributeError):
        try:
            if isinstance(enum_, str):
                candidates = [enum_, enum_.lower()]
                success = False
                for candidate in candidates:
                    try:
                        enum_parsed = intermediate(candidate)
                        success = True
                        break
                    except ValueError:
                        pass
                if not success:
                    raise ValueError()
            else:
                enum_parsed = intermediate(enum_)
        except ValueError:
            raise InvalidEnumeration(f"{enum_} could not be parsed from {intermediate.__name__}.")

    if base:
        try:
            enum_parsed = base[enum_parsed.name]
        except (KeyError, AttributeError):
            try:
                enum_parsed = base(enum_parsed)
            except ValueError:
                raise InvalidEnumeration(f"{enum_parsed} could not be parsed from {base.__name__}.")

    return enum_parsed


def parse_enumeration(values, intermediate, base=None):
    return [parse_enumeration_from_template(x, intermediate, base) for x in as_list(values)]

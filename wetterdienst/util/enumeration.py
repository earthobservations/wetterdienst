from enum import Enum
from typing import Union, Optional, Type

from numpy.distutils.misc_util import as_list

from wetterdienst.exceptions import InvalidEnumeration


def parse_enumeration_from_template(
    enum_: Union[str, Enum],
    enum_template: Type[Enum],
) -> Optional[Enum]:
    """
    Function used to parse an enumeration(string) to a enumeration based on a template

    :param enum_:           Enumeration as string or Enum
    :param enum_template:   Base enumeration from which the enumeration is parsed

    :return:                Parsed enumeration from template
    :raises InvalidParameter: if no matching enumeration found
    """
    if enum_ is None:
        return None

    enum_name = None

    try:
        enum_name = enum_.upper()
    except AttributeError:
        try:
            enum_name = enum_.name
        except AttributeError:
            pass

    try:
        return enum_template[enum_name]
    except (KeyError, AttributeError):
        try:
            return enum_template(enum_)
        except ValueError:
            raise InvalidEnumeration(
                f"{enum_} could not be parsed from {enum_template.__name__}."
            )


def parse_enumeration(template, values):
    return list(
        map(lambda x: parse_enumeration_from_template(x, template), as_list(values))
    )

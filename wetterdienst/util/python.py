import collections.abc as collections_abc
from typing import Any

from pydantic import BaseModel

string_types = (str,)
binary_types = (bytes,)


def to_list(x: Any, default: Any = None) -> list | Any:  # noqa: ANN401
    """
    Conveniently wrap single items into list, while keeping lists as is.

    From `sqlalchemy.util._collection`.
    """
    if x is None:
        return default
    if (
        not isinstance(x, collections_abc.Iterable)
        or isinstance(x, string_types + binary_types)
        or isinstance(x, BaseModel)
    ):
        return [x]
    elif isinstance(x, list):
        return x
    else:
        return list(x)

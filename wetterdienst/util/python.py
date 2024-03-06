import collections.abc as collections_abc

string_types = (str,)
binary_types = (bytes,)


class classproperty(property):
    """
    A decorator that behaves like @property except that operates
    on classes rather than instances.

    From SQLAlchemy's `sqlalchemy.util.langhelpers`.
    """

    def __init__(self, fget, *arg, **kw):
        super().__init__(fget, *arg, **kw)
        self.__doc__ = fget.__doc__

    def __get__(desc, self, cls):
        return desc.fget(cls)


def to_list(x, default=None):
    """
    Conveniently wrap single items into list, while keeping lists as is.

    From `sqlalchemy.util._collection`.
    """
    if x is None:
        return default
    if not isinstance(x, collections_abc.Iterable) or isinstance(x, string_types + binary_types):
        return [x]
    elif isinstance(x, list):
        return x
    else:
        return list(x)

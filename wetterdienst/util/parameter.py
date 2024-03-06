# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import types

from wetterdienst.util.python import classproperty


class _GetAttrMeta(type):
    # https://stackoverflow.com/questions/33727217/subscriptable-objects-in-class
    def __getitem__(cls, x):
        return getattr(cls, x)

    def __iter__(cls):
        """Getting subclasses which usually represent resolutions"""
        for attr in vars(cls):
            slot = cls[attr]
            if not attr.startswith("_") and not isinstance(slot, types.MethodType):
                yield slot


class DatasetTreeCore(metaclass=_GetAttrMeta):
    @classproperty
    def name(cls):
        return cls.__name__

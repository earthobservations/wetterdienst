# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
class _GetAttrMeta(type):
    # https://stackoverflow.com/questions/33727217/subscriptable-objects-in-class
    def __getitem__(cls, x):
        return getattr(cls, x)


class DatasetTreeCore(metaclass=_GetAttrMeta):
    pass

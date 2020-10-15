class _GetAttrMeta(type):
    # https://stackoverflow.com/questions/33727217/subscriptable-objects-in-class
    def __getitem__(cls, x):
        return getattr(cls, x)


class WDDataColumnBase(metaclass=_GetAttrMeta):
    pass

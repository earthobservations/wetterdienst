class _GetAttrMeta(type):
    # https://stackoverflow.com/questions/33727217/subscriptable-objects-in-class
    def __getitem__(cls, x):
        return getattr(cls, x)


class WDParameterStructureBase(metaclass=_GetAttrMeta):
    pass

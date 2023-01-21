class classproperty(property):
    """
    A decorator that behaves like @property except that operates
    on classes rather than instances.

    From SQLAlchemy's `sqlalchemy.util.langhelpers`.
    """

    def __init__(self, fget, *arg, **kw):
        super(classproperty, self).__init__(fget, *arg, **kw)
        self.__doc__ = fget.__doc__

    def __get__(desc, self, cls):
        return desc.fget(cls)

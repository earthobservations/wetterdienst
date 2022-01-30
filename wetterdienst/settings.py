from contextvars import ContextVar
from dataclasses import dataclass

from environs import Env


@dataclass
class Settings:
    """Wetterdienst class for general settings"""

    env = Env()
    env.read_env()

    with env.prefixed("WD_"):
        # cache
        cache_disable: bool = env.bool("CACHE_DISABLE", False)

        with env.prefixed("SCALAR_"):
            # scalar
            humanize: bool = env.bool("HUMANIZE", True)
            tidy: bool = env.bool("TIDY", True)
            si_units: bool = env.bool("SI_UNITS", True)

    @classmethod
    def reset(cls):
        """Reset Wetterdienst Settings to start"""
        cls.env.read_env()
        cls.__init__(cls)

    @classmethod
    def default(cls):
        """Ignore environmental variables and use all default arguments as defined above"""
        # Put empty env to force using the given defaults
        cls.env = Env()
        cls.__init__(cls)

    _local_settings = ContextVar("local_settings")
    _local_settings_token = None

    # Context manager for managing settings in concurrent situations
    def __enter__(self):
        self._local_settings_token = self._local_settings.set(self)
        return self._local_settings.get()

    def __exit__(self, type_, value, traceback):
        self._local_settings.reset(self._local_settings_token)
        # this is not the same object as the original one
        return Settings.__init__(self)


Settings = Settings()

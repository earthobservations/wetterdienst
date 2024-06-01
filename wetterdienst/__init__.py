# """Wetterdienst - Open weather data for humans"""
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from dataclasses import asdict, dataclass
from textwrap import dedent

from wetterdienst import boot
from wetterdienst.api import Wetterdienst
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.settings import Settings

__appname__ = "wetterdienst"
__version__ = boot.get_version(__appname__)


@dataclass
class Author:
    name: str
    email: str
    github_handle: str


class Info:
    def __init__(self):
        self.name = __appname__
        self.slogan = f"{self.name} - open weather data for humans."
        self.version = __version__
        self.authors = [
            Author("Benjamin Gutzmann", "gutzemann@gmail.com", "gutzbenj"),
            Author("Andreas Motl", "andreas.motl@panodata.org", "amotl"),
        ]
        self.repository = "https://github.com/earthobservations/wetterdienst"
        self.documentation = "https://wetterdienst.readthedocs.io"
        self.cache_dir = Settings().cache_dir

    def __str__(self):
        return dedent(f"""
        ===========================================
        {self.name} - open weather data for humans
        ===========================================
        version:                {self.version}
        authors:                {', '.join([f"{author.name} <{author.email}>" for author in self.authors])}
        documentation:          {self.documentation}
        repository:             {self.repository}
        cache_dir (default):    {self.cache_dir}
        """).strip()

    def to_dict(self):
        return {
            "name": self.name,
            "version": self.version,
            "authors": [asdict(author) for author in self.authors],
            "repository": self.repository,
            "documentation": self.documentation,
            "cache_dir": self.cache_dir,
        }


__all__ = [
    "__appname__",
    "__version__",
    "Author",
    "Info",
    "Kind",
    "Parameter",
    "Period",
    "Provider",
    "Resolution",
    "Settings",
    "Wetterdienst",
]

import pytest


@pytest.fixture
def metadata():
    return {
        "producer": {
            "doi": "10.5281/zenodo.3960624",
            "name": "Wetterdienst",
            "url": "https://github.com/earthobservations/wetterdienst",
        },
        "provider": {
            "copyright": "© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)",
            "country": "Germany",
            "name_english": "German Weather Service",
            "name_local": "Deutscher Wetterdienst",
            "url": "https://opendata.dwd.de/climate_environment/CDC/",
        },
    }

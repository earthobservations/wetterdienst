import pytest

from wetterdienst import Settings


@pytest.fixture(scope="function")
def default_settings():
    return Settings.default()


# True settings
@pytest.fixture
def settings_skip_empty_true():
    return Settings(skip_empty=True, ignore_env=True)


@pytest.fixture
def settings_dropna_true():
    return Settings(dropna=True, ignore_env=True)


# False settings
@pytest.fixture
def settings_humanize_false():
    return Settings(humanize=False, ignore_env=True)


@pytest.fixture
def settings_humanize_si_false():
    return Settings(humanize=False, si_units=False, ignore_env=True)


@pytest.fixture
def settings_humanize_si_tidy_false():
    return Settings(tidy=False, humanize=False, si_units=False, ignore_env=True)


@pytest.fixture
def settings_humanize_tidy_false():
    return Settings(tidy=False, humanize=False, ignore_env=True)


@pytest.fixture
def settings_si_false():
    return Settings(si_units=False, ignore_env=True)


@pytest.fixture
def settings_si_tidy_false():
    return Settings(tidy=False, si_units=False, ignore_env=True)


@pytest.fixture
def settings_tidy_false():
    return Settings(tidy=False, ignore_env=True)

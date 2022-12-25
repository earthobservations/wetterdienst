# https://github.com/orchestracities/ngsi-timeseries-api/pull/441#issuecomment-772835331
from pathlib import Path

import pytest
import requests

from wetterdienst import Settings


@pytest.fixture(scope="function")
def settings():
    return Settings()


@pytest.fixture(scope="function")
def special_settings():
    settings = Settings()
    settings.tidy = False
    return settings


@pytest.fixture(scope="session")
def docker_compose_files(pytestconfig):
    """
    Override this fixture in order to specify a custom location to your
    `docker-compose.yml`.
    """
    return Path(__file__).parent / "docker-compose.yml"


@pytest.fixture(scope="session")
def cratedb(docker_services):
    """
    Spin up CrateDB within a Docker container by referencing
    a service name within your `docker-compose.yml`.
    """
    docker_services.start("cratedb")
    public_port = docker_services.wait_for_service("cratedb", 4200, check_server=check_http)
    return "{docker_services.docker_ip}:{public_port}".format(**locals())


@pytest.fixture(scope="session")
def cratedb_connection(request):
    """
    Provide a CrateDB client connection to be able to execute queries.
    """
    from crate import client

    cratedb_url = request.getfixturevalue("cratedb")
    connection = client.connect(cratedb_url)
    yield connection
    connection.close()


def check_http(docker_ip, public_port):
    """
    Custom probing function for `wait_for_service()`.
    Waits until the service responds to HTTP requests.
    """

    # Define URL to status endpoint.
    url = f"http://{docker_ip}:{public_port}/"

    # Signal "not ready" on any connection errors.
    try:
        response = requests.get(url)
        if response.ok:
            return True
    except requests.exceptions.ConnectionError:
        pass

    return False

""" Tests for global requests.Session """
from wetterdienst.dwd.network import create_dwd_session


def test_create_dwd_session():
    s1 = create_dwd_session()
    s2 = create_dwd_session()

    assert id(s1) == id(s2)

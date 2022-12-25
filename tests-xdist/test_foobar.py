"""
Synopsis::

    pip install pytest pytest-cov pytest-xdist
    poetry run pytest --cov --numprocesses=auto tests-xdist
"""


def test_foo():
    assert True is True


def test_bar():
    assert False is False

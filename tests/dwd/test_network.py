# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE.rst for more info.
""" Tests for global requests.Session """
from wetterdienst.dwd.network import create_dwd_session


def test_create_dwd_session():
    s1 = create_dwd_session()
    s2 = create_dwd_session()

    assert id(s1) == id(s2)

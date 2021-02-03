# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import doctest
from pathlib import Path


def test_readme():
    readme_file = Path(__name__).parent / "README.rst"
    failures, _ = doctest.testfile(
        filename=str(readme_file),
        module_relative=False,
    )

    assert failures == 0

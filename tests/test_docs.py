# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import doctest
from pathlib import Path


def test_readme():
    readme_file = Path(__file__).parent.parent / "README.rst"

    failures, _ = doctest.testfile(
        filename=str(readme_file),
        module_relative=False,
        optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS,
    )

    assert failures == 0

# -*- coding: utf-8 -*-
# Copyright (c) 2018-2020 earthobservations
# Copyright (c) 2018-2020 Andreas Motl <andreas.motl@panodata.org>
# Copyright (c) 2018-2020 Benjamin Gutzmann <gutzemann@gmail.com>
from pathlib import Path
import doctest


def test_readme():
    readme_file = Path(__name__).parent / "README.rst"

    failures, _ = doctest.testfile(
        filename=str(readme_file),
        module_relative=False,
    )

    assert failures == 0

# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import platform
import sys

import pytest

mac_arm64 = sys.platform == "darwin" and platform.machine() == "arm64"
mac_arm64_unsupported = pytest.mark.skipif(
    mac_arm64, reason="can't be tested under mac arm64 due to h5py incompatibility"
)

windows = platform.system() == "Windows"
windows_unsupported = pytest.mark.skipif(
    windows, reason="can't be tested under windows due to unsupported wradlib library"
)

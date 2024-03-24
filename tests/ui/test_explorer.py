# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parent.parent.parent
WETTERDIENST_EXPLORER = ROOT / "wetterdienst/ui/explorer.py"


def test_explorer():
    at = AppTest.from_file(str(WETTERDIENST_EXPLORER))
    at.run()
    assert not at.exception

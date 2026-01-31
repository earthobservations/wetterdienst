# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the CLI command `history`."""

import json

import pytest
from click.testing import CliRunner

from wetterdienst.ui.cli import cli


@pytest.mark.remote
def test_cli_history_multiple_stations() -> None:
    """Test the CLI command `history` for multiple stations."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "history",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl",
            "--station=01048,00011",
            "--with_metadata=true",
            "--with_stations=true",
            "--format=json",
        ],
    )
    assert result.exit_code == 0
    response = json.loads(result.output)
    # basic structure
    assert set(response.keys()) >= {"stations", "histories"}
    assert len(response["stations"]) == 2
    assert len(response["histories"]) == 2

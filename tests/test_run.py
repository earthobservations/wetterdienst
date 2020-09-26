import sys
import shlex
import mock
import runpy


@mock.patch(
    "wetterdienst.dwd.observations.access.collect_climate_observations_data",
    side_effect=[None],
)
def test_run(mock_ccod):
    args = (
        "run.py collect_climate_observations_data "
        '"[1048]" "kl" "daily" "recent" /app/dwd_data/ '
        "False False True False True False"
    )
    sys.argv = shlex.split(args)
    runpy.run_module("wetterdienst.run", run_name="__main__")
    mock_ccod.assert_called_once()

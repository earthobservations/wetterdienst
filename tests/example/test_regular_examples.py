from pathlib import Path

THIS = Path(__name__).parent.absolute()
EXAMPLES_DIR = THIS.parent.parent / "example"


def test_regular_examples():
    from example import (
        mosmix_forecasts,
        observations_hdf5,
        observations_sites,
        observations_sql,
    )

    assert mosmix_forecasts.main() is None
    assert observations_hdf5.main() is None
    assert observations_sites.main() is None
    assert observations_sql.main() is None


""" Testing radar currently not possible as GDAL is required """
# def test_radar_examples():
#     from example.radar import radar_composite_rx, radar_radolan_cdc, radar_radolan_rw,
#     radar_scan_precip, radar_scan_volume, radar_site_dx, radar_sweep_hdf5
#
#     assert radar_composite_rx.main() is None
#     assert radar_radolan_cdc.main() is None
#     assert radar_radolan_rw.main() is None
#     assert radar_scan_precip.main() is None
#     assert radar_scan_volume.main() is None
#     assert radar_site_dx.main() is None
#     assert radar_sweep_hdf5.main() is None

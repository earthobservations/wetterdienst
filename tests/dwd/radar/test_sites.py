from wetterdienst import DWDRadarRequest


def test_radar_sites():

    sites = DWDRadarRequest.get_sites()

    assert len(sites) == 17
    assert sites["ASB"]["name"] == "ASR Borkum"
    assert sites["UMD"]["name"] == "Ummendorf"

from python_dwd.additionals.helpers import _station_id_index_from_seperated_file_name_list


def test__station_id_index_from_seperated_file_name_list():
    assert _station_id_index_from_seperated_file_name_list(
        ['10minutenwerte', 'extrema', 'wind', '00011', 'akt.zip']) == 3

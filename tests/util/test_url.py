# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.util.url import ConnectionString


def test_connectionstring_database_from_path():
    url = "foobar://host:1234/dbname"
    cs = ConnectionString(url)
    assert cs.get_database() == "dbname"


def test_connectionstring_database_from_query_param():
    url = "foobar://host:1234/?database=dbname"
    cs = ConnectionString(url)
    assert cs.get_database() == "dbname"


def test_connectionstring_table_from_query_param():
    url = "foobar://host:1234/?database=dbname&table=tablename"
    cs = ConnectionString(url)
    assert cs.get_table() == "tablename"


def test_connectionstring_temporary_file(tmp_path):
    filepath = tmp_path.joinpath("foobar.txt")
    url = f"file://{filepath}"
    cs = ConnectionString(url)
    assert cs.get_path() == str(filepath)

"""Tests for station history of DWD Obs."""

import datetime as dt
from zoneinfo import ZoneInfo

from dirty_equals import IsApprox, IsDatetime

from wetterdienst.provider.dwd.observation.api import DwdObservationRequest


def test_dwd_obs_daily_climate_summary_history() -> None:
    """Test history query for daily climate summary dataset."""
    stations = DwdObservationRequest(parameters=[("daily", "climate_summary")]).filter_by_station_id("02564")
    history_result = next(stations.history.query())
    history = history_result.history
    assert len(history.name.station) == 1
    station_name = history.name.station[0]
    assert station_name.station_id == "02564"
    assert station_name.station_name == "Kiel-Holtenau"
    assert station_name.start_date == dt.datetime(1927, 2, 1, tzinfo=ZoneInfo("UTC"))
    assert len(history.name.operator) == 4
    first_operator_name = history.name.operator[0]
    assert first_operator_name.station_id == "02564"
    assert first_operator_name.operator_name == "Wetterdienst"
    assert first_operator_name.start_date == dt.datetime(1927, 2, 1, tzinfo=ZoneInfo("UTC"))
    assert first_operator_name.end_date == dt.datetime(1951, 1, 16, tzinfo=ZoneInfo("UTC"))
    second_operator_name = history.name.operator[1]
    assert second_operator_name.station_id == "02564"
    assert second_operator_name.operator_name == "GeophysBdBw"
    assert second_operator_name.start_date == dt.datetime(1951, 1, 17, tzinfo=ZoneInfo("UTC"))
    assert second_operator_name.end_date == dt.datetime(2002, 12, 31, tzinfo=ZoneInfo("UTC"))
    third_operator_name = history.name.operator[2]
    assert third_operator_name.station_id == "02564"
    assert third_operator_name.operator_name == "GeoInfoDBw"
    assert third_operator_name.start_date == dt.datetime(2003, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert third_operator_name.end_date == dt.datetime(2012, 12, 31, tzinfo=ZoneInfo("UTC"))
    fourth_operator_name = history.name.operator[3]
    assert fourth_operator_name.station_id == "02564"
    assert fourth_operator_name.operator_name == "DWD"
    assert fourth_operator_name.start_date == dt.datetime(2013, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert not fourth_operator_name.end_date
    assert len(history.parameter) == 30
    # FM parameters
    parameter_history = history.parameter[0]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1974, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(1974, 12, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "FM"
    assert parameter_history.description == "Tagesmittel der Windgeschwindigkeit m/s  Messnetz 3"
    assert parameter_history.unit == "m/sec"
    assert (
        parameter_history.data_source
        == "Winddaten (Stundenmittel, maximale Windspitze 00:00-23:59 MEZ) generiert aus analogen Registrierungen. "
        "Richtungsangaben in der 32-teiligen Windrose."
    )
    assert parameter_history.extra_info == "arithm.Mittel aus mind. 21 Stundenwerten"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[1]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1975, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2007, 12, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "FM"
    assert parameter_history.description == "Tagesmittel der Windgeschwindigkeit m/s  Messnetz 3"
    assert parameter_history.unit == "m/sec"
    assert (
        parameter_history.data_source
        == "Winddaten (Stundenmittel, maximale Windspitze 00:00-23:59 MEZ) generiert aus analogen Registrierungen. "
        "Richtungsangaben in der 36-teiligen Windrose."
    )
    assert parameter_history.extra_info == "arithm.Mittel aus mind. 21 Stundenwerten"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[2]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "FM"
    assert parameter_history.description == "Tagesmittel der Windgeschwindigkeit m/s  Messnetz 3"
    assert parameter_history.unit == "m/sec"
    assert (
        parameter_history.data_source
        == "Winddaten (Stundenmittel, maximale Windspitze 23:51-23:50 UTC) generiert aus 10-Minutenmittel von "
        "automatischen Stationen der 2. Generation (AMDA), Richtungsangaben in 36-teiliger Windrose"
    )
    assert parameter_history.extra_info == "arithm.Mittel aus mind. 21 Stundenwerten"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    # FX parameters
    parameter_history = history.parameter[3]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1974, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(1974, 12, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "FX"
    assert parameter_history.description == "Maximum der Windspitze Messnetz 3"
    assert parameter_history.unit == "m/sec"
    assert (
        parameter_history.data_source
        == "Winddaten (Stundenmittel, maximale Windspitze 00:00-23:59 MEZ) generiert aus analogen Registrierungen. "
        "Richtungsangaben in der 32-teiligen Windrose."
    )
    assert parameter_history.extra_info == "00:00 - 24:00 MEZ"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[4]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1975, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2007, 12, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "FX"
    assert parameter_history.description == "Maximum der Windspitze Messnetz 3"
    assert parameter_history.unit == "m/sec"
    assert (
        parameter_history.data_source
        == "Winddaten (Stundenmittel, maximale Windspitze 00:00-23:59 MEZ) generiert aus analogen Registrierungen. "
        "Richtungsangaben in der 36-teiligen Windrose."
    )
    assert parameter_history.extra_info == "00:00 - 24:00 MEZ"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[5]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "FX"
    assert parameter_history.description == "Maximum der Windspitze Messnetz 3"
    assert parameter_history.unit == "m/sec"
    assert (
        parameter_history.data_source
        == "Winddaten (Stundenmittel, maximale Windspitze 23:51-23:50 UTC) generiert aus 10-Minutenmittel von "
        "automatischen Stationen der 2. Generation (AMDA), Richtungsangaben in 36-teiliger Windrose"
    )
    assert parameter_history.extra_info == "23:51 - 23:50 UTC"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    # NM parameters
    parameter_history = history.parameter[6]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2001, 3, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "NM"
    assert parameter_history.description == "Tagesmittel des Bedeckungsgrades"
    assert parameter_history.unit == "Achtel"
    assert (
        parameter_history.data_source
        == "Klimadaten aus Klimaroutine des DWD (3 Termine: um  07, 14, 21 MOZ, ab 01.01.1987 07:30,14:30,21:30 MEZ) "
        "und Tageswerte jeweils nach Beobachteranleitung für Klimastationen (BAK)"
    )
    assert parameter_history.extra_info == "arithm.Mittel aus 3 Terminwerten"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[7]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2001, 4, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "NM"
    assert parameter_history.description == "Tagesmittel des Bedeckungsgrades"
    assert parameter_history.unit == "Achtel"
    assert (
        parameter_history.data_source
        == "Klimadaten aus der Klimaroutine nach 1.4.2001, generiert aus SYNOP-Meldungen (3 Termine 06, 12, 18 UTC "
        "und Tageswerte aus stündlichen Werten oder Beobachtungen an Hauptterminen)"
    )
    assert parameter_history.extra_info == "arithm.Mittel aus mind. 21 Stundenwerten"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    # PM parameters
    parameter_history = history.parameter[8]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2001, 3, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "PM"
    assert parameter_history.description == "Tagesmittel des Luftdrucks"
    assert parameter_history.unit == "hpa"
    assert (
        parameter_history.data_source
        == "Klimadaten aus Klimaroutine des DWD (3 Termine: um  07, 14, 21 MOZ, ab 01.01.1987 07:30,14:30,21:30 MEZ) "
        "und Tageswerte jeweils nach Beobachteranleitung für Klimastationen (BAK)"
    )
    assert parameter_history.extra_info == "arithm.Mittel aus 3 Terminwerten"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[9]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2001, 4, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "PM"
    assert parameter_history.description == "Tagesmittel des Luftdrucks"
    assert parameter_history.unit == "hpa"
    assert (
        parameter_history.data_source
        == "Klimadaten aus der Klimaroutine nach 1.4.2001, generiert aus SYNOP-Meldungen (3 Termine 06, 12, 18 UTC "
        "und Tageswerte aus stündlichen Werten oder Beobachtungen an Hauptterminen)"
    )
    assert parameter_history.extra_info == "arithm.Mittel aus mind. 21 Stundenwerten"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    # RSK parameters
    parameter_history = history.parameter[10]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2001, 3, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "RSK"
    assert parameter_history.description == "tgl. Niederschlagshoehe"
    assert parameter_history.unit == "mm"
    assert (
        parameter_history.data_source
        == "Klimadaten aus Klimaroutine des DWD (3 Termine: um  07, 14, 21 MOZ, ab 01.01.1987 07:30,14:30,21:30 MEZ) "
        "und Tageswerte jeweils nach Beobachteranleitung für Klimastationen (BAK)"
    )
    assert parameter_history.extra_info == "07:30 - 07:30 FT. MEZ (bis 1986 MOZ)"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[11]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2001, 4, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "RSK"
    assert parameter_history.description == "tgl. Niederschlagshoehe"
    assert parameter_history.unit == "mm"
    assert (
        parameter_history.data_source
        == "Klimadaten aus der Klimaroutine nach 1.4.2001, generiert aus SYNOP-Meldungen (3 Termine 06, 12, 18 UTC "
        "und Tageswerte aus stündlichen Werten oder Beobachtungen an Hauptterminen)"
    )
    assert parameter_history.extra_info == "06:00 - 06:00 FT. UTC (05:51-05:50 FT.UTC)"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    # RSKF parameters
    parameter_history = history.parameter[12]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2001, 3, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "RSKF"
    assert parameter_history.description == "tgl. Niederschlagsform (=Niederschlagshoehe_ind)"
    assert parameter_history.unit == "numerischer Code"
    assert (
        parameter_history.data_source
        == "Klimadaten aus Klimaroutine des DWD (3 Termine: um  07, 14, 21 MOZ, ab 01.01.1987 07:30,14:30,21:30 MEZ) "
        "und Tageswerte jeweils nach Beobachteranleitung für Klimastationen (BAK)"
    )
    assert parameter_history.extra_info == "07:30 - 07:30 FT. MEZ (bis 1986 MOZ)"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[13]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2001, 4, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "RSKF"
    assert parameter_history.description == "tgl. Niederschlagsform (=Niederschlagshoehe_ind)"
    assert parameter_history.unit == "numerischer Code"
    assert (
        parameter_history.data_source
        == "Klimadaten aus der Klimaroutine nach 1.4.2001, generiert aus SYNOP-Meldungen (3 Termine 06, 12, 18 UTC "
        "und Tageswerte aus stündlichen Werten oder Beobachtungen an Hauptterminen)"
    )
    assert parameter_history.extra_info == "06:00 - 06:00 FT. UTC (05:51-05:50 FT.UTC)"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    # SDK parameters
    parameter_history = history.parameter[14]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2001, 3, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "SDK"
    assert parameter_history.description == "Sonnenscheindauer Tagessumme"
    assert parameter_history.unit == "Stunde"
    assert (
        parameter_history.data_source
        == "Klimadaten aus Klimaroutine des DWD (3 Termine: um  07, 14, 21 MOZ, ab 01.01.1987 07:30,14:30,21:30 MEZ) "
        "und Tageswerte jeweils nach Beobachteranleitung für Klimastationen (BAK)"
    )
    assert parameter_history.extra_info == "00:00-24:00 MEZ (bis 1986 MOZ)"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[15]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2001, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2019, 5, 4, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "SDK"
    assert parameter_history.description == "Sonnenscheindauer Tagessumme"
    assert parameter_history.unit == "Stunde"
    assert (
        parameter_history.data_source
        == "Klimadaten aus der Klimaroutine nach 1.4.2001, generiert aus SYNOP-Meldungen (3 Termine 06, 12, 18 UTC "
        "und Tageswerte aus stündlichen Werten oder Beobachtungen an Hauptterminen)"
    )
    assert parameter_history.extra_info == "00:00 - 24:00 UTC"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    # SHK_TAG parameters
    parameter_history = history.parameter[16]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2001, 3, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "SHK_TAG"
    assert parameter_history.description == "Schneehoehe Tageswert"
    assert parameter_history.unit == "cm"
    assert (
        parameter_history.data_source
        == "Klimadaten aus Klimaroutine des DWD (3 Termine: um  07, 14, 21 MOZ, ab 01.01.1987 07:30,14:30,21:30 MEZ) "
        "und Tageswerte jeweils nach Beobachteranleitung für Klimastationen (BAK)"
    )
    assert parameter_history.extra_info == "07:30 MEZ (bis 1986 MOZ)"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[17]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2001, 4, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "SHK_TAG"
    assert parameter_history.description == "Schneehoehe Tageswert"
    assert parameter_history.unit == "cm"
    assert (
        parameter_history.data_source
        == "Klimadaten aus der Klimaroutine nach 1.4.2001, generiert aus SYNOP-Meldungen (3 Termine 06, 12, 18 UTC "
        "und Tageswerte aus stündlichen Werten oder Beobachtungen an Hauptterminen)"
    )
    assert parameter_history.extra_info == "06 UTC"
    assert (
        parameter_history.special
        == "Winter 2016/2017: Schneehöhen von Stationen mit Schneehöhensensor wurden erst ab 2 cm Schneehöhe "
        "verbreitet, d.h. Schneehöhe=NULL."
    )
    assert parameter_history.literature == ""
    # TGK parameters
    parameter_history = history.parameter[18]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2001, 3, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "TGK"
    assert parameter_history.description == "Minimum der Lufttemperatur am Erdboden in 5cm Hoehe"
    assert parameter_history.unit == "°C"
    assert (
        parameter_history.data_source
        == "Klimadaten aus Klimaroutine des DWD (3 Termine: um  07, 14, 21 MOZ, ab 01.01.1987 07:30,14:30,21:30 MEZ) "
        "und Tageswerte jeweils nach Beobachteranleitung für Klimastationen (BAK)"
    )
    assert parameter_history.extra_info == "21:30 VT. - 07:30 MEZ (bis 1986 MOZ)"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[19]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "TGK"
    assert parameter_history.description == "Minimum der Lufttemperatur am Erdboden in 5cm Hoehe"
    assert parameter_history.unit == "°C"
    assert (
        parameter_history.data_source
        == "Klimadaten aus der Klimaroutine nach 1.4.2001, generiert aus SYNOP-Meldungen (3 Termine 06, 12, 18 UTC "
        "und Tageswerte aus stündlichen Werten oder Beobachtungen an Hauptterminen)"
    )
    assert parameter_history.extra_info == "00:00 - 24:00 UTC gemessen"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    # TMK parameters
    parameter_history = history.parameter[20]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2001, 3, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "TMK"
    assert parameter_history.description == "Tagesmittel der Temperatur"
    assert parameter_history.unit == "°C"
    assert (
        parameter_history.data_source
        == "Klimadaten aus Klimaroutine des DWD (3 Termine: um  07, 14, 21 MOZ, ab 01.01.1987 07:30,14:30,21:30 MEZ) "
        "und Tageswerte jeweils nach Beobachteranleitung für Klimastationen (BAK)"
    )
    assert parameter_history.extra_info == "TMK=(TT1+TT2+(TT3*2))/4"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[21]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2001, 4, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "TMK"
    assert parameter_history.description == "Tagesmittel der Temperatur"
    assert parameter_history.unit == "°C"
    assert (
        parameter_history.data_source
        == "Klimadaten aus der Klimaroutine nach 1.4.2001, generiert aus SYNOP-Meldungen (3 Termine 06, 12, 18 UTC "
        "und Tageswerte aus stündlichen Werten oder Beobachtungen an Hauptterminen)"
    )
    assert parameter_history.extra_info == "arithm.Mittel aus mind. 21 Stundenwerten"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    # TNK parameters
    parameter_history = history.parameter[22]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2001, 3, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "TNK"
    assert parameter_history.description == "Tagesminimum der Lufttemperatur in 2m Hoehe"
    assert parameter_history.unit == "°C"
    assert (
        parameter_history.data_source
        == "Klimadaten aus Klimaroutine des DWD (3 Termine: um  07, 14, 21 MOZ, ab 01.01.1987 07:30,14:30,21:30 MEZ) "
        "und Tageswerte jeweils nach Beobachteranleitung für Klimastationen (BAK)"
    )
    assert parameter_history.extra_info == "21:30 VT. - 21:30 MEZ (bis 1986 MOZ)"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[23]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2006, 4, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "TNK"
    assert parameter_history.description == "Tagesminimum der Lufttemperatur in 2m Hoehe"
    assert parameter_history.unit == "°C"
    assert (
        parameter_history.data_source
        == "Klimadaten aus der Klimaroutine nach 1.4.2001, generiert aus SYNOP-Meldungen (3 Termine 06, 12, 18 UTC "
        "und Tageswerte aus stündlichen Werten oder Beobachtungen an Hauptterminen)"
    )
    assert parameter_history.extra_info == "00:00 - 24:00 UTC gemessen"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    # TXK parameters
    parameter_history = history.parameter[24]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2001, 3, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "TXK"
    assert parameter_history.description == "Tagesmaximum der Lufttemperatur in 2m Höhe"
    assert parameter_history.unit == "°C"
    assert (
        parameter_history.data_source
        == "Klimadaten aus Klimaroutine des DWD (3 Termine: um  07, 14, 21 MOZ, ab 01.01.1987 07:30,14:30,21:30 MEZ) "
        "und Tageswerte jeweils nach Beobachteranleitung für Klimastationen (BAK)"
    )
    assert parameter_history.extra_info == "21:30 VT. - 21:30 MEZ (bis 1986 MOZ)"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[25]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2006, 4, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "TXK"
    assert parameter_history.description == "Tagesmaximum der Lufttemperatur in 2m Höhe"
    assert parameter_history.unit == "°C"
    assert (
        parameter_history.data_source
        == "Klimadaten aus der Klimaroutine nach 1.4.2001, generiert aus SYNOP-Meldungen (3 Termine 06, 12, 18 UTC "
        "und Tageswerte aus stündlichen Werten oder Beobachtungen an Hauptterminen)"
    )
    assert parameter_history.extra_info == "00:00 - 24:00 UTC gemessen"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    # UPM parameters
    parameter_history = history.parameter[26]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2001, 3, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "UPM"
    assert parameter_history.description == "Tagesmittel der Relativen Feuchte"
    assert parameter_history.unit == "%"
    assert (
        parameter_history.data_source
        == "Klimadaten aus Klimaroutine des DWD (3 Termine: um  07, 14, 21 MOZ, ab 01.01.1987 07:30,14:30,21:30 MEZ) "
        "und Tageswerte jeweils nach Beobachteranleitung für Klimastationen (BAK)"
    )
    assert parameter_history.extra_info == "arithm.Mittel aus 3 Terminwerten"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[27]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2001, 4, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "UPM"
    assert parameter_history.description == "Tagesmittel der Relativen Feuchte"
    assert parameter_history.unit == "%"
    assert (
        parameter_history.data_source
        == "Klimadaten aus der Klimaroutine nach 1.4.2001, generiert aus SYNOP-Meldungen (3 Termine 06, 12, 18 UTC "
        "und Tageswerte aus stündlichen Werten oder Beobachtungen an Hauptterminen)"
    )
    assert parameter_history.extra_info == "arithm.Mittel aus mind. 21 Stundenwerten"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    # VPM parameters
    parameter_history = history.parameter[28]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == dt.datetime(2001, 3, 31, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "VPM"
    assert parameter_history.description == "Tagesmittel des Dampfdruckes"
    assert parameter_history.unit == "hpa"
    assert (
        parameter_history.data_source
        == "Klimadaten aus Klimaroutine des DWD (3 Termine: um  07, 14, 21 MOZ, ab 01.01.1987 07:30,14:30,21:30 MEZ) "
        "und Tageswerte jeweils nach Beobachteranleitung für Klimastationen (BAK)"
    )
    assert parameter_history.extra_info == "arithm.Mittel aus 3 Terminwerten"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    parameter_history = history.parameter[29]
    assert parameter_history.station_id == "2564"
    assert parameter_history.start_date == dt.datetime(2001, 4, 1, tzinfo=ZoneInfo("UTC"))
    assert parameter_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert parameter_history.station_name == "Kiel-Holtenau"
    assert parameter_history.parameter == "VPM"
    assert parameter_history.description == "Tagesmittel des Dampfdruckes"
    assert parameter_history.unit == "hpa"
    assert (
        parameter_history.data_source
        == "Klimadaten aus der Klimaroutine nach 1.4.2001, generiert aus SYNOP-Meldungen (3 Termine 06, 12, 18 UTC und "
        "Tageswerte aus stündlichen Werten oder Beobachtungen an Hauptterminen)"
    )
    assert parameter_history.extra_info == "arithm.Mittel aus mind. 21 Stundenwerten"
    assert parameter_history.special == ""
    assert parameter_history.literature == ""
    assert len(history.device) == 49
    device_history = history.device[0]
    assert device_history.device_type == "Stationsbarometer"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 31.0
    assert device_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2009, 11, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Luftdruckmessung, konv."
    device_history = history.device[1]
    assert device_history.device_type == "Luftdrucksensor Vaisala PTB 220"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 31.0
    assert device_history.start_date == dt.datetime(2009, 11, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2013, 2, 25, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Luftdruckmessung, elektr."
    device_history = history.device[2]
    assert device_history.device_type == "Luftdrucksensor Vaisala PTB 220"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 28.0
    assert device_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2015, 10, 14, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Luftdruckmessung, elektr."
    device_history = history.device[3]
    assert device_history.device_type == "Digitalbarometer PTB 330 (ohne Anzeige, einfach)"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 28.0
    assert device_history.start_date == dt.datetime(2015, 10, 15, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2019, 9, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Luftdruckmessung, elektr."
    device_history = history.device[4]
    assert device_history.device_type == "Digitalbarometer PTB 330 (ohne Anzeige, einfach)"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 29.56
    assert device_history.start_date == dt.datetime(2019, 9, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert device_history.method == "Luftdruckmessung, elektr."
    device_history = history.device[5]
    assert device_history.device_type == "Minimumthermometer"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 0.05
    assert device_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2009, 11, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Temperaturmessung, konv."
    device_history = history.device[6]
    assert device_history.device_type == "PT 100 (Luft)"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 0.05
    assert device_history.start_date == dt.datetime(2009, 11, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2013, 2, 25, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Temperaturmessung, elektr."
    device_history = history.device[7]
    assert device_history.device_type == "PT 100 (Luft)"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 0.05
    assert device_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2019, 9, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Temperaturmessung, elektr."
    device_history = history.device[8]
    assert device_history.device_type == "PT 100 (Luft)"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 0.05
    assert device_history.start_date == dt.datetime(2019, 9, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert device_history.method == "Temperaturmessung, elektr."
    device_history = history.device[9]
    assert device_history.device_type == "Psychrometerthermometer (trocken)"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.0
    assert device_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2009, 11, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Temperatur/Feuchtemessung, konv."
    device_history = history.device[10]
    assert device_history.device_type == "PT 100 (Luft)"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.0
    assert device_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2019, 9, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Temperaturmessung, elektr."
    device_history = history.device[11]
    assert device_history.device_type == "PT 100 (Luft)"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 2.0
    assert device_history.start_date == dt.datetime(2019, 9, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert device_history.method == "Temperaturmessung, elektr."
    device_history = history.device[12]
    assert device_history.device_type == "Maximumthermometer"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.2
    assert device_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2009, 11, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Temperaturmessung, konv."
    device_history = history.device[13]
    assert device_history.device_type == "PT 100 (Luft)"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.0
    assert device_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2019, 9, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Temperaturmessung, elektr."
    device_history = history.device[14]
    assert device_history.device_type == "PT 100 (Luft)"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 2.0
    assert device_history.start_date == dt.datetime(2019, 9, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert device_history.method == "Temperaturmessung, elektr."
    device_history = history.device[15]
    assert device_history.device_type == "Minimumthermometer"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.2
    assert device_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2009, 12, 31, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Temperaturmessung, konv."
    device_history = history.device[16]
    assert device_history.device_type == "PT 100 (Luft)"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.0
    assert device_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2019, 9, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Temperaturmessung, elektr."
    device_history = history.device[17]
    assert device_history.device_type == "PT 100 (Luft)"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 2.0
    assert device_history.start_date == dt.datetime(2019, 9, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert device_history.method == "Temperaturmessung, elektr."
    device_history = history.device[18]
    assert device_history.device_type == "Hellmann"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 1.0
    assert device_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2009, 11, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Niederschlagsmenge, konv."
    device_history = history.device[19]
    assert device_history.device_type == "PLUVIO"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 1.0
    assert device_history.start_date == dt.datetime(2009, 11, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2013, 2, 28, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Niederschlagsmenge, elektr."
    device_history = history.device[20]
    assert device_history.device_type == "PLUVIO"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 1.0
    assert device_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2019, 9, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Niederschlagsmenge, elektr."
    device_history = history.device[21]
    assert device_history.device_type == "rain[e]H3, Wägetechnologie"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 1.0
    assert device_history.start_date == dt.datetime(2019, 9, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert device_history.method == "Niederschlagsmenge, elektr."
    device_history = history.device[22]
    assert device_history.device_type == "Niederschlagswächter"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 1.0
    assert device_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2019, 9, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Niederschlagsdauer, elektr."
    device_history = history.device[23]
    assert device_history.device_type == "Niederschlagswächter"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 1.0
    assert device_history.start_date == dt.datetime(2019, 9, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert device_history.method == "Niederschlagsdauer, elektr."
    device_history = history.device[24]
    assert device_history.device_type == "Hygrograph nach Frankenberg"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.0
    assert device_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2009, 12, 31, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Feuchteregistrierung, konv."
    device_history = history.device[25]
    assert device_history.device_type == "Feuchtesonde HMP45D"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.0
    assert device_history.start_date == dt.datetime(2009, 11, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2013, 2, 25, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Feuchtemessung, elektr."
    device_history = history.device[26]
    assert device_history.device_type == "Feuchtesonde HMP45D"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.0
    assert device_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2014, 7, 9, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Feuchtemessung, elektr."
    device_history = history.device[27]
    assert device_history.device_type == "EE33"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.0
    assert device_history.start_date == dt.datetime(2014, 7, 10, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2019, 9, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Feuchtemessung, elektr."
    device_history = history.device[28]
    assert device_history.device_type == "EE33"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 2.0
    assert device_history.start_date == dt.datetime(2019, 9, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert device_history.method == "Feuchtemessung, elektr."
    device_history = history.device[29]
    assert device_history.device_type == "Schneepegel"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height is None
    assert device_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2012, 12, 31, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Schneehöhenmessung, manuell"
    device_history = history.device[30]
    assert device_history.device_type == "Schneehöhensensor SHM 30"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.0
    assert device_history.start_date == dt.datetime(2013, 10, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2019, 9, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Schneehöhenmessung, elektr."
    device_history = history.device[31]
    assert device_history.device_type == "Schneehöhensensor SHM 30"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 2.3
    assert device_history.start_date == dt.datetime(2019, 9, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2024, 8, 12, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Schneehöhenmessung, elektr."
    device_history = history.device[32]
    assert device_history.device_type == "Schneehöhensensor SHM 31"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 2.3
    assert device_history.start_date == dt.datetime(2024, 8, 13, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert device_history.method == "Schneehöhenmessung, elektr."
    device_history = history.device[33]
    assert device_history.device_type == "Sonnenscheinschreiber nach Campbell-Stokes"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 1.6
    assert device_history.start_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2012, 9, 30, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Sonnenscheinregistrierung, konv."
    device_history = history.device[34]
    assert device_history.device_type == "SONIe Sonnenenergie-Sensor"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.7
    assert device_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2014, 11, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Sonnenscheindauer, elektr."
    device_history = history.device[35]
    assert device_history.device_type == "SONIe Sonnenenergie-Sensor e3"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.7
    assert device_history.start_date == dt.datetime(2014, 11, 19, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2019, 3, 4, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Sonnenscheindauer, elektr."
    device_history = history.device[36]
    assert device_history.device_type == "SONIe Sonnenenergie-Sensor e2"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 2.7
    assert device_history.start_date == dt.datetime(2019, 3, 5, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2019, 5, 5, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Sonnenscheindauer, elektr."
    device_history = history.device[37]
    assert device_history.device_type == "Universal-Windschreiber 90"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.15
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 10.0
    assert device_history.start_date == dt.datetime(1974, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(1985, 8, 31, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Windmessung, elektromechanisch"
    device_history = history.device[38]
    assert device_history.device_type == "Universal-Windschreiber 90"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 10.0
    assert device_history.start_date == dt.datetime(1985, 9, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Windmessung, elektromechanisch"
    device_history = history.device[39]
    assert device_history.device_type == "Windmessanlage FA 106"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 10.0
    assert device_history.start_date == dt.datetime(1986, 6, 2, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2013, 2, 25, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Windmessung, elektromechanisch"
    device_history = history.device[40]
    assert device_history.device_type == "Windsensor Classic 4.3303"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 10.0
    assert device_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2019, 9, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Windmessung, elektr."
    device_history = history.device[41]
    assert device_history.device_type == "Windsensor Classic 4.3303"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 10.0
    assert device_history.start_date == dt.datetime(2019, 9, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2020, 10, 13, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Windmessung, elektr."
    device_history = history.device[42]
    assert device_history.device_type == "Ultrasonic Anemometer 2D compact"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 10.0
    assert device_history.start_date == dt.datetime(2020, 10, 14, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert device_history.method == "Windmessung, elektr."
    device_history = history.device[43]
    assert device_history.device_type == "Universal-Windschreiber 90"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.15
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 10.0
    assert device_history.start_date == dt.datetime(1974, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(1985, 8, 31, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Windmessung, elektromechanisch"
    device_history = history.device[44]
    assert device_history.device_type == "Universal-Windschreiber 90"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 10.0
    assert device_history.start_date == dt.datetime(1985, 9, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(1986, 6, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Windmessung, elektromechanisch"
    device_history = history.device[45]
    assert device_history.device_type == "Windmessanlage FA 106"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 10.0
    assert device_history.start_date == dt.datetime(1986, 6, 2, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2013, 2, 25, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Windmessung, elektromechanisch"
    device_history = history.device[46]
    assert device_history.device_type == "Windsensor Classic 4.3303"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 27.0
    assert device_history.device_height == 10.0
    assert device_history.start_date == dt.datetime(2013, 5, 1, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2019, 9, 17, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Windmessung, elektr."
    device_history = history.device[47]
    assert device_history.device_type == "Windsensor Classic 4.3303"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 10.0
    assert device_history.start_date == dt.datetime(2019, 9, 18, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == dt.datetime(2020, 10, 13, tzinfo=ZoneInfo("UTC"))
    assert device_history.method == "Windmessung, elektr."
    device_history = history.device[48]
    assert device_history.device_type == "Ultrasonic Anemometer 2D compact"
    assert device_history.station_id == "2564"
    assert device_history.station_name == "Kiel-Holtenau"
    assert device_history.longitude == 10.14
    assert device_history.latitude == 54.38
    assert device_history.station_height == 28.41
    assert device_history.device_height == 10.0
    assert device_history.start_date == dt.datetime(2020, 10, 14, tzinfo=ZoneInfo("UTC"))
    assert device_history.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert device_history.method == "Windmessung, elektr."
    assert len(history.geography) == 8
    geography = history.geography[0]
    assert geography.station_id == "2564"
    assert geography.station_height == 4.0
    assert geography.latitude == 54.3767
    assert geography.longitude == 10.1601
    assert geography.start_date == dt.datetime(1927, 2, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.end_date == dt.datetime(1935, 3, 31, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.station_name == "Kiel-Holtenau"
    geography = history.geography[1]
    assert geography.station_id == "2564"
    assert geography.station_height == 26.0
    assert geography.latitude == 54.3766
    assert geography.longitude == 10.1485
    assert geography.start_date == dt.datetime(1935, 4, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.end_date == dt.datetime(1946, 8, 7, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.station_name == "Kiel-Holtenau"
    geography = history.geography[2]
    assert geography.station_id == "2564"
    assert geography.station_height == 6.0
    assert geography.latitude == 54.3696
    assert geography.longitude == 10.1522
    assert geography.start_date == dt.datetime(1946, 8, 8, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.end_date == dt.datetime(1967, 12, 31, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.station_name == "Kiel-Holtenau"
    geography = history.geography[3]
    assert geography.station_id == "2564"
    assert geography.station_height == 27.0
    assert geography.latitude == 54.3773
    assert geography.longitude == 10.1469
    assert geography.start_date == dt.datetime(1968, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.end_date == dt.datetime(1985, 8, 31, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.station_name == "Kiel-Holtenau"
    geography = history.geography[4]
    assert geography.station_id == "2564"
    assert geography.station_height == 27.0
    assert geography.latitude == 54.3761
    assert geography.longitude == 10.1434
    assert geography.start_date == dt.datetime(1985, 9, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.end_date == dt.datetime(1986, 5, 31, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.station_name == "Kiel-Holtenau"
    geography = history.geography[5]
    assert geography.station_id == "2564"
    assert geography.station_height == 27.0
    assert geography.latitude == 54.3761
    assert geography.longitude == 10.1434
    assert geography.start_date == dt.datetime(1986, 6, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.end_date == dt.datetime(2013, 2, 28, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.station_name == "Kiel-Holtenau"
    geography = history.geography[6]
    assert geography.station_id == "2564"
    assert geography.station_height == 27.0
    assert geography.latitude == 54.3761
    assert geography.longitude == 10.1434
    assert geography.start_date == dt.datetime(2013, 3, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.end_date == dt.datetime(2019, 9, 17, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.station_name == "Kiel-Holtenau"
    geography = history.geography[7]
    assert geography.station_id == "2564"
    assert geography.station_height == 28.41
    assert geography.latitude == 54.3776
    assert geography.longitude == 10.1424
    assert geography.start_date == dt.datetime(2019, 9, 18, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert geography.end_date is not None
    assert geography.end_date > geography.start_date
    assert geography.station_name == "Kiel-Holtenau"
    assert len(history.missing_data.summary) == 14
    summary_missing_data = history.missing_data.summary[0]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "TMK"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert summary_missing_data.missing_count == IsApprox(147, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"
    summary_missing_data = history.missing_data.summary[1]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "TXK"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert summary_missing_data.missing_count == IsApprox(2176, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"
    summary_missing_data = history.missing_data.summary[2]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "TNK"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert summary_missing_data.missing_count == IsApprox(2176, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"
    summary_missing_data = history.missing_data.summary[3]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "TGK"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert summary_missing_data.missing_count == IsApprox(4424, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"
    summary_missing_data = history.missing_data.summary[4]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "PM"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert summary_missing_data.missing_count == IsApprox(235, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"
    summary_missing_data = history.missing_data.summary[5]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "FM"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert summary_missing_data.missing_count == IsApprox(1983, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"
    summary_missing_data = history.missing_data.summary[6]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "FX"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert summary_missing_data.missing_count == IsApprox(2015, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"
    summary_missing_data = history.missing_data.summary[7]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "UPM"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert summary_missing_data.missing_count == IsApprox(249, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"
    summary_missing_data = history.missing_data.summary[8]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "VPM"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert summary_missing_data.missing_count == IsApprox(242, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"
    summary_missing_data = history.missing_data.summary[9]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "NM"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert summary_missing_data.missing_count == IsApprox(272, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"
    summary_missing_data = history.missing_data.summary[10]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "SDK"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == dt.datetime(2019, 5, 4, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.missing_count == IsApprox(251, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"
    summary_missing_data = history.missing_data.summary[11]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "RSK"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert summary_missing_data.missing_count == IsApprox(148, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"
    summary_missing_data = history.missing_data.summary[12]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "RSKF"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert summary_missing_data.missing_count == IsApprox(147, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"
    summary_missing_data = history.missing_data.summary[13]
    assert summary_missing_data.station_id == "02564"
    assert summary_missing_data.station_name == "Kiel-Holtenau"
    assert summary_missing_data.parameter == "SHK_TAG"
    assert summary_missing_data.start_date == dt.datetime(1974, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert summary_missing_data.end_date == IsDatetime(gt=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert summary_missing_data.missing_count == IsApprox(1712, delta=200)
    assert summary_missing_data.description == "Gesamt_Messzeitraum"


def test_dwd_obs_monthly_climate_summary_history() -> None:
    """Test history query for monthly climate_summary dataset.

    We only assert numbers of entries here to make sure both wind_extreme files for each station are taken into account.
    """
    stations = DwdObservationRequest(parameters=[("monthly", "climate_summary")]).filter_by_station_id("2564")
    history_result = next(stations.history.query())
    history = history_result.history
    assert len(history.name.station) == 1
    assert len(history.name.operator) == 4
    assert len(history.parameter) == 23
    assert len(history.device) == 26
    assert len(history.geography) == 8
    assert len(history.missing_data.summary) == 11
    assert len(history.missing_data.periods) == 158


def test_dwd_obs_subdaily_wind_extreme_history() -> None:
    """Test history query for subdaily wind_extreme dataset.

    We only assert numbers of entries here to make sure both wind_extreme files for each station are taken into account.
    """
    stations = DwdObservationRequest(parameters=[("subdaily", "wind_extreme")]).filter_by_station_id("2564")
    history_result = next(stations.history.query())
    history = history_result.history
    assert len(history.name.station) == 2
    assert len(history.name.operator) == 8
    assert len(history.parameter) == 4
    assert len(history.device) == 8
    assert len(history.geography) == 16
    assert len(history.missing_data.summary) == 2
    assert len(history.missing_data.periods) == IsApprox(3909, delta=200)
    # one special assertion here for parameter names
    assert {parameter.parameter for parameter in history.parameter} == {"FX_911_3", "FX_911_6"}

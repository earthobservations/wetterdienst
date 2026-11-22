/**
 * "So wird Wetter gemessen" auf Deutsch (GH-3787).
 *
 * Der deutsche Text sagt dasselbe wie `en.ts`, Eintrag für Eintrag und Absatz für Absatz
 * (`tests/unit/measurement.test.ts` hält die beiden aneinander). Jede Aussage stützt sich auf eine der `sources`
 * des Eintrags, nach Band, Kapitel und Abschnitt, oder auf die Datei des Anbieters, die der Eintrag nennt; was keine
 * Quelle trägt, steht nicht da. Die Titel der zitierten Werke bleiben in ihrer Sprache.
 *
 * Die Ausgaben des WMO-Leitfadens sind die jeweils aktuellen der Bände: die von 2024 für Band I, II und III (gegen die
 * offiziellen PDFs geprüft; die Kapitel 2, 5 und 8 von Band I, Kapitel 2 von Band II und alle Kapitel von Band III
 * außer Kapitel 5 sind der Text der Ausgabe 2023) und die von 2023 für Band V. Die vorläufige Ausgabe 2026 wird nicht
 * verwendet.
 */

import type { MeasurementSource, MeasurementTexts } from './types'

const WMO_I = 'https://library.wmo.int/records/item/68695-guide-to-instruments-and-methods-of-observation'
const WMO_II = 'https://library.wmo.int/records/item/68660-guide-to-instruments-and-methods-of-observation'
const WMO_III = 'https://library.wmo.int/records/item/68661-guide-to-instruments-and-methods-of-observation'
const WMO_V = 'https://library.wmo.int/records/item/68663-guide-to-instruments-and-methods-of-observation'
const DWD_DAILY = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/BESCHREIBUNG_obsgermany-climate-daily-kl_de.pdf'

/** Wo die Stationsdateien der Tagesdaten liegen: sie haben keine eigene Adresse, sie stecken im Archiv jeder Station */
const DWD_KL = 'opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/'
const STATION_FILES = `DWD Climate Data Center, Dateien in den Stationsarchiven von ${DWD_KL}recent/ (tageswerte_KL_03987_akt.zip, tageswerte_KL_01420_akt.zip) und ${DWD_KL}historical/ (tageswerte_KL_01048_19340101_20251231_hist.zip), am 20. November 2026 gelesen für Potsdam (03987), Dresden-Klotzsche (01048) und Frankfurt/Main (01420):`

/** Die stündlichen Datensätze des DWD: die Stationsdateien der Einträge zu Druck, Feuchte, Strahlung und Sichtweite stecken in den Archiven dieser Ordner */
const DWD_HOURLY = 'opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/'
const DWD_HOURLY_PRESSURE = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/pressure/BESCHREIBUNG_obsgermany_climate_hourly_pressure_de.pdf'
const DWD_HOURLY_HUMIDITY = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/BESCHREIBUNG_obsgermany_climate_hourly_air_temperature_de.pdf'
const DWD_HOURLY_SOLAR = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/solar/BESCHREIBUNG_obsgermany_climate_hourly_solar_de.pdf'
const DWD_HOURLY_VISIBILITY = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/visibility/BESCHREIBUNG_obsgermany_climate_hourly_visibility_de.pdf'
const NOAA_GHCNH = 'https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf'

const DWD_HOURLY_CLOUDINESS = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloudiness/BESCHREIBUNG_obsgermany_climate_hourly_cloudiness_de.pdf'
const DWD_HOURLY_WEATHER = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/weather_phenomena/BESCHREIBUNG_obsgermany_climate_hourly_weather_phenomena_de.pdf'
/** Der abgeleitete Datensatz zum Boden des DWD: Verdunstung und Bodenfeuchte werden von einem Modell berechnet */
const DWD_SOIL_DAILY_DE = 'https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/daily/recent/BESCHREIBUNG_derived_ermany_soil_daily_recent_de_v2.pdf'
/** Der Monatsdatensatz des DWD: seine Beschreibung sagt, wie ein Monatswert gebildet wird und was bei den Tagesmitteln zu beachten ist */
const DWD_MONTHLY = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/monthly/kl/BESCHREIBUNG_obsgermany-climate-monthly-kl_de.pdf'
/** Die Stadtklimastationen des DWD (climate_urban): die Beschreibung der stündlichen Lufttemperatur und Luftfeuchte sagt, wofür die Stationen da sind */
const DWD_URBAN = 'opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/'
const DWD_URBAN_TU = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/air_temperature/recent/BESCHREIBUNG_obsgermany_climate_urban_hourly_tu_recent_de.pdf'
/** Die Straßenwetterstationen des DWD: das BUFR-Template sagt, was eine Station meldet, der Hinweis zum SH10-Schlüssel, was die Daten sind und was nicht */
const DWD_ROAD = 'opendata.dwd.de/weather/weather_reports/road_weather_stations/'
const DWD_ROAD_TEMPLATE = 'https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/bufr/bufr_templates_sws_national_pdf.pdf?__blob=publicationFile&v=3'
const DWD_ROAD_NOTICE = 'https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/bufr/sws_sh10_code_pdf.pdf?__blob=publicationFile&v=4'

/** Das Radar des DWD: seine Seite zu den Radarprodukten und die Blätter seiner Komposite, RADVOR und RADOLAN */
const DWD_RADAR_PRODUCTS = 'https://www.dwd.de/DE/leistungen/radarprodukte/radarprodukte.html'
const DWD_RADVOR = 'https://www.dwd.de/DE/leistungen/radvor/radvor.html'
const DWD_RADOLAN = 'https://www.dwd.de/DE/leistungen/radolan/radolan.html'
/** Die Hydrologiedienste, auf deren eigene Seiten sich der Eintrag zu Wasserstand und Abfluss stützt, und der Guide to Hydrological Practices der WMO */
const WMO_168 = 'https://community.wmo.int/en/product/605'
const WSV_HELP = 'https://pegelonline.wsv.de/gast/hilfe'
const EA_HYDROLOGY = 'https://environment.data.gov.uk/hydrology/doc/reference'
const HUBEAU_HYDROMETRY = 'https://hubeau.eaufrance.fr/page/api-hydrometrie'
const IMGW_HYDROLOGY = 'https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/'
const WETTERDIENST_DOCS = 'https://wetterdienst.readthedocs.io/en/latest/data/'
const KNMI_DAILY = 'https://www.knmi.nl/nederland-nu/klimatologie/daggegevens'
const NOAA_GHCN_DAILY = 'https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt'

/** Die Tagesdaten des KNMI, die die Einträge zu Verdunstung und Wolken nennen, wo sich Anbieter unterscheiden */
function knmi(plain: string, citation: string): MeasurementSource {
  return {
    plain: `Das Königlich Niederländische Meteorologische Institut (KNMI) ist der nationale Wetterdienst der Niederlande. ${plain}`,
    citation,
    href: KNMI_DAILY,
  }
}

/** Der tägliche Datensatz der NOAA, den die Einträge zu Verdunstung, gegenwärtigem Wetter und Wolken nennen, wo sich Anbieter unterscheiden */
function ghcnDaily(plain: string, citation: string): MeasurementSource {
  return {
    plain: `Die National Centers for Environmental Information (NCEI) der amerikanischen NOAA veröffentlichen GHCN-Daily, die täglichen Beobachtungen von Wetterstationen. ${plain}`,
    citation,
    href: NOAA_GHCN_DAILY,
  }
}

/** Der stündliche Datensatz der NOAA, den die Einträge zu Druck, Feuchte und Sichtweite nennen, wo sich Anbieter unterscheiden */
function ghcnh(plain: string, citation: string): MeasurementSource {
  return {
    plain: `Die National Centers for Environmental Information (NCEI) der amerikanischen NOAA veröffentlichen GHCNh, die stündlichen Beobachtungen von Wetterstationen aus der ganzen Welt. ${plain}`,
    citation: `NOAA NCEI. Global Historical Climatology Network hourly (GHCNh), documentation, version 1.1.0 (10 March 2026). ${citation}`,
    href: NOAA_GHCNH,
  }
}

/** Was die WMO ist, einmal, für jeden Eintrag, der ihren Leitfaden nennt */
const WMO_PLAIN = 'Die Weltorganisation für Meteorologie (WMO) ist die Organisation der Vereinten Nationen, in der sich die nationalen Wetterdienste darauf einigen, wie Wetter gemessen und verglichen wird. Der Leitfaden Guide to Instruments and Methods of Observation ist ihr Handbuch dafür.'

/** Band I, II und III: die Ausgabe 2024, die aktuelle */
function wmoGuide(plain: string, citation: string, href: string): MeasurementSource {
  return { plain: `${WMO_PLAIN} ${plain}`, citation: `WMO (2024). Guide to Instruments and Methods of Observation (WMO-No. 8), 2024 edition. ${citation}`, href }
}

/** Band V: seine Ausgabe 2023 ist die aktuelle */
function wmoGuideV(plain: string, citation: string): MeasurementSource {
  return { plain: `${WMO_PLAIN} ${plain}`, citation: `WMO (2023). Guide to Instruments and Methods of Observation (WMO-No. 8), 2023 edition. ${citation}`, href: WMO_V }
}

function dwdFiles(plain: string, citation: string, href: string): MeasurementSource {
  return { plain: `Der Deutsche Wetterdienst (DWD) ist der nationale Wetterdienst Deutschlands. ${plain}`, citation, href }
}

export const measurement: MeasurementTexts = {
  'temperature': {
    title: 'Luft- und Bodentemperatur',
    summary: 'Warum die Lufttemperatur etwa zwei Meter über dem Boden in einem beschatteten, belüfteten Gehäuse gemessen wird und was das für die Zahl bedeutet.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Eine Wetterstation misst die Lufttemperatur mit einem elektrischen Thermometer, meist einem Platin-Widerstandsthermometer: einem Draht oder Film aus Platin, dessen elektrischer Widerstand sich mit der Temperatur ändert (das übliche Format heißt Pt100). Die WMO nennt elektrische Thermometer als die empfohlenen Instrumente.',
          'Nach der Definition der WMO ist die Lufttemperatur das, was ein Thermometer anzeigt, das an einem Ort der Luft ausgesetzt ist, der vor direktem Sonnenlicht geschützt ist. Sonne, Wolken und Boden senden Strahlung aus, die durch die Luft geht, ohne sie nennenswert zu erwärmen; ein Thermometer im Freien nimmt sie aber auf. Bei gewöhnlichen Instrumenten kann die Anzeige dann unter äußerst ungünstigen Bedingungen um bis zu 25 K danebenliegen. Darum sitzt das Thermometer in einem Strahlungsschutz, der es vor der Strahlung und vor Regen schützt und die Luft trotzdem hindurchlässt.',
          'Die Standardhöhe liegt zwischen 1,25 und 2 m über dem Boden, über natürlichem Grund, am besten Gras, auf ebenem, offenem Gelände und nicht in der Nähe von Bäumen oder Gebäuden. Die Höhe ist festgelegt, weil es in der untersten Luftschicht große senkrechte Temperaturunterschiede geben kann.',
          'Die Bodentemperatur wird in den Standardtiefen 5, 10, 20, 50 und 100 cm gemessen, auf einer ebenen Fläche aus nacktem Boden. Die Grasminimumtemperatur, die tiefste Temperatur einer Nacht, wird 5 cm über kurzem Gras gemessen.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Die Lufttemperatur ändert sich innerhalb von Sekunden um ein oder zwei Grad, ein einzelner Messwert sagt daher wenig. Das Thermometer soll träge genug sein, um das auszugleichen (die WMO empfiehlt eine Zeitkonstante von etwa 20 Sekunden). Für den internationalen Austausch und für viele operationelle Anwendungen ist ein gemeldeter Messwert ein Mittelwert und steht laut Übereinkunft für die vorangegangenen 1 bis 10 Minuten (beim Wind 2 oder 10 Minuten).',
          'Der höchste und der niedrigste Wert eines Zeitraums stammen aus der Aufzeichnung selbst: Wird ein elektrisches Thermometer fortlaufend und oft genug aufgezeichnet, lassen sich die Extreme aus den Messdaten bestimmen, und es braucht kein eigenes Maximum- oder Minimumthermometer.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'An einem Tag mit starker Sonne und schwachem Wind kann die Luft in einer natürlich belüfteten Lamellenhütte wärmer sein als die wahre Lufttemperatur, in einer klaren, windstillen Nacht etwas kühler; die WMO nennt in Extremfällen Fehler von bis zu etwa 2,5 K und -0,5 K. Zu wenig Luftdurchzug durch den Strahlungsschutz (Wind unter 1 m/s), vor allem bei starker Sonne, und ein nasser Strahlungsschutz oder Fühler nach Regen, die durch Verdunstung gekühlt werden, sind weitere Fehlerquellen.',
          'Eine Station ist nicht die ganze Gegend. Der Messwert soll für die freie Luft um die Station stehen, in Städten sind die örtlichen Unterschiede aber größer, und Messungen auf einem Dach sind von zweifelhaftem Nutzen. Ändert sich der Strahlungsschutz, der Bewuchs oder die Bebauung um eine Station, ändert sich, was sie misst; das zählt, wenn Jahre verglichen werden.',
          'Eine Bodentemperatur beschreibt eine Fläche nackten Bodens von etwa 2 m mal 2 m. Sie hängt vom Boden, seiner Bedeckung und der Neigung ab; deshalb empfiehlt die WMO, diese festzuhalten.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Einen einzigen Strahlungsschutz für die ganze Welt gibt es nicht. Die WMO hält fest, dass es schwierig ist, eine Bauart für weltweite Messungen zu empfehlen, weil Anwendungen, Automatisierungsgrad und Klima sich unterscheiden, und es sind sehr verschiedene Bauarten im Einsatz.',
          'Der DWD führt in den Dateien, die zu den Daten gehören, für jede Station das Instrument und seine Höhe über dem Boden auf. In Potsdam zum Beispiel wird die Lufttemperatur seit 1978 mit einem Pt100-Thermometer in 2 m Höhe gemessen und die Minimumtemperatur in 5 cm über dem Boden seit 1986 mit einem Pt100.',
          'Welcher Zeitabschnitt zu einem Tagesmaximum oder -minimum gehört, bestimmt der Anbieter. In den Tagesdaten des DWD sind es ab April 2001 an den geprüften Stationen 00:00 bis 24:00 UTC, und das Tagesmittel ist das arithmetische Mittel aus mindestens 21 Stundenwerten. Welchen Tag andere Anbieter verwenden, steht unter „Zeit“.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 2 zur Temperatur stammen in diesem Eintrag die Definition, die Höhe, der Strahlungsschutz und die typischen Fehler.',
        'Volume I, Chapter 2 (Measurement of temperature), sections 2.1.1, 2.1.3.3, 2.1.4, 2.1.4.1, 2.1.4.2, 2.1.4.3, 2.2.1.1, 2.2.3, 2.5, 2.5.1.',
        WMO_I,
      ),
      wmoGuideV(
        'Aus Band V, Kapitel 3 zur Datenreduktion stammt in diesem Eintrag die Regel, dass ein gemeldeter Wert für die vorangegangenen 1 bis 10 Minuten steht.',
        'Volume V (Quality assurance and management of observing systems), Chapter 3 (Data reduction), section 3.5.',
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welches Instrument in welcher Höhe benutzt wurde und was ein Tageswert abdeckt.',
        `${STATION_FILES} Metadaten_Geraete_Lufttemperatur_*, Metadaten_Geraete_Lufttemp_Am_Erdb_Minimum_* und Metadaten_Parameter_klima_tag_*; Datensatzbeschreibung „Tägliche Stationsbeobachtungen (Temperatur, Druck, Niederschlag, Sonnenscheindauer, etc.) für Deutschland“, Version v24.3 (2024).`,
        DWD_DAILY,
      ),
    ],
  },

  'pressure': {
    title: 'Luftdruck und seine Umrechnung auf Meereshöhe',
    summary: 'Der Luftdruck ist das Gewicht der Luft über der Station. Um Stationen in verschiedenen Höhen zu vergleichen, wird er auf Meereshöhe umgerechnet, und diese Zahl ist eine Rechnung und keine Messung.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Der Luftdruck ist die Kraft, die das Gewicht der Luft über einer Fläche auf jede Flächeneinheit ausübt. Die Einheit ist das Pascal; in der Meteorologie ist es das Hektopascal (hPa), das 100 Pa entspricht und dasselbe ist wie das ältere Millibar.',
          'Der Luftdruck wird meist mit elektronischen oder Aneroid-Barometern gemessen. In einem Aneroid-Barometer wird eine geschlossene, teilweise luftleer gepumpte Metalldose von der Luft eingedrückt, eine Feder hält sie davon ab zusammenzufallen, und die Verformung wird mechanisch oder elektrisch abgelesen. Elektronische Barometer wandeln den Druck in ein elektrisches Signal um, zum Beispiel indem sie messen, wie weit sich eine dünne Membran aus Silizium, Keramik oder Metall durchbiegt, wie ein Quarzelement zusammengedrückt wird oder wie sich die Schwingungsfrequenz eines dünnen Zylinders ändert. Quecksilberbarometer sind noch im Einsatz, werden von der WMO aber nicht mehr empfohlen.',
          'Das Barometer braucht einen Ort ohne Zugluft und eine feste, erschütterungsfreie Halterung. Wind ist eine häufige Fehlerquelle: Ein starker, böiger Wind verändert den Druck in dem Raum, in dem das Barometer steht, und diese Schwankungen überlagern den statischen Druck und können bis zu 2 oder 3 hPa betragen. Eine Klimaanlage kann einen Druckunterschied zwischen einem Raum und draußen erzeugen. Ein statischer Druckkopf, ein Einlass, der das Barometer mit der Außenluft verbindet, vermeidet das zum größten Teil.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Ein Barometer wird normalerweise so eingestellt, dass es den Druck in seiner eigenen Höhe anzeigt, den Stationsdruck. Wie andere Messwerte wird er gemittelt: Die Anforderungstabelle der WMO nennt für die Ausgabe einer Druckmessung 1 Minute, und ein gemeldeter Wert steht laut Übereinkunft für die vorangegangenen 1 bis 10 Minuten.',
          'Weil der Luftdruck das Gewicht der Luft darüber ist, lassen sich die Messwerte von Stationen in verschiedenen Höhen nicht einfach vergleichen. Die WMO sagt, dass sie auf dieselbe Höhe umgerechnet werden müssen, und empfiehlt Meereshöhe für jede Station, bei der das mit angemessener Genauigkeit möglich ist. Die Umrechnung wird aus dem Stationsdruck, der Höhe der Station, der Temperatur an der Station und dem Wasserdampfdruck dort berechnet, für eine gedachte Luftsäule zwischen der Station und dem Meeresspiegel, in der die Temperatur mit der Höhe um 0,0065 K je Meter abnehmen soll. Die WMO gibt diese Formel für Stationen unter 750 m an und eine einfachere für Stationen unter 50 m, die dem Stationsdruck eine Konstante hinzufügt.',
          'Die Drucktendenz ist, wie sich der Druck in den letzten drei Stunden geändert hat: der Unterschied zwischen dem Wert am Ende und dem am Anfang. Der Fehler eines einzelnen Messwerts ist überwiegend zufällig, in einer Differenz können sich die zufälligen Fehler also addieren. Die WMO weist aber darauf hin, dass die Fehler teilweise systematisch sind und innerhalb von drei Stunden wahrscheinlich dasselbe Vorzeichen haben, und dass dieser Teil durch die Differenzbildung verkleinert wird.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Die WMO fordert eine Unsicherheit von 0,1 hPa und nennt 0,15 hPa als das im Betrieb Erreichbare; ein gut gebautes Aneroid-Barometer kann 0,3 hPa erreichen. Barometer driften zwischen den Kalibrierungen, vor allem wenn sie neu sind, was die WMO als eine der wichtigsten Fehlerquellen bezeichnet, und sie empfiehlt, sie oft zu prüfen, zunächst etwa einmal im Jahr.',
          'Auch diese Zahlen setzen Schutz vor dem Wind voraus: Die WMO weist darauf hin, dass die Unsicherheit stark vom dynamischen Druck des Windes beeinflusst wird, wenn keine Vorkehrungen getroffen sind, und dass ein Sensor, dessen Temperatur nicht gut genug ausgeglichen wird, deutlich beeinflusst werden kann.',
          'Der Druck auf Meereshöhe wird nicht auf Meereshöhe gemessen. Er ist eine Berechnung dessen, was der Druck an dem Punkt unter der Station wäre, und enthält deshalb die Fehler von allem, was in sie eingeht: den Stationsdruck, die Höhe der Station und die Temperatur, die für die gedachte Luftsäule angenommen wird. Wo eine Umrechnung auf Meereshöhe nicht mit angemessener Genauigkeit möglich ist, bittet die WMO eine Station, stattdessen etwas anderes zu melden: die Höhe einer vereinbarten Druckfläche oder den auf eine vereinbarte Höhe der Station umgerechneten Druck.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Anbieter veröffentlichen unterschiedliche Drücke, und die Namen sind wichtig. Der stündliche Datensatz GHCNh der NOAA hat drei: den Stationsdruck, an der Station beobachtet; den Druck auf Meereshöhe, berechnet mit den Temperaturen, die tatsächlich an der Station herrschen; und die Höhenmessereinstellung (altimeter), berechnet mit dem Temperaturprofil einer „Standard“-Atmosphäre, die für die mittleren Verhältnisse über den Vereinigten Staaten auf 40 Grad Nord steht. Die letzten beiden sind beide auf Meereshöhe umgerechnet, und es ist nicht dieselbe Zahl. Wetterdienst hält sie auseinander: pressure_air_site ist der Druck in Stationshöhe, pressure_air_sea_level der auf mittlere Meereshöhe umgerechnete Druck und pressure_air_site_reduced die Höhenmessereinstellung, umgerechnet mit der Standardatmosphäre.',
          'Die stündlichen Druckdaten des DWD haben für jede Station zwei Werte, den auf Meereshöhe („NN“) umgerechneten Druck und den Druck in Stationshöhe. Seine Stationsdateien sagen, dass beide aus den SYNOP-Wettermeldungen der Station stammen, den international verschlüsselten Beobachtungen, und dass die Zeiten in UTC sind.',
          'Auch das Instrument steht in den Stationsdateien. In Potsdam, das 80,86 m über dem Meeresspiegel liegt, führt der DWD seit dem 20. November 2015 ein Digitalbarometer vom Typ PTB 330 auf, von 1992 bis 2015 ein Digitalbarometer vom Typ AIR-DB und davor ein konventionelles Stationsbarometer; von 1986 bis 1992 lief daneben ein elektronischer Absolutdruckwandler (ADMW).',
          'Wetterdienst liefert den Druck standardmäßig in Hektopascal, welche Einheit der Anbieter auch benutzt.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 3 zum Luftdruck stammen in diesem Eintrag die Definition, die Barometer, der Einfluss des Windes, die typischen Fehler und die Umrechnung auf Meereshöhe. Kapitel 1 desselben Bandes enthält die Tabelle der Unsicherheiten, die die WMO fordert.',
        'Volume I, Chapter 3 (Measurement of atmospheric pressure), sections 3.1.1, 3.1.2, 3.1.4.1, 3.1.4.2, 3.1.4.3.2, 3.1.4.3.3, 3.2.1, 3.2.2, 3.2.3, 3.2.6, 3.2.7.1, 3.3.1, 3.3.2, 3.5.1, 3.5.2, 3.7, 3.7.1, 3.7.2, 3.7.3; Volume I, Chapter 1 (General), Annex 1.A, row 3.1.',
        WMO_I,
      ),
      wmoGuideV(
        'Aus Band V, Kapitel 3 zur Datenreduktion stammt in diesem Eintrag die Regel, dass ein gemeldeter Wert für die vorangegangenen 1 bis 10 Minuten steht.',
        'Volume V (Quality assurance and management of observing systems), Chapter 3 (Data reduction), section 3.5.',
      ),
      ghcnh(
        'Ihre Dokumentation sagt, was jedes Element ist, darunter die drei Arten von Druck, die dieser Eintrag nennt.',
        'Section IV (List of Elements/Variables), Table 1: station_level_pressure, sea_level_pressure, altimeter.',
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welches Instrument in welcher Höhe benutzt wurde und woher die Werte stammen.',
        `DWD Climate Data Center, Dateien im Stationsarchiv stundenwerte_P0_03987_akt.zip in ${DWD_HOURLY}pressure/recent/, am 21. November 2026 gelesen für Potsdam (03987): Metadaten_Geraete_Luftdruck_Reduziert_*, Metadaten_Geraete_Luftdruck_Stationshoehe_*, Metadaten_Parameter_p0_stunde_* und Metadaten_Geographie_*; Datensatzbeschreibung „Stündliche Stationsmessungen des Luftdrucks für Deutschland“ (Version v24.03, 2024).`,
        DWD_HOURLY_PRESSURE,
      ),
    ],
  },

  'humidity': {
    title: 'Luftfeuchte und Taupunkt',
    summary: 'Die Luftfeuchte wird auf mehrere Arten angegeben. Die relative Feuchte ist ein Prozentwert, der von der Temperatur abhängt, und der Taupunkt wird meist berechnet und nicht gemessen.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Die Luftfeuchte ist, wie viel Wasserdampf die Luft enthält, und sie wird auf mehrere Arten angegeben. Die relative Feuchte ist der Anteil in Prozent des vorhandenen Wasserdampfdrucks am höchsten, den er bei dieser Temperatur und diesem Druck haben könnte, wenn die Luft gesättigt ist. Der Taupunkt ist die Temperatur, bei der die Luft mit Wasserdampf gesättigt wäre; wird die Luft darauf abgekühlt, kann sich Tau oder Reif bilden. Der Dampfdruck ist der Teil des Luftdrucks, den der Wasserdampf ausmacht. Die absolute Feuchte ist die Masse Wasserdampf in einem Luftvolumen.',
          'Jedes Instrument, das die Luftfeuchte misst, ist ein Hygrometer. Die führende Technik ist heute das elektronische, kapazitive Hygrometer: Ein dünner Polymerfilm zwischen zwei Elektroden nimmt Wasserdampf aus der Luft auf, wodurch sich seine elektrischen Eigenschaften ändern, und die Änderung wird als relative Feuchte abgelesen. Ein Psychrometer hat zwei Thermometer nebeneinander, eines davon mit einer nassen Hülle; das Wasser, das verdunstet, kühlt es ab, und je trockener die Luft ist, desto größer ist der Unterschied zwischen beiden. Psychrometer sind noch im Einsatz, werden aber mehr und mehr von elektronischen Sensoren ersetzt. Unter dem Gefrierpunkt ist die nasse Hülle mit einer dünnen Eisschicht überzogen, und die Berechnung unterscheidet sich für eine Kugel mit Eis und eine mit unterkühltem Wasser. Ein Taupunktspiegel-Hygrometer kühlt einen kleinen Spiegel ab, bis sich Tau oder Reif darauf bildet, und misst die Temperatur des Spiegels, das ist der Taupunkt; es wird meist als Referenz benutzt.',
          'Der Sensor sitzt in einem Strahlungsschutz wie dem des Thermometers, geschützt vor direktem Sonnenlicht, Schmutz, Regen und Wind, und sein Gehäuse darf kein eigenes kleines Klima um ihn herum erzeugen. Eine Temperaturmessung ist immer nebenher nötig, weil die relative Feuchte stark von der Temperatur abhängt und weil andere Größen, etwa der Taupunkt, aus beiden berechnet werden.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Was ein Hygrometer liefert, ist eine relative Feuchte. Der Taupunkt wird aus ihr und aus der Lufttemperatur berechnet, mit Formeln, die die WMO 1990 angenommen hat, wenn er nicht direkt mit einem Taupunktspiegel gemessen wird.',
          'Ein Feuchtewert ist wie die anderen Werte ein Mittelwert, der für die vorangegangenen 1 bis 10 Minuten steht. Die WMO sagt, dass eine Zeitkonstante von etwa 1 Minute für die meisten Zwecke passt, und ihre Anforderungstabelle nennt 40 Sekunden für Festkörpersensoren und 20 Sekunden für den Taupunkt.',
          'Die WMO weist darauf hin, dass das Mitteln einer Größe, die sich nicht proportional ändert, schwierig ist, wenn sie sich während des Mittelungszeitraums ändert. Für den Taupunkt nennt ihre Tabelle die absolute Feuchte als die Größe, die gemittelt werden soll, und sagt, dass Taupunkt, relative Feuchte und Lufttemperatur zusammenhängen und ihre Unsicherheiten ebenfalls.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Die WMO fordert eine Unsicherheit von 1 % relativer Feuchte und 0,1 K für den Taupunkt und nennt, was im Betrieb erreichbar ist: 3 % für Festkörpersensoren und 0,25 K für den Taupunkt. Sie fügt hinzu, dass diese Unsicherheiten in der Praxis nicht leicht zu erreichen sind, selbst mit guten, gut gepflegten Instrumenten, und dass ein Psychrometer in einem Strahlungsschutz ohne Zwangsbelüftung deutlich schlechter sein kann.',
          'Elektronische Sensoren altern. Schmutz, Meersalzgischt oder Chemikalien auf dem Sensor können ihn bei niedriger Feuchte zu hoch und bei hoher Feuchte zu niedrig anzeigen lassen oder einem anderen Muster folgen. In feuchter Luft, bei Tau oder Nebel, driftet ein Sensor, meist nach oben, sodass er 100 % bei 95 % anzeigen kann. Ein Sensor, der über die Lufttemperatur erwärmt wird, zum Beispiel in einem von der Sonne aufgeheizten Strahlungsschutz, zeigt fälschlich zu wenig an. Für elektronische Sensoren in Wetterstationen in feuchtem Klima nennt die WMO eine Lebensdauer, die üblicherweise zwischen sechs Monaten und zwei oder mehr Jahren liegt.',
          'Ein Temperaturfehler geht in alles ein, was damit berechnet wird: Wird der Taupunkt aus der relativen Feuchte berechnet, hat ein Fehler von 0,1 °C bei etwa 20 °C dieselbe Wirkung wie ein Fehler von 0,6 % relativer Feuchte. Bei einem Psychrometer bedeutet ein Fehler von 0,5 K in der Feuchtkugeltemperatur einen Fehler von 4 % relativer Feuchte bei 20 °C und von 27 % bei -20 °C, bei einer wahren relativen Feuchte von 50 %, und die WMO sagt, dass Psychrometer bei niedriger Feuchte weniger genau sind.',
          'Unter 0 °C ist die relative Feuchte nach der WMO in Bezug auf Wasser zu bestimmen, nicht auf Eis: Die meisten Hygrometer zeigen sie so an, die meisten Wolken unter 0 °C bestehen aus Wasser oder überwiegend aus Wasser, Werte über 100 % würden im Allgemeinen nicht beobachtet, und die meisten älteren Aufzeichnungen beruhen darauf.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Die Stationsdateien des DWD sagen, woher die stündlichen Werte stammen. In Frankfurt/Main kommt die relative Feuchte bis Oktober 1993 aus den Papieraufzeichnungen eines Thermohygrographen, in MEZ, bis zum 1. April 2001 von automatischen Stationen und seitdem aus SYNOP-Wettermeldungen, den international verschlüsselten Beobachtungen; der stündliche Taupunkt stammt in allen Zeiträumen aus SYNOP-Meldungen. Die Zeiten sind in UTC, außer bei den Aufzeichnungen bis 1993.',
          'Die Dateien nennen auch den Sensor und seine Höhe. In Frankfurt/Main wird die relative Feuchte seit dem 5. Dezember 2015 mit einem elektronischen Sensor vom Typ EE33 in 2 m Höhe über dem Boden gemessen, davor seit Februar 2012 mit einer Sonde vom Typ HMP45D; ein konventioneller schreibender Thermohygrograph war bis August 2022 im Einsatz.',
          'Anbieter unterscheiden sich auch darin, was sie Luftfeuchte nennen. Die GHCNh der NOAA sagt, dass ihre relative Feuchte je nach Quelle entweder direkt gemessen oder aus der Lufttemperatur und dem Taupunkt berechnet ist, und sagt dasselbe von ihrer Feuchtkugeltemperatur. Wetterdienst liefert die relative Feuchte standardmäßig in Prozent und den Taupunkt in °C.',
          'Ob das Tages- oder Monatsmittel der relativen Feuchte oder des Taupunkts eines Anbieters aus den Werten so, wie sie sind, gebildet wird oder aus der absoluten Feuchte, wie es die WMO für das Mitteln empfiehlt, muss die Dokumentation des Anbieters sagen; dieser Eintrag nimmt keines von beiden an.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 4 zur Luftfeuchte stammen in diesem Eintrag die Definitionen, die Instrumente, die typischen Fehler und die Regel für Temperaturen unter 0 °C. Kapitel 1 desselben Bandes enthält die Tabelle der Unsicherheiten, die die WMO fordert.',
        'Volume I, Chapter 4 (Measurement of humidity), sections 4.1.1, 4.1.3, 4.1.4.1.1, 4.1.4.1.2, 4.1.4.1.3, 4.1.4.2, 4.2.2, 4.2.3, 4.2.5, 4.2.7, 4.3.1.4, 4.3.1.8, Table 4.1, Annex 4.A (paragraphs 3 and 17); Volume I, Chapter 1 (General), Annex 1.A, rows 2.1 and 2.2 and note 11.',
        WMO_I,
      ),
      wmoGuideV(
        'Aus Band V, Kapitel 3 zur Datenreduktion stammen in diesem Eintrag die Regel, dass ein gemeldeter Wert für die vorangegangenen 1 bis 10 Minuten steht, und die Größe, die für einen Taupunkt gemittelt wird.',
        'Volume V (Quality assurance and management of observing systems), Chapter 3 (Data reduction), sections 3.5, 3.6.',
      ),
      ghcnh(
        'Ihre Dokumentation sagt, was jedes Element ist und wie die relative Feuchte und die Feuchtkugeltemperatur gefunden wurden.',
        'Section IV (List of Elements/Variables), Table 1: relative_humidity, wet_bulb_temperature.',
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welchen Sensor sie in welcher Höhe benutzt hat und woher die Werte stammen.',
        `DWD Climate Data Center, Dateien in den Stationsarchiven stundenwerte_TU_01420_akt.zip (${DWD_HOURLY}air_temperature/recent/) und stundenwerte_TD_01420_akt.zip (${DWD_HOURLY}dew_point/recent/), am 21. November 2026 gelesen für Frankfurt/Main (01420): Metadaten_Geraete_Rel_Feuchte_*, Metadaten_Parameter_tu_stunde_* und Metadaten_Parameter_td_stunde_*; Datensatzbeschreibungen „Stündliche Stationsmessungen der Lufttemperatur und Luftfeuchte für Deutschland“ und „Stündliche Stationsmessungen der Luft- und Taupunkttemperatur für Deutschland“ (Version v24.03, 2024).`,
        DWD_HOURLY_HUMIDITY,
      ),
    ],
  },

  'wind': {
    title: 'Wind: mittlere Geschwindigkeit und Böen',
    summary: 'Ein Mittelwind ist ein Mittelwert über zehn Minuten, eine Böe die höchste kurze Spitze, und beides hängt davon ab, wo das Anemometer steht.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Der Wind am Boden wird mit einem Schalen- oder Propelleranemometer für die Geschwindigkeit und einer Windfahne für die Richtung gemessen. Auch Ultraschallanemometer, die die Laufzeit eines Ultraschallimpulses über eine feste Strecke messen, sind im Einsatz; sie haben keine bewegten Teile und sind deshalb langlebig. Die Standardhöhe ist 10 m über offenem, ebenem Gelände, weil die Windgeschwindigkeit mit der Höhe stark zunimmt. Offen heißt, dass das nächste Hindernis mindestens zehnmal so weit entfernt ist, wie es hoch ist. Die Richtung ist die, aus der der Wind weht, in Grad im Uhrzeigersinn von geografisch Nord aus gezählt.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Geschwindigkeit und Richtung einer Wettermeldung sind ein Mittelwert über 10 Minuten. Für Klimastatistiken werden meist Mittelwerte über jede ganze Stunde, den Tag und die Nacht verwendet.',
          'Eine Spitzenböe ist die höchste in einem genannten Zeitraum beobachtete Windgeschwindigkeit; in einer stündlichen Meldung ist es die höchste der letzten vollen Stunde. Die WMO empfiehlt, eine Böe über etwa 3 Sekunden zu messen, was für die meisten Nutzer passt, und sagt, dass ein „Mittel“ über 1 Minute eine lange Böe ist und kein Mittelwind.',
          'Wie scharf eine Böe ausfällt, hängt davon ab, wie schnell das Instrument reagiert: Ein träges verschmiert die Extreme, ein schnelles zeichnet hohe, schmale Spitzen auf. Damit Böen verschiedener Stationen vergleichbar sind, muss nach der WMO die Antwort der ganzen Messkette sorgfältig festgelegt sein; sie empfiehlt eine Böendauer von etwa 3 Sekunden.',
          'Die Beaufortskala von 0 bis 12 macht aus einer Windgeschwindigkeit in 10 m Höhe eine Beschreibung. Stärke 7, ein steifer Wind, sind zum Beispiel 13,9 bis 17,1 m/s.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Die WMO nennt die Aufstellung (Exposition) des Anemometers den schwierigsten Punkt der Windmessung und hält es für fast unmöglich, einen Ort zu finden, an dem der Wind für ein großes Gebiet steht. Ein Mast im Windschatten von Bäumen oder Gebäuden sagt wenig über den ungestörten Wind. Näher als das 20-Fache der Höhe eines Hindernisses kann der Wert vor einer Korrektur um bis zu 25 % danebenliegen.',
          'Schalen- und Propellersensoren beschleunigen schneller, als sie abbremsen, und senkrechte Böen kommen hinzu; ihr Mittel liegt daher bei böigem Wind zu hoch. Die WMO nennt eine gesamte Überschätzung von bis zu 10 % bei manchen Bauarten unter sehr turbulenten Bedingungen über sehr rauem Gelände.',
          'Weil der Wind weiter oben stärker ist, misst ein Sensor in einer anderen Höhe als 10 m eine andere Geschwindigkeit.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Die Stationsdateien des DWD nennen Typ und Höhe jedes Windsensors, und die Höhe ist nicht immer 10 m: In Potsdam sitzt das Ultraschallanemometer 37,7 m über dem Boden.',
          'Der 10-Minuten-Wind des DWD ist ein 10-Minuten-Mittel. Seine Stationsdateien beschreiben das Tagesmittel des Windes als arithmetisches Mittel aus mindestens 21 Stundenmitteln, gebildet aus 10-Minuten-Mitteln, und die größte Tagesböe als die höchste von 23:51 bis 23:50 UTC; das gilt an den geprüften Stationen seit September 2003.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 5 zum Bodenwind stammen in diesem Eintrag die Definitionen von Mittelwind und Böe, die Standardhöhe und die typischen Fehler.',
        'Volume I, Chapter 5 (Measurement of surface wind), sections 5.1.1, 5.1.2, 5.1.3, 5.1.4, 5.4, 5.6, 5.8.2, 5.9.1, 5.9.2 and Table 5.1.',
        WMO_I,
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welches Instrument in welcher Höhe benutzt wurde und was ein Tageswert abdeckt.',
        `${STATION_FILES} Metadaten_Geraete_Windgeschwindigkeit_* und Metadaten_Parameter_klima_tag_*; Datensatzbeschreibung „10-minütige Stationsmessungen des Windes für Deutschland“ (Version v24.03, 2024).`,
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/BESCHREIBUNG_obsgermany_climate_10min_wind_de.pdf',
      ),
    ],
  },

  'precipitation': {
    title: 'Niederschlag',
    summary: 'Regen und Schnee werden in einem Niederschlagsmesser aufgefangen und als Höhe gemessen. Was er auffängt, ist nicht genau das, was fällt, und Schnee bei Wind ist der schwierigste Fall.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Niederschlag ist das flüssige oder feste Wasser, das aus Wolken als Regen, Nieselregen, Schnee, Schneegriesel, Graupel, Hagel oder Eiskörner fällt oder als Diamantstaub aus klarer Luft. Er wird als senkrechte Höhe des Wassers gemessen, das eine ebene Bodenfläche bedecken würde, wobei Schnee als das Wasser zählt, zu dem er schmilzt. Ein Millimeter ist ein Liter auf jedem Quadratmeter.',
          'Ein Niederschlagsmesser ist ein oben offenes Gefäß mit senkrechten Wänden, meist ein Zylinder, mit einem Trichter, wenn er hauptsächlich für Regen gedacht ist; gemessen wird das Volumen oder das Gewicht des Aufgefangenen. Ein manueller Niederschlagsmesser sammelt das Wasser in einem Behälter, der zu festen Zeiten abgelesen wird, ein wägender wiegt es, und ein Kippwaagen-Niederschlagsmesser zählt, wie oft eine kleine Wippe kippt, wenn sie sich mit einer festen Wassermenge gefüllt hat (0,1 bis 0,5 mm bei den Geräten einer internationalen Umfrage). Auch Instrumente, die nichts auffangen und mit Licht oder Radar messen, sind im Einsatz.',
          'Wenn nennenswerte Mengen Schnee zu erwarten sind, muss die Öffnung des Niederschlagsmessers mindestens 200 cm² groß sein; Öffnungen von 200 bis 500 cm² sind am üblichsten. Die WMO empfiehlt, den Niederschlagsmesser abzuschirmen, wo der Wind einen bedeutenden Teil des Aufgefangenen wegnehmen dürfte, natürlich, auf einer Waldlichtung, oder künstlich, mit einem Windschutz, vor allem bei Schnee. Sie empfiehlt außerdem, dass Hindernisse nicht näher als das Doppelte ihrer Höhe über der Öffnung stehen und dass Niederschlagsmesser nicht auf einem Hang oder einem Dach aufgestellt werden.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Die Menge eines Zeitraums ist die Gesamtmenge, die in diesem Zeitraum den Boden erreicht hat, in Millimetern. Eine Menge unter 0,1 mm heißt Spur. Die Intensität ist die Menge je Zeiteinheit, meist in Millimetern pro Stunde; die WMO empfiehlt, sie aus Intervallen von mindestens einer Minute abzuleiten, weil sie von Minute zu Minute so stark schwankt.',
          'Ein manueller Niederschlagsmesser wird zu festen Zeiten abgelesen, die für das ganze Messnetz gleich sind, auf 0,2 mm genau, wenn möglich auf 0,1 mm. Deshalb läuft der „Tag“ einer Niederschlagsmessung von einer Ablesung zur nächsten, und die muss nicht um Mitternacht liegen (siehe „Zeit“). Ein wägender Niederschlagsmesser liefert die Menge eines Intervalls als Differenz des Gewichts seines Behälters zwischen Anfang und Ende des Intervalls.',
          'Eine gemessene Menge kann mit einer Transferfunktion, die die Windgeschwindigkeit und die Lufttemperatur der Station verwendet, der wahren Menge näher gebracht werden. Die WMO bittet darum, in Archiven die angepasste und die nicht angepasste Menge aufzubewahren und die Anpassung zu dokumentieren; damit die nicht angepasste Menge wiederhergestellt werden kann, falls die Anpassung überarbeitet wird.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Wind lenkt die Luft um den Niederschlagsmesser ab, und ein Teil dessen, was hineingefallen wäre, wird an der Öffnung vorbeigetragen. Bei Regen sind das typischerweise 2 bis 10 % (bis zu 10 % gegenüber einem Niederschlagsmesser in einer Grube). Bei Schnee sind es typischerweise 10 bis 50 % oder mehr, und die Abweichung von Niederschlagsmessern bei festem oder gemischtem Niederschlag beträgt typischerweise 30 % oder mehr, je nach Aufstellung, Wind in Höhe des Niederschlagsmessers und Kristallen; Schnee ist weniger dicht als Regen und wird leichter vorbeigetragen. Abschirmung verringert das, beseitigt es aber in der Regel nicht.',
          'Wasser, das an den Innenwänden eines manuellen Niederschlagsmessers haftet, bleibt zurück: im Mittel bis zu 0,2 mm je Ablesung, typischerweise 2 bis 15 % der Messwerte im Sommer und 1 bis 8 % im Winter, und mehr, wenn oft abgelesen wird. Auch aus dem Behälter verdunstet Wasser, Verluste von über 0,8 mm am Tag wurden im späten Frühjahr in mittleren Breiten bei Niederschlagsmessern ohne Trichter gemeldet, im Winter sind es 0,1 bis 0,2 mm am Tag. Spritzer in den Niederschlagsmesser hinein und aus ihm heraus verändern das Aufgefangene um 1 bis 2 %. Benetzungsverluste sind bei wägenden Niederschlagsmessern klein.',
          'Ein Kippwaagen-Niederschlagsmesser, der nicht korrigiert ist, kann bei Starkregen bei manchen Geräten bis zu 20 % zu wenig melden, weil beim Kippen Wasser verloren geht (eine dynamische Kalibrierung und eine Korrektur verringern das), und er zeichnet in Stufen auf: Eine Wippe von 0,2 mm ergibt eine Intensität je Minute in Stufen von 12 mm/h.',
          'Ein Niederschlagsmesser misst eine einzelne Stelle. Auch die beste Messung steht nur für ein begrenztes Gebiet, und Hindernisse, Gelände und Wind in der Umgebung fügen örtlich Niederschlag hinzu oder nehmen welchen weg.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Höhe, Größe und Form der Öffnung der Niederschlagsmesser unterscheiden sich zwischen den Ländern, und die WMO sagt, dass Messungen deshalb nicht streng vergleichbar sind; in mehr als 100 Ländern liegt die übliche Höhe der Öffnung zwischen 0,5 und 1,5 m. Auch die Bauart unterscheidet sich: manuell, wägend, Kippwaage oder Instrumente, die nichts auffangen.',
          'Der DWD führt in den Dateien, die zu den Daten gehören, jeden Niederschlagsmesser einer Station und seine Höhe auf. In Potsdam stand zum Beispiel ab 2009 ein PLUVIO-Gerät 1 m über dem Boden, und seit 2017 steht in derselben Höhe ein rain[e]H3, das das Wasser wiegt.',
          'Der 10-Minuten-Wert des DWD ist die Summe der vorangegangenen 10 Minuten; beim PLUVIO-Gerät ist seit November 2008 ein Wert mit dem Zeitstempel 11:50 UTC das Intervall, das um 11:45 UTC endete. Der Stundenwert ist eine Stundensumme, und der Tageswert deckt 06:00 bis 06:00 UTC des nächsten Tages ab (siehe „Zeit“).',
          'Ob ein Anbieter seine Mengen um die genannten Verluste anpasst, sagt die Dokumentation des Anbieters selbst; dieser Eintrag nimmt weder das eine noch das andere an.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 6 zum Niederschlag stammen in diesem Eintrag die Definition, die Niederschlagsmesser, die typischen Fehler, die Abschirmung und die Transferfunktionen.',
        'Volume I, Chapter 6 (Measurement of precipitation), sections 6.1.1, 6.1.2, 6.1.3, 6.2.1, 6.2.1.2, 6.2.2, 6.2.3, 6.2.3.1, 6.2.5, 6.3.1.1, 6.3.2.1, 6.3.2.2, 6.3.2.4, 6.4.2, 6.5, 6.5.2, 6.6.',
        WMO_I,
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welcher Niederschlagsmesser in welcher Höhe benutzt wurde und was ein Wert abdeckt.',
        `${STATION_FILES} Metadaten_Geraete_Niederschlagshoehe_* und Metadaten_Parameter_klima_tag_*; Datensatzbeschreibung „10-minütige Stationsmessungen des Niederschlages für Deutschland“ (Version v24.03, 2024).`,
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/precipitation/BESCHREIBUNG_obsgermany-climate-10min-precipitation_de.pdf',
      ),
    ],
  },

  'radiation': {
    title: 'Strahlung',
    summary: 'Strahlung ist Energie von der Sonne und vom Himmel, die auf eine waagerechte Fläche fällt. Sie wird als Leistung in einem Augenblick oder als über eine Stunde oder einen Tag aufsummierte Energie angegeben, und die beiden werden leicht verwechselt.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Die WMO unterscheidet zwei Arten. Die Sonnenstrahlung kommt von der Sonne; 97 % der Energie der Strahlung der Sonne außerhalb der Atmosphäre liegen in Wellenlängen zwischen 290 und 3000 nm, weshalb Sonnenstrahlung auch kurzwellige Strahlung heißt. Ein Teil davon erreicht den Boden, ein Teil wird auf dem Weg von Gasmolekülen, Teilchen und Wolkentröpfchen gestreut oder aufgenommen. Die terrestrische Strahlung ist die langwellige Strahlung der Erdoberfläche und der Gase, Teilchen und Wolken der Atmosphäre, mit Wellenlängen von 3000 bis 100000 nm.',
          'Die Globalstrahlung ist die Sonnenstrahlung, die aus dem ganzen Himmel auf eine waagerechte Fläche trifft: der direkte Strahl von der Sonnenscheibe plus die diffuse Himmelsstrahlung, das Sonnenlicht, das in der Atmosphäre gestreut wurde. Sie wird mit einem Pyranometer gemessen, das den ganzen Himmel sieht und Wellenlängen von 300 bis 3000 nm misst. Um die diffuse Strahlung allein zu messen, hält eine kleine Scheibe oder ein Schattenring das direkte Sonnenlicht vom Pyranometer ab.',
          'Der direkte Strahl wird mit einem Pyrheliometer gemessen, das nur die Sonne und einen schmalen Ring Himmel um sie herum sieht und von einem Sonnennachführer auf die Sonne gerichtet gehalten wird. Ein Pyrgeometer misst die langwellige Strahlung, die vom Himmel herunterkommt, und ein Paar Instrumente, eines nach oben und eines nach unten gerichtet, liefert die Strahlungsbilanz, den Unterschied zwischen dem, was herunterkommt, und dem, was hinaufgeht. Die Sonnenscheindauer, die aus dem direkten Strahl abgeleitet wird, hat einen eigenen Eintrag: siehe „Sonnenscheindauer“.',
          'Ein Pyranometer braucht einen Standort ohne Hindernis über der Ebene des Sensors, ohne eine hellfarbige Wand in der Nähe, die die Sonne auf ihn zurückwerfen könnte, und in den Richtungen, in denen die Sonne im Lauf des Jahres auf- und untergeht, ohne etwas, das höher als 5 Grad über dem Horizont liegt. Es muss waagerecht stehen, und die WMO verlangt, dass es mindestens täglich kontrolliert wird: Die Glaskuppel wird sauber und trocken gewischt, und Frost oder Schnee darauf werden entfernt.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Zwei Arten von Zahlen sind in Gebrauch. Die Bestrahlungsstärke ist eine Leistung je Fläche, in Watt je Quadratmeter (W/m²), in einem Augenblick oder über eine kurze Zeit gemittelt. Die Bestrahlung ist eine Energie je Fläche, in Joule je Quadratmeter (J/m²), über einen genannten Zeitraum wie eine Stunde oder einen Tag. Eine mittlere Bestrahlungsstärke von 100 W/m² über eine Stunde ist eine Bestrahlung von 0,36 MJ/m². Die WMO weist darauf hin, dass dies die am häufigsten aufgezeichneten Größen sind, mit Mittelwerten und Summen über 1 Stunde und mehr, und dass Tagessummen häufig verwendet, aber als mittlere Tagesbestrahlungsstärke angegeben werden.',
          'Ein Messwert wird oft genommen und aufsummiert. Die WMO verlangt Abtastungen, die öfter erfolgen als die Zeitkonstante des Instruments, selbst wenn am Ende nur die Summe einer Stunde oder mehr aufbewahrt wird.',
          'Die WMO verlangt, dass Strahlungsmessungen auf die wahre Sonnenzeit bezogen werden, die Zeit nach dem Stand der Sonne selbst, die von der Uhrzeit eines Ortes abweicht. Die Weltzeit (UTC) wird für automatische Systeme akzeptiert, wenn die Daten so oft abgetastet und gespeichert werden, dass ihre Umrechnung auf die wahre Sonnenzeit keinen nennenswerten Informationsverlust bringt. Die „Stunde“ eines Strahlungswerts kann also in beiden angegeben sein, und ein Anbieter kann beide veröffentlichen (siehe „Zeit“).',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Wie genau die Zahl ist, hängt vom Instrument ab. Die WMO ordnet Pyranometer in hohe, gute und mäßige Qualität ein und nennt, was sie mit geeigneten Einrichtungen, gut geschultem Personal und Qualitätskontrolle bei einem Vertrauensniveau von 95 % erreichen können, bei klarem Himmel und ohne die Kalibrierfehler zu zählen: Stundensummen innerhalb von 3 %, 8 % oder 20 % und Tagessummen innerhalb von 2 %, 5 % oder 10 %. Pyranometer mäßiger Qualität sind für Stunden- oder Tagessummen nicht geeignet, für Monats- und Jahressummen aber vielleicht. Für eine Tagessumme aus einem einzelnen Pyranometer ohne weitere Messungen nennt die WMO eine Unsicherheit von weniger als 5 % das Ergebnis guter, sorgfältiger Arbeit.',
          'Mehrere Dinge fügen Fehler hinzu: ein Pyranometer, das nicht waagerecht steht, Schmutz oder Tau auf der Kuppel und ein Ansprechen, das vom Sonnenstand und von der Temperatur des Instruments abhängt. Bei der diffusen Strahlung nennt die WMO das Signal, das der Sensor auch dann zeigt, wenn kein Licht ankommt, das Nullsignal, eine bedeutende Fehlerquelle: Es entspricht bei klarem Himmel 5 bis 10 W/m² und könnte 15 % der diffusen Strahlung erreichen. Die diffuse Strahlung eines wolkenlosen Himmels kann weniger als ein Zehntel der Globalstrahlung betragen.',
          'Ein Gebäude, ein Baum oder ein Hügel, der die Sonne oder einen Teil des Himmels verdeckt, oder eine helle Wand, die Sonnenlicht auf den Sensor zurückwirft, verändert die Messung; deshalb verlangt die WMO, den Horizont um die Station und die Höhe des Sensors zu beschreiben.',
          'Die langwellige Strahlung ist noch schwieriger: Die WMO schreibt, ihre Messung sei noch schwieriger und weniger verstanden als die der solaren Bestrahlungsstärke. Eine Strahlungsbilanz kann negativ sein, da mehr Energie den Boden verlassen kann, als ankommt.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Die stündlichen Strahlungsdaten des DWD sind Summen über die Stunde, in J/cm², von der Globalstrahlung, der diffusen Strahlung und der langwelligen Strahlung vom Himmel, mit der Sonnenscheindauer in Minuten; seine 10-Minuten-Daten sind Summen der vorangegangenen 10 Minuten. Die Stundendateien haben zwei Zeitstempel, einen in UTC und einen in wahrer Ortszeit (WOZ).',
          'Wetterdienst liefert die Energie standardmäßig in MJ/m² (1 J/cm² sind 0,01 MJ/m²) und eine mittlere Leistung, die manche Anbieter stattdessen veröffentlichen, in W/m². Energie und Leistung sind verschiedene Größen und nicht austauschbar: radiation_global ist eine über das Intervall summierte Energie, radiation_global_intensity_mean eine Leistung.',
          'Die Instrumente stehen in den Stationsdateien. In Potsdam führt der DWD für die Globalstrahlung von 2009 bis 2020 ein Pyranometer CM11 auf und seit dem 29. Juli 2021 ein CMP22, beide 33 m über dem Boden, und für die Strahlung vom Himmel bis 2021 ein Pyrgeometer CG4 und seitdem ein CGR4.',
          'Manche Anbieter veröffentlichen die direkte Strahlung, wie sie auf eine Ebene fällt, die der Sonne zugewandt ist (Wetterdienst: radiation_sky_short_wave_direct_perpendicular), was ein Pyrheliometer misst. Sie ist kein Teil der Globalstrahlung auf eine waagerechte Fläche, die die direkte Strahlung multipliziert mit dem Kosinus des Zenitwinkels der Sonne, des Winkels von senkrecht oben, plus die diffuse Strahlung ist, und sie kann diese übersteigen.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 7 zur Strahlung stammen in diesem Eintrag die Definitionen, die Instrumente, die Standorte und die typischen Fehler.',
        'Volume I, Chapter 7 (Measurement of radiation), sections 7.1.1, 7.1.3.1, 7.1.3.3, 7.1.3.4, 7.2, 7.3, 7.3.2, 7.3.2.5, 7.3.3, 7.3.3.3, 7.3.3.5, 7.4, 7.4.1, 7.4.5, Table 7.4, Annex 7.B.',
        WMO_I,
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welches Instrument in welcher Höhe benutzt wurde und was ein Wert abdeckt.',
        `DWD Climate Data Center, Dateien im Stationsarchiv stundenwerte_ST_03987_row.zip in ${DWD_HOURLY}solar/, am 21. November 2026 gelesen für Potsdam (03987): Metadaten_Geraete_Global_Kw_J_*, Metadaten_Geraete_Atmosphaere_Lw_J_* und Metadaten_Parameter_st_stunde_*; Datensatzbeschreibungen „Stündliche Stationsmessungen der Solarstrahlung (global/diffus) und der atmosphärischen Gegenstrahlung für Deutschland“ und „10-minütige Stationsmessungen der Strahlung und Sonnenscheindauer für Deutschland“ (Version v24.03, 2024).`,
        DWD_HOURLY_SOLAR,
      ),
    ],
  },

  'sunshine': {
    title: 'Sonnenscheindauer',
    summary: 'Die Sonnenstunden sind die Zeit, in der der direkte Sonnenstrahl stark genug ist, nicht die Zeit ohne Wolken.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Die WMO definiert die Sonnenscheindauer eines Zeitraums als die Summe der Zeit, in der die direkte Sonnenstrahlung 120 W pro Quadratmeter übersteigt. Die Schwelle wurde so gewählt, dass sie dem Punkt entspricht, an dem die Sonne die Karte des Campbell-Stokes-Sonnenscheinautographen verbrennt, des einfachen Instruments, das seit 1880 an Wetterstationen im Einsatz ist.',
          'Mehr und mehr messen Sensoren statt Papier: ein Pyrheliometer, das den direkten Strahl misst, Pyranometer, die Global- und Diffusstrahlung messen und daraus den direkten Strahl berechnen, oder Geräte mit mehreren Sensoren. Die Brennmethode empfiehlt die WMO nicht mehr, weil sie die Dauer des hellen Sonnenscheins nicht gleichmäßig genug erfasst.',
          'Der Detektor braucht freie Sicht zur Sonne, solange die Sonne mehr als 3 Grad über dem Horizont steht.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Die Sonnenscheindauer ist eine Zeit, in Sekunden oder Stunden, für einen genannten Zeitraum wie einen Tag, einen Monat oder ein Jahr; der Zeitraum gehört zur Einheit. Sie wird auch als Anteil der möglichen Sonnenscheindauer angegeben.',
          'Aus einem einzelnen Pyranometer wird der Sonnenschein jeder 10 Minuten oder jeder Minute aus der gemessenen Strahlung mit einem Rechenverfahren geschätzt (die WMO beschreibt zwei: das Verfahren von Slob und Monna und das Carpentras-Verfahren), und der Tageswert ist die Summe daraus.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Die WMO empfiehlt eine Unsicherheit von 0,1 h und eine Auflösung von 0,1 h. Eine aus einem Pyranometer berechnete Tagessumme ist unsicherer: Für das Verfahren von Slob und Monna nennt die WMO etwa 0,6 h und hält fest, dass nach neueren Arbeiten die erweiterte Unsicherheit von Tagessummen über 1 h liegen kann, und für das Carpentras-Verfahren eine erweiterte Unsicherheit von etwa 0,7 h.',
          'Instrumente und Verfahren liefern verschiedene Werte. Schon die ersten Sonnenscheinautographen, gebaut ohne internationale Regeln, ergaben unterschiedliche Dauern. Dünne, hohe Bewölkung, die den Strahl auf etwa die Schwelle schwächt, ist der schwierigste Fall, denn ein kleiner Fehler der Schwelle ändert das Ergebnis dann stark.',
          'Sonnenscheindauer und Bewölkung hängen nur im Mittel zusammen: Bei hoher, dünner Bewölkung und bei Wolken, die die Sonne nicht bedecken, gilt der Zusammenhang nicht.',
          'Ein Berg oder ein Gebäude, das die Sonne bei tiefem Stand verdeckt, verkürzt die gemessene Dauer. In Gebirgstälern akzeptiert die WMO natürliche Hindernisse als Teil des örtlichen Klimas, wenn sie dokumentiert sind.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Das Instrument ist von Station zu Station verschieden und wechselt im Lauf der Zeit. In Potsdam führt der DWD bis März 2005 einen Campbell-Stokes-Sonnenscheinautographen, von August 1992 bis Januar 2025 einen SONIe-Sensor und seitdem ein Pyranometer vom Typ CMP22.',
          'Die tägliche Sonnenscheindauer des DWD ist an den geprüften Stationen in Stunden für 00:00 bis 24:00 UTC angegeben, der Stundenwert in Minuten.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 8 zur Sonnenscheindauer stammen in diesem Eintrag die Definition, die Instrumente und die typischen Fehler.',
        'Volume I, Chapter 8 (Measurement of sunshine duration), sections 8.1, 8.1.1, 8.1.2, 8.1.3, 8.1.3.2, 8.1.3.3, 8.1.4, 8.2.2.1, 8.3.',
        WMO_I,
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welches Instrument benutzt wurde und was ein Tageswert abdeckt.',
        `${STATION_FILES} Metadaten_Geraete_Sonnenscheindauer_* und Metadaten_Parameter_klima_tag_*; Datensatzbeschreibung „Stündliche Stationsmessungen der Sonnenscheindauer für Deutschland“ (Version v24.03, 2024).`,
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/sun/BESCHREIBUNG_obsgermany_climate_hourly_sun_de.pdf',
      ),
    ],
  },

  'visibility': {
    title: 'Sichtweite',
    summary: 'Die Sichtweite ist, wie weit man sehen kann. Ein Instrument kann nicht schauen: Es misst, wie stark die Luft Licht abschwächt, und die Entfernung wird daraus berechnet.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Die WMO definiert die Sichtweite am Tag als die größte Entfernung, in der ein schwarzes Objekt passender Größe am Boden vor dem Himmel am Horizont gesehen und erkannt werden kann. Was ein Mensch sieht, hängt vom Menschen ab; deshalb benutzt die WMO ein Maß, das auch Instrumente finden können, die meteorologische optische Reichweite (MOR): die Länge des Wegs in der Luft, die das Licht eines schmalen Strahls von einer Lampe auf 5 % seines ursprünglichen Werts abschwächt. Sie wird in Metern oder Kilometern angegeben.',
          'Mit dem Auge schätzt ein Beobachter die Entfernung zu bekannten Objekten: am Tag dunkle Objekte vor dem Himmel, etwa Baumgruppen, Türme oder Masten, in der Nacht Lichter bekannter Stärke. Jede Station erstellt einen Plan dieser Objekte mit ihren Entfernungen und Richtungen, und der Beobachter schaut aus etwa 1,5 m Höhe über dem Boden, nicht aus einem hohen Gebäude. In der Nacht brauchen die Augen 5 bis 15 Minuten, um sich an die Dunkelheit zu gewöhnen.',
          'Instrumente messen, wie stark die Luft Licht abschwächt, den Extinktionskoeffizienten. Ein Transmissometer schickt einen Lichtstrahl über eine bekannte Strecke, von wenigen Metern bis zu 150 m (oder sogar 300 m), und misst, wie viel davon ankommt. Ein Vorwärtsstreulicht-Messgerät strahlt Licht in ein kleines Luftvolumen und misst, wie viel davon zu einem Empfänger hin gestreut wird; es braucht wenig Platz und wird in immer mehr automatischen Stationen benutzt. Die WMO sagt, dass das gemessene Luftvolumen normalerweise in der Höhe der Augen eines Beobachters liegen soll, etwa 1,5 m über dem Boden, und dass die Sonne nie im Blickfeld des Empfängers stehen darf.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Aus dem Extinktionskoeffizienten berechnet das Instrument die MOR: Sie ist etwa 3 geteilt durch den Extinktionskoeffizienten. Das nimmt an, dass die Luft entlang des ganzen Wegs so ist wie die Luft in dem kleinen Volumen, das das Instrument betrachtet.',
          'Der Extinktionskoeffizient eines kleinen Luftvolumens schwankt schnell und unregelmäßig, deshalb werden viele Messwerte gemittelt. Der erste internationale Vergleich von Sichtweitenmessungen der WMO fand für die meisten Instrumente keinen Gewinn durch ein Mitteln über mehr als 1 Minute, für die unruhigsten 2 Minuten. Die Tabelle der WMO nennt Mittelungszeiten der Ausgabe von 1 und 10 Minuten und rät, beim Mitteln den Extinktionskoeffizienten zu mitteln und nicht die Sichtweite.',
          'Gemeldete Sichtweiten kommen in Stufen, die mit der Entfernung gröber werden: im Schlüssel der synoptischen Meldung 100-m-Stufen von 100 bis 5000 m, 1-km-Stufen von 6 bis 30 km und 5-km-Stufen von 35 bis 70 km. Das liegt daran, dass die Fehler von Sichtweitenmessungen im Verhältnis zur Sichtweite wachsen.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Ein Mensch und ein Instrument sehen nicht dasselbe. Die WMO nennt jede visuelle Schätzung subjektiv. In ihrem ersten internationalen Vergleich schätzten Beobachter am Tag etwa 15 % mehr als die Instrumente und in der Dunkelheit etwa 30 % mehr. In der Nacht hängt die Schätzung von den vorhandenen Lichtern und von der Anpassung der Augen des Beobachters ab, und die WMO nennt sie besonders problematisch.',
          'Ein Instrument liest ein kleines Luftvolumen. Es liefert nur dann eine gute MOR, wenn dieses Volumen der Luft rund um die Station bis in eine Entfernung der MOR gleicht; bei Nebelfeldern oder einem örtlichen Regen- oder Schneeschauer kann es in die Irre führen, und die WMO sagt, dass instrumentelle Messungen der MOR mit Vorsicht zu deuten sind. Der Schritt vom Extinktionskoeffizienten zur Entfernung gilt für Nebeltröpfchen; wenn Regen, Schnee oder aufgewirbelter Sand die Sicht verringern, sollen die Werte nach der WMO mit mehr Sorgfalt behandelt werden.',
          'Die WMO fordert eine Unsicherheit von 50 m bis 600 m, 10 % zwischen 600 und 1500 m und 20 % über 1500 m und nennt das Größere von 20 m oder 20 % als das Erreichbare. Die Instrumente unterscheiden sich: Die besten Vorwärtsstreulicht-Messgeräte erreichten eine Standardabweichung von etwa 10 % über einen Bereich von etwa 100 m bis 50 km, doch Vorwärtsstreulicht-Messgeräte waren bei geringer Sicht im Allgemeinen weniger genau als Transmissometer und stärker vom Niederschlag beeinflusst, und Spinnweben oder fliegende Insekten im Messvolumen können eines zu niedrig anzeigen lassen.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Die stündliche Sichtweite des DWD ist in Metern, mit einem Kennzeichen, das sagt, ob ein Wert von einem Menschen beobachtet (P) oder von einem Instrument gemessen (I) wurde. In den aktuellen Dateien der drei geprüften Stationen ist jeder Wert mit I gekennzeichnet. Von den Werten ab dem 19. Mai 2025 liegen an diesen Stationen 87 bis 93 % nicht auf den Stufen des synoptischen Schlüssels (zum Beispiel 32280 m), und die Beschreibung des DWD sagt, warum: Bei automatischen Messungen hängt der Wertebereich vom Instrument ab, und die Häufigkeitsverteilung der Sichtweite ist stationsabhängig und nicht unbedingt zeitlich konstant. Die Stationsdateien nennen SYNOP-Wettermeldungen, die international verschlüsselten Beobachtungen, als Quelle der Werte, und die Zeiten sind in UTC.',
          'Die Stationsdateien nennen das Instrument und seine Höhe. Der DWD führt einen Sichtweitensensor vom Typ FS11 in 2,5 m Höhe über dem Boden auf, seit dem 30. Oktober 2018 in Potsdam (davor ab 2009 ein DF20+ in 2,3 m Höhe über dem Boden), seit dem 14. Oktober 2019 in Dresden-Klotzsche und seit dem 6. August 2021 in Frankfurt/Main. Die WMO sagt, dass das gemessene Luftvolumen normalerweise in etwa 1,5 m Höhe liegen soll.',
          'Auch in der Einheit unterscheiden sich die Anbieter: Die GHCNh der NOAA gibt die Sichtweite in Kilometern an, der DWD in Metern, und Wetterdienst liefert standardmäßig Meter. Manche liefern nur das Mittel über einen Zeitraum (visibility_mean) oder eine Klasse der Sichtweite (visibility_index), einen Code und keine Entfernung. Auch eine Vorhersage der Sichtweite ist keine Messung: siehe „Beobachtung, Vorhersage und abgeleitete Daten“.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 9 zur Sichtweite stammen in diesem Eintrag die Definitionen, die Beobachtung mit dem Auge, die Instrumente, die Mittelung und die typischen Fehler. Kapitel 1 desselben Bandes enthält die Tabelle der Unsicherheiten, die die WMO fordert.',
        'Volume I, Chapter 9 (Measurement of visibility), sections 9.1.1, 9.1.2, 9.1.4, 9.2.1, 9.2.2, 9.2.3, 9.2.5, 9.3.2, 9.3.3, 9.3.4, 9.3.5.1, 9.3.6.1, 9.3.6.3; Volume I, Chapter 1 (General), Annex 1.A, row 8.1.',
        WMO_I,
      ),
      wmoGuideV(
        'Aus Band V, Kapitel 3 zur Datenreduktion stammt in diesem Eintrag die Größe, die für eine Sichtweite gemittelt wird.',
        'Volume V (Quality assurance and management of observing systems), Chapter 3 (Data reduction), section 3.6.',
      ),
      ghcnh(
        'Ihre Dokumentation sagt, was jedes Element ist und in welcher Einheit.',
        'Section IV (List of Elements/Variables), Table 1: visibility.',
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welches Instrument in welcher Höhe benutzt wurde und woher die Werte stammen.',
        `DWD Climate Data Center, Dateien in den Stationsarchiven stundenwerte_VV_03987_akt.zip, stundenwerte_VV_01048_akt.zip und stundenwerte_VV_01420_akt.zip in ${DWD_HOURLY}visibility/recent/, am 21. November 2026 gelesen für Potsdam (03987), Dresden-Klotzsche (01048) und Frankfurt/Main (01420): Metadaten_Geraete_Sichtweite_*, Metadaten_Parameter_vv_stunde_* und die Spalte V_VV_I der Datendatei; Datensatzbeschreibung „Stündliche Stationsmessungen der Sichtweite für Deutschland“ (Version v24.03, 2024, Abschnitt „Unsicherheiten“).`,
        DWD_HOURLY_VISIBILITY,
      ),
    ],
  },

  'evaporation': {
    title: 'Verdunstung',
    summary: 'Die WMO sagt, dass es derzeit nicht praktikabel ist, die Verdunstung eines ganzen Feldes oder Sees direkt zu messen. Schalen und Lysimeter messen das Wasser, das sie verlieren; der Rest wird geschätzt oder berechnet.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Die WMO hält mehrere Größen auseinander. Evaporation ist das Wasser, das von einer offenen Wasserfläche oder vom Boden als Dampf in die Luft geht. Transpiration ist das Wasser, das Pflanzen abgeben. Evapotranspiration ist die Summe aus Boden und Pflanzen, wenn der Boden seine natürliche Feuchte hat. Potenzielle Evapotranspiration ist das Meiste, was von einer geschlossenen, gut mit Wasser versorgten Pflanzendecke verdunsten könnte. Die WMO sagt, dass bei der Verwendung von „potenzieller Evapotranspiration“ klar angegeben werden muss, welche Art von Evaporation und Transpiration sie enthält.',
          'Die WMO sagt, dass es derzeit nicht praktikabel ist, die Verdunstung einer ausgedehnten natürlichen Wasser- oder Landfläche direkt zu messen. Die WMO sagt, dass die Verfahren im Allgemeinen indirekt sind: eine Punktmessung mit einem Instrument oder eine Berechnung aus anderen gemessenen Größen des Wetters. Die Verdunstung wird als Wassertiefe in Millimetern angegeben, normalerweise je Tag.',
          'Verdunstungsschalen werden in Messnetzen häufig eingesetzt: ein offener Behälter mit Wasser, dessen Stand abgelesen wird; der Verlust an Höhe, unter Berücksichtigung des gefallenen Regens, ist die Verdunstung. Die amerikanische Class-A-Schale zum Beispiel ist 25,4 cm tief und hat 120,7 cm Durchmesser, und ihr Wasserstand wird mit einem Hakenmaß abgelesen. Ein Lysimeter ist ein in den Boden eingelassenes, mit Boden gefülltes und bepflanztes Gefäß. Es ist eine Wasserbilanz: Die Evapotranspiration ist der Niederschlag (und die Bewässerung) minus das Wasser, das unten abfließt, minus die Änderung des im Boden gespeicherten Wassers. Die WMO sagt, dass wägbare Lysimeter verlässliche und genaue kurzfristige Werte liefern, wenn die nötigen Vorkehrungen bei Bauweise, Betrieb und Aufstellung getroffen werden.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Die Verdunstungsrate ist die Wassermenge, die je Flächeneinheit und Zeiteinheit verloren geht, geschrieben als die Tiefe flüssigen Wassers, die diese Menge ergäbe. Die Zeiteinheit ist normalerweise ein Tag. Für Tagessummen verlangt die WMO eine Unsicherheit von 0,1 mm bei Mengen unter 5 mm und von 2 % bei größeren (mit 95 % Konfidenz), und sie sagt, dass die üblichen Instrumente dies im Prinzip erfüllen könnten, dass aber Schwierigkeiten bei der Aufstellung und im praktischen Betrieb viel größere Fehler verursachen. Die WMO nennt 1 mm als vorgeschlagenen erreichbaren Wert.',
          'Weil eine direkte Messung nicht praktikabel ist, wird die Verdunstung natürlicher Flächen oft berechnet. Als Beispiel nennt die WMO das Verfahren des Königlich Niederländischen Meteorologischen Instituts (KNMI) nach G. F. Makkink, das die tägliche Verdunstung einer Referenzvegetation aus der Mitteltemperatur der Luft des Tages und der Globalstrahlungsmenge des Tages berechnet. Die WMO sagt auch, dass sich die potenzielle oder Referenz-Evapotranspiration bewachsenen Landes mit den Verfahren finden lässt, die für Seen benutzt werden, angepasst an die Vegetation, und dass einige Verfahren Koeffizienten hinzunehmen, die vom Wachstumsstadium der jeweiligen Pflanze abhängen.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Das Wasser, das eine Schale verliert, ist nicht das Wasser, das ein See oder ein Feld verliert. Die WMO sagt, dass sich die Verdunstungsrate einer natürlichen Fläche notwendigerweise von der eines Verdunstungsmessers unter demselben Wetter unterscheidet, weil die beiden Flächen physikalisch verschieden sind, und dass sich die Werte eines Verdunstungsmessers nicht ohne Anpassung als Verdunstung eines Sees oder als tatsächliche oder potenzielle Evapotranspiration verwenden lassen. Verschiedene Verdunstungsmesser und Lysimeter messen physikalisch Verschiedenes, deshalb sollen das Instrument und seine Aufstellung genau beschrieben werden.',
          'Die Aufstellung ist wichtig. Eine Schale über dem Boden verdunstet mehr als eine eingelassene, vor allem weil ihre Seiten zusätzliche Strahlungsenergie aufnehmen; eine eingelassene Schale hat geringere Randeffekte, sammelt aber mehr Schmutz, ihre Lecks sind schwerer zu finden, und sie tauscht Wärme mit dem Boden aus. Starker Regen und sehr starker Wind spritzen wahrscheinlich Wasser aus einer Schale und können die Messung ungültig machen. Ist eine Schale zu voll, können 10 % oder mehr des fallenden Regens herausspritzen, wodurch die Verdunstung zu hoch gemessen wird; steht das Wasser zu niedrig, beschattet der Rand das Wasser, und die Verdunstung sinkt um etwa 2,5 % für jeden Zentimeter unter dem Bezugsniveau (in gemäßigten Breiten).',
          'Ein Lysimeter verändert den Boden, den es misst. Die WMO nennt als Fehlerquellen unter anderem ein eingeschränktes Wachstum der Wurzeln, einen Bruch zwischen dem Pflanzenbestand im Gefäß und der Umgebung, thermische Unterschiede zur Umgebung und eine Wasserbilanz, die sich von der Umgebung unterscheidet, zum Beispiel durch eingeschränkte Dränage oder weil Oberflächenabfluss und seitliche Bewegung des Bodenwassers verhindert werden. Ein allgemeingültiges internationales Standard-Lysimeter gibt es nicht.',
          'Die Verdunstungsrate hängt vom Wetter und von der Oberfläche ab. Die WMO ordnet die meteorologischen Faktoren in Energie (großenteils von Sonnen- und Erdstrahlung geliefert) und den Abtransport des Dampfes (Windgeschwindigkeit an der Oberfläche und Unterschied des Dampfdrucks zwischen der Oberfläche und der unteren Luft) und die Oberflächenfaktoren in die Menge und den Zustand des Wassers, die Rauigkeit und bei Pflanzen ihre eigenen Eigenschaften und die Verfügbarkeit von Bodenfeuchte. Jede der beiden Gruppen kann die Rate begrenzen.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Die Verdunstung, die Wetterdienst vom DWD im abgeleiteten Datensatz zum Boden anbietet, ist berechnet und nicht gemessen. Die Beschreibung des DWD sagt, dass die Werte von Verdunstung, Bodenfeuchte und Bodentemperatur für verschiedene Orte in Deutschland berechnet wurden und normalerweise nicht gemessen werden. Die Werte von Verdunstung und Bodenfeuchte stammen aus dem agrarmeteorologischen Modell AMBAV. Die Dokumentation des Modells nennt die Penman-Monteith-Gleichung als seinen Kern und sagt, dass es routinemäßige Wettermeldungen als Eingang nimmt, in stündlichen oder dreistündlichen Schritten rechnet und Tagessummen auswertet. Der DWD gibt die „reale Verdunstung“ für Gras, Wintergetreide und Mais an, jeweils auf einem Sandboden und auf einem lehmigen Schluff, dazu zwei potenzielle Verdunstungen über Gras, eine nach FAO und eine nach Haude. Der DWD sagt, dass die nach FAO der nach Haude vorzuziehen ist, weil sehr viel mehr einflussnehmende Größen berücksichtigt werden.',
          'Der Name eines Parameters sagt nicht, ob er eine Vorhersage oder eine Berechnung ist. evapotranspiration_potential_last_24h ist eine Vorhersage des MOSMIX des DWD (siehe „Beobachtung, Vorhersage und abgeleitete Daten“), und es ist auch der Name von EV24 des KNMI, das der Dateikopf des KNMI die potenzielle Evapotranspiration nach Makkink nennt, das Verfahren, das die WMO als Berechnung aus der mittleren Lufttemperatur und der Globalstrahlung des Tages beschreibt. evapotranspiration_potential_grass_fao ist das des DWD, aus dessen Modell, und auch das von MeteoSchweiz, dessen Dokumentation nicht gelesen wurde, weshalb nichts darüber gesagt wird, wie es gebildet wird. Die GHCN-Daily der NOAA hat eine gemessene Größe: EVAP, die Verdunstung von Wasser aus einer Verdunstungsschale, mit MDEV für eine Summe über mehrere Tage und DAEV für die Zahl der Tage, die sie umfasst, sowie der kleinsten und der größten Temperatur des Wassers in der Schale. Diese Seite sagt nichts über die Verdunstung anderer Anbieter.',
          'Die Namen sind also wichtig: evaporation_amount_* von Wetterdienst aus einer Schale oder aus einem Modell, evapotranspiration_potential_* und evapotranspiration_last_24h sind verschiedene Größen, und nur Größen derselben Art lassen sich vergleichen. Standardmäßig liefert Wetterdienst Millimeter.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 10 zur Verdunstung stammen in diesem Eintrag die Definitionen, die Instrumente, die Fehlerquellen und das Beispiel einer Berechnung.',
        'Volume I, Chapter 10 (Measurement of evaporation), sections 10.1.1, 10.1.2, 10.1.3, 10.1.4, 10.3, 10.3.1, 10.3.4, 10.3.6, 10.4, 10.4.1, 10.4.3, 10.5.',
        WMO_I,
      ),
      dwdFiles(
        'Die Beschreibung ihres abgeleiteten Datensatzes sagt, dass Verdunstung, Bodenfeuchte und Bodentemperatur berechnet werden, und mit welchem Modell. Die Dokumentation des Modells sagt, wie es arbeitet.',
        'DWD Climate Data Center. Berechnete aktuelle Tageswerte von charakteristischen Elementen aus dem Boden und dem Pflanzenbestand, Version v2 (2024), Abschnitte „Zusammenfassung“, „Datenherkunft“ und „Zusatzinformationen“; englische Monatsbeschreibung „Calculated recent monthly values for different characteristic elements of soil and crops“, version v2 (2024; revised 2026-05-28). Löpmeier, F.-J., „Agrarmeteorologisches Modell zur Berechnung der aktuellen Verdunstung (AMBAV)“, Abschnitte 1, 2.1 und 2.2 (opendata.dwd.de/climate_environment/CDC/grids_germany/daily/evapo_r/AMBAV.pdf). Beide am 21. November 2026 gelesen.',
        DWD_SOIL_DAILY_DE,
      ),
      knmi(
        'Der Kopf ihrer Datei mit Tagesdaten nennt jedes Element und seine Einheit.',
        'KNMI, daily data of the weather in the Netherlands (daggegevens), file header for station 260 (De Bilt), element EV24, read on 21 November 2026.',
      ),
      ghcnDaily(
        'Ihre Readme nennt jedes Element und seine Einheit.',
        'NOAA NCEI. Readme of the Global Historical Climatology Network daily (GHCN-Daily), version 3.35, section III: the elements EVAP, MDEV, DAEV, MNPN and MXPN.',
      ),
    ],
  },

  'soil-moisture': {
    title: 'Bodenfeuchte',
    summary: 'Die Bodenfeuchte ist, wie viel Wasser im Boden ist. Sie kann als Anteil an der Masse, als Anteil am Volumen oder als die Energie angegeben werden, mit der der Boden das Wasser hält (das Wasserpotenzial), und was eine Zahl bedeutet, hängt vom Boden ab.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Die WMO sagt, dass Bestimmungen der Bodenfeuchte entweder den Wassergehalt des Bodens oder das Wasserpotenzial des Bodens messen. Der Gehalt ist die Masse oder das Volumen des Wassers im Boden. Das Potenzial beschreibt den Energiezustand des Bodenwassers: Wasser neigt dazu, von einem Ort mit höherem Potenzial zu einem mit niedrigerem zu fließen, und wenn der Boden trocknet, wird das Potenzial negativer, und die Pflanzen können das Wasser schwerer aufnehmen. Die Beziehung zwischen Gehalt und Potenzial ist nicht allgemeingültig; sie hängt vom örtlichen Boden ab.',
          'Das Grundverfahren ist gravimetrisch. Eine Bodenprobe von etwa 50 g wird entnommen, gewogen, in einem Ofen bei 105 °C getrocknet, bis ihre Masse konstant bleibt, was meist 16 bis 24 Stunden dauert, und wieder gewogen; der Unterschied ist das Wasser. Das ist eine direkte Messung, deshalb nennt die WMO sie den Maßstab, an dem alle anderen Verfahren verglichen werden. Aber die Probenahme zerstört die Probe, die Messung lässt sich an ihr also nicht wiederholen.',
          'Indirekte Verfahren lassen den Boden an seinem Platz. Eine Neutronensonde wird in ein Rohr im Boden gesenkt: Wasserstoff, der größtenteils im Wasser steckt, bremst die Neutronen, woraus sich der Wassergehalt ergibt. Dielektrische Verfahren wie die Zeitbereichsreflektometrie nutzen, dass flüssiges Wasser etwa 20-mal so viel Permittivität hat wie durchschnittlicher trockener Boden; die WMO sagt, dass sie sich vollständig automatisieren lassen. Das Wasserpotenzial des Bodens wird mit Tensiometern, Widerstandsblöcken und Boden-Psychrometern gemessen. Die WMO beschreibt auch die Messung der Bodenfeuchte durch Satelliten, die die Oberfläche betrachtet.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Der gravimetrische Wassergehalt ist die Masse des Wassers geteilt durch die Masse des trockenen Bodens. Der volumetrische Wassergehalt ist das Volumen des Wassers geteilt durch das Volumen der ganzen Probe (trockener Boden, Luft und Wasser). Beide werden meist in Prozent angegeben, obwohl viele Forschungsgemeinschaften für das Volumen inzwischen Kubikmeter Wasser je Kubikmeter Boden verwenden. Um den einen in den anderen umzurechnen, braucht man die Dichte des trockenen Bodens. Das Wasserpotenzial des Bodens wird als Energie je Masse, als Druck oder als Höhe einer Wassersäule angegeben.',
          'Die Bodenfeuchte ändert sich mit der Tiefe, und was gebraucht wird, hängt vom Zweck ab. Die WMO sagt, dass Modelle der Evapotranspiration meist eine flache Tiefe von einigen zehn Zentimetern betreffen, die Landwirtschaft die Feuchte in der Tiefe der Wurzeln braucht, in der Größenordnung eines Meters, und Modelle der Atmosphäre Schichten bis in einige Meter Tiefe verwenden. Die WMO sagt, dass es keine Standardtiefe und kein Standard-Messintervall gibt; die Stationen des International Soil Moisture Network messen meist in mehreren Tiefen zwischen 0,05 m und 0,50 m oder 1 m.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Eine Messung gilt für einen Ort. Die WMO sagt, dass Böden horizontal und vertikal in Struktur, Bewuchs und Relief stark variieren und dass ein einzelner Beobachtungsort kein absolutes Wissen über die Bodenfeuchte einer Region liefern kann, nur ein relatives über ihre Änderung. Messungen durch Probenahme oder mit einem Instrument im Boden sind nur am Messpunkt verlässlich, die Beschreibung eines Standorts braucht also viele Proben.',
          'Dieselbe Prozentzahl bedeutet in verschiedenen Böden Verschiedenes. Die WMO beschreibt die Feldkapazität, den Zustand, in dem der Boden nach einer starken Durchfeuchtung alle Feuchte hält, die er gegen die Schwerkraft halten kann, und den Welkepunkt, an dem die Wurzeln die Kräfte, die das Wasser an den Bodenteilchen halten, nicht mehr überwinden können. Das für Pflanzen verfügbare Wasser wird üblicherweise als die Menge zwischen beiden genommen, und sie unterscheidet sich stark zwischen Böden: In sandigen Böden kann sie unter 10 Volumenprozent liegen, in Böden mit viel organischer Substanz über 40 Volumenprozent. Wassergehalte steiniger oder kiesiger Böden können grob irreführend sein.',
          'Jedes Verfahren hat Grenzen. Die Neutronenmethode lässt sich in den obersten 20 cm des Bodens nicht wirksam einsetzen. Widerstandsblöcke zeigen einen feuchteren Boden an, als es ihn gibt, wenn der Boden salzhaltig ist, wobei Gipsblöcke dafür weniger empfindlich sind. Tensiometer arbeiten nur in feuchtem Boden gut, und ihre praktische Grenze liegt bei etwa -85 kPa.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Die Bodenfeuchte in Wetterdienst stammt aus dem abgeleiteten Datensatz zum Boden des DWD, und sie ist berechnet, nicht gemessen. Der DWD sagt, dass alle berechneten Werte zu Bodenfeuchte und Evapotranspiration aus dem agrarmeteorologischen Modell AMBAV stammen und dass die Werte normalerweise nicht gemessen werden. Als Grund nennt er, dass die Messung der Bodenfeuchte sehr aufwendig und fehlerbehaftet ist. Das Modell braucht stündliches Wetter: Temperatur, Feuchte, Wind, Niederschlag und außerdem Globalstrahlung und langwellige Strahlung. Der DWD sagt, dass die Strahlung nicht an jeder Station gemessen wird und oft aus der Sonnenscheindauer und der Bedeckung abgeleitet wird. Zur Prüfung der Feuchte sagt der DWD, dass sie nur an einzelnen Punkten in Sondermesskampagnen mit Messungen verglichen wurde und gut übereinstimmte.',
          'Die Einheit ist nicht der Volumenanteil der WMO. Der DWD gibt die Bodenfeuchte in Prozent der nutzbaren Feldkapazität an (% nFK). 100 % ist die Spanne zwischen dem Welkepunkt und der Feldkapazität des Bodens, den das Modell verwendet, 0 % ist also der Welkepunkt und 100 % die Feldkapazität. Der DWD sagt, dass Werte über 100 % korrekt sind und auftreten, wenn der Wassergehalt über der Feldkapazität liegt; in leichten Böden sind bei der selten beobachteten Sättigung des Bodens bis zu 300 % möglich, aber nur zusammen mit undurchlässigen Sperrschichten oder Bodenfrost. Standardmäßig liefert Wetterdienst die Zahl in Prozent, wie der DWD sie angibt, „Prozent“ bedeutet bei diesen Parametern also Prozent der nutzbaren Feldkapazität und nicht Prozent des Volumens.',
          'Der DWD rechnet für zwei Böden, einen lehmigen Schluff mit einem Welkepunkt von 13 Volumenprozent und einer Feldkapazität von 37 Volumenprozent und einen lehmigen Sand mit 3 und 17 Volumenprozent, unter Gras, Wintergetreide und Mais. Unter Gras auf dem lehmigen Schluff gibt er die Schichten 0 bis 10 cm, 10 bis 20 cm und so weiter bis 50 bis 60 cm an, und für jede Kombination die Schicht von 0 bis 60 cm. Die Tageswerte stehen im Tagesdatensatz und die Monatsmittel im Monatsdatensatz (soil_moisture_mean_*). Zum Zeitpunkt des Schreibens bietet in Wetterdienst kein anderer Anbieter Bodenfeuchte an, es gibt also keine andere Quelle zum Vergleich.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 11 zur Bodenfeuchte stammen in diesem Eintrag die Definitionen, die Verfahren, ihre Grenzen und die Hinweise zu Tiefe und Repräsentativität.',
        'Volume I, Chapter 11 (Measurement of soil moisture), sections 11.1.1, 11.1.2, 11.1.3, 11.1.4, 11.2, 11.3.1.1, 11.3.2, 11.4, 11.4.1, 11.4.2, 11.5, 11.6.',
        WMO_I,
      ),
      dwdFiles(
        'Die Beschreibung ihres abgeleiteten Datensatzes sagt, dass die Bodenfeuchte berechnet wird, mit welchem Modell, mit welchem Eingang und für welche Böden. Ihre Dokumentation zur Bodenfeuchte definiert die Einheit.',
        'DWD Climate Data Center. Berechnete aktuelle Tageswerte von charakteristischen Elementen aus dem Boden und dem Pflanzenbestand, Version v2 (2024), Abschnitte „Datenherkunft“, „Unsicherheiten“ und „Zusatzinformationen“; englische Monatsbeschreibung „Calculated recent monthly values for different characteristic elements of soil and crops“, version v2 (2024; revised 2026-05-28). DWD, „Bodenfeuchte“ (Dokumentation, Stand März 2024), Abschnitte 1 und 2 (dwd.de/DE/fachnutzer/landwirtschaft/dokumentationen/allgemein/bf_erlaeuterungen.pdf). Beide am 21. November 2026 gelesen.',
        DWD_SOIL_DAILY_DE,
      ),
    ],
  },

  'present-weather': {
    title: 'Gegenwärtiges Wetter und Erdbodenzustand',
    summary: 'Das gegenwärtige Wetter ist eine Beschreibung und keine Zahl: ein Schlüssel, der sagt, was zur Zeit der Beobachtung geschah, etwa Regen, Nebel oder Gewitter. Die WMO sagt, dass derzeit nur ein geschulter Beobachter alles beobachten kann.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Als „Wetter“ bezeichnet die WMO die qualitativen Beschreibungen der Erscheinungen in der Atmosphäre oder auf der Erdoberfläche, die zunächst nicht gemessen werden sollten. Das gegenwärtige Wetter beschreibt die Wettererscheinungen, die zur Zeit der Beobachtung da sind. Das vergangene Wetter beschreibt die bedeutenden Wetterereignisse der letzten Stunde, die zur Zeit der Beobachtung nicht auftraten. Der Erdbodenzustand ist ein verwandter Punkt: der Zustand der Erdoberfläche, der sich aus dem jüngsten Wetter ergibt, in Bezug auf ihre Feuchte oder auf Schichten aus festen, wässrigen oder anderen Teilchen, die sie bedecken.',
          'Die WMO führt auf, was beobachtet wird: Niederschlag (Regen, Sprühregen, Schnee, Eiskörner, Schneegriesel, Eisnadeln und Hagel), Trübung und schwebende Teilchen (trockener Dunst, Staub, Rauch, feuchter Dunst, Nebel, Schneefegen und Schneetreiben, Staub- und Sandstürme, Staubteufel), Trichterwolken, Böen und Blitze. Die WMO sagt, dass die einzige derzeitige Möglichkeit, alle Formen des Wetters zu beobachten, das Sehen und Hören eines geschulten Beobachters ist. Ein Ereignis kann durch das bestimmt sein, was ein Mensch wahrnimmt: Es ist ein Gewitter, wenn Donner zu hören ist, auch wenn kein Blitz gesehen wird.',
          'Instrumente decken einen Teil ab. Die WMO sagt, dass kein einzelner Sensor das gesamte gegenwärtige Wetter einordnet. Automatische Systeme verknüpfen Daten mehrerer Sensoren, etwa Sichtweite, Temperatur, Taupunkt, Windgeschwindigkeit und die Unterscheidung von Regen und Schnee, mit Algorithmen. Die Art des Niederschlags wird unter anderem mit Streulichtsensoren, optischen Disdrometern, Doppler-Radaren und Aufprallsensoren erkannt. Gewitter werden hauptsächlich mit Blitzzählern erkannt. Das Beispiel der WMO für Dunst: Hat eine Station Messinstrumente, kann man ziemlich sicher annehmen, dass eine Trübung trockener Dunst ist, wenn die relative Feuchte unter einem bestimmten Wert liegt, zum Beispiel 80 %, und die Sichtweite innerhalb bestimmter Grenzen liegt, zum Beispiel horizontal über 1 km und vertikal über 2 km; feuchter Dunst wird bei hoher Feuchte und einer Sichtweite von 1 km oder mehr gemeldet.',
          'Der Erdbodenzustand wird von Beobachtern mit den Schlüsseln des Manual on Codes der WMO (WMO-No. 306) gemeldet. Die WMO sagt, dass seine automatische Messung noch relativ neu und nicht weit verbreitet ist. Die WMO sagt, dass die Forschung gezeigt hat, dass sich die Hauptzustände an der Art unterscheiden lassen, wie die Oberfläche Licht reflektiert und streut: trocken, feucht, nass, schneebedeckt, bereift oder vereist. Streulichtsensoren nutzen das; ein kapazitiver Sensor, der nach der WMO noch entwickelt wird, würde die unterschiedlichen Dielektrizitätskonstanten von trockener und nasser Erde nutzen.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Gegenwärtiges Wetter, vergangenes Wetter und Erdbodenzustand werden als Schlüssel gemeldet. Der Beobachter wählt einen Begriff aus einer großen Zahl von Beschreibungen, die im Manual on Codes (WMO-No. 306) festgelegt sind, und an bemannten Stationen wird der Schlüssel zusammen mit quantitativen Daten gemeldet. Die WMO sagt, dass die Daten hochentwickelter Systeme für das gegenwärtige Wetter als Größen in einem binären Schlüsselformat wie BUFR gemeldet werden sollen, weil der alphanumerische Schlüssel viele Beschränkungen hat. Gibt es zur Zeit der Beobachtung in einer synoptischen Meldung keinen Niederschlag, werden bei der Wahl der Schlüsselzahl die Verhältnisse der letzten Stunde berücksichtigt.',
          'Die Intensität hat Klassen. Beobachter oder die Instrumente, die sie ersetzen, ordnen Niederschlag als leicht, mäßig oder stark ein. Der Anhang der WMO nennt Kriterien nach der Fallrate, bezogen auf einen Messzeitraum von 3 Minuten: Bei Regen ist leicht unter 2,5 mm je Stunde, mäßig von 2,5 bis unter 10 mm je Stunde, stark von 10 bis unter 50 mm je Stunde und heftig 50 mm je Stunde oder mehr; bei Schnee, im Wasseräquivalent, ist leicht unter 1,0 mm je Stunde, mäßig von 1,0 bis unter 5,0 mm je Stunde und stark 5,0 mm je Stunde oder mehr. Die WMO sagt, dass ein Ereignis des gegenwärtigen Wetters durch einen Zeitraum von 3 Minuten gut bestimmt sein kann und dass das höchste gleitende 3-Minuten-Mittel innerhalb des 10-Minuten-Zeitraums gemeldet werden soll.',
          'Ein Wort kann in Meldungen und in Klimazusammenfassungen Verschiedenes bedeuten. In synoptischen Meldungen bedeutet „Nebel“ Wasser- oder Eisnebel, der die horizontale Sichtweite an der Erdoberfläche im Allgemeinen auf weniger als 1 km senkt, und die WMO sagt, dass der Begriff überall, wo er in den Schlüsseln für gegenwärtiges und vergangenes Wetter vorkommt, in diesem Sinn zu lesen ist. In Klimazusammenfassungen gelten dagegen alle Fälle mit einer Sichtweite von weniger als 1 km als Nebel.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Gegenwärtiges Wetter, vergangenes Wetter und Erdbodenzustand sind nach der WMO in erster Linie als qualitative Beschreibung von Wetterereignissen gedacht. Die Niederschlagsmenge ist eine andere Messung (siehe „Niederschlag“), und die Wolken auch (siehe „Wolken“). Ein Schlüssel sagt, welche Art von Wetter es gab, und nicht, wie viel.',
          'Mit der heutigen Technik, sagt die WMO, können Instrumente für gegenwärtiges und vergangenes Wetter, Wolkenmenge und -höhe und Schneedecke nicht die ganze Bandbreite der Erscheinungen beobachten, menschliche Beobachter dagegen schon. Was die Instrumente erkennen, ist auch nicht für jede Art von Instrument gleich. Die WMO berichtet von Feldtests, in denen Sensoren für die Niederschlagsart die wichtigen Arten, außer dem allerleichtesten Schnee oder Sprühregen, in über 90 % der Fälle im Vergleich zu einem geschulten Beobachter erkannten, mit einem viel geringeren Anteil bei sehr schwachem Niederschlag. Für Streulichtsensoren wurden je nach Test und Gerät 70 bis 90 % für die häufigen Arten Regen und Schnee berichtet. Gemischter Niederschlag aus Regen und Schnee und Hagel werden weniger gut beobachtet, und nasser oder schmelzender Schnee ist schwer von Regen zu unterscheiden. Die WMO sagt auch, dass diese Sensoren die Qualität oder die Unsicherheit ihrer Meldung nicht angeben.',
          'Eine Intensität von einem solchen Sensor ist gröber als die eines Niederschlagsmessers. Die WMO sagt, dass die Intensität von einem Streulichtsensor meist weniger genau ist als die der herkömmlichen Verfahren wie Wägeniederschlagsmesser oder Kippwaagen und dass sie für eine grobe Angabe wie leicht oder stark brauchbar ist.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Das stündliche Wetter des DWD ist ein Schlüssel mit einem Text daneben, und die Stationsdateien nennen SYNOP-Wettermeldungen als Quelle, mit den Zeiten in UTC. Die Liste der Schlüssel des DWD hat zwei Bereiche: 0 bis 99 und 100 bis 199 mit eigenen Bedeutungen, zum Beispiel 100 „bei Bewölkung (mehr als 0/8) zum Beobachtungstermin: keine signifikanten Wettererscheinungen beobachtet“, 123 „Regen, nicht gefrierend (nicht zum Beobachtungszeitpunkt): an der Station in der letzten Stunde“ und 161 „Regen, nicht gefrierend: leicht“. In den aktuellen Dateien der drei geprüften Stationen liegt jeder Schlüssel im Bereich 100 bis 199 oder ist -1; bei -1 sagt die Datei „Wetter wurde nicht gemeldet“, und das trifft an diesen Stationen auf 70 bis 72 % der Stunden zu (zum Beispiel 9124 von 13118 Stunden in Potsdam). -1 sagt also nicht, wie das Wetter war, ob gut oder nicht, und Wetterdienst liefert für diese Stunden keinen Wert. Die Schlüssel der beiden Bereiche werden nicht ineinander umgerechnet.',
          'Die Daten des DWD zu festen Beobachtungsterminen enthalten einen verschlüsselten Erdbodenzustand („Terminwerte des Erdbodenzustand“, EK_TER, in Wetterdienst der Parameter soil_state_index), der laut Stationsdatei aus SYNOP-Meldungen zu den festen Beobachtungsterminen erzeugt wird, seit 2001. Im Ordner recent gibt es ihn für 30 Stationen. An der einen gelesenen Station (Altenstadt, 00125) fehlen mehr als die Hälfte der Einträge (1169 von 1835). Die Datei nennt ihn einen Schlüssel und sagt nicht, welchen; die Schlüsseltabellen stehen im Manual on Codes der WMO, das keine der Quellen dieser Seite ist.',
          'Die GHCN-Daily der NOAA hält fest, welche Arten von Wetter an einem Tag auftraten, als Wettertypen, ein Element je Art (WT01 Nebel, Eisnebel oder gefrierender Nebel; WT03 Donner; WT05 Hagel; WT06 Glatteis oder Raueis; WT16 Regen; WT18 Schnee, und weitere) und eine zweite Gruppe für Wetter in der Nähe der Station. Wetterdienst nennt sie weather_type_*. Die Vorhersagen MOSMIX und DMO des DWD geben unter weather_significant* und weather_last_6h Schlüssel der Vorhersage an, die keine Beobachtungen sind: siehe „Beobachtung, Vorhersage und abgeleitete Daten“.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 14 zu gegenwärtigem und vergangenem Wetter und zum Erdbodenzustand stammen in diesem Eintrag die Definitionen, die Verfahren, die Kriterien für die Intensität und die Ergebnisse der Tests von Sensoren. Kapitel 1 desselben Bandes sagt, was Instrumente noch nicht beobachten können.',
        'Volume I, Chapter 14 (Observation of present and past weather; state of the ground), sections 14.1.1, 14.1.2, 14.1.3, 14.1.4, 14.2, 14.2.1.2, 14.2.1.3, 14.2.1.4, 14.2.2.1, 14.2.3.1, 14.2.3.2, 14.3.1, 14.3.2 and the Annex (criteria for slight, moderate and heavy precipitation intensity); Volume I, Chapter 1 (General), section 1.3.',
        WMO_I,
      ),
      dwdFiles(
        'Die Beschreibung des Datensatzes, die Liste der Wetterschlüssel und die Dateien, die zu jeder Station gehören, sagen, was der DWD als gegenwärtiges Wetter veröffentlicht, woher die Werte stammen und wofür -1 steht.',
        `DWD Climate Data Center, Dateien in den Stationsarchiven stundenwerte_WW_03987_akt.zip, stundenwerte_WW_01048_akt.zip und stundenwerte_WW_01420_akt.zip in ${DWD_HOURLY}weather_phenomena/recent/, am 21. November 2026 gelesen für Potsdam (03987), Dresden-Klotzsche (01048) und Frankfurt/Main (01420): Metadaten_Parameter_ww_stunde_* und die Spalte WW der Datendatei; Wetter_Beschreibung.txt im selben Ordner; Datensatzbeschreibung „Stündliche Stationsmessungen der Wetterphaenomene für Deutschland“ (Version v24.03, 2024). Für den Erdbodenzustand: terminwerte_EK_00125_akt.zip in opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/soil/recent/ (Metadaten_Parameter_ek_termin_00125 und die Spalte EK_TER der Datendatei) und die Liste EK_Terminwerte_Beschreibung_Stationen.txt im selben Ordner, am 21. November 2026 gelesen.`,
        DWD_HOURLY_WEATHER,
      ),
      ghcnDaily(
        'Ihre Readme nennt jedes Element und wofür es steht.',
        'NOAA NCEI. Readme of the Global Historical Climatology Network daily (GHCN-Daily), version 3.35, section III: the elements WT** (weather type) and WV** (weather in the vicinity).',
      ),
    ],
  },

  'clouds': {
    title: 'Wolken',
    summary: 'Die Menge der Wolken, die Höhe ihrer Basis und ihre Art sind drei verschiedene Beobachtungen. Ein Beobachter sieht den ganzen Himmel; ein Ceilometer schaut senkrecht nach oben auf nur einen kleinen Teil davon.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Die WMO definiert eine Wolke als eine Ansammlung sehr kleiner Wassertröpfchen, Eiskristalle oder einer Mischung aus beiden, deren Basis über dem Boden liegt und die vom Beobachtungsort aus wahrnehmbar ist. Beobachtet werden drei Dinge: wie viel vom Himmel bedeckt ist (Wolkenmenge), wie hoch der unterste Teil der Wolke über dem Boden liegt (Höhe der Wolkenbasis) und welche Art von Wolke es ist (Wolkenart). Die WMO sagt, dass die Wolkenmenge traditionell mit dem Auge beobachtet wurde und dass instrumentelle Verfahren inzwischen weithin anerkannt sind und eingesetzt werden.',
          'Ein Beobachter schätzt den bedeckten Teil des Himmels auf ein Okta genau, ein Achtel des Himmels. Der Beobachter soll den Bereich über sich und die niedrigeren Teile des Himmels gleich gewichten; sind die Wolken sehr ungleichmäßig verteilt, kann der Himmel in Quadranten geteilt und können die Schätzungen addiert werden. Die Schlüsselzahl 9 wird gemeldet, wenn der Himmel wegen Nebel, fallenden Schnees und dergleichen nicht zu sehen ist oder wenn der Beobachter die Menge wegen Dunkelheit oder fremden Lichts nicht schätzen kann. Nachts muss der Beobachter den Augen Zeit geben, sich an die Dunkelheit zu gewöhnen. Wo es kein Instrument gibt, kann die Höhe einer Wolkenbasis nur geschätzt werden, in Bergregionen zum Beispiel durch Vergleich mit den Höhen bekannter Landmarken. Die WMO fügt hinzu, dass eine Wolke wegen der Perspektive auf fernen Hügeln zu ruhen scheinen kann und dass Beobachter am Boden bei tropischen Cumuluswolken mit hoher Basis die Höhe häufig sehr stark unterschätzt haben.',
          'Die Höhe der Wolkenbasis wird mit einem Ceilometer gemessen. Die WMO sagt, dass das Laser-Ceilometer jetzt das am meisten benutzte Verfahren ist und als das am besten geeignete gelten sollte. Es schickt Pulse nahinfraroten Lichts nach oben und misst, wie lange das von der Wolke gestreute Licht zurück braucht. Die Wolkenmenge lässt sich aus der Reihe der Messwerte eines Ceilometers finden, aus Infrarotsensoren, die die Wärmeabstrahlung des Himmels in vielen Richtungen messen, und aus Kameras, die den ganzen Himmel ansehen. Die WMO sagt, dass für die meisten Wolkenarten die einzige Methode noch das Sehen ist und dass die Wolkenart noch im Allgemeinen von Menschen beobachtet wird; ein automatisches Verfahren gibt es für die Flugwetter-Meldungen, das Niederschlagsradar und Blitzortung verbindet, um Cumulonimbus und hoch aufragende Cumuluswolken zu erkennen.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Die Wolkenmenge wird auf einer Skala in Oktas gemeldet, von 0 für einen klaren Himmel bis 8 für einen vollständig bedeckten. 1 steht für ein Okta oder weniger, aber nicht null, und 7 für sieben Oktas oder mehr, aber nicht acht, sodass 0 und 8 einem vollständig klaren oder vollständig bedeckten Himmel vorbehalten bleiben. Die Tabelle der WMO gibt dieselbe Skala auch in Zehnteln an. Im BUFR-Schlüssel wird die gesamte Bedeckung in Prozent angegeben.',
          'Die WMO unterscheidet die gesamte Wolkenmenge von der Teilmenge. Die gesamte ist der Teil der Himmelskuppel, der von allen sichtbaren Wolken bedeckt ist. Die Teilmenge ist der Teil, der von einer Wolkenart oder -schicht bedeckt ist, als wäre sie die einzige Wolke am Himmel, sodass die Teilmengen zusammen mehr als die gesamte Menge und mehr als acht Oktas ergeben können.',
          'Ein Ceilometer hat keinen Blick auf den ganzen Himmel, deshalb baut es eine Menge aus vielen Messwerten auf. Die WMO sagt, dass sich die Wolkenmenge in der Reichweite eines Ceilometers aus dem Anteil der Zeit schätzen lässt, den gut erkannte Schichten einnehmen, unter der Annahme, dass dieses Zeitmittel für den Himmel um die Station steht. Als Beispiel beschreibt die WMO das amerikanische System ASOS: Das Ceilometer nimmt alle 30 Sekunden eine Probe; jede Minute werden die letzten 30 Minuten verarbeitet, die letzten 10 Minuten mit doppeltem Gewicht; die Wolkenhöhen werden zu Schichten gruppiert, und die Menge einer Schicht ergibt sich aus dem Anteil der Proben, die Wolke fanden, umgerechnet, damit sie einer Beobachtung durch einen Menschen entspricht. Zur Wolkenart beschreibt die WMO Klassen: zehn Gattungen im International Cloud Atlas (WMO-No. 407) und für synoptische Meldungen Schlüssel für tiefe, mittelhohe und hohe Wolken, deren Zweck es ist, charakteristische Zustände des Himmels zu melden und nicht einzelne Wolkenarten.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Ein Ceilometer schaut senkrecht nach oben auf ein kleines Stück Himmel. Die WMO sagt, dass sich die meisten Unterschiede zur Menge, die ein Beobachter schätzt, auf diese begrenzte räumliche Repräsentativität zurückführen lassen und dass das Verfahren darauf beruht, dass die Wolken über das Instrument ziehen und für den ganzen Himmel repräsentativ sind. In einem Vergleich an Küstenstationen der mittleren Breiten stimmte das Ceilometer-Verfahren mit der gesamten Wolkenmenge des Beobachters typischerweise in 85 bis 90 % der Fälle bis auf 2 Oktas überein, und die WMO sagt, dass dieses Ergebnis von den vielen bedeckten Lagen beeinflusst ist (7 oder 8 Oktas etwa 55 % der Zeit). Ein Ceilometer meldet viel öfter 8 Oktas als 7 Oktas, während ein Beobachter Lücken irgendwo in der Wolkendecke sehen kann und 7 und 8 etwa gleich oft meldet.',
          'Die Höhe einer Wolkenbasis ist nicht so scharf, wie es klingt. Die WMO sagt, dass Studien systematische Unterschiede von 30 bis 50 m in den Höhen der Wolkenbasis von Ceilometern verschiedener Hersteller fanden, die von den Algorithmen herzurühren scheinen, die die Basis festlegen, und dass es für Instrumente keine klare Definition der Wolkenbasis gibt. In Nebel und bei Niederschlag können ernste Fehler auftreten. Der Laser erkennt hohe Cirren womöglich nicht, und feuchte Schichten, Aerosol, Flugzeuge, Vögel, Bewuchs über dem Gerät oder Schnee auf dem Gerät können eine Basis ergeben, die es nicht gibt. Die Tabelle der Anforderungen der WMO verlangt eine Unsicherheit von 1/8 für die Wolkenmenge und sagt, dass 2/8 erreichbar sind; für die Höhe der Basis verlangt sie 10 m bis 100 m und 10 % darüber und gibt als erreichbar etwa 10 m gegen ein hartes Ziel (keine Wolke) an, mit einer deutlichen Abweichung bei Niederschlag.',
          'Die WMO sagt, dass es Gelegenheiten gibt, bei denen es sehr schwierig ist, die Wolkenmenge zu schätzen, besonders nachts, und dass der Beobachter Zeit braucht, damit sich die Augen anpassen; in mondlosen Nächten lässt sich die gesamte Menge meist aus dem Teil des Himmels schätzen, in dem die Sterne von Wolken abgeschwächt oder verdeckt werden, obwohl Dunst allein Sterne nahe dem Horizont verdecken kann. Die WMO sagt, dass scannende Infrarotdetektoren und Infrarotkameras nachts beobachten können und Kameras, die Tageslicht nutzen, nicht; jedes Verfahren hat eigene Nachteile, zum Beispiel kann ein scannender Infrarotdetektor teiltransparente Wolken schlecht einordnen.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Die stündliche Bedeckung des DWD ist in Achteln, mit einem Kennzeichen, das sagt, ob ein Mensch (P) oder ein Instrument (I) die Beobachtung gemacht hat. In den aktuellen Dateien der drei geprüften Stationen ist fast jeder Wert mit I gekennzeichnet; Potsdam und Dresden-Klotzsche haben 47 mit P gekennzeichnete Werte, Frankfurt/Main keinen. Die Stationsdateien nennen SYNOP-Wettermeldungen als Quelle, mit Zeiten in UTC. Sie führen als Instrument für die gesamte Bedeckung ein Ceilometer vom Typ CHM 15k „Nimbus“ auf, seit dem 21. Juli 2015 in Potsdam (davor ab 2009 ein LD 40 und bis 1997 ein Wolkenhöhenmesser vom Typ IVO), seit dem 19. September 2019 in Dresden-Klotzsche und seit dem 6. August 2021 in Frankfurt/Main. Die Dateien und die Datensatzbeschreibung, die gelesen wurden, sagen nicht, wie aus den Messwerten des Ceilometers die Bedeckung wird. Der DWD sagt, dass viele seiner Stationen zwischen Ende der neunziger Jahre und 2009 von manueller auf automatische Beobachtung umgestellt wurden, und nennt Änderungen der Instrumente und des Beobachtungspersonals unter den Quellen der Unsicherheit für lange Zeitreihen.',
          'Der Datensatz zur Wolkenart hat bis zu vier Schichten, jede mit einer Art, der Höhe ihrer Basis und ihrer Bedeckung. In den aktuellen Dateien der drei geprüften Stationen gibt es Höhen und Bedeckungen für bis zu drei Schichten, keine Art für irgendeine Schicht und keine vierte Schicht. Der DWD schreibt in manchen Stunden -1; seine Beschreibung nennt nur -999 als fehlenden Wert. Wetterdienst liest -1 als einen Himmel, der nicht zu sehen war, und liefert dafür keinen Wert; das ist die Lesart von Wetterdienst und keine Aussage des DWD. Standardmäßig liefert Wetterdienst die Bedeckung in Prozent des Himmels und die Höhe in Metern.',
          'Die mittlere Tagesbedeckung des DWD (NM) ist ein arithmetisches Mittel: für die geprüften Stationen seit dem 1. April 2001 aus mindestens 21 Stundenwerten aus SYNOP-Meldungen und davor aus den Beobachtungen zu drei Tageszeiten (in Potsdam 1967 bis 1990 aus vier oder acht). Das KNMI gibt die mittlere Bewölkung des Tages (NG) in Oktas an und schreibt 9 für einen Himmel, der nicht zu sehen ist, was Wetterdienst als keinen Wert liefert. Die GHCN-Daily der NOAA gibt die mittlere Bewölkung als Prozentzahl an und hält die Quellen auseinander: ACMC und ACSC stammen aus Ceilometerdaten im 30-Sekunden-Takt, ACMH und ACSH aus manuellen Beobachtungen, jeweils für Mitternacht bis Mitternacht oder für Sonnenaufgang bis Sonnenuntergang. Die Vorhersagen MOSMIX und DMO des DWD geben die Bedeckung nach Höhenschichten (zum Beispiel cloud_cover_below_2km) und eine effektive Bedeckung an. Das sind Vorhersagen und keine Messungen: siehe „Beobachtung, Vorhersage und abgeleitete Daten“.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 15 zu den Wolken stammen in diesem Eintrag die Definitionen, die Beobachtung mit dem Auge, die Instrumente und ihre Fehler. Kapitel 1 desselben Bandes enthält die Tabelle der Unsicherheiten, die die WMO fordert.',
        'Volume I, Chapter 15 (Observation and measurement of clouds), sections 15.1.1, 15.1.2, 15.1.3, 15.1.4.1, 15.1.4.2, 15.1.4.3, 15.2.1, 15.2.2, 15.2.3, 15.3, 15.3.1, 15.3.2, 15.3.3, 15.4, 15.4.1.1, 15.4.1.3, 15.5; Volume I, Chapter 1 (General), Annex 1.A, rows 4.1 and 4.2.',
        WMO_I,
      ),
      dwdFiles(
        'Die Dateien, die zu jeder Station gehören, sagen, welches Instrument sie benutzte und woher die Werte stammen. Die Beschreibungen der Datensätze sagen, was die Zahlen sind.',
        `DWD Climate Data Center, Dateien in den Stationsarchiven stundenwerte_N_*_akt.zip und stundenwerte_CS_*_akt.zip in ${DWD_HOURLY}cloudiness/recent/ und ${DWD_HOURLY}cloud_type/recent/ und tageswerte_KL_*_akt.zip in ${DWD_KL}recent/, am 21. November 2026 gelesen für Potsdam (03987), Dresden-Klotzsche (01048) und Frankfurt/Main (01420): Metadaten_Geraete_Gesamt_Bedeckungsgrad_*, Metadaten_Parameter_n_stunde_*, Metadaten_Parameter_klima_tag_* (Parameter NM) und die Spalten V_N, V_N_I und V_S1_CS bis V_S4_NS der Datendateien; Datensatzbeschreibungen „Stündliche Stationsmessungen der Wolkenbedeckung für Deutschland“ und „Stündliche Stationsmessungen der Wolkenbedeckung, der Wolkenart und der Wolkenhöhe in bis zu 4 Schichten für Deutschland“ (Version v24.03, 2024).`,
        DWD_HOURLY_CLOUDINESS,
      ),
      knmi(
        'Der Kopf ihrer Datei mit Tagesdaten nennt jedes Element und seine Einheit.',
        'KNMI, daily data of the weather in the Netherlands (daggegevens), file header for station 260 (De Bilt), element NG, read on 21 November 2026.',
      ),
      ghcnDaily(
        'Ihre Readme nennt jedes Element und seine Einheit.',
        'NOAA NCEI. Readme of the Global Historical Climatology Network daily (GHCN-Daily), version 3.35, section III: the elements ACMC, ACMH, ACSC and ACSH.',
      ),
    ],
  },

  'snow': {
    title: 'Schnee',
    summary: 'Schneehöhe, Neuschnee, das Wasser im Schnee und das Vorhandensein von Schnee sind vier verschiedene Messungen.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Die WMO unterscheidet vier Dinge. Die Schneehöhe ist der senkrechte Abstand von der Schneeoberfläche bis zum Boden, in ganzen Zentimetern. Die Neuschneehöhe ist die Höhe des Schnees, der in einem Zeitraum gefallen ist und sich angehäuft hat, meist 24 Stunden. Das Wasseräquivalent ist die Höhe des Wassers, die bliebe, wenn die Schneedecke schmilzt; es ist die Höhe des Schnees mal seine mittlere Dichte. Das Vorhandensein von Schnee ist ein Ja oder Nein: ob mehr als die Hälfte der Messfläche bedeckt ist.',
          'Von Hand wird die Schneehöhe an einem Pegel oder Stab mit Zentimeterstrichen abgelesen. Automatische Stationen benutzen einen Sensor über dem Schnee, mit Ultraschall oder Laser, der den Abstand zur Schneeoberfläche misst; die Schneehöhe ist der Abstand zum freien Boden minus der Abstand zum Schnee.',
          'Neuschnee wird auf einem weißen Brett aus Sperrholz gemessen, 40 bis 60 cm Kantenlänge, das jeden Tag zur gleichen Zeit auf 0,5 cm genau abgelesen und dann leergefegt wird. Ein anerkanntes automatisches Verfahren dafür gibt es nicht.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Eine Schneehöhe ist, wenn nichts anderes gesagt wird, ein Messwert an einem Ort zu einer Zeit. Ist mehr als die Hälfte der Messfläche schneefrei, wird eine Höhe von 0 cm eingetragen, auch wenn am Pegel noch Schnee liegt.',
          'Neuschnee lässt sich nicht aus der Differenz zweier Schneehöhen bestimmen: Liegender Schnee setzt sich und schmilzt, die Differenz wäre zu klein. Neuschnee von weniger als 0,5 cm wird als Spur eingetragen.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Ein Pegel ist ein Punkt. Steht er in einer Verwehung oder an einer vom Wind leergefegten Stelle, kann er um so viel danebenliegen wie die mittlere Schneehöhe oder mehr; die WMO empfiehlt deshalb ebene, geschützte Standorte, die ihre Umgebung vertreten. Automatische Sensoren sollen mit einer Datenunsicherheit von höchstens 2 cm angegeben sein, besser 1 cm.',
          'Wind und Schmelze machen Neuschnee unsicher: Die Beobachterin oder der Beobachter muss schätzen, was gefallen wäre, und die WMO sagt, der Fehler kann bis zu 100 % betragen. In einer Wärmeperiode kann eine Stunde früher oder später einen Unterschied von mehreren Zentimetern machen.',
          'Schnee fällt auch in einen Niederschlagsmesser, der bei Wind deutlich weniger davon auffängt: Die Abweichung von Niederschlagsmessern bei Schnee beträgt typischerweise 30 % oder mehr (siehe „Niederschlag“).',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Die tägliche Schneehöhe des DWD ist an den geprüften Stationen der Messwert von 06 UTC; die Neuschneehöhe ist ein eigener Tageswert. Wo eine kanadische Station zweimal am Tag meldet, stützt Environment and Climate Change Canada den „Schnee am Boden“ eines Tages auf die Morgenbeobachtung dieses Tages.',
          'Die Instrumente wechseln: In Dresden-Klotzsche führt der DWD bis Juli 2022 einen manuellen Schneepegel neben einem automatischen Schneehöhensensor, der seit September 2019 im Einsatz ist.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band II, Kapitel 2 zum Schnee stammen in diesem Eintrag die Definitionen, die Instrumente und die typischen Fehler. Aus Band I, Kapitel 6 stammt die Abweichung von Niederschlagsmessern bei Schnee.',
        'Volume II (Measurement of cryospheric variables), Chapter 2 (Measurement of snow), sections 2.1.1, 2.2, 2.3.1.2, 2.3.1.3, 2.3.2.1, 2.3.2.2, 2.6, 2.7; Volume I, Chapter 6 (Measurement of precipitation), sections 6.2.1.2, 6.5.2.',
        WMO_II,
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welches Instrument benutzt wurde und wann ein Wert abgelesen wurde.',
        `${STATION_FILES} Metadaten_Geraete_Schneehoehe_* und Metadaten_Parameter_klima_tag_*; Datensatzbeschreibung „Tägliche Niederschlagsbeobachtungen für Deutschland“ (more_precip, Version v24.3, 2024). Environment and Climate Change Canada, Climate glossary, „Climatological Day“ (climate.weather.gc.ca/glossary_e.html).`,
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/more_precip/BESCHREIBUNG_obsgermany-climate-daily-more_precip_de.pdf',
      ),
    ],
  },

  'automatic-stations': {
    title: 'Automatische Wetterstationen',
    summary: 'Eine automatische Wetterstation misst und meldet ohne Beobachter. Software bildet ihre Werte aus vielen Abtastwerten, und die WMO sagt, dass das, was ein Instrument von Wolken, Sichtweite und gegenwärtigem Wetter beobachtet, nicht dasselbe ist wie das, was ein Mensch beobachtet.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Die WMO definiert eine automatische Wetterstation (AWS) als „meteorologische Station, an der Beobachtungen automatisch gemacht und übertragen werden“ (im Original: „meteorological station at which observations are made and transmitted automatically“). Ihre Hauptaufgaben sind, die Messungen der Wetterelemente mit Sensoren in elektrische Signale zu verwandeln, diese Signale zu meteorologischen Daten zu verarbeiten und das Ergebnis aufzuzeichnen oder zu übertragen. Eine Station mit AWS kann vollautomatisch sein oder ein Mischsystem, in dem ein Beobachter visuelle Beobachtungen ergänzt.',
          'Eine AWS ist meist kein eigenständiges Gerät. Die WMO beschreibt sie als Teil eines Systems mit drei Hauptelementen: der Station mit den angeschlossenen Sensoren, einem Modem oder einer Schnittstelle zu einem Telekommunikationsnetz und einem zentralen Verarbeitungssystem, das mit den Daten aller Stationen des Messnetzes gespeist wird. Die zentrale Recheneinheit der Station erfasst, verarbeitet, speichert und überträgt die Daten.',
          'Die WMO ordnet AWS vier Kategorien zu, wobei manche Geräte mehrere abdecken. Leichte Stationen messen wenige Größen wie Niederschlag oder Lufttemperatur. „Basis“-Stationen messen typischerweise Lufttemperatur, relative Luftfeuchte, Windgeschwindigkeit und -richtung, Niederschlag und manchmal Luftdruck. „Erweiterte“ Stationen messen zusätzlich Sonnenstrahlung, Sonnenscheindauer, Bodentemperatur, Verdunstung und so weiter. Die vierte Kategorie sind Basis- oder erweiterte Stationen mit automatischer Beobachtung von Sichtweite, Wolkenuntergrenze und gegenwärtigem Wetter.',
          'Zu ihren Gründen für die Automatisierung zählt die WMO Beobachtungen von Orten, an denen keine Menschen verfügbar oder die schwer erreichbar sind, Daten 24 Stunden am Tag an bemannten Stationen, zuverlässigere Messung durch digitale Verfahren, Messnetze, die auf dieselbe vereinheitlichte Weise messen, und Messen und Melden mit hoher Frequenz oder fortlaufend. Sie sagt, dass alle modernen Messinstrumente für eine AWS geeignet sind, mit Bedingungen wie robust zu sein, wenig Wartung und Reinigung zu brauchen und leicht austauschbar zu sein. Band I des Leitfadens beschreibt die Instrumente, und die anderen Einträge dieser Seite folgen ihm.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Die Software einer AWS erledigt die Schritte vom Signal zum Wert. Als Arbeitsschritte, die typischerweise nötig sind, nennt die WMO einige oder alle der folgenden: das Ausgangssignal des Instruments abtasten, es in meteorologische Daten umrechnen, linearisieren, mitteln, Qualitätskontrolle, Datenreduktion, Meldungen formatieren und prüfen sowie die Daten speichern, übertragen und anzeigen. Die Linearisierung, sagt die WMO, sollte immer vor der Berechnung eines Mittelwerts erfolgen.',
          'Abtasten und Mitteln gehören zusammen. Als allgemein anerkannte Faustregel gilt, mindestens einmal während der Zeitkonstante des Instruments abzutasten. Wegen der kleinräumigen Veränderlichkeit der Atmosphäre und des Rauschens, das Elektronik hineinträgt, nennt die WMO das Mitteln ein höchst wünschenswertes Verfahren, um die Unsicherheit gemeldeter Daten zu verringern. Sie verweist auf ihre Tabelle der Anforderungen, die empfiehlt, „momentane“ Werte der meisten Größen als Ein-Minuten-Mittel zu bilden, außer bei Wind und Sichtweite. Windmessungen brauchen, sagt die WMO, eine hohe Erfassungsrate und eine Berechnung von Mittelwerten und Böen über längere Zeiträume (10 Minuten für den synoptischen Gebrauch, 2 Minuten für den lokalen Flugwetterdienst); die Berechnung kann auf der Station erfolgen, aber viele moderne Windmesser haben sie eingebaut.',
          'Die Statistiken bildet die Station oder das zentrale System. Die WMO nennt Extremwerte über einen oder mehrere Zeiträume (zum Beispiel bei der Temperatur), Gesamtmengen über Zeiträume von Minuten bis Tagen (zum Beispiel beim Regen), Mittelwerte über verschiedene Zeiträume und integrierte Werte (zum Beispiel bei der Strahlung), und sie nennt abgeleitete Größen wie den Taupunkt und den Luftdruck auf Meereshöhe. Sie stellt einen Trend fest, wo das Telekommunikationsnetz es erlaubt, Ein-Minuten-Daten zentral zu sammeln und dort zu verarbeiten. Siehe „Von der Messung zum Wert“.',
          'Die Meldungen, die die Station verlassen, werden verschlüsselt. Die WMO stellt den Übergang von alphanumerischen Schlüsseln, typischerweise SYNOP, zu tabellengesteuerten Schlüsseln wie BUFR fest und sagt, dass das Verschlüsseln von Standardmeldungen in einer zentralen Verarbeitungsplattform im Allgemeinen einfacher ist.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Die WMO sagt, dass die Leistung der heutigen Elektronik kein begrenzender Faktor mehr dafür ist, die geforderte Genauigkeit zu erreichen: Die Messunsicherheiten einer AWS hängen vor allem mit den Eigenschaften der Instrumente selbst und ihrer Aufstellung zusammen. Die bestehenden Leitlinien für den Standort konventioneller Stationen, sagt die WMO, gelten auch für AWS.',
          'Automatisierung ändert, was beobachtet wird. Die WMO sagt, dass die Wolkenbedeckung meist aus der Höhe der Wolkenuntergrenze abgeleitet wird, die ein Ceilometer misst, zusammengefasst oder gemittelt über einen Zeitraum von 10, 30 oder 60 Minuten, während ein Mensch eine größere Sicht auf den Himmel hat, zumindest tagsüber; die automatische Messung steht für eine Linie durch den Himmel in Richtung der Höhenwinde, die mit der ganzen Himmelsansicht eines Menschen in einem Moment nicht übereinstimmen muss. Eine Messung der Sichtweite steht für den Ort des Instruments, es sei denn, mehrere Sichtweitenmesser sind aufgestellt, während ein Mensch ringsum schaut, aber durch die vorhandenen Sichtmarken begrenzt ist. Ein Instrument für das gegenwärtige Wetter kann derzeit nicht die ganze Bandbreite der Schlüsselzahlen für das gegenwärtige Wetter erkennen, die ein Mensch melden kann. Mit den Worten der WMO: Manuelle und automatische Beobachtungen von Sichtweite, Wolkenbedeckung und gegenwärtigem Wetter sind deutlich verschieden.',
          'Ein Teil der Arbeit ist nicht automatisiert. Die WMO führt auf, dass die Qualität mancher Beobachtungen sich verschlechtern kann, weil Schlüsselteile des Messvorgangs nicht automatisiert sind, zum Beispiel das Reinigen der Kuppel eines Strahlungsinstruments oder einer Verdunstungsschale, und dass der Wechsel von manuellen visuellen Beobachtungen zu automatischen Messungen die Art mancher Beobachtungen so ändern kann, dass es für die Klimaüberwachung zählt. Instrumente mit elektrischem Ausgang driften mit der Zeit, sagt die WMO, sie brauchen deshalb regelmäßige Prüfung und Kalibrierung, und der Netzbetreiber soll alle 6 bis 12 Monate eine regelmäßige Feldprüfung organisieren, je nach Instrumenten, Zugang zu den Standorten und Wartungsorganisation.',
          'Wo eine Station Daten für Klimaaufzeichnungen liefert, verlangt die WMO überlappende Zeiträume vergleichbarer Messungen zwischen den alten und den neuen Instrumenten sowie eine Dokumentation der Unterschiede zwischen altem und neuem Standort und der Wechsel der Instrumente. Als allgemeine Richtwerte schlägt sie 12 Monate Überlappung für Windgeschwindigkeit und -richtung vor, 24 Monate für Temperatur, Feuchte, Sonnenschein und Verdunstung und 60 Monate für Niederschlag, und sie nennt 24 Monate, zwei Jahreszeitenzyklen, einen brauchbaren Kompromiss.',
          'Die Station prüft ihre eigenen Abtastwerte. Die WMO beschreibt Prüfungen auf einen plausiblen Wert und eine plausible Änderungsrate, auf ein Instrument, das nicht mehr auf das Wetter reagiert, auf die Zahl gültiger Abtastwerte in einem Zeitraum und gegen andere gemessene Größen (der Taupunkt kann die Lufttemperatur nicht übersteigen). Sie sagt, dass die Daten einer Station, die keine Qualitätskontrolle und keine Prüfung ihrer Meldungen hat, wahrscheinlich unentdeckte Fehler enthalten und dass die Prüfungen oft zwischen Station und zentralem System aufgeteilt sind.',
          'Auch wie eine Station gebaut ist, begrenzt, was sie sagen kann. Die WMO schreibt über „Alles-in-einem“-Bauarten, dass einige ihrer Instrumente schwer zu kalibrieren und oft schlecht dokumentiert sind und dass alle Größen in derselben Höhe gemessen werden, was sie eine große Schwäche nennt: Bei etwa 2 m Montagehöhe ist die Windmessung sehr empfindlich für die Fläche darunter; bei 10 m Montagehöhe, um den Empfehlungen für den Wind zu folgen, werden auch die anderen Größen in 10 m gemessen, was den Standortempfehlungen nicht entspricht.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Die Stationsdateien des DWD sagen, aus welcher Art automatischer Station ein Wert stammt und seit wann. In Potsdam sind die Winddaten hinter dem Tagesmittel der Windgeschwindigkeit und der höchsten Tagesböe, schreibt der DWD, von August 1992 bis April 2002 und wieder von Juni 2002 bis August 2003 aus 10-Minuten-Mitteln automatischer Stationen der ersten Generation (MIRIAM/AFMS2 genannt) erzeugt und seit dem 1. September 2003 aus denen der zweiten Generation (AMDA genannt); für den Mai 2002 nennt die Datei SYNOP-Meldungen, die international verschlüsselten Beobachtungen. In Frankfurt/Main stammen die stündliche Lufttemperatur und die relative Luftfeuchte von November 1993 bis April 2001 von automatischen Stationen der ersten Generation und seitdem aus SYNOP-Meldungen.',
          'Der DWD sagt, dass zwischen dem Ende der neunziger Jahre und 2009 viele seiner Stationen von manueller auf automatische Beobachtung umgestellt wurden. Seine Beschreibung des Monatsdatensatzes nennt Änderungen der Instrumente und des Beobachtungspersonals unter den Quellen der Unsicherheit langer Reihen.',
          'Der DWD kennzeichnet manche Beobachtungen als von einem Menschen oder von einem Instrument gemacht: Seine stündliche Wolkenbedeckung und seine stündliche Sichtweite tragen einen Indikator, P für einen Menschen und I für ein Instrument (siehe „Wolken“ und „Sichtweite“). Die WMO beschreibt Straßenwetterstationen als automatische Wetterstationen für einen besonderen Zweck (siehe „Straßenwetterstationen“). Diese Seite sagt nichts über die automatischen Stationen anderer Anbieter.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band III, Kapitel 1 zu Messungen an automatischen Wetterstationen stammen in diesem Eintrag die Definition, die Arten von Stationen, die Schritte vom Signal zum Wert, die Qualitätskontrolle und die Unterschiede zwischen automatischer und manueller Beobachtung.',
        'Volume III (Observing systems), Chapter 1 (Measurements at automatic weather stations), sections 1.1.1, 1.1.2, 1.1.3, 1.1.4, 1.1.5, 1.2.3, 1.3.1, 1.4.2, 1.4.2.2, 1.4.2.5, 1.4.2.7, 1.5, 1.6, 1.7.2.',
        WMO_III,
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, aus welcher Art Station ein Wert stammt. Die Beschreibung seines Tagesdatensatzes sagt, dass viele Stationen von manueller auf automatische Beobachtung umgestellt wurden.',
        `${STATION_FILES} Metadaten_Parameter_klima_tag_* (Parameter FM und FX von Potsdam); Stundenarchiv stundenwerte_TU_01420_akt.zip in ${DWD_HOURLY}air_temperature/recent/ (Metadaten_Parameter_tu_stunde_01420), am 22. November 2026 gelesen; Datensatzbeschreibung „Tägliche Stationsbeobachtungen (Temperatur, Druck, Niederschlag, Sonnenscheindauer, etc.) für Deutschland“, Version v24.3 (2024), Abschnitt „Datenherkunft“.`,
        DWD_DAILY,
      ),
      dwdFiles(
        'Die Beschreibung seines Monatsdatensatzes führt die Quellen der Unsicherheit langer Reihen auf, darunter Änderungen der Instrumente und des Beobachtungspersonals.',
        'DWD Climate Data Center. Datensatzbeschreibung „Monatliche Stationsbeobachtungen (Temperatur, Niederschlag, Sonnenscheindauer, Wind und Bewölkung) für Deutschland“, Version v24.03 (2024), Abschnitt „Unsicherheiten“, am 22. November 2026 gelesen.',
        DWD_MONTHLY,
      ),
    ],
  },

  'radar': {
    title: 'Radar',
    summary: 'Ein Wetterradar misst das Echo, das Regen, Schnee oder Hagel zurückschicken, nicht den Niederschlag am Boden. Eine Formel macht aus dem Echo eine Rate, und der DWD fügt seine Radare zu Bildern von Deutschland zusammen.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Ein Wetterradar sendet von einer sich drehenden Antenne kurze Impulse aus Radiowellen aus und lauscht auf das Echo, das zurückkommt. Die WMO sagt, dass die Radare, die sich am besten für die Beobachtung der Atmosphäre eignen, Frequenzen von 3 bis 10 GHz nutzen, also Wellenlängen von 10 bis 3 cm. Die Zeit zwischen dem Impuls und seinem Echo gibt die Entfernung des Ziels an. Wie stark das Echo ist, hängt von der Größe und der Zahl der Teilchen in dem Volumen ab, das der Strahl füllt, und die WMO sagt, dass diese Stärke genutzt wird, um den Reflektivitätsfaktor (Z) zu bestimmen, aus dem über empirische Beziehungen die Intensität des Niederschlags geschätzt wird. Der Strahl wird mit der Entfernung breiter: Ein Strahl von nominell 1° ist in 50 km Entfernung 0,9 km breit, in 100 km 1,7 km und in 200 km 3,5 km.',
          'Das Echo stammt nicht immer vom Regen. Die WMO nennt Insekten, Vögel, Flugzeuge, Sand und Staub, Bodenechos (Clutter) und sogar Schwankungen des Brechungsindex der Luft als andere Dinge, die ein Wetterradar erfassen kann. Die aktuelle Generation der Radare hat Dual-Polarisation: Die Impulse werden gleichzeitig mit horizontaler und mit vertikaler Polarisation gesendet. Die WMO sagt, dass die Hauptvorteile eine bessere Datenqualität sind, weil das Radar erkennen kann, was das Ziel ist (Vögel, Insekten, Niederschlag und seine Art, Clutter), sowie die Klassifizierung von Hydrometeoren und die Schätzung des Niederschlags; für Vorhersagen kann die Dual-Polarisation Hagel und die Grenze zwischen Regen und Schnee erkennen.',
          'Der DWD betreibt ein Netz von 17 operationellen Wetterradaren mit Dual-Polarisations-Doppler-Technik. Ein weiteres Radar am Observatorium Hohenpeißenberg dient der Qualitätssicherung und dem Testen neuer Hard- und Software. Die horizontale Reichweite der Radare beträgt bis zu 180 km, und in der Vertikalen reicht ihre Abdeckung von bodennah bis über 10 km. Die Scanstrategie des DWD ist ein Zyklus von 5 Minuten. Er beginnt mit einem Niederschlags-Scan nahe am Boden, bei dem die Antenne dem Gelände folgt (Reichweite 150 km). Es folgt ein Volumen-Scan aus zehn Umdrehungen bei festen Elevationswinkeln: sechs von 5,5° hinunter bis 0,5° (Reichweite 180 km), dann vier bei 8°, 12°, 17° und 25°, mit einer Reichweite, die mit dem Winkel von 160 km auf 120 km abnimmt. Der Zyklus endet mit einem senkrechten Scan in den Himmel, zur Kalibrierung.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Ein Echo sagt wenig. Die WMO erklärt, dass sich die Teilchen im Volumen des Strahls ständig gegeneinander verschieben, sodass einer einzelnen Echointensität wenig Bedeutung zukommt, und dass mindestens 25 bis 30 Impulse integriert werden müssen, um die mittlere Intensität einigermaßen zu schätzen. Eine weitere Mittelung in Entfernung, Azimut und Zeit wird oft vorgenommen, auf Kosten einer gröberen räumlichen Auflösung.',
          'Die Stärke des Echos wird dann mit einer Beziehung zwischen Z und der Rate R in eine Niederschlagsrate umgerechnet: Z = A R^b. Die WMO sagt, dass diese Beziehung nicht eindeutig ist, weil verschiedene Tropfengrößenverteilungen dasselbe Echo ergeben können, und dass viele Beziehungen für verschiedene Klimate und Sturmarten entwickelt wurden. Die nominellen und typischen Werte sind A = 200 und b = 1,6 (Marshall und Palmer); sie lassen sich für Regen wie für Schnee auf einen Faktor zwei genau anwenden. Die WMO zitiert eine Umfrage, in der 80 % der operationellen Wetterradare diese Beziehung nutzten.',
          'Die Messungen eines Radars liegen in Polarkoordinaten vor, und die Radare eines Netzes werden zusammengefügt. Die WMO sagt, dass Polardaten durch Interpolation in zwei- oder dreidimensionale kartesische Gitter umgerechnet werden und dass für Gebiete, in denen sich die Abdeckung von Radaren überlappt, die Algorithmen auf dem nächsten Radar, auf dem Höchstwert oder auf einer Schätzung der Datenqualität beruhen. Die Komposite des DWD sind solche Bilder des gesamten Netzes, auf Gittern von 1 km oder 250 m.',
          'Der DWD veröffentlicht mehrere Komposite von Deutschland, jedes mit einem eigenen Produktblatt. Das RV-Komposit ist der über 5 Minuten akkumulierte Niederschlag in mm auf einem Gitter von 1 km × 1 km (1200 × 1100 Zellen), alle 5 Minuten; für die grafische Darstellung hat der DWD es auf eine Stunde hochgerechnet (mm in 1 h). Das RS-Komposit ist der Niederschlag einer Stunde. Das WN-Komposit ist ein Reflektivitäts-Komposit des Niederschlags-Scans, in dBZ, und die Komposite HX und DMAX sind Reflektivitäts-Komposite des Niederschlags-Scans und des Volumen-Scans, auf einem Gitter von 250 m × 250 m. Das VII-Komposit ist die Eismasse, die das Radar in einer senkrechten Luftsäule erfasst, und das HymecNG-Komposit gibt die Niederschlagsart in 2 m Höhe über Grund in 11 Klassen an (großer Hagel, kleiner Hagel, Graupel, gefrierender Regen, gefrierender Sprühregen, Schnee, Schneeregen, Regen, Sprühregen, nicht klassifizierbar, kein Niederschlag); für diese beiden sagt der DWD, dass neben dem Radar-Scan weitere Datenarten genutzt werden, darunter Modelldaten.',
          'Der DWD bietet das RV- und das WN-Komposit auch mit einer Vorhersage für 2 Stunden an, die durch Verlagerung berechnet wird. Das Prinzip dieses Nowcastings, wie der DWD es für sein System RADVOR beschreibt, ist es, ähnliche Strukturen in aufeinanderfolgenden Radarbildern des Niederschlags zu erkennen, zu bestimmen, wie sie sich über Deutschland verlagern, und diese Verlagerung in 5-Minuten-Schritten bis zu 2 Stunden in die Zukunft fortzuschreiben. Es ist kein Wettermodell. Die WMO beschreibt Nowcasting ebenso: Traditionell ist es eine automatisierte lineare Extrapolation der aktuellen Lage. Eine Annahme des Beispiels, das die WMO gibt, ist, dass das Niederschlagssystem fortbesteht, ohne Entwicklung, und die Güte dieses Beispiels war in den ersten 20 bis 30 Minuten sehr hoch. Siehe „Beobachtung, Vorhersage und abgeleitete Daten“.',
          'Der DWD eicht den Radarniederschlag auch an den Boden an. Sein Verfahren RADOLAN verbindet die Stundenwerte von Niederschlagsmessern mit den 17 Radaren zu Niederschlagsdaten für ganz Deutschland. Der DWD sagt, dass Radar den bodennahen Niederschlag nicht direkt messen kann, sondern nur die Signale, die die Hydrometeore in der Atmosphäre reflektieren, sodass eine quantitativ richtige Radaranalyse mit Niederschlagsmessern am Boden geeicht werden muss. Das beste Produkt ist ein Komposit stündlicher Niederschlagshöhen mit einer Intensitätsauflösung von 0,1 mm und einer räumlichen Auflösung von 1 km², das innerhalb von 30 Minuten verfügbar ist und seit dem 25. April 2018 alle zehn Minuten berechnet wird. Die Seite des DWD zeigt die Stundensummen als Produkt RW und die Summen von 24 Stunden als SF.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Ein Radar schaut auf die Luft über dem Boden. Die WMO erklärt, dass der Strahl mit der Entfernung ansteigt und dass wegen der Strahlbreite, der Neigung des Strahls und der Erdkrümmung Radarmessungen des Niederschlags in großen Entfernungen niedriger sind als am Boden. In großen Entfernungen ist der Strahl breit und womöglich nicht mit Niederschlag gefüllt, und er kann flache Wetterlagen überschießen. Für gute quantitative Schätzungen nennt die WMO ohne Anpassung eine effektive Reichweite von etwa 80 km für ein Radar mit einem 1° breiten Strahl und von 110 bis 120 km für eines mit einem 0,65° breiten Strahl. Die Reflektivität nimmt meist mit der Höhe ab, sodass das Radar Regen bei schichtförmigem Wetter und Schnee unterschätzt.',
          'Die Rate ist eine Schätzung. Die WMO sagt, dass die natürliche Schwankung der Tropfengrößen eine wichtige Quelle der Unsicherheit der Z–R-Beziehung ist und dass Radarschätzungen mit den punktuellen Messungen von Niederschlagsmessern innerhalb eines Faktors zwei übereinstimmen. Ein Teil des Unterschieds ist, dass ein Niederschlagsmesser eine äußerst kleine Fläche erfasst (100 oder 200 cm²), während das Radar über einen viel größeren Maßstab integriert (1 bis 4 km²). Die WMO sagt, dass Vergleiche mit Niederschlagsmessern routinemäßig als Kontrolle des Radars gemacht werden sollen und dass Anpassungen vorgenommen werden sollen, wenn ein Fehler deutlich erkennbar ist, aber mit Bedacht, weil das Abstimmen für eine Lage in anderen Lagen Probleme schaffen kann. Zu dem, was ein Niederschlagsmesser auffängt, siehe „Niederschlag“.',
          'Nicht jedes Echo ist Niederschlag. Die WMO sagt, dass Bodenechos (Echos von Gebäuden, Hügeln und Bergen) für die Niederschlagsschätzung beseitigt werden müssen, dass anomale Ausbreitung, bei der der Strahl zum Boden hin gebogen wird, Bodenechos verursacht, die auf dieselbe Weise beseitigt werden, und dass Echos von Insekten und Vögeln für die Niederschlagsmessung Rauschen sind. Berge und Hindernisse können den Strahl teilweise oder ganz abschatten, was zu Unterschätzungen führt. Starker Regen schwächt das Signal ab, besonders bei den kurzen Wellenlängen von 5 und 3 cm, und ein nasses Radom, die Hülle der Antenne, kann es ebenfalls abschwächen. Windkraftanlagen sind eine Quelle von Echos, die sich schwer entfernen lassen. Die WMO fügt hinzu, dass quantitative Anwendungen des Wetterradars noch in Entwicklung sind, während die qualitative Nutzung zum Verstehen und Erkennen schwerer Stürme ausgereift ist.',
          'Ein Radarbild ist keine Karte von Niederschlagsmessern. Im Radar-Werkzeug dieser App ist jede Farbe eine Klasse der Rate über 5 Minuten, und eine Rate unter 0,1 mm/h ist so durchsichtig wie ein Ort ohne Daten, sodass keine Farbe nicht heißt, dass es nicht regnet. Ein Bild, das als Vorhersage markiert ist, ist die Fortschreibung der jüngsten Bewegung des Regens, keine Messung.',
        ],
      },
      {
        title: 'Worin sich die Anbieter unterscheiden',
        paragraphs: [
          'Wetterdienst hat Radardaten von einem Anbieter, dem DWD (dwd/radar). Neben den oben genannten Kompositen hat es die RADOLAN-Produkte und die Polardaten einzelner Radare (die Sweeps im Format ODIM HDF5 und andere Produkte eines Standorts). Sein Befehl radar listet auch die Radarstandorte anderer Länder aus der Datenbank von EUMETNET OPERA auf, aber nur als Liste von Standorten: Wetterdienst hat keine Radardaten eines anderen Anbieters, und diese Seite sagt nichts darüber, wie die Radare anderer Länder betrieben werden. Die WMO nennt OPERA, das European Operational Programme for the Exchange of Weather Radar Information, als multinationales Modell, in dem Radarprodukte ausgetauscht werden, um Komposite zu erzeugen.',
          'Die Namen der Produkte sagen nicht immer, was sie enthalten. In Wetterdienst ist RV_REFLECTIVITY der Niederschlag von 5 Minuten und keine Reflektivität, und RS_PRECIPITATION_SUM ist der Niederschlag einer Stunde; WN_REFLECTIVITY, HX_REFLECTIVITY und DMAX_REFLECTIVITY sind Reflektivitäten in dBZ.',
          'Das Radar-Werkzeug dieser App (/radar) zeigt das RV-Komposit: die letzten zwei Stunden und die Vorhersage des DWD für die nächsten zwei, in einem Bild alle 5 Minuten. Wetterdienst rechnet die Summe von 5 Minuten in eine Rate in mm/h um (indem es sie mit 12 multipliziert), ordnet sie sieben Klassen zu (0,1 bis unter 0,5, 0,5 bis 1, 1 bis 2,5, 2,5 bis 5, 5 bis 10, 10 bis 25 und 25 mm/h und mehr) und zeichnet das Gitter des DWD, das in einer polar-stereografischen Projektion liegt, als Bild in der Web-Mercator-Projektion neu, in dem jedes Pixel die Zelle übernimmt, in der es liegt. Das neueste Bild ist beim Anzeigen etwa 5 bis 15 Minuten alt, weil der DWD einen Lauf 3 bis 8 Minuten nach seiner Zeit veröffentlicht. Das Werkzeug sagt es, wenn der neueste Lauf mehr als 20 Minuten alt ist, was bedeutet, dass der Datenstrom des DWD stehen geblieben ist.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Band III, Kapitel 7 über Radarmessungen ist, woher dieser Eintrag übernimmt, wie ein Radar misst, wie aus dem Echo eine Rate wird, was Komposite und Nowcasting sind und welche Fehlerquellen es gibt.',
        'Volume III (Observing systems), Chapter 7 (Radar measurements), sections 7.1.1, 7.2.1, 7.2.5, 7.4.1, 7.5.3, 7.8.2, 7.9, 7.10.3, 7.10.4.1, 7.10.4.2, 7.10.4.3, 7.11.',
        WMO_III,
      ),
      dwdFiles(
        'Seine Seite zu den Radarprodukten beschreibt sein Radarnetz und seine Scanstrategie, und zu jedem Komposit gibt es ein Produktblatt, das sagt, was es enthält.',
        'DWD. Radar products, dwd.de/EN/ourservices/radar_products/radar_products.html; die Produktblätter „Radarkomposit“ RV, WN, HX, DMAX, RS, VII und HymecNG, verlinkt von dwd.de/DE/leistungen/radarprodukte/radarprodukte.html, am 22. November 2026 gelesen.',
        DWD_RADAR_PRODUCTS,
      ),
      dwdFiles(
        'Seine Seite zu RADVOR beschreibt das Nowcasting, das die Vorhersage der nächsten zwei Stunden liefert.',
        'DWD. RADVOR (Radar-Niederschlagsvorhersage), dwd.de/DE/leistungen/radvor/radvor.html, am 22. November 2026 gelesen.',
        DWD_RADVOR,
      ),
      dwdFiles(
        'Seine Seite zu RADOLAN beschreibt, wie Radar und Niederschlagsmesser zu stündlichen und täglichen Niederschlagshöhen verbunden werden.',
        'DWD. Analysen radarbasierter stündlicher (RW) und täglicher (SF) Niederschlagshöhen (RADOLAN), dwd.de/DE/leistungen/radolan/radolan.html, am 22. November 2026 gelesen.',
        DWD_RADOLAN,
      ),
      {
        plain: 'Die Dokumentation der Bibliothek Wetterdienst beschreibt die Radarprodukte so, wie die Bibliothek sie liefert, und wie das Radar-Werkzeug dieser App das RV-Komposit in die Klassen seiner Legende umrechnet.',
        citation: 'Wetterdienst documentation, the pages "Radar" (dwd/radar, with the section "Radar frames on the REST API") and "Python examples" (the radar sites of EUMETNET OPERA).',
        href: `${WETTERDIENST_DOCS}provider/dwd/radar/index.html`,
      },
    ],
  },
  'urban-stations': {
    title: 'Stationen in der Stadt',
    summary: 'Die WMO sagt, dass die meisten bebauten Standorte es unmöglich machen, die üblichen Regeln für die Aufstellung von Instrumenten einzuhalten. Eine Stadtstation wird deshalb so gesetzt, dass sie für eine Art Stadtviertel steht, und was sie misst, ist das Lokalklima dieses Viertels.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Die Maßeinheiten und die Instrumente sind dieselben wie in anderen Umgebungen, sagt die WMO; besonders an einer Stadt sind die Wahl des Standorts, die Aufstellung der Instrumente und die Dokumentation. Die WMO nennt den Grund: Die meisten bebauten Standorte machen es unmöglich, den üblichen Leitlinien für Standortwahl und Aufstellung aus Band I zu folgen, weil Gebäude und Bäume den Luftstrom und den Strahlungsaustausch behindern, der Boden mit unnatürlichen Oberflächen bedeckt ist und menschliche Tätigkeiten Abwärme und Wasserdampf abgeben. Sie fügt hinzu, dass es manchmal nötig ist, eine Aufstellung über nicht standardmäßigen Oberflächen in nicht standardmäßigen Höhen hinzunehmen, die Beobachtungen auf zwei oder mehr Orte aufzuteilen oder näher als üblich an Gebäuden oder Abwärmeaustritten zu stehen.',
          'Die WMO unterscheidet drei Maßstäbe. Der Mikromaßstab ist der einzelner Gebäude, Bäume, Straßen und Höfe, von weniger als 1 m bis zu Hunderten von Metern, wo Oberflächen- und Lufttemperaturen auf sehr kurzen Strecken um mehrere Grad schwanken können. Der lokale Maßstab ist der eines Viertels mit ähnlicher Bebauung, ein bis mehrere Kilometer, und das ist es, was eine übliche Klimastation überwachen soll. Der Mesomaßstab ist der der ganzen Stadt, typischerweise Dutzende Kilometer, und eine einzelne Station kann ihn nicht abbilden.',
          'In der Senkrechten bilden die Gebäude und Bäume die Stadtkronenschicht (urban canopy layer). Die WMO sagt, dass ein Instrument unterhalb einer bestimmten Höhe, der Durchmischungshöhe (blending height), Mikroklima-Abweichungen erfassen kann und dass es oberhalb davon ein durchmischtes Signal „sieht“, das für den lokalen Maßstab steht. Faustregeln und Feldmessungen deuten darauf hin, dass diese Höhe bei dicht bebauten und gleichförmigen Standorten bis auf das 1,5-Fache der mittleren Höhe der Gebäude und Bäume sinken kann, in Gebieten geringer Dichte aber mehr als das 4-Fache beträgt.',
          'Die WMO beschreibt zwei Wege, die Instrumente aufzustellen: in der Stadtkronenschicht an einer Stelle, die von typischen Bedingungen umgeben ist, mit den Sensoren in Höhen wie an nicht städtischen Standorten, oder auf einem hohen Mast über der Rauigkeitsschicht. Im Allgemeinen, sagt sie, funktioniert der erste am besten für Lufttemperatur und Luftfeuchte und der zweite für Windgeschwindigkeit und -richtung und für Niederschlag, sodass Stadtstationen oft aus Instrumenten bestehen, die sowohl unter als auch über Dachhöhe stehen.',
          'Um das Viertel zu wählen, ordnet die WMO städtische Formen sieben städtischen Klimazonen zu, von dicht bebauten Zentren mit hohen Gebäuden bis zu halbländlicher Bebauung mit verstreuten Häusern, nach Höhe und Abstand der Gebäude und dem Anteil versiegelten Bodens. Innerhalb einer Zone sucht sie eine einigermaßen gleichförmige Bebauung und nennt, was zu meiden ist: ungewöhnlich feuchte Flecken in einem sonst trockenen Gebiet, einzelne Gebäude, die mehr als die halbe mittlere Gebäudehöhe herausragen, einen großen asphaltierten Parkplatz in einem Gebiet bewässerter Gärten, eine große, konzentrierte Wärmequelle und den Übergang zwischen zwei Zonen. Dächer haben eigene, abweichende Mikroklimate, sagt die WMO, und sind sehr schlechte Orte für Lufttemperatur, Luftfeuchte, Wind und Niederschlag, außer die Instrumente stehen auf sehr hohen Masten; für die einfallende Strahlung können sie gut sein.',
          'Für die Lufttemperatur eignen sich die üblichen Sensoren, sagt die WMO, mit besonderer Sorgfalt bei Strahlungsschutz und Belüftung. Die Standardhöhe des Strahlungsschutzes von 1,25 bis 2 m ist zulässig, aber es kann besser sein, größere Höhen zuzulassen, weil Beobachtungen in Straßenschluchten durch den größten Teil der Stadtkronenschicht sehr geringe Temperaturgradienten zeigen, sofern der Sensor mehr als 1 m von einer Fläche entfernt ist: Messungen in 3 oder 5 m unterscheiden sich nicht sehr von denen in Standardhöhe, haben etwas größere Einzugsgebiete, liegen außer Reichweite und bekommen weniger Wärme von Fahrzeugabgasen und weniger Staub ab.',
          'Für den Wind sagt die WMO, dass ein Ort, der die Regel für offenes Gelände erfüllt (der Windmesser 10 m über dem Boden, Hindernisse mindestens das 10-Fache ihrer Höhe entfernt), in typischen Stadtvierteln nicht zu finden ist und dass einer, den es gibt, mit ziemlicher Sicherheit nicht repräsentativ für die Zone ist. In dicht bebauten Vierteln mit ziemlich gleichmäßiger Gebäudehöhe empfiehlt sie einen Windmesser auf einem Mast offener Bauart in mindestens dem 1,5-Fachen der mittleren Höhe der Gebäude und Bäume. Windgeschwindigkeit oder -richtung in dicht bebauten Gebieten mit mehreren Hochhäusern zu messen, empfiehlt sie nicht, außer es wird ein sehr hoher Turm benutzt.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Aus der Messung wird ein Wert wie an jeder anderen Station: Die WMO sagt, dass Zeitpunkt und Häufigkeit der Beobachtungen und das Verschlüsseln der Meldungen den entsprechenden Normen folgen sollen und dass für automatische Stationen die Empfehlungen ihres Kapitels über automatische Stationen gelten (siehe „Automatische Wetterstationen“). Anders ist die Fläche, für die ein Wert steht.',
          'Ein Sensor sieht nur einen Teil seiner Umgebung, sagt die WMO: sein Quellgebiet (source area). Für ein nach unten blickendes Strahlungsmessgerät ist es ein Kreis um das Instrument, dessen Größe von der Höhe des Sensors abhängt. Für ein Thermometer, ein Hygrometer oder einen Windmesser, deren Messwert durch Turbulenz zu ihnen getragen wird, ist es eine Ellipse, die windaufwärts liegt und sich mit der Windrichtung und mit der Stabilität der Luft bewegt. Als Schätzungen gibt die WMO an, dass die Entfernung, die für einen Sensor in Strahlungsschutzhöhe, etwa 1,5 m, zählt, einige Dutzend Meter bei neutralen Bedingungen beträgt und vielleicht mehr als 100 m bei stabiler Luft und dass der Einflusskreis auf einen Temperatur- oder Feuchtesensor in dieser Höhe typischerweise einen Radius von etwa 0,5 km haben dürfte, abhängig von der Bebauungsdichte. Die unmittelbare Umgebung der Station nennt sie bei Weitem die wichtigste.',
          'Wird der Wind in einer Siedlung in verschiedenen Höhen gemessen, beschreibt die WMO, wie man die Werte mit dem logarithmischen Windprofil auf eine gemeinsame Höhe bringt, in dem die Höhen von der Verschiebungshöhe (displacement height) an gezählt werden, der Höhe des „Bodens“ in der Luft, den die Gebäude bilden; sie sagt, dass eine geeignete Bezugshöhe 50 m über der Verschiebungshöhe sein könnte. Wo es keinen geeigneten Ort für einen Windsensor gibt, kann der Wind in der Bezugshöhe aus den Beobachtungen einer anderen Stadtstation oder des Flughafens berechnet werden.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Die WMO sagt, dass in Städten das Interesse dem Stadteffekt selbst gilt: der Änderung der Wettergrößen, wenn eine Stadt wächst, verglichen mit dem, was ohne sie geschehen wäre. Diese Frage ist, sagt die WMO, im Grunde nicht zu beantworten, sobald die Stadt gebaut ist, die Beurteilung von Stadteffekten ist mit methodischen Schwierigkeiten behaftet, und es ist keine „Wahrheit“ möglich, nur Ersatznäherungen.',
          'Eine Station steht für eine Art Viertel. Lufttemperatur und Luftfeuchte in der Stadtkronenschicht können lokal repräsentativ sein, wenn der Standort sorgfältig gewählt ist, sagt die WMO; werden sie über Dachhöhe beobachtet, gibt es keine gesicherte Verbindung zwischen ihnen und den Werten in der Stadtkronenschicht. Wind und turbulente Flüsse sollen über der Rauigkeitsschicht gemessen werden, wo gezeigt werden muss, dass die beitragende Fläche für die Zone repräsentativ ist. Eine Station, die den Namen einer Stadt trägt, muss nicht in ihr stehen: Für die Strahlung hält die WMO fest, dass Standorte oft an ländlichen oder abgelegenen Orten liegen, um die Schadstoffe der Städte zu meiden, und dass selbst bei einer Station mit dem Namen einer Stadt die Metadaten meist zeigen, dass sie weit außerhalb der Stadtgrenzen liegt.',
          'Niederschlagsmesser kommen in der Stadt schlecht zurecht. Für den Niederschlag nennt die WMO vier Probleme: Bäume und Gebäude, die Niederschlag auf dem Weg zum Boden auffangen, harte Flächen, die Wasser in den Messer spritzen, und überhängende Gegenstände, die hineintropfen, die sehr örtliche Anhäufung oder das Fehlen niederschlagführender Luftströmung um Hindernisse und die Böigkeit des Windes zusammen mit dem Messer selbst, die zu Unter- oder Überfang führt. Auf einem Mast über den Dächern trifft ein Messer mehr Wind als nahe am Boden, sein Ergebnis muss deshalb korrigiert werden. Übliche Verdunstungsinstrumente werden in der Stadtkronenschicht nicht empfohlen, weil die Oberflächen von Schalen und Lysimetern für die Umgebung eines Stadtstandorts wahrscheinlich nicht repräsentativ sind (siehe „Verdunstung“).',
          'Städte ändern sich, und damit ändert sich, was eine Station sieht. Die WMO sagt, dass Stadtstandorte eine ungewöhnlich hohe Komplexität und eine größere Neigung zur Veränderung haben und dass häufig aktualisierte Metadaten deshalb so wichtig sind wie die Messungen selbst; ohne eine gute Beschreibung der Station ist es unmöglich, die Messungen mit dem umgebenden Gelände zu verbinden.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Wetterdienst hat Stadtstationen von einem Anbieter, dem DWD, in den Datensätzen, deren Namen mit urban_ beginnen (zum Beispiel 10_minutes/urban_temperature_air). Der DWD sagt in seiner Beschreibung, dass die Messungen in Städten gemacht werden, um die Stadt mit dem umgebenden Land zu vergleichen, dass die Stationen wegen ihrer städtischen Lage die üblichen WMO-Standards nicht erfüllen können und stattdessen der WMO-Anleitung für Stadtstandorte von T. R. Oke folgen (WMO Instruments and Observing Methods Report No. 81, 2006) und dass die Daten des Ordners recent/ noch nicht vollständig qualitätsgeprüft sind. Er führt Kriterien für die Lage in der Stadt auf: eine Lage in der Innenstadt, ein Punkt, der für sein Viertel typisch ist, ein Ort möglichst inmitten zusammenhängender Bebauung und nicht an einem Übergang zwischen Vierteln, ein Boden, der zur Umgebung passt, ein Abstand zum nächsten Haus von der Hälfte des üblichen Häuserabstands, aber nicht weniger als 5 m, und keine Lage in einem Park oder unter Bäumen.',
          'Der DWD sagt, dass seine Stadtdaten eine eingeschränkte Repräsentativität und Qualität haben, und empfiehlt den Nutzern, das zu beachten. Rekordwerte für Deutschland, sagt er, werden nicht aus diesen Stationen abgeleitet, sondern nur aus Klimastationen, die die üblichen WMO-Anforderungen erfüllen und außerhalb der Städte stehen. Als die Unsicherheit, die in Städten überwiegt, nennt er örtliche Einflüsse wie Abschirmungen und spiegelnde Flächen.',
          'Die Stationen und ihre Instrumente unterscheiden sich. Die 10-Minuten-Lufttemperatur hat in der Liste des Ordners recent sechs Stationen: Berlin-Alexanderplatz (seit Juli 2015), Freiburg-Mitte, Hannover-Nordstadt, Dresden-Neustadt, Regensburg-Mitte und Hamburg-Neustadt (seit Juli 2024). Nicht jede Station hat jede Größe: Den stündlichen Luftdruck und die stündliche Bodentemperatur des Ordners recent gibt es nur für Berlin-Alexanderplatz. Die Stationsdateien führen die Höhen der Sensoren auf, wo sie welche haben. In Berlin-Alexanderplatz werden die Lufttemperatur und die Feuchte in 2 m Höhe über dem Boden gemessen, der Niederschlagsmesser in 1 m und der Windsensor in 368 m; in Freiburg-Mitte, Dresden-Neustadt und Regensburg-Mitte ist der Windsensor in 2 m Höhe über dem Boden aufgeführt, und die Windarchive von Hannover-Nordstadt und Hamburg-Neustadt führen keinen auf. Die WMO rät, den Wind über der Rauigkeitsschicht zu messen (siehe oben); die Dateien sagen nicht, warum drei Stationen ihren Windsensor in 2 m Höhe aufführen.',
          'Der DWD beschreibt, wie seine Werte gebildet werden. Die Stationsdateien beschreiben die 10-Minuten-Lufttemperatur und -Feuchte der sechs Stationen als „momentane“ Werte in 2 m Höhe, in UTC. In den Stundendateien ist der Wert für die Stunde x der von 10 Minuten davor: Unter UTC 11 ist, schreibt der DWD, das Mittel des Ein-Minuten-Intervalls abgelegt, das um UTC 10:50 endet.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band III, Kapitel 9 zu Beobachtungen in der Stadt stammen in diesem Eintrag die Maßstäbe, die Wahl des Standorts, die Aufstellung der Instrumente, die Grenzen der Werte und die Hinweise zu Metadaten.',
        'Volume III (Observing systems), Chapter 9 (Urban observations), sections 9.1, 9.1.1.1, 9.1.1.2, 9.1.1.3, 9.1.1.4, 9.1.1.5, 9.1.1.6, 9.2.2, 9.3.2.1, 9.3.5.2, 9.3.6, 9.3.7, 9.3.10, 9.4, 9.5, 9.6.1, 9.6.3, Table 9.1.',
        WMO_III,
      ),
      dwdFiles(
        'Die Beschreibung seines Stadtklima-Datensatzes sagt, wofür die Stationen da sind und wie ihre Standorte gewählt wurden. Die Dateien, die zu den Daten jeder Station gehören, nennen die Sensoren und ihre Höhen.',
        `DWD Climate Data Center, Dateien in ${DWD_URBAN}, am 22. November 2026 gelesen: Datensatzbeschreibung „Aktuelle stündliche Lufttemperatur und Luftfeuchte, gemessen an Stadtklimastationen, für ausgewählte urbane Räume in Deutschland“ (hourly/air_temperature/recent/, zuletzt editiert am 19. Dezember 2018); die Stationsliste zehn_st_min_tu_Beschreibung_Stationen.txt (10_minutes/air_temperature/recent/) und die Ordner hourly/pressure/recent/ und hourly/soil_temperature/recent/; in den Stationsarchiven 10minutenwerte_TU_STADT_*_akt.zip, 10minutenwerte_FF_STADT_*_akt.zip und 10minutenwerte_RR_STADT_00399_akt.zip: Metadaten_Geraete_Lufttemperatur_*, Metadaten_Geraete_Rel_Feuchte_*, Metadaten_Geraete_Geschw_Mittel_*, Metadaten_Geraete_Niederschlagshoehe_* und Metadaten_Parameter_zehn_st_min_tu_*.`,
        DWD_URBAN_TU,
      ),
    ],
  },

  'road-stations': {
    title: 'Straßenwetterstationen',
    summary: 'Eine Straßenwetterstation steht neben der Straße und misst, was ein Straßenbetreiber braucht: die Luft sowie die Temperatur und den Zustand der Fahrbahn. Sie ist für die Straße aufgestellt, also keine Standardstation.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Straßenwetterstationen dienen den Betreibern von Straßennetzen. Die WMO sagt, dass betriebliche Entscheidungen, etwa Straßenwetterinformationen herauszugeben und mit Enteisen und Schneeräumen zu beginnen, von straßenmeteorologischen Beobachtungen abhängen, die zunehmend von automatischen Wetterstationen für diesen besonderen Zweck gemacht werden. Sie nennt vier Hauptbedürfnisse der Betreiber: die Echtzeitbeobachtung des Straßenwetters, eine bessere Vorhersage der Temperatur der Fahrbahnoberfläche, eine Straßenklima-Datenbank und verlässliche Daten. Straßenbetreiber brauchen keine außerordentlich genauen Messungen, mit Ausnahme der Fahrbahntemperatur; sie wollen Daten, die so verlässlich wie möglich sind.',
          'Die WMO führt die Messungen auf, die an einer Straßenwetterstation wichtig sind, um den Zustand der Straße vorherzusagen: Lufttemperatur und Luftfeuchte, Windgeschwindigkeit und -richtung, Menge und Art des Niederschlags, Sichtweite, Global- und langwellige Strahlung, Fahrbahntemperatur und Fahrbahnzustand. Die Luftsensoren sollen den üblichen Regeln des Leitfadens folgen. Für Straßenstationen fügt die WMO hinzu, dass das Thermometer nicht über Beton oder Asphalt montiert sein soll, die die gemessene Temperatur erhöhen könnten, und nicht im Sprühwasser der Räder vorbeifahrender Fahrzeuge, und dass ein Psychrometer mit feuchtem Thermometer nicht empfohlen wird, weil Kohlenwasserstoffe den Docht fortlaufend verunreinigen.',
          'Die Fahrbahntemperatur wird mit einem Sensor gemessen, der in die Straße eingebaut ist. Die WMO beschreibt aktive Sensoren auf der Grundlage eines 100-Ohm-Platinwiderstands, die in der Ebene der Straße liegen müssen, ohne Mulde, in der sich Wasser sammeln könnte, und außerhalb der Spurrillen der Reifen, sonst wird die Sensoroberfläche verschmutzt und die Messung durch Reibungswärme beeinflusst. Die Temperatur des Straßenkörpers kann auch in 5, 10 und 20 cm unter der Fahrbahnoberfläche gemessen werden. Der Sensor für den Fahrbahnzustand schätzt, ob die Fläche trocken, nass, bereift oder vereist ist, und die Gefriertemperatur des Wassers darauf: Er erwärmt und kühlt dann den Sensor mit dem Peltier-Effekt, und die Abkühlungsrate hängt vom Zustand der Fläche und von der Gefriertemperatur ab.',
          'Der Niederschlag wird meist mit einer Kippwaage gemessen, bei der Schritte von meist 0,2 mm summiert werden und die für Schnee beheizt sein kann, und die Art des Niederschlags mit Sensoren, die sie elektronisch oder optisch schätzen. Die Sichtweite wird mit Transmissometern und Vorwärtsstreumessern gemessen, und die WMO stellt fest, dass Straßenbetreiber an Sichtweiten unter 200 m interessiert sind, der Gefahrenschwelle. Der Wind wird in der Standardhöhe von 10 m in offenem Gelände gemessen.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Die Rohsignale der Sensoren müssen zu repräsentativen Mittelwerten verarbeitet oder gefiltert werden, sagt die WMO, entweder in aktiven Sensoren, in der Schnittstelle der Datenerfassungseinheit oder in der höheren Verarbeitung der Station; die Mittelungszeiten sind die der Tabelle der Anforderungen in Band I, Kapitel 1 (siehe „Von der Messung zum Wert“). Algorithmen, die auf die Ausgaben der Sensoren wirken, sollen aus maßgeblichen Quellen stammen und gründlich geprüft sein, und jeder hauseigene Algorithmus soll in den Stationsmetadaten oder in Netzhandbüchern festgehalten werden.',
          'Station und zentraler Rechner teilen sich die Arbeit. Die WMO beschreibt einen Trend zu mehr Verarbeitung in der Außeneinheit, sagt aber, dass ein Netz von Stationen, die nicht komplexer sind als für eine verlässliche Datenerfassung nötig, mit einem zentralen Rechner für die komplexen Algorithmen, die Qualitätssicherung und die Schlüsselumsetzung ein verlässlicheres und billigeres System sein kann. Ein Beispiel für das, was berechnet werden kann, ist eine extrapolierte Fahrbahntemperatur: Ein Algorithmus nimmt die letzten Messungen und bildet eine quadratische Gleichung, aus der Schätzungen der Temperatur über die nächsten 3 Stunden berechnet werden können; die WMO nutzt sie in ihren Beispielen für Alarme.',
          'Die WMO sagt, dass die Planer eines Straßennetzes die Standardschlüssel der WMO für Meldungen bedenken sollen, die es anderen Nutzern wie den nationalen Wetterdiensten erlauben, die Daten zu empfangen und in anderen meteorologischen Anwendungen zu nutzen. Das Verschlüsseln kann auf der Station geschehen oder, wie es wahrscheinlicher ist, im zentralen Rechner nach der Qualitätssicherung der Daten.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Eine Straßenstation ist für die Straße aufgestellt. Sie muss neben der Fahrbahn stehen, damit die Sensoren für die Fahrbahn eingebaut werden können, sodass ein Kompromiss bei idealem meteorologischem Standort und idealer Aufstellung entstehen kann, sagt die WMO, und sie weist Nutzer, die Straßenmessungen in anderen meteorologischen Anwendungen verwenden wollen, auf wichtige Abweichungen hin, zum Beispiel bei der Aufstellung der Sensoren. Der Standort neben der Straße soll im Allgemeinen eben sein, mit kurzem Gras und nicht von Gebäuden oder Bäumen beschattet.',
          'Der Sensor für den Fahrbahnzustand ist ein Sonderfall. Die WMO sagt, dass es schwierig ist sicherzustellen, dass sein Messwert für den wahren Fahrbahnzustand repräsentativ ist, wegen der kleinen Probe, der Lage auf der Straße und unterschiedlicher Einbaupraxis, und dass seine Messung von der Verkehrsdichte abhängt und sonst zeitlich nicht sehr stabil ist. Der Sensor für die Fahrbahntemperatur braucht eine thermische Trägheit, die zu der der Fahrbahnoberfläche passt, eine Oberfläche mit geringer Absorption im Infrarot, um den Strahlungsfehler klein zu halten, und bei Kabeln über 20 m einen Ausgleich des Kabelwiderstands. Die Fahrbahntemperatur aus der Ferne mit Wärmebild-Infrarotsensoren zu messen, ist wegen des Sprühwassers der Fahrzeugreifen im Allgemeinen nicht praktikabel, sagt die WMO.',
          'Die Luft- und Niederschlagssensoren haben die Fehler der anderen Einträge und einige eigene. Die WMO sagt, dass Feuchtesensoren unter Verunreinigung durch Luft- und Fahrzeugschadstoffe leiden und dass ihre Kalibrierung mindestens alle sechs Monate geprüft werden soll, besonders vor der Wintersaison. Eine Kippwaage ist nicht zufriedenstellend, um den Beginn sehr leichten Regens oder lang anhaltende Frostperioden anzuzeigen, und ihre Summen sind niedriger als die wahren Werte wegen Windeffekten um die Öffnung, Verdunstung aus den Wippen zwischen Schauern und Verlust zwischen den Kippungen der Wippen bei starkem Regen. Für die Art des Niederschlags sagt die WMO, dass es den vorhandenen Sensoren an Unterscheidungsvermögen und stabiler Reproduzierbarkeit fehlt.',
          'Die Straße ist ein schwieriger Ort für eine Station. Die WMO nennt Vibrationen, Störungen durch Fahrzeugzündungen, Abgasbelastung, Korrosion durch Salznebel und Beschädigung als Probleme von Straßenstationen, und sie sagt, dass es für einen Straßenbetreiber sehr schwierig ist, fehlerhafte Messungen zu erkennen; grobe Sensorfehler können von der Software der Station erkannt werden, die dann einen Alarm auslösen soll.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Wetterdienst hat Straßenwetterstationen von einem Anbieter, dem DWD (dwd/road, 15-Minuten-Daten). Der DWD veröffentlicht die Meldungen der Stationen als BUFR-Dateien, eine für jede Stationsgruppe alle 15 Minuten. In seinem Hinweis zur Verwertung der Daten der Glättemeldeanlagen sagt er, dass die Straßenbauverwaltungen der Länder die Daten an den DWD übermitteln, dass es ungeprüfte Punktmessungen sind, die nicht die Verhältnisse auf einem Straßenabschnitt widerspiegeln, und dass kein Anspruch auf regelmäßige und vollständige Datenlieferungen besteht.',
          'Das BUFR-Template des DWD für Straßenwetterinformationen (Stand März 2015) sagt, was eine Station meldet: die Lufttemperatur (trockenes Thermometer), den Taupunkt, die relative Luftfeuchte und die Sichtweite; die Temperatur der Fahrbahnoberfläche; die Temperatur unter der Fahrbahnoberfläche, die erste in 0,30 m Tiefe und eine zweite zum Beispiel in 0,15 oder 0,07 m; die Dicke des Wasserfilms und den Fahrbahnzustand; den Niederschlag (Intensitätsklasse, Intensität, Art und Menge); den Wind und die höchste Böe; und Angaben zur Funktionsweise der Station. Der DWD merkt an, dass die meisten Stationen nur eine Position und eine Temperatur unter der Straße melden und dass die Standardzeitspanne einer Meldung 15 Minuten beträgt. Wetterdienst gibt die Temperatur der Fahrbahnoberfläche als temperature_surface zurück, den Wasserfilm als water_film_thickness (standardmäßig in Millimetern, wo der DWD Meter schreibt) und den Zustand der Fahrbahn als road_surface_condition. Welche Sensoren eine Station hat, ist unterschiedlich: Die ältere Beschreibung des DWD zum Schlüssel der Straßenwetterdaten (SH10, Stand Mai 2001) sagt, dass Glättemeldeanlagen in der Regel keine Sichtweite, keine Niederschlagshöhen oder Intensitätsklassen und keine Wasserfilmdicke messen.',
          'Die Unterlagen des DWD nennen noch einiges, das sich von Station zu Station unterscheidet. Die Position des Straßensensors ist als Fahrspur verschlüsselt, zwischen oder in den Rollstreifen; in der Beschreibung des Schlüssels durch den DWD ist die Standardposition der Fahrbahntemperatur die äußerste Überholspur, mittig zwischen den Rollstreifen. Einige Stationen können nur zwischen trocken, nicht trocken und glatt unterscheiden: Für sie hat der DWD die Schlüsselzahlen 6 (Glätte) und 7 (nicht trocken) in die Tabelle des Fahrbahnzustands aufgenommen, die außerdem 0 trocken, 1 feucht, 2 nass, 3 Reif, 4 Schnee und 5 Eis hat. Der DWD sagt, dass es keine einheitliche Definition von Klassen der Wasserfilmdicke gibt. In den am 22. November 2026 gelesenen Dateien mehrerer Stationsgruppen ist die Höhe des Lufttemperatursensors in einigen zwischen 4 und 5 m angegeben (4 m, 4,05 m oder 5 m, nach der Dokumentation von wetterdienst) und in anderen gar nicht, wo die WMO 1,25 bis 2 m verlangt. Der Mittelungszeitraum des Windes ist je Stationsgruppe verschieden: Die Beschreibung des Schlüssels durch den DWD sagt, dass nur der Wind gemittelt wird, über 10 Minuten, und dass die übrigen Werte die aktuellen Werte jeder Viertelstunde sind, während die Dateien einiger Gruppen dafür 15 Minuten, einen Zeitraum von 0 oder keinen nennen (Dokumentation des Datensatzes von wetterdienst).',
          'Die Namen der Parameter unterscheiden nicht zwischen Vorhersage und Messung. temperature_surface ist auch der Name der Vorhersage der Fahrbahntemperatur im Straßenwetter-Vorhersagemodell SWSMOS des DWD (dwd/swsmos, aus einem Straßenwettermodell), und die Vorhersage hat eigene Schlüsselzahlen für den Fahrbahnzustand (road_surface_condition_forecast, 1 trocken, 2 feucht, 3 Schnee, 4 Reif, 5 gefrierende Nässe, 6 Glatteis), die nicht die der Stationen sind. Siehe „Beobachtung, Vorhersage und abgeleitete Daten“. Diese Seite sagt nichts über die Straßenwetterstationen anderer Anbieter.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band III, Kapitel 10 zu straßenmeteorologischen Messungen stammen in diesem Eintrag der Zweck der Stationen, die Messungen, die Sensoren und ihre typischen Probleme.',
        'Volume III (Observing systems), Chapter 10 (Road meteorological measurements), sections 10.1.2, 10.1.3, 10.2.1, 10.3.1, 10.3.1.1, 10.3.1.2, 10.3.1.3, 10.3.1.4, 10.3.1.6, 10.3.1.7, 10.3.1.8, 10.3.1.9, 10.4.1, 10.4.2, 10.5.2, 10.8.1, 10.8.2, 10.9, 10.10.1.',
        WMO_III,
      ),
      dwdFiles(
        'Sein BUFR-Template für Straßenwetterinformationen sagt, was eine Straßenwetterstation meldet und wie die Schlüssel aufgebaut sind.',
        `DWD. „BUFR Template für Straßenwetter Informationen“ (nationales Template der Straßenwetterstationen, Stand März 2015), die Anmerkungen und die Schlüsseltabellen, am 22. November 2026 gelesen; das Verzeichnis ${DWD_ROAD}, dessen Liste für jede Stationsgruppe alle 15 Minuten eine Datei zeigt.`,
        DWD_ROAD_TEMPLATE,
      ),
      dwdFiles(
        'Sein Hinweis zu den Daten der Glättemeldeanlagen sagt, woher die Daten stammen und was sie sind und was nicht. Die Beschreibung des älteren Schlüssels, die dabei ist, sagt, welche Werte gemittelt werden.',
        'DWD. „Verwertung der Daten von Glättemeldeanlagen (GMA Daten)“ und die Anlage „Aufbau und Inhalt des Straßenwetterdatenschlüssels (SH10)“ (Stand Mai 2001), am 22. November 2026 gelesen.',
        DWD_ROAD_NOTICE,
      ),
      {
        plain: 'Die Dokumentation der Bibliothek wetterdienst beschreibt die Straßenwetterdaten, wie die Bibliothek sie liefert, mit dem Mittelungszeitraum, den die Dateien jeder Stationsgruppe nennen, und den Sensorhöhen, die sie angeben.',
        citation: 'Wetterdienst documentation, the pages „Road: 15_minutes“ (dwd/road) and „SWSMOS: hourly“ (dwd/swsmos).',
        href: `${WETTERDIENST_DOCS}provider/dwd/road/15_minutes.html`,
      },
    ],
  },

  'from-measurement-to-value': {
    title: 'Von der Messung zum Wert: wie Mittelwerte, Summen, Maxima und Minima entstehen',
    summary: 'Ein Wert ist selten ein einzelner Messwert. Eine Station nimmt viele Abtastwerte und bildet daraus den Wert als Mittel, als Summe, als Höchst- oder als Tiefstwert, und wie das geschieht, entscheidet, was die Zahl bedeutet.',
    parts: [
      {
        title: 'Vom Signal zum Messwert',
        paragraphs: [
          'Ein Sensor misst die Wettergröße nicht unmittelbar. Die WMO nennt Instrumentenmesswerte in physikalischen Einheiten Daten der Stufe I (Level I) und die meteorologischen Größen selbst, die man direkt erhalten oder aus Daten der Stufe I ableiten kann, Daten der Stufe II (Level II). Ihr Beispiel: Ein Sensor kann die Sichtweite nicht messen, die eine Größe der Stufe II ist; er misst den Extinktionskoeffizienten, eine Größe der Stufe I.',
          'Auf dem Weg vom Sensor zum Wert führt die WMO unter anderen Schritten auf: das Abtasten des Signals, das Anwenden der Kalibrierung, das Linearisieren (ein Signal, das nicht genau proportional zur Größe ist, wird begradigt), das Bilden von Statistiken wie dem Mittelwert, das Ableiten verwandter Größen, Korrekturen und Qualitätskontrolle. Die Reihenfolge ist nur ungefähr aufeinanderfolgend, aber die Linearisierung muss vor dem Mitteln kommen: Erst zu mitteln und dann zu linearisieren liefert ein anderes Ergebnis, wenn das Signal während des Mittelungszeitraums nicht konstant ist.',
          'Abgetastet wird das Signal eines Sensors, nicht die Atmosphäre. Die WMO sagt, dass eine atmosphärische Größe nie abgetastet wird, nur das Ausgangssignal eines Sensors dafür, und dass Sensoren langsamer reagieren, als sich die Atmosphäre ändert, und Rauschen hinzufügen. Ein Abtastwert (sample) ist eine einzelne Messung, eine Beobachtung ist das Ergebnis des Abtastvorgangs und wird aus einer Reihe von Abtastwerten abgeleitet. Das Beispiel der WMO ist eine Temperatur, die jede Minute gemessen wird (die Abtastwerte), ein daraus berechnetes 10-Minuten-Mittel und dieses Mittel, das alle 3 Stunden in einer synoptischen Meldung übertragen wird (die Beobachtung).',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Ein Mittelwert glättet die kleinräumige Veränderlichkeit der Atmosphäre und das Rauschen des Instruments. Für den internationalen Austausch und viele operationelle Anwendungen muss, sagt die WMO, ein gemeldeter Messwert für die vorangegangenen 2 oder 10 Minuten beim Wind stehen und laut Übereinkunft für 1 bis 10 Minuten bei anderen Größen. Manche konventionellen Sensoren reagieren in etwa einer Minute, ein einzelner Messwert von ihnen ist deshalb dem Sinn nach ein Ein-Minuten-Mittel. Die Tabelle der Anforderungen der WMO kennzeichnet jede Größe als momentan, gemittelt oder summiert: Für einen „momentanen“ Wert gilt ein Mittel über 1 Minute als Minimum und am besten geeignet, und Mittel über bis zu 10 Minuten sind zulässig; ein „gemittelter“ Wert ist ein Mittel über einen festen Zeitraum, den die Anforderungen der Verschlüsselung festlegen; eine „Summe“ ist eine Summe über einen festen Zeitraum.',
          'Das arithmetische Mittel ist das, was man normalerweise unter einem Mittelwert versteht. Das exponentielle Mittel ist die Ausgabe des einfachsten Tiefpassfilters und die einfachste Antwort eines Sensors auf die Schwankungen der Atmosphäre; wenn seine Zeitkonstante etwa die Hälfte der Zeit beträgt, über die ein Mittel berechnet wird, sind die beiden praktisch nicht zu unterscheiden.',
          'Die Größe, die gemittelt wird, ist nicht immer die, die gemeldet wird. Die Tabelle der WMO nennt die kartesischen Komponenten für Windgeschwindigkeit und -richtung, die absolute Feuchte für den Taupunkt und den Extinktionskoeffizienten für die Sichtweite, weil das Mitteln einer Größe, die nicht linear ist, ein anderes Ergebnis liefert, wenn sie sich während des Zeitraums ändert.',
          'Maxima und Minima sind eigene Größen. Die WMO sagt, dass neben den Mittelwerten Extremwerte und andere Größen bestimmt werden müssen, die für bestimmte Zeiträume repräsentativ sind, je nach Zweck der Beobachtung, und sie nennt die Böe als Beispiel, für das höhere Abtastraten nötig sind: Abtastwerte, mit denen Extremwerte von Schwankungen wie Böen geschätzt werden, sollen mindestens viermal so oft genommen werden wie die für Mittelwerte. Für die Böe selbst empfiehlt die WMO, das höchste 3-Sekunden-Mittel aufzuzeichnen (siehe „Wind“), und ihre Tabelle führt die Extremwerte der Lufttemperatur als momentane Werte mit einer Zeitkonstante von 20 Sekunden und einer Mittelungszeit von 1 Minute auf.',
          'Summen können aus kleineren Summen zusammengezählt werden. Unter den Statistiken, die eine Station berechnet, führt die WMO Gesamtmengen über Zeiträume von Minuten bis Tagen auf, mit Regen als Beispiel, und integrierte Werte, mit Strahlung als Beispiel. Sie werden auf der Station oder in einer zentralen Verarbeitungsplattform berechnet, aus momentanen Daten oder Extremwerten und aus Summen über kleine Zeiträume, zum Beispiel eine Stunde.',
          'Wo der Wert gebildet wird, ist eine Entwurfsentscheidung. Die WMO stellt einen Trend fest, wo das Telekommunikationsnetz es erlaubt, Ein-Minuten-Daten zentral zu sammeln und die Statistiken in einer zentralen Verarbeitungsplattform zu berechnen. Sie sagt, dass die Algorithmen, die die Werte ableiten, so wichtig sind wie die Wahl des Instruments, dass kleine und feine Änderungen im Lauf der Zeit später erhebliche Auswirkungen haben können und dass ein Verzeichnis der Algorithmen und der Softwareversionen als Metadaten geführt werden soll.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Ein Mittel aus wenigen Messwerten kann falsch sein. Das Beispiel der WMO ist eine Temperatur, die alle drei Stunden abgelesen wird: Ändert sie sich gleichmäßig, wie sie es meist tut, ist ein aus den acht Messwerten berechnetes Tagesmittel hinreichend stabil, hat aber ein Gewitter die Temperatur 30 Minuten lang um viele Grad gesenkt, ist das berechnete Mittel falsch. Die Verlässlichkeit von Tagesmitteln, sagt die WMO, hängt davon ab, dass es auf Zeitskalen kürzer als der Abstand der Messwerte meist wenig Veränderung gibt; ein kurzes Ereignis wie das Gewitter beeinflusst das Mittel und die Streuungsmaße. Ein einzelner Messwert pro Tag zu einer festen Zeit liefert keine gute Schätzung der mittleren Monatstemperatur, sagt die WMO, und die Unsicherheit eines Mittels ist umgekehrt proportional zur Quadratwurzel der Zahl der Beobachtungen.',
          'Ein Extremwert hängt vom Instrument ab. Die WMO sagt, dass aufgezeichnete Böen durch das Ansprechverhalten des Instruments geglättet werden und dass das aufgezeichnete Maximum über ein Mehrfaches seiner Zeitkonstante gemittelt ist.',
          'Die WMO sagt, dass es bei der Verarbeitung meteorologischer Daten meist ein richtiges Verfahren, einen richtigen Algorithmus oder Ansatz gibt und dass es viele Näherungen geben kann, deren Gültigkeit von gut bis nutzlos reicht. Wie ein Anbieter seine Tages- oder Monatswerte bildet, sagt die Dokumentation des Anbieters selbst; dieser Eintrag nimmt das nicht an.',
          'Auch Korrekturen und Qualitätskontrolle formen den Wert. Die WMO sagt, dass die Algorithmen für Korrekturen, etwa für die Aufstellung, auf Studien beruhen können, die nicht ganz endgültig sind, dass in Zukunft andere Algorithmen entstehen können und dass es ratsam ist, sie zu dokumentieren, damit die ursprünglichen unkorrigierten Daten wiederhergestellt werden können. Die Qualitätskontrolle, sagt die WMO, funktioniert am besten, wenn jede Beobachtung aus einer hinreichend großen Zahl qualitätsgeprüfter Abtastwerte berechnet wird, weil Abtastwerte mit großen Ausreißerfehlern dann aussortiert werden können und die Berechnung ohne sie weitergehen kann, und die Zahl gültiger Abtastwerte in einem Zeitraum entscheidet, ob das Mittel gültig ist.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Der DWD sagt in den Dateien, die zu den Daten jeder Station gehören, wie seine Tageswerte gebildet werden, und die Regel ändert sich mit der Zeit. Ab dem 1. April 2001 ist an den drei geprüften Stationen das Tagesmittel von Temperatur, relativer Luftfeuchte, Dampfdruck, Luftdruck und Bedeckungsgrad das arithmetische Mittel aus mindestens 21 Stundenwerten aus SYNOP-Meldungen, und das Tagesmaximum und -minimum der Lufttemperatur sind der höchste und der tiefste Wert, gemessen von 00:00 bis 24:00 UTC. Davor nennen die Dateien andere Regeln. Von 1991 (in Frankfurt/Main schon ab 1935) bis März 2001 wird das Tagesmittel der Temperatur aus den drei Beobachtungsterminen der Klimastationen mit der Formel TMK=(TT1+TT2+(TT3*2))/4 berechnet, in der der dritte Wert doppelt zählt (die Termine sind 07, 14 und 21 Uhr mittlere Ortszeit, seit 1987 07:30, 14:30 und 21:30 MEZ); in Potsdam nennen die Dateien dieselbe Formel bis 1966 und in Dresden-Klotzsche von 1934 bis 1945. In Potsdam (ab 1967) und Dresden-Klotzsche (ab 1960) ist es bis 1990 das arithmetische Mittel aus vier oder acht Beobachtungswerten, die auf den synoptischen Hauptterminen um 00, 06, 12 und 18 UTC beruhen.',
          'Der DWD weist selbst darauf hin. Seine Beschreibung der Monatsdaten sagt, dass für eine statistische Auswertung die Formel beachtet werden soll, mit der die Tagesmittel berechnet wurden, die sich zeitlich und je Station ändern kann und in den Dateien Metadaten_Parameter steht, und dass erst ab 1936 vereinheitlichte Formeln angewendet wurden. Welchen Zeitabschnitt ein Tageswert abdeckt, hat sich ebenfalls geändert: siehe „Zeit“.',
          'Der DWD berechnet seine Monatsmittel aus den Tageswerten, und nur, wenn die Tageswerte vollständig sind: Fehlen welche, wird kein Monatsmittel angegeben. Für einige Stationen gibt es nur Monatswerte, ohne Tageswerte, und sie sind so aufgenommen, wie sie sind. Die Monatsdaten haben unter anderem das Monatsmittel der Tagesmaxima der Temperatur, den höchsten der Tageshöchstwerte im Monat, den niedrigsten der Tagestiefstwerte und die Monatssumme des Niederschlags. Die Regel der WMO für Klimanormalwerte ist eine andere: siehe „Klimanormalwerte“.',
          'Wetterdienst sagt für jeden Parameter, was für ein Wert er ist. Die Aggregation eines Parameters wird seinem Namen entnommen, wenn der Name eine Statistik nennt (zum Beispiel _mean, _max oder _min), und sonst dem, was der Anbieter angibt. Ein Wert ist „instant“, wenn er ein einzelner Messwert ist, wobei ein Mittel über höchstens 5 Minuten noch als Messwert zählt, und „mean“, „max“, „min“ oder „sum“ und so weiter, wenn er eine Statistik eines Intervalls ist; null heißt, dass die Quelle es nicht angibt, nicht dass der Wert ein Messwert oder ein Mittel ist. Manche DWD-Werte sagen in ihrer eigenen Beschreibung, wie sie gebildet werden: siehe „Stationen in der Stadt“ für einen Stundenwert, der das Ein-Minuten-Mittel ist, das 10 Minuten vor seinem Zeitstempel endet.',
        ],
      },
    ],
    sources: [
      wmoGuideV(
        'Aus Band V, Kapitel 2 zum Abtasten und Kapitel 3 zur Datenreduktion stammen in diesem Eintrag die Schritte vom Signal zum Wert, das Mitteln, die Größen, die gemittelt werden, die Extremwerte und die Folgen zu weniger Abtastwerte.',
        'Volume V (Quality assurance and management of observing systems), Chapter 2 (Sampling meteorological variables), sections 2.1, 2.1.1, 2.1.2, 2.4.2, 2.4.3; Chapter 3 (Data reduction), sections 3.1.1, 3.1.3, 3.4, 3.5, 3.6, 3.7.',
      ),
      wmoGuide(
        'In Band I, Kapitel 1 steht die Tabelle der Anforderungen, die sagt, welche Größen momentan, gemittelt oder summiert sind und über welche Zeit. Aus Band III, Kapitel 1 zu automatischen Wetterstationen stammen in diesem Eintrag die Statistiken, die eine Station berechnet, wo sie sie berechnet und die Prüfungen der Zahl gültiger Abtastwerte.',
        'Volume I, Chapter 1 (General), Annex 1.A, rows 1.2 and 5.3 and note 4; Volume III (Observing systems), Chapter 1 (Measurements at automatic weather stations), sections 1.4.2.5, 1.5.',
        WMO_I,
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, mit welcher Formel und aus welchen Werten ein Tageswert gebildet wird. Die Beschreibung seines Monatsdatensatzes sagt, wie ein Monatswert gebildet wird und was bei den Tagesmitteln zu beachten ist.',
        `${STATION_FILES} Metadaten_Parameter_klima_tag_* (Parameter TMK, TXK, TNK, UPM, VPM, PM und NM); Datensatzbeschreibung „Monatliche Stationsbeobachtungen (Temperatur, Niederschlag, Sonnenscheindauer, Wind und Bewölkung) für Deutschland“, Version v24.03 (2024), Abschnitte „Datenherkunft“ und „Hinweise für Anwendungen“, am 22. November 2026 gelesen.`,
        DWD_MONTHLY,
      ),
      {
        plain: 'Die Dokumentation der Bibliothek wetterdienst sagt, was ihr Feld aggregation über einen Wert angibt: ob er ein Messwert oder eine Statistik ist.',
        citation: 'Wetterdienst documentation, „Parameters“, section „Aggregation and timestamp position in the answers“.',
        href: `${WETTERDIENST_DOCS}parameters.html`,
      },
    ],
  },

  'normals': {
    title: 'Klimanormalwerte: die 30-jährige Referenzperiode',
    summary: 'Ein Normalwert ist ein Mittel über dreißig Jahre, mit dem das heutige Wetter verglichen wird, und es macht einen Unterschied, welche dreißig Jahre das sind.',
    parts: [
      {
        title: 'Was ein Normalwert ist',
        paragraphs: [
          'Ein Klimanormalwert ist der Durchschnitt von Wetterbeobachtungen über einen langen, festen Zeitraum. Er hat zwei Aufgaben: Er ist der Maßstab, mit dem aktuelle Beobachtungen verglichen werden, und er dient als Annahme, welche Bedingungen an einem Ort am wahrscheinlichsten eintreten.',
          'Die WMO definiert den klimatologischen Standardnormalwert als Durchschnitt über einen Zeitraum von 30 Jahren, der in einem auf 0 endenden Jahr endet: 1981 bis 2010, 1991 bis 2020 und so fort. Er wird alle zehn Jahre neu berechnet. Dreißig Jahre wurden vor allem deshalb zum Standard, weil bei der ersten Empfehlung nur dreißig Jahre Daten vorlagen.',
          'Der Zeitraum 1961 bis 1990 ist als Bezug für Bewertungen des langfristigen Klimawandels beibehalten worden; die Richtlinien der WMO nennen die Durchschnitte dieses Zeitraums Referenznormalwerte.',
        ],
      },
      {
        title: 'Wie er berechnet wird',
        paragraphs: [
          'Ein Monatsnormalwert ist das Mittel aller gültigen Werte dieses Monats im Zeitraum. Ein Jahres- oder Jahreszeitennormalwert wird aus den Monatsnormalwerten berechnet, nicht aus den einzelnen Jahren, und fehlt der Normalwert eines Monats, fehlt auch der der Jahreszeit oder des Jahres.',
          'Ein Monatsmittel wird nicht berechnet, wenn an 11 oder mehr Tagen des Monats oder an 5 oder mehr Tagen in Folge Beobachtungen fehlen. Ein Normalwert wird nur berechnet, wenn in mindestens 80 % der Jahre gültige Monate vorliegen: 24 von 30. Eine Monatssumme, etwa der Monatsniederschlag, braucht in der Regel vollständige Daten für den Monat.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Ein Normalwert ist ein Bezug, keine Vorhersage für ein bestimmtes Jahr und keine Grenze. Dasselbe Jahr, verglichen mit dem Normalwert 1961 bis 1990 und mit dem von 1991 bis 2020, ergibt verschiedene Antworten. Die WMO hält den festen Maßstab 1961 bis 1990 bei, damit ein „überdurchschnittliches“ Jahr nicht zu einem „unterdurchschnittlichen“ wird, nur weil sich der Bezugszeitraum geändert hat; bei manchen Elementen mit klarem, durchgehendem Trend, vor allem der Temperatur, sagt der neueste Normalwert dagegen am meisten über die zu erwartenden Bedingungen.',
          'Extremwerte und seltene Perzentile aus nur dreißig Jahren können bei manchen Elementen, etwa dem Niederschlag, deutlich weniger stabil sein als Mittelwerte. Die WMO sagt, dass eine Berechnung, die von ihren Regeln abweicht, das angeben soll.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Anbieter veröffentlichen Normalwerte für verschiedene Zeiträume. Der DWD führt Stationen für die Zeiträume 1961 bis 1990, 1971 bis 2000, 1981 bis 2010 und 1991 bis 2020 auf; 1971 bis 2000 ist weder ein Standard- noch ein Referenzzeitraum der WMO.',
          'Ein Parameter des Glossars, dessen Name auf „normal“ endet, etwa sunshine_duration_normal, ist ein Normalwert „für den Zeitraum“, den der Anbieter verwendet. Prüfe, welcher Zeitraum das ist, bevor du damit vergleichst.',
        ],
      },
    ],
    sources: [
      {
        plain: `${WMO_PLAIN} Die Richtlinien der WMO zur Berechnung von Klimanormalwerten sagen, was ein Normalwert ist, welche Zeiträume zählen und wie viele fehlende Werte erlaubt sind. Das alles stammt in diesem Eintrag daraus.`,
        citation: 'WMO (2017). WMO Guidelines on the Calculation of Climate Normals (WMO-No. 1203), 2017 edition. Chapters 2 (Background), 3 (Definitions), 4.3 and 4.4 (Calculation of normal values, Data completeness), 5.1 and 5.2.2 (Application aspects).',
        href: 'https://library.wmo.int/records/item/55797-wmo-guidelines-on-the-calculation-of-climate-normals',
      },
      dwdFiles(
        'Er veröffentlicht Listen der Stationen, für die er Normalwerte berechnet.',
        'DWD Climate Data Center, Verzeichnis help: Stationslisten nach Zeitraum, etwa Temperatur_1991-2020_Stationsliste_festerStandort.txt, gelesen am 20. November 2026.',
        'https://opendata.dwd.de/climate_environment/CDC/help/',
      ),
    ],
  },

  'water-level': {
    title: 'Wasserstand und Abfluss',
    summary: 'Ein Wasserstand ist eine Höhe über dem Nullpunkt eines einzelnen Pegels, und ein Abfluss ist die Wassermenge, die in jeder Sekunde durch einen Querschnitt fließt und meist aus dem Wasserstand berechnet wird. Keines von beiden lässt sich zwischen Pegeln vergleichen, ohne zu wissen, wie es entstanden ist.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Die WMO definiert den Wasserstand (englisch stage) als die Höhe der Wasseroberfläche eines Flusses, Sees oder anderen Gewässers relativ zu einem Bezugsniveau. An einem Pegel wird er vom Nullpunkt des Pegels abgelesen. Die WMO sagt, dass der Pegel so gesetzt werden soll, dass ein Ablesewert von null unter dem niedrigsten erwarteten Wasserstand liegt, um negative Werte zu vermeiden, dass sein Bezugsniveau jährlich durch Nivellement von örtlichen Festpunkten geprüft werden soll, dass über den gesamten Zeitraum der Aufzeichnung dasselbe Bezugsniveau des Pegels beibehalten werden soll und dass es, wenn möglich, an ein nationales oder regionales Bezugsniveau angebunden werden soll.',
          'Die deutsche WSV sagt dasselbe mit eigenen Worten. Der Wasserstand ist der lotrechte Abstand eines Punktes der Wasseroberfläche über dem Pegelnullpunkt der Pegellatte, meist in Zentimetern angegeben, und er sagt nichts über die örtliche Wassertiefe oder über die Höhe relativ zum umgebenden Gelände. Der Pegelnullpunkt dagegen ist absolut: Er wird in Metern über Normalhöhennull (NHN, im Höhensystem DHHN92) angegeben, vom Betreiber des Pegels festgelegt und liegt meist unter dem niedrigsten Wasserstand, der über eine lange Zeit gemessen wurde. Das Beispiel der WSV ist der Pegel Dresden: Ein Wasserstand von 176 cm und ein Pegelnullpunkt von 102,68 m über NHN ergeben eine Wasseroberfläche von 104,44 m über NHN.',
          'Die WMO nennt mehrere Geräte für den Wasserstand. Eine Pegellatte, ein senkrechter Maßstab mit Einteilung, wird von einem Beobachter abgelesen. Ein häufig genutzter schreibender Pegel ist ein Schwimmer in einem Pegelbrunnen, der durch Rohre mit dem Fluss verbunden ist. Ein Drucksensor berechnet den Wasserstand aus dem Druck des Wassers über einem festen Punkt abzüglich des Luftdrucks, mit einem Faktor für das Gewicht des Wassers, das sich mit Temperatur und Salzgehalt ändert. Ultraschall- und Radarsensoren über dem Wasser messen den Abstand zur Wasseroberfläche aus der Zeit, die ein Echo braucht; die Schallgeschwindigkeit hängt von der Lufttemperatur ab, was ausgeglichen wird, und die WMO sagt, dass der Radarsensor davon nicht betroffen ist. Die WMO sagt, dass an Pegeln mit kontinuierlicher Aufzeichnung stündliche Aufzeichnungen an den meisten Flüssen normalerweise genügen, dass kleine oder schnell reagierende Bäche und städtische Einzugsgebiete häufigere brauchen und dass allgemein empfohlen wird, so oft aufzuzeichnen, wie die Batterie und der Speicher des Datenloggers erlauben.',
          'Die WMO definiert den Abfluss eines Flusses als die Rate, mit der Wasser durch einen Querschnitt fließt, ein Volumen je Zeiteinheit. Er kann zu einem gegebenen Zeitpunkt mit mehreren Verfahren gemessen werden, und die Wahl hängt vom Standort ab. Das klassische ist das Geschwindigkeits-Flächen-Verfahren: Die Tiefe wird an mehreren Lotrechten quer über den Fluss mit einer Stange oder einer Peilleine gemessen, die Geschwindigkeit mit einem Strömungsmesser an einem oder mehreren Punkten jeder Lotrechten, und die Abflüsse der Abschnitte zwischen den Lotrechten werden summiert. Die WMO beschreibt auch Verdünnungsverfahren sowie das Verfahren mit fahrendem Boot und das Ultraschall-, das elektromagnetische, das akustische Doppler- und die bildbasierten Verfahren, und sie sagt, dass die Genauigkeit einer Messung von der Zeit abhängt, die sie braucht, und davon, wie stark sich Wasserstand und Abfluss währenddessen ändern.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Ein Pegel zeichnet den Wasserstand auf, und der Abfluss wird meist aus ihm berechnet. Die WMO sagt, dass der Abfluss normalerweise auf den zugehörigen Wasserstand an einer Abflussmessstelle bezogen werden soll und dass die Beziehung zwischen Wasserstand und Abfluss für die meisten Messstellen definiert wird, indem die gemessenen Abflüsse gegen die Wasserstände zur selben Zeit aufgetragen werden. Viele Messungen über einen weiten Bereich von Abflüssen ergeben eine durchgehende Abflusskurve (englisch rating curve), und der Abfluss wird berechnet, indem die Abflusskurve auf die Reihe der Wasserstände angewendet wird. Das französische Hub\'Eau sagt dasselbe über seine Stationen: Eine Station kann Beobachtungen der Höhe und des Abflusses tragen, „direkt gemessen oder aus einer Abflusskurve berechnet“ (unsere Übersetzung; die Quelle schreibt „courbe de tarage“).',
          'Eine Abflusskurve ist nicht fest. Die WMO sagt, dass die Beziehung von der Kontrolle des Gerinnes abhängt: Sie kann sich mit Auskolkung und Ablagerung, mit dem Wuchs von Wasserpflanzen und im Herbst mit Laub sowie mit Eis ändern, und dass regelmäßige Messungen nötig sind, um ihr zu folgen, wobei mindestens 10 Abflussmessungen im Jahr empfohlen werden. Die WMO fügt hinzu, dass das Erstellen von Abflusskurven Auslegung und Entscheidungen verlangt, dass sie nach weiteren Messungen, besonders bei hohen Abflüssen, geprüft und manchmal überarbeitet werden und dass frühere Abflusskurven aufbewahrt werden sollen, damit Abflüsse neu berechnet werden können. Ein Abfluss, der einmal berechnet wurde, kann noch einmal berechnet werden.',
          'Wetterdienst nennt die Statistik im Namen des Parameters. stage und discharge sind die Werte der Reihe, stage_max, stage_mean und stage_min der höchste, der mittlere und der niedrigste Wasserstand eines Zeitraums, und discharge_max, discharge_mean und discharge_min dasselbe für den Abfluss.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Ein Wasserstand sagt nichts über die Tiefe des Wassers, und zwei Wasserstände lassen sich nur gegen denselben Nullpunkt vergleichen: Jeder Pegel hat seinen eigenen. Um die Höhe des Wassers über dem Meer zu erhalten, addiert man den Pegelnullpunkt, wie im Beispiel der WSV. Wetterdienst gibt den Pegelnullpunkt in der Stationsliste von WSV, Hub\'Eau und IMGW an (gauge_zero), bei WSV und Hub\'Eau mit seinem Bezugsniveau (gauge_zero_datum); das Bezugsniveau der Pegel des IMGW steht nicht in der Liste. Die Dokumentation von Wetterdienst sagt, dass sich die Bezugsniveaus zwischen Stationen unterscheiden, sodass zwei Pegelnullpunkte nur verglichen werden sollten, wo ihre Bezugsniveaus übereinstimmen.',
          'Ein Pegelnullpunkt kann sich verschieben. Die WMO sagt, es sei wichtig, über den gesamten Zeitraum der Aufzeichnung denselben beizubehalten, und die Wasserstandsreihen des IMGW zeigen, was sonst geschieht. Die Dokumentation von Wetterdienst findet bei einigen polnischen Pegeln Sprünge im Wasserstand, die der Abfluss nicht mitmacht: In Warszawa-Nadwilanówka geht der Monatsmittelwert des Wasserstands von 118 cm im Oktober 1990 auf 311 cm im November 1990, während der Abfluss von 396 auf 379 m³/s geht. Sie erklärt die Sprünge einiger Pegel mit einem verschobenen Pegelnullpunkt, den das IMGW nicht datiert. Ein Trend eines Wasserstands über einen solchen Sprung hinweg ist kein Trend des Flusses.',
          'Der Abfluss ist unsicherer als der Wasserstand. Die allgemeine Empfehlung der WMO für die Genauigkeit eines Abflusses ist 5 % im 95-Prozent-Vertrauensbereich. Die WMO sagt, dass die empfohlene Genauigkeit vor allem von der Verwendung der Daten, von den verfügbaren Geräten und von den verfügbaren Finanzmitteln abhängt, sodass sie ein flexibler Bereich ist, und dass sie in vielen Ländern durch nationale Normen geregelt wird. Ein Abfluss, der aus dem Wasserstand berechnet wird, hat die Grenzen der Abflusskurve: Die WMO sagt, dass eine geschätzte Beziehung zwischen Wasserstand und Abfluss nicht extrapoliert werden soll und dass der Abfluss an vielen Orten keine eindeutige Funktion des Wasserstands ist. Rückstau, Gezeiten, der Betrieb eines Speichers unterhalb oder eine schnelle Änderung des Wasserstands können machen, dass derselbe Wasserstand zu verschiedenen Abflüssen gehört. Bei Hochwasser, wenn Messen unmöglich ist, kann der Spitzenabfluss laut WMO nachträglich mit indirekten Verfahren bestimmt werden, aus Hochwassermarken und der Geometrie des Gerinnes. Auch eine Eisdecke ändert die Beziehung, und ihre Wirkung lässt sich nur genau bestimmen, indem man den Abfluss misst.',
          'Ein Grundwasserstand wird in einer Beobachtungsbohrung abgelesen. Die WMO beschreibt manuelle Verfahren, von denen das häufigste ein beschwertes Maßband ist, das von einem festgelegten Punkt am Brunnenkopf hinuntergelassen wird, bis es unter dem Wasser ist, und von dessen Länge dann der nasse Teil abgezogen wird, sowie automatische Schreiber, von denen die WMO den schwimmergesteuerten für den am besten geeigneten analogen Schreiber hält. Die WSV veröffentlicht den Grundwasserstand in Metern über NHN und die Environment Agency in Metern über Ordnance Datum (mAOD), sodass es Höhen über einem Bezugsniveau sind und keine Tiefen unter dem Boden.',
          'Wetterdienst macht keine Bereichsprüfung für Wasserstand, Abfluss, Grundwasserstand und Fließgeschwindigkeit, weil sie ein eigenes Bezugsniveau haben und ein Fluss mit Gezeiten rückwärts fließen kann. Siehe „Datenqualität“.',
        ],
      },
      {
        title: 'Worin sich die Anbieter unterscheiden',
        paragraphs: [
          'Wetterdienst hat Wasserstand und Abfluss von vier Anbietern: WSV (wsv/pegel, Deutschland), der Environment Agency (ea/hydrology, England), Hub\'Eau (eaufrance/hubeau, Frankreich) und dem IMGW (imgw/hydrology, Polen). Ein Test liest jeden Anbieter der Bibliothek und hält fest, dass diese vier die einzigen sind, die einen stage und einen discharge haben. Wetterdienst nennt den Wasserstand bei allen vieren stage und den Abfluss discharge und rechnet sie in eine Einheit um, standardmäßig Meter und m³/s. Die anderen hydrologischen Dienste der Welt sind für diese Seite nicht gelesen.',
          'Die WSV, die Wasserstraßen- und Schifffahrtsverwaltung des Bundes, veröffentlicht in PEGELONLINE die Wasserstände und Abflüsse von Pegeln an den Bundeswasserstraßen und an der Küste. Sie sagt, dass es ungeprüfte Rohdaten sind und dass sie keine Haftung für ihre Richtigkeit übernimmt. Ihre REST-Schnittstelle liefert die letzten 31 Tage, und jede Reihe hat ein eigenes Intervall von 1, 5, 10, 15 oder 60 Minuten, nach dem Wetterdienst die Station einordnet. Die WSV sagt, dass der Wasserstand meist in Zentimetern angegeben wird; die Dokumentation von Wetterdienst ergänzt, dass er an einigen Pegeln in Metern über NN veröffentlicht wird, was Wetterdienst umrechnet. Die WSV schreibt gesetzliche Zeit, die Ortszeit des Jahres, wo Wetterdienst UTC liefert (siehe „Zeit“). Die gelesenen Seiten der WSV sagen nichts darüber, wie der Abfluss einer Reihe bestimmt wird. Die WSV veröffentlicht auch kennzeichnende Wasserstände eines Pegels, darunter das mittlere Niedrigwasser (MNW), den mittleren Wasserstand (MW), das mittlere Hochwasser (MHW), den höchsten bekannten Wasserstand (HHW) und drei Marken (I, II und III), die mit den Bundesländern als Richtwerte für die Schifffahrt festgelegt sind und bei deren Erreichen Beschränkungen wie Sperrungen gelten; Wetterdienst gibt sie in Metern als Spalten der Stationsliste an.',
          'Die Hydrology API der Environment Agency mit fast achttausend Messstationen hat den Abfluss als 15-Minuten-Werte und als Tageswerte (Mittel, Minimum und Maximum), den Flusswasserstand ebenso (Tagesminimum und Tagesmaximum) sowie den Grundwasserstand. Ihre Referenz gibt den Flusswasserstand in Metern in drei Arten an: relativ zum Ordnance-Survey-Bezugsniveau (mAOD), relativ zu einem örtlichen Pegelbezugsniveau (mASD) oder in Metern mit einem nicht angegebenen Bezugsniveau (m). Der stage von Wetterdienst ist von der letzten Art, also relativ zu einem Bezugsniveau, das nicht angegeben ist. Die Dokumentation von Wetterdienst sagt, dass ein Tageswert die 24 Stunden von 09:00 bis 09:00 abdeckt und dass die Quelle keine Zeitzone angibt; die gelesene Referenzseite nennt das nicht. Jede Messung trägt das eigene Wort der Agency für ihre Qualität (Good, Estimated, Suspect, Unchecked oder Missing) und bei einem Tageswert, ob er auf vollständigen Daten beruht. Die Referenz sagt nicht, wie der Abfluss abgeleitet wird. Unter den anderen Kennzeichen einer Messung führt sie Namen auf, die sich auf eine Abflusskurve beziehen (WithinRating, NoRating, ExtrapolateUpperPart, ExtrapolateLowerPart, BeyondUpperLimit und BeyondLowerLimit), die Wetterdienst nicht zurückgibt.',
          'Hub\'Eau ist die Open-Data-Plattform des französischen Wasserinformationsdienstes Eaufrance. Seine Hydrometrie-Daten stammen von der Plattform PHyC, die der Service Central Vigicrues betreibt: Messungen der Wasserhöhe (H) und des Abflusses (Q) in nahezu Echtzeit vom französischen Netz von etwa 5000 hydrometrischen Stationen, die die regionalen Direktionen für Umwelt, Planung und Wohnungswesen (DREAL) und andere Erzeuger betreiben, alle 5 bis 60 Minuten gespeichert, mit einem Verlauf von einem Monat. Die Höhe ist in Millimetern und der Abfluss in Litern je Sekunde angegeben, was Wetterdienst umrechnet. Eine Station kann die Höhe, den Abfluss oder beides tragen. Hub\'Eau sagt nicht, in welchem Intervall eine Station meldet; Wetterdienst misst es an den Zeitstempeln, sodass eine Station unter 5, 6, 10, 15 oder 60 Minuten eingeordnet wird und eine Station, die in einem anderen Schritt meldet, etwa 30 Minuten, nicht geliefert wird. Die Höhe ist relativ zum Nullpunkt des Pegels der Station, sodass Stationen kein gemeinsames Bezugsniveau haben. Die Nutzungsbedingungen von Hub\'Eau sagen, dass seine Datensätze Rohdaten enthalten, die ohne Weiterverarbeitung bereitgestellt werden. Jede Beobachtung trägt einen Qualifizierungscode aus sieben möglichen (siehe „Datenqualität“). Die API hat auch aufbereitete Werte: den mittleren Abfluss je Tag und Monat, für einige Stationen bis zurück ins Jahr 1900, sowie den höchsten und den niedrigsten Momentanabfluss und die höchste Momentanhöhe jedes Tages und Monats. Wetterdienst liefert sie nicht.',
          'Das IMGW, das polnische Institut für Meteorologie und Wasserwirtschaft, veröffentlicht tägliche und monatliche Dateien: den Wasserstand und den Abfluss jedes Tages sowie Mittel, Minimum und Maximum jedes Monats. Es ordnet sie nach hydrologischen Jahren, die am 1. November des Vorjahres beginnen: Das hydrologische Jahr 2016 ist die Zeit vom 1. November 2015 bis zum 31. Oktober 2016. Der Wasserstand ist in Zentimetern und der Abfluss in m³/s. Die Änderungsliste des IMGW sagt für die hydrologischen Jahre 2017 und 2019, dass die Daten hinzugefügt wurden, außer den Abflüssen, die „nach dem Abschluss ihrer Kontrolle hinzugefügt werden“ (unsere Übersetzung), und die Abflüsse folgten später. Wetterdienst gibt für WSV und für die Hydrologie des IMGW kein Qualitätskennzeichen zurück.',
        ],
      },
    ],
    sources: [
      {
        plain: 'Die Weltorganisation für Meteorologie (WMO) ist die Organisation der Vereinten Nationen, in der sich die nationalen Wetter- und Hydrologiedienste darauf einigen, wie Wetter und Wasser gemessen werden. Band I ihres Guide to Hydrological Practices beschreibt, wie Wasserstände und Abflüsse gemessen und zu hydrologischen Informationen werden; dieser Eintrag übernimmt daraus die Pegel, die Messung des Abflusses, die Abflusskurve, ihre Grenzen und die empfohlene Genauigkeit.',
        citation: 'WMO (2008). Guide to Hydrological Practices, Volume I: Hydrology – From Measurement to Hydrological Information (WMO-No. 168), 2008 edition, updated in 2025. Chapter 2 (Methods of observation), section 2.3.3 and Table I.2.5; Chapter 5 (Surface water quantity and sediment measurement), sections 5.1.1, 5.1.2, 5.1.3.1, 5.1.4, 5.3.1, 5.3.2, 5.3.4, 5.3.5.1, 5.3.7.1, 5.4.5.1, 5.4.5.2 and 5.4.5.3; Chapter 6 (Groundwater), section 6.4.1; Chapter 9 (Data processing and quality control), sections 9.6.2.1 to 9.6.2.4.',
        href: WMO_168,
      },
      {
        plain: 'Die Wasserstraßen- und Schifffahrtsverwaltung des Bundes (WSV) veröffentlicht die Wasserstände der Bundeswasserstraßen auf ihrem Portal PEGELONLINE. Ihre Hilfeseite erklärt den Wasserstand, den Pegelnullpunkt und die kennzeichnenden Wasserstände, und ihre Seiten zu den Webservices sagen, dass die Daten ungeprüfte Rohdaten sind und wie sie geliefert werden.',
        citation: 'WSV. PEGELONLINE: Hilfe (pegelonline.wsv.de/gast/hilfe); Webservices & APIs, Übersicht (pegelonline.wsv.de/webservice/ueberblick); REST-API, Dokumentation (pegelonline.wsv.de/webservice/dokuRestapi), am 22. November 2026 gelesen.',
        href: WSV_HELP,
      },
      {
        plain: 'Die Environment Agency von England veröffentlicht Flussabflüsse, Flusswasserstände und Grundwasserstände in ihrer Hydrology API. Ihre Referenz sagt, welche Reihen es gibt, in welchen Einheiten und mit welchen Qualitätswörtern.',
        citation: 'Environment Agency. Hydrology API, API Documentation (environment.data.gov.uk/hydrology/doc/reference), am 22. November 2026 gelesen.',
        href: EA_HYDROLOGY,
      },
      {
        plain: 'Hub\'Eau ist die Open-Data-Plattform des französischen Wasserinformationsdienstes. Seine Seite zur Hydrometrie-API sagt, woher die Daten kommen, in welchen Einheiten sie angegeben sind und was eine Station tragen kann, und seine Nutzungsbedingungen sagen, was die Daten sind.',
        citation: 'Hub\'Eau (Eaufrance). API "Hydrométrie" (hubeau.eaufrance.fr/page/api-hydrometrie) und Conditions générales (hubeau.eaufrance.fr/page/conditions-generales), am 22. November 2026 gelesen.',
        href: HUBEAU_HYDROMETRY,
      },
      {
        plain: 'Das polnische Institut für Meteorologie und Wasserwirtschaft (IMGW-PIB) veröffentlicht seine hydrologischen Beobachtungen auf seinem Portal für öffentliche Daten, mit einer Datei mit allgemeinen Informationen und einer Änderungsliste im Ordner der Daten.',
        citation: 'IMGW-PIB. Dane hydrologiczne, die Dateien hydrologia_info_ogolne.txt und lista_zmian_hydro.txt in danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/, am 22. November 2026 gelesen.',
        href: IMGW_HYDROLOGY,
      },
      {
        plain: 'Die Dokumentation der Bibliothek Wetterdienst beschreibt die vier Hydrologie-Netze so, wie die Bibliothek sie liefert: die Einheiten, die Pegelnullpunkte und ihre Bezugsniveaus, die Intervalle und die Sprünge in einigen Wasserstandsreihen.',
        citation: 'Wetterdienst documentation, the pages "Pegel" (wsv/pegel), "Hydrology" (ea/hydrology, imgw/hydrology) and "Hubeau" (eaufrance/hubeau).',
        href: `${WETTERDIENST_DOCS}provider/wsv/pegel/index.html`,
      },
    ],
  },
  'time': {
    title: 'Zeit: was eine Stunde und ein Tag in den Daten sind',
    summary: 'Zeitstempel sind in UTC, ein Stempel kann den Anfang oder das Ende eines Intervalls meinen, und ein Tag geht nicht immer von Mitternacht bis Mitternacht.',
    parts: [
      {
        title: 'Welche Uhr',
        paragraphs: [
          'Die Bibliothek wetterdienst gibt jeden Zeitstempel in UTC zurück, welche Uhr der Anbieter auch schreibt. Anbieter nutzen UTC, Ortszeit oder einen festen Versatz wie die MEZ des DWD, die Zeit Mitteleuropas ohne Sommerzeit (UTC+1). Ein Fehler der Uhr ist eine Stunde daneben und löst nie eine Fehlermeldung aus; die Bibliothek folgt deshalb dem, was die Dokumentation jedes Anbieters über seine Uhr sagt.',
          'Der DWD gibt die Uhr jedes Zeitabschnitts jeder Station in seinen Dateien an. Seine 10-Minuten-Daten sind seit dem Jahr 2000 in UTC, davor in MEZ; seine stündliche Lufttemperatur und sein stündlicher Niederschlag der letzten Jahre sind in UTC.',
        ],
      },
      {
        title: 'Anfang oder Ende eines Intervalls',
        paragraphs: [
          'Ein Wert, der ein Intervall abdeckt, etwa eine 10-Minuten-Summe, trägt den Stempel seines Anfangs, seines Endes oder, seltener, seiner Mitte. Der DWD stempelt seinen 10-Minuten-Niederschlag beim rain[e]H3 auf das Ende des Intervalls; ein PLUVIO-Wert kommt etwa 5 Minuten verspätet. Bei den stündlichen Schätzungen von Sonnenscheindauer und Strahlung aus dem DUETT-Projekt des DWD deckt ein Stempel 11:00 UTC die Stunde von 09:50 bis 10:50 ab, der Stempel ist also weder Anfang noch Ende der Stunde, für die er steht.',
        ],
      },
      {
        title: 'Der Klimatag',
        paragraphs: [
          'Ein Tageswert folgt einem „Klimatag“, den der Anbieter gewählt hat. Environment and Climate Change Canada erklärt, warum: Ein Kalendertag kann das Maximum und das Minimum, die wirklich zu einem Tag gehören, nicht erfassen, weil es kurz vor Sonnenaufgang am kältesten und kurz nach dem höchsten Sonnenstand am wärmsten ist. Sein klimatologischer Tag beginnt und endet deshalb zur gleichen Stunde zweier Tage, zum Beispiel von den Beobachtungen um 0601 UTC eines Tages bis zur Beobachtung um 0600 UTC des nächsten. Die WMO empfiehlt, dass der tägliche Niederschlag zu festen Zeiten abgelesen wird, die für das ganze Messnetz gleich sind.',
          'In den Tagesdaten des DWD deckt ab April 2001 an den geprüften Stationen der tägliche Niederschlag 06:00 UTC bis 06:00 UTC des nächsten Tages ab, und die tägliche Höchst- und Tiefsttemperatur, das Minimum in 5 cm über dem Boden und die Sonnenscheindauer decken 00:00 bis 24:00 UTC ab. Die Schneehöhe ist der Messwert von 06 UTC, und die größte Tagesböe deckt 23:51 bis 23:50 UTC ab. „Ein Tag“ sind also nicht in jeder Spalte einer DWD-Datei dieselben 24 Stunden. Der DWD schreibt ein Fenster wie „06:00 - 06:00 FT. UTC“, wobei FT für Folgetag steht.',
          'Vor 2001 waren die Fenster andere. In Dresden-Klotzsche zum Beispiel deckte der tägliche Niederschlag von 1991 bis 2001 07:30 MEZ bis 07:30 MEZ des nächsten Tages ab; eine lange Reihe kann also zwei Fenster mischen.',
        ],
      },
    ],
    sources: [
      dwdFiles(
        'Die Beschreibungen seiner Datensätze und die Dateien jeder Station sagen, welche Uhr ein Wert benutzt und welchen Zeitabschnitt er abdeckt.',
        `${STATION_FILES} Metadaten_Parameter_klima_tag_*; Stundenarchive stundenwerte_TU_01048_akt.zip und stundenwerte_RR_01048_akt.zip in opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/recent/ und .../hourly/precipitation/recent/ (Metadaten_Parameter_tu_stunde_*, Metadaten_Parameter_rr_stunde_*); Datensatzbeschreibungen „10-minütige Stationsmessungen des Niederschlages für Deutschland“ (Version v24.03, 2024) und „Pseudo-Stationsdaten der stündlichen Echtzeitdaten der Globalstrahlung und der Sonnenscheindauer basierend auf Bodenmessungen und Satellitendaten - DUETT Projekt“ (Version 006, 2024, „Hinweise zur Anwendung“).`,
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/precipitation/BESCHREIBUNG_obsgermany-climate-10min-precipitation_de.pdf',
      ),
      {
        plain: 'Environment and Climate Change Canada (ECCC) ist der nationale Wetterdienst Kanadas. Sein Klimaglossar erklärt den klimatologischen Tag, dem seine Tageswerte folgen.',
        citation: 'Environment and Climate Change Canada. Climate glossary, „Climatological Day“. climate.weather.gc.ca/glossary_e.html',
        href: 'https://climate.weather.gc.ca/glossary_e.html',
      },
      {
        plain: 'Die Dokumentation der Bibliothek wetterdienst führt für jeden Anbieter auf, welche Uhr er benutzt, welchen Teil eines Intervalls sein Stempel markiert und wo der Anbieter das sagt.',
        citation: 'Wetterdienst documentation, „Time zones and reference times“.',
        href: 'https://wetterdienst.readthedocs.io/en/latest/data/time_reference.html',
      },
      wmoGuide(
        'Aus Band I, Kapitel 6 zum Niederschlag stammt in diesem Eintrag die Regel, dass der tägliche Niederschlag zu festen Zeiten abgelesen wird, die für das ganze Messnetz gleich sind.',
        'Volume I, Chapter 6 (Measurement of precipitation), section 6.1.2.',
        WMO_I,
      ),
    ],
  },

  'observation-forecast-derived': {
    title: 'Beobachtung, Vorhersage und abgeleitete Daten',
    summary: 'Eine Messung wurde an einer Station abgelesen, eine Vorhersage wird für einen Ort und eine kommende Zeit berechnet, und ein abgeleiteter Wert wird aus Messungen berechnet.',
    parts: [
      {
        title: 'Beobachtung',
        paragraphs: [
          'Eine Beobachtung ist das, was ein Instrument an einer Station angezeigt hat. Auch dann hat die Zahl Schritte durchlaufen: Die WMO nennt unter anderem das Abtasten, das Anwenden der Kalibrierung, das Mitteln und das Berechnen verwandter Größen. Ein Sensor kann zum Beispiel die Sichtweite nicht messen, sondern nur, wie viel Licht die Luft auslöscht, und daraus wird die Sichtweite berechnet; auch der Taupunkt und der Druck auf Meereshöhe werden berechnet.',
        ],
      },
      {
        title: 'Vorhersage',
        paragraphs: [
          'MOSMIX des DWD ist eine Vorhersage für Orte. Es nimmt die Vorhersagen zweier Wettermodelle, ICON des DWD und IFS des Europäischen Zentrums für mittelfristige Wettervorhersage, und korrigiert sie statistisch mit dem, was Wetterstationen gemessen haben, weil jedes Modell den Boden vereinfacht und systematische Fehler hat. Es liefert Vorhersagen für etwa 5400 Orte für die nächsten zehn Tage in Schritten von einer Stunde.',
          'An etwa 2800 dieser Orte hat MOSMIX eigene Statistiken, aufgebaut aus der Geschichte der Station. Die übrigen rund 2600 werden aus benachbarten Orten berechnet; ein MOSMIX-Wert dort ist also eine Schätzung zwischen Stationen. MOSMIX liefert auch Größen, die die Modelle nicht berechnen, wie die Sichtweite, über statistische Regeln.',
          'Eine Vorhersage wird zu einer Zeit herausgegeben und gilt für eine kommende Zeit. MOSMIX gibt es in zwei Sätzen: MOSMIX_S, 24-mal am Tag mit 40 Parametern, und MOSMIX_L, viermal am Tag mit 115 Parametern, beide bis +240 Stunden. Bei MOSMIX_S werden die ersten 24 Stunden jede Stunde mit den neuesten Beobachtungen aktualisiert, die Stunden von +25 bis +240 viermal am Tag, um 04, 10, 16 und 22 UTC. Eine Vorhersage ist keine Aufzeichnung dessen, wie das Wetter war.',
        ],
      },
      {
        title: 'Abgeleitete Daten',
        paragraphs: [
          'Ein abgeleiteter Wert wird aus Messungen oder aus einem Modell berechnet und wurde an keinem Instrument abgelesen. Ein Beispiel ist das DUETT-Projekt des DWD: Es verbindet Satellitenbilder mit den Messungen von 42 DWD-Stationen zu stündlichen Karten der Strahlung und der Sonnenscheindauer und entnimmt dann der Karte die Werte für 576 Stationen, vom nächsten Gitterpunkt mit einer Korrektur für die Abschattung durch die Berge ringsum. Die Datei gibt zu jedem Wert eine Unsicherheit an, und ihre Qualitätsstufe sagt, ob Stationen, der Satellit oder beide eingegangen sind.',
        ],
      },
      {
        title: 'Woran sich die Arten unterscheiden lassen',
        paragraphs: [
          'Die Bibliothek wetterdienst unterscheidet die Arten am Netzwerk eines Anbieters: Ein Netzwerk ist zum Beispiel eine Beobachtung, eine Vorhersage, abgeleitete Daten, Radar, Warnungen oder Gewitterzellen (die Seite Anbieter nennt die Art jedes Netzwerks). Das Glossar und die Parameter sind für alle gleich, eine Temperatur einer Vorhersage und eine Temperatur einer Beobachtung können also denselben Namen tragen und sind nicht dieselbe Art von Zahl.',
        ],
      },
    ],
    sources: [
      dwdFiles(
        'Er beschreibt sein Vorhersageprodukt MOSMIX und seine abgeleiteten Datensätze auf seiner Website und bei jedem Datensatz.',
        'DWD. Model Output Statistics-MIX (MOSMIX), dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html. DWD Climate Data Center: Datensatzbeschreibung „Pseudo-Stationsdaten der stündlichen Echtzeitdaten der Globalstrahlung und der Sonnenscheindauer basierend auf Bodenmessungen und Satellitendaten - DUETT Projekt“, Version 006 (2024).',
        'https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html',
      ),
      wmoGuideV(
        'Band V, Kapitel 3 zur Datenreduktion beschreibt, wie aus dem Signal eines Instruments eine meteorologische Größe wird.',
        'Volume V (Quality assurance and management of observing systems), Chapter 3 (Data reduction), sections 3.1.1, 3.1.3, 3.5, 3.6.',
      ),
    ],
  },
  'data-quality': {
    title: 'Datenqualität: die Kennzeichen der Quellen und die Prüfungen von Wetterdienst',
    summary: 'Manche Quellen markieren einen Wert als zweifelhaft, und Wetterdienst prüft Werte an Grenzen, die keine echte Messung überschreitet. Was mit einem zweifelhaften Wert geschieht, entscheidest du, und das Kennzeichen bleibt bei ihm.',
    parts: [
      {
        title: 'Was die Quelle über einen Wert sagt',
        paragraphs: [
          'Viele Quellen markieren einen Wert in einem eigenen Qualitätskennzeichen und veröffentlichen ihn trotzdem: einen Wert von GHCN-Daily, der eine Prüfung nicht bestanden hat, einen Wert von Frost mit dem Qualitätscode 7, eine Messung der Environment Agency, die Suspect ist, einen Wert von Hub\'Eau mit dem Code 12, „zweifelhaft“. Wetterdienst gibt dieses Kennzeichen so zurück, wie die Quelle es geschrieben hat, in der Spalte quality_flags. Das Kennzeichen der Quelle steht zuerst, weitere Arten von Kennzeichen folgen als kind:code, und der Text, den die Quelle anstelle eines fehlenden Werts geschrieben hat, steht zuletzt, als raw:-999.',
          'Die Kennzeichen zweier Quellen sind nicht vergleichbar. Die Quellen nennen das Feld mit vielen Namen, und die Bedeutung eines Codes ist von Anbieter zu Anbieter verschieden, sodass ein Code des einen nichts über einen Code des anderen sagt und keiner eine Skala von besser und schlechter ist, wenn die Dokumentation es nicht sagt. Das QN des DWD zum Beispiel sagt, wie weit die Kontrolle einer Zeile gediehen ist, von 1 (nur formale Kontrolle) bis 10 (Qualitätskontrolle abgeschlossen); eine größere Zahl ist eine gründlichere Kontrolle, und die Daten bis 1980 erreichen höchstens 5.',
          'Das Wort einer Quelle für einen zweifelhaften Wert ist nicht immer ein Urteil. Wetterdienst liest nur die Codes, die die Dokumentation des Anbieters als Urteil formuliert, dass ein Wert eine Prüfung nicht bestanden hat, fehlerhaft, verdächtig, zweifelhaft oder von schlechter Qualität ist. Was die Dokumentation als Grad der Unsicherheit formuliert, als Behandlung (geschätzt, korrigiert, interpoliert), als fehlenden Wert oder als gar keine Kontrolle (etwa Unchecked der Environment Agency), ist kein Urteil und wird nicht gelesen. Wo ein Kennzeichen gelesen wird, wendet die Prüfung source es an.',
          'Solche Kennzeichen sind häufig. Von den ersten 20.000 Zeilen der Echtzeitbeobachtungen von Hub\'Eau, die Wetterdienst am 2. November 2026 gelesen hat, hatten 2.170 den Code „zweifelhaft“ und 17.830 den Code „nicht qualifiziert“, was heißt, dass keine Kontrolle gemacht wurde. Siehe „Wasserstand und Abfluss“.',
        ],
      },
      {
        title: 'Was Wetterdienst prüft',
        paragraphs: [
          'Eine Plausibilitätsprüfung beurteilt Zahlen, die kein Sensor erzeugt haben kann und die kein Code der Quelle sind: 4021 °C für ein Tagesmaximum, einen Stationsdruck, den die Höhe der Station nicht zulässt, einen Sensor, der einen Monat lang einen Wert hielt. Es gibt neun Prüfungen, jede für die Parameter, für die sie eine Regel hat. Es sind: range, eine Messung außerhalb des physikalischen Bereichs ihres Parameters; elevation, ein Stationsdruck, den die Standardatmosphäre in der Höhe der Station nicht zulässt; stuck, ein Sensor, der länger einen Wert hielt, als er sollte; step, eine Messung, die sich von der davor um mehr unterscheidet, als das Wetter in dieser Zeit tut, oder die von beiden Nachbarn weg und wieder zurück springt; relations, zwei Messungen einer Zeile, die sich widersprechen, etwa ein Maximum unter dem Mittel, ein Taupunkt über der Lufttemperatur oder eine Böe unter dem mittleren Wind; consistency, eine Messung, der ein anderer Parameter derselben Datei widerspricht; floor, ein Modellwert wenig unter der Untergrenze seiner Größe, etwa ein kleiner negativer Niederschlag einer Vorhersage; limits, eine Grenze, die du selbst setzt; und source, das Urteil der Quelle.',
          'Die WMO beschreibt dieselben Arten von Prüfungen für eine automatische Wetterstation: einen plausiblen Wert, eine grobe Prüfung gegen die absoluten Grenzen der Veränderlichkeit der Größe; eine plausible Änderungsrate; eine geforderte Mindestveränderlichkeit, bei der ein langer Zeitraum ohne nennenswerte Änderung ein Zeichen für eine Störung ist, zum Beispiel eines Schalenstern-Anemometers, das zu klemmen beginnt; und Prüfungen einer gemessenen Größe gegen andere, zum Beispiel dass der Taupunkt die Lufttemperatur nicht übersteigen kann. Die WMO sagt, dass die Daten einer automatischen Station ohne Datenqualitätskontrolle wahrscheinlich unentdeckte Fehler enthalten.',
          'Die Grenzen sind großzügig und für jeden Anbieter dieselben. Die Grenze einer Größe stützt sich der Reihe nach auf das Extrem, das das World Weather and Climate Extremes Archive der WMO aufführt, auf eine Grenze, die sich aus der Definition der Größe ergibt (ein Anteil ist 0 bis 100 %), oder auf eine genannte Quelle, und sie wird nach außen gerundet, sodass die Prüfung einen Wert findet, der ein Fehler der Quelle ist, und nie einen Rekord. Die Lufttemperatur zum Beispiel wird auf -90 bis 60 °C begrenzt, bei Rekorden von 56,7 °C (Furnace Creek, 1913) und -89,2 °C (Vostok, 1983). Die Grenzen für eine Folge gleicher Werte stammen aus veröffentlichten Qualitätskontrollen (HadISD, ECA&D und die Studie von Durre und anderen für GHCN-Daily); eine Grenze, die keine Quelle veröffentlicht, ist eine Herleitung von Wetterdienst, und die Dokumentation sagt es.',
        ],
      },
      {
        title: 'Was mit einem zweifelhaften Wert geschieht',
        paragraphs: [
          'Jede Prüfung hat einen Modus. Im Modus hard ist der Wert null, und die Zahl, die die Quelle geschrieben hat, bleibt in quality_flags, als rejected:<check>,raw:<number>. Im Modus soft bleibt der Wert erhalten, und quality_flags sagt suspect:<check>. Es gibt keinen Modus, der eine Prüfung überspringt: Eine weiche Prüfung behält den Wert, und das Kennzeichen hält das Urteil sichtbar. Hart ist der Standard für range, elevation, consistency, floor und limits; weich ist der Standard für stuck, step, relations und source. Die Dokumentation nennt die Gründe: Gleiche Messungen sind ein Zeichen für einen festgefahrenen Sensor und kein Beweis, eine Front ist ein echter Sprung, eine Relation kann nicht sagen, welche von zwei Messungen falsch ist, und das Urteil von source ist das der Quelle und nicht das der Bibliothek.',
          'Eine Vorhersage wird weich beurteilt, bis auf zwei Prüfungen. Sie ist die Ausgabe eines Modells und keine Messung, sodass ein Wert, den eine Prüfung findet, behalten und als suspect:range markiert und nie auf null gesetzt wird. Die beiden Ausnahmen sind floor, das einen kleinen negativen Wert des Modells auf die Untergrenze seiner Größe setzt und die Zahl behält, und limits, die Grenzen, die du selbst setzt.',
          'Eine Interpolation und eine Zusammenfassung lassen einen Wert, der als suspect markiert ist, immer weg, gleich welcher Modus, weil eine Zahl, die eine Prüfung unplausibel findet, in einem gewichteten Mittel nichts zu suchen hat. Der Modus wird für jede Prüfung gesetzt, in Python, auf der Kommandozeile und in der REST-API, mit der Option plausibility.',
          'Was eine Quelle dokumentiert, ist kein Urteil und hat keinen Modus. Ein -999, ein ---, ein NaN, eine Spur Regen oder ein windstiller Wind, den die Quelle als solchen dokumentiert, wird in beiden Modi entschlüsselt, und der Text der Quelle bleibt in quality_flags als raw: allein. Ein rejected: vor raw: ist das Urteil von Wetterdienst.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Eine Prüfung sagt, dass eine Zahl möglich ist, nicht dass sie stimmt. Weil die Grenzen großzügig sind, geht ein falscher Wert innerhalb von ihnen durch, und ein Wert, der als suspect markiert ist, kann richtig sein: Eine Prüfung einer Relation markiert beide Messungen eines widersprüchlichen Paars, sodass eine gute Lufttemperatur neben einem falschen Taupunkt markiert sein kann.',
          'Manche Größen haben keine Grenze: abgeleitete Größen, Codes und Kennzeichen sowie die Pegel der Hydrologie (Wasserstand, Abfluss, Grundwasserstand, der Abstand zum Pegel und die Fließgeschwindigkeit), die ein eigenes Bezugsniveau haben, und ein Fluss mit Gezeiten kann rückwärts fließen. Eine Zahl dort bleibt, wie die Quelle sie geschrieben hat, abgesehen von den Urteilen der Quelle, die gelesen werden. Siehe „Wasserstand und Abfluss“.',
          'Eine Prüfung liest nie mehr, als der Leser gelesen hat. Was stuck findet, hängt davon ab, welche Werte gelesen wurden, und eine Prüfung, die zwei Messungen vergleicht, braucht beide in derselben Datei, sodass ein Datensatz, den ein Anbieter einen Parameter nach dem anderen sammelt, wie WSV, die Environment Agency, Hub\'Eau und die Hydrologie des IMGW, keine zweite Messung zum Vergleichen hat.',
        ],
      },
      {
        title: 'Worin sich die Anbieter unterscheiden',
        paragraphs: [
          'Nicht jeder Anbieter hat ein Kennzeichen. Bei WSV, der Hydrologie des IMGW, FMI, KNMI, IPMA, LHMT, MeteoSwiss, AEMET, Geosphere und den Synop-Daten von Météo-France ist quality_flags null, abgesehen von den Tokens der Prüfungen von Wetterdienst, und so ist es bei MOSMIX, DMO, POI, SWSMOS und Radar des DWD. Die Beobachtungsdaten des DWD tragen die Kontrollstufe QN jeder Zeile, die sagt, wie weit die Kontrolle gediehen ist, und kein Urteil ist.',
          'Die Prüfung source liest das Urteil von zehn Anbietern: NOAA GHCN (täglich und stündlich), MET Norway Frost, CHMI, DMI, die Straßenstationen des DWD, die Environment Agency, Hub\'Eau, Météo-France, das Met Office und NWS. Die Dokumentation von Wetterdienst führt für jeden die Codes auf, die zählen, mit dem Wortlaut des Anbieters.',
        ],
      },
    ],
    sources: [
      {
        plain: 'Die Dokumentation der Bibliothek Wetterdienst listet die neun Prüfungen auf, die Grenzen, die sie anwenden, mit den Quellen, auf die sich die Grenzen stützen, die Modi sowie die Kennzeichen und Urteile jedes Anbieters. Dieser Eintrag übernimmt daraus, was die Prüfungen tun und wie sie gesetzt werden.',
        citation: 'Wetterdienst documentation, the pages "Plausibility checks" (data/plausibility.md) and "Quality flags" (data/quality-flags.md), and the modules wetterdienst.model.quality_flags and wetterdienst.model.plausibility_ranges.',
        href: `${WETTERDIENST_DOCS}plausibility.html`,
      },
      wmoGuide(
        'Band III, Kapitel 1 über Messungen an automatischen Wetterstationen führt die Qualitätskontrolle auf, die eine solche Station machen soll, und was ohne sie geschieht.',
        'Volume III (Observing systems), Chapter 1 (Measurements at automatic weather stations), sections 1.4.2 and 1.5.',
        WMO_III,
      ),
      {
        plain: 'Die Grenzen für eine Folge gleicher Werte stammen aus veröffentlichten Qualitätskontrollen von Wetterdaten, die die Dokumentation von Wetterdienst nennt: die Qualitätskontrolle der globalen Datenbank von Synop-Meldungen HadISD, die Studie zur Qualitätssicherung von GHCN-Daily und die Algorithmen des European Climate Assessment & Dataset.',
        citation: 'Dunn, R. J. H., et al. (2012). HadISD: a quality-controlled global synoptic report database for selected variables at long-term stations from 1973–2011. Climate of the Past 8, 1649–1679. Durre, I., et al. (2010). Comprehensive Automated Quality Assurance of Daily Surface Observations. Journal of Applied Meteorology and Climatology 49, 1615–1633. KNMI (2021). Algorithm Theoretical Basis Document (ECA&D), version 11, section 3.',
        href: 'https://doi.org/10.5194/cp-8-1649-2012',
      },
    ],
  },
}

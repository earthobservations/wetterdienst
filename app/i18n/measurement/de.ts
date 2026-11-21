/**
 * "So wird Wetter gemessen" auf Deutsch (GH-3787).
 *
 * Der deutsche Text sagt dasselbe wie `en.ts`, Eintrag für Eintrag und Absatz für Absatz
 * (`tests/unit/measurement.test.ts` hält die beiden aneinander). Jede Aussage stützt sich auf eine der `sources`
 * des Eintrags, nach Band, Kapitel und Abschnitt, oder auf die Datei des Anbieters, die der Eintrag nennt; was keine
 * Quelle trägt, steht nicht da. Die Titel der zitierten Werke bleiben in ihrer Sprache.
 *
 * Die Ausgaben des WMO-Leitfadens sind die jeweils aktuellen der Bände: die von 2024 für Band I und II (gegen die
 * offiziellen PDFs geprüft; die Kapitel 2, 5 und 8 von Band I und Kapitel 2 von Band II sind der Text der Ausgabe 2023)
 * und die von 2023 für Band V. Die vorläufige Ausgabe 2026 wird nicht verwendet.
 */

import type { MeasurementSource, MeasurementTexts } from './types'

const WMO_I = 'https://library.wmo.int/records/item/68695-guide-to-instruments-and-methods-of-observation'
const WMO_II = 'https://library.wmo.int/records/item/68660-guide-to-instruments-and-methods-of-observation'
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

/** Band I und II: die Ausgabe 2024, die aktuelle */
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
          'Das Barometer braucht einen Ort ohne Zugluft und eine feste, erschütterungsfreie Halterung. Der Wind ist die Hauptquelle von Störungen: In Innenräumen baut ein starker, böiger Wind rund um das Gebäude Druck auf und ab, was der Anzeige 2 oder 3 hPa hinzufügen kann, und eine Klimaanlage kann einen Druckunterschied zwischen einem Raum und draußen erzeugen. Ein statischer Kopf, ein Einlass, der das Barometer mit der Außenluft verbindet, vermeidet das zum größten Teil.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Ein Barometer wird normalerweise so eingestellt, dass es den Druck in seiner eigenen Höhe anzeigt, den Stationsdruck. Wie andere Messwerte wird er gemittelt: Die Anforderungstabelle der WMO nennt für die Ausgabe einer Druckmessung 1 Minute, und ein gemeldeter Wert steht laut Übereinkunft für die vorangegangenen 1 bis 10 Minuten.',
          'Weil der Luftdruck das Gewicht der Luft darüber ist, lassen sich die Messwerte von Stationen in verschiedenen Höhen nicht einfach vergleichen. Die WMO sagt, dass sie auf dieselbe Höhe umgerechnet werden müssen, und empfiehlt Meereshöhe für jede Station, bei der das mit angemessener Genauigkeit möglich ist. Die Umrechnung wird aus dem Stationsdruck, der Höhe der Station, der Temperatur an der Station und dem Wasserdampfdruck dort berechnet, für eine gedachte Luftsäule zwischen der Station und dem Meeresspiegel, in der die Temperatur mit der Höhe um 0,0065 K je Meter abnehmen soll. Die WMO gibt diese Formel für Stationen unter 750 m an und eine einfachere für Stationen unter 50 m, die dem Stationsdruck eine Konstante hinzufügt.',
          'Die Drucktendenz ist, wie sich der Druck in den letzten drei Stunden geändert hat: der Unterschied zwischen dem Wert am Ende und dem am Anfang. Die WMO weist darauf hin, dass die Fehler zweier Messwerte desselben Barometers teilweise systematisch sind und innerhalb von drei Stunden wahrscheinlich dasselbe Vorzeichen haben, sich in der Differenz also weitgehend aufheben.',
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
          'Auch das Instrument steht in den Stationsdateien. In Potsdam, das 80,86 m über dem Meeresspiegel liegt, führt der DWD seit dem 20. November 2015 ein Digitalbarometer vom Typ PTB 330 auf, von 1992 bis 2015 ein Digitalbarometer vom Typ AIR-DB und davor ein konventionelles Stationsbarometer.',
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
          'Jedes Instrument, das die Luftfeuchte misst, ist ein Hygrometer. Die meisten Wetterstationen benutzen heute ein elektronisches: Ein dünner Polymerfilm zwischen zwei Elektroden nimmt Wasserdampf aus der Luft auf, wodurch sich seine elektrischen Eigenschaften ändern, und die Änderung wird als relative Feuchte abgelesen. Ein Psychrometer hat zwei Thermometer nebeneinander, eines davon mit einer nassen Hülle; das Wasser, das verdunstet, kühlt es ab, und je trockener die Luft ist, desto größer ist der Unterschied zwischen beiden. Psychrometer sind noch im Einsatz, werden aber mehr und mehr von elektronischen Sensoren ersetzt. Unter dem Gefrierpunkt ist die nasse Hülle mit einer dünnen Eisschicht überzogen, und die Berechnung unterscheidet sich für eine Kugel mit Eis und eine mit unterkühltem Wasser. Ein Taupunktspiegel-Hygrometer kühlt einen kleinen Spiegel ab, bis sich Tau oder Reif darauf bildet, und misst die Temperatur des Spiegels, das ist der Taupunkt; es wird meist als Referenz benutzt.',
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
          'Elektronische Sensoren altern. Schmutz, Meersalzgischt oder Chemikalien auf dem Sensor lassen ihn bei niedriger Feuchte zu hoch und bei hoher Feuchte zu niedrig anzeigen. In feuchter Luft, bei Tau oder Nebel, driftet ein Sensor, meist nach oben, sodass er 100 % bei 95 % anzeigen kann. Ein Sensor, der über die Lufttemperatur erwärmt wird, zum Beispiel in einem von der Sonne aufgeheizten Strahlungsschutz, zeigt fälschlich zu wenig an. Für elektronische Sensoren in Wetterstationen in feuchtem Klima nennt die WMO eine Lebensdauer, die üblicherweise zwischen sechs Monaten und zwei oder mehr Jahren liegt.',
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
          'Wie genau die Zahl ist, hängt vom Instrument ab. Die WMO ordnet Pyranometer in hohe, gute und mäßige Qualität ein und nennt, was sie bei richtiger Pflege und einem Vertrauensniveau von 95 % erreichen können: Stundensummen innerhalb von 3 %, 8 % oder 20 % und Tagessummen innerhalb von 2 %, 5 % oder 10 %. Pyranometer mäßiger Qualität sind für Stunden- oder Tagessummen nicht geeignet, für Monats- und Jahressummen aber vielleicht. Für eine Tagessumme aus einem einzelnen Pyranometer ohne weitere Messungen nennt die WMO eine Unsicherheit von weniger als 5 % das Ergebnis guter, sorgfältiger Arbeit.',
          'Mehrere Dinge fügen Fehler hinzu: ein Pyranometer, das nicht waagerecht steht, Schmutz oder Tau auf der Kuppel und ein Ansprechen, das vom Sonnenstand und von der Temperatur des Instruments abhängt. Die diffuse Strahlung ist am schwersten zu messen. Ein wolkenloser Himmel kann weniger als ein Zehntel der Globalstrahlung liefern, und das Signal, das der Sensor auch dann zeigt, wenn kein Licht ankommt, das Nullsignal, entspricht bei klarem Himmel 5 bis 10 W/m² und könnte 15 % der diffusen Strahlung erreichen.',
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
    summary: 'Die Sichtweite ist, wie weit man sehen kann. Ein Instrument kann nicht schauen: Es misst, wie viel Licht die Luft schluckt, und die Entfernung wird daraus berechnet.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Die WMO definiert die Sichtweite am Tag als die größte Entfernung, in der ein schwarzes Objekt passender Größe am Boden vor dem Himmel am Horizont gesehen und erkannt werden kann. Was ein Mensch sieht, hängt vom Menschen ab; deshalb benutzt die WMO ein Maß, das auch Instrumente finden können, die meteorologische optische Reichweite (MOR): die Länge des Wegs in der Luft, die das Licht eines schmalen Strahls von einer Lampe auf 5 % seines ursprünglichen Werts abschwächt. Sie wird in Metern oder Kilometern angegeben.',
          'Mit dem Auge schätzt ein Beobachter die Entfernung zu bekannten Objekten: am Tag dunkle Objekte vor dem Himmel, etwa Baumgruppen, Türme oder Masten, in der Nacht Lichter bekannter Stärke. Jede Station erstellt einen Plan dieser Objekte mit ihren Entfernungen und Richtungen, und der Beobachter schaut aus etwa 1,5 m Höhe über dem Boden, nicht aus einem hohen Gebäude. In der Nacht brauchen die Augen 5 bis 15 Minuten, um sich an die Dunkelheit zu gewöhnen.',
          'Instrumente messen, wie stark die Luft Licht abschwächt, den Extinktionskoeffizienten. Ein Transmissometer schickt einen Lichtstrahl über eine bekannte Strecke, von wenigen Metern bis zu 150 m, und misst, wie viel davon ankommt. Ein Vorwärtsstreulicht-Messgerät strahlt Licht in ein kleines Luftvolumen und misst, wie viel davon zu einem Empfänger hin gestreut wird; es braucht wenig Platz und wird in immer mehr automatischen Stationen benutzt. Die WMO sagt, dass das gemessene Luftvolumen normalerweise in der Höhe der Augen eines Beobachters liegen soll, etwa 1,5 m über dem Boden, und dass die Sonne nie im Blickfeld des Empfängers stehen darf.',
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
          'Die stündliche Sichtweite des DWD ist in Metern, mit einem Kennzeichen, das sagt, ob ein Wert von einem Menschen beobachtet (P) oder von einem Instrument gemessen (I) wurde. In den aktuellen Dateien der drei geprüften Stationen ist jeder Wert mit I gekennzeichnet. Die Werte stammen aus SYNOP-Wettermeldungen, den international verschlüsselten Beobachtungen, und sind mit UTC gestempelt.',
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
        `DWD Climate Data Center, Dateien in den Stationsarchiven stundenwerte_VV_03987_akt.zip, stundenwerte_VV_01048_akt.zip und stundenwerte_VV_01420_akt.zip in ${DWD_HOURLY}visibility/recent/, am 21. November 2026 gelesen für Potsdam (03987), Dresden-Klotzsche (01048) und Frankfurt/Main (01420): Metadaten_Geraete_Sichtweite_*, Metadaten_Parameter_vv_stunde_* und die Spalte V_VV_I der Datendatei; Datensatzbeschreibung „Stündliche Stationsmessungen der Sichtweite für Deutschland“ (Version v24.03, 2024).`,
        DWD_HOURLY_VISIBILITY,
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
}

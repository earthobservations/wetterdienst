/**
 * "So wird Wetter gemessen" auf Deutsch (GH-3787).
 *
 * Der deutsche Text sagt dasselbe wie `en.ts`, Eintrag für Eintrag und Absatz für Absatz
 * (`tests/unit/measurement.test.ts` hält die beiden aneinander). Jede Aussage stützt sich auf eine der `sources`
 * des Eintrags, nach Band und Kapitel, oder auf die Datei des Anbieters, die der Eintrag nennt; was keine Quelle
 * trägt, steht nicht da. Die Titel der zitierten Werke bleiben in ihrer Sprache.
 *
 * Die Ausgabe des WMO-Leitfadens ist die von 2024. Wo WMO ein Kapitel zwischen der Ausgabe 2023 und der von 2024
 * nicht geändert hat, sagt WMO das; der Niederschlag (Band I, Kapitel 6) wurde geändert und steht hier nur so, wie
 * ihn das Schulungsmaterial der WMO aus dem Kapitel von 2024 zitiert.
 */

import type { MeasurementSource, MeasurementTexts } from './types'

const WMO_I = 'https://library.wmo.int/records/item/68695-guide-to-instruments-and-methods-of-observation'
const WMO_II = 'https://library.wmo.int/records/item/68660-guide-to-instruments-and-methods-of-observation'
const WMO_V = 'https://library.wmo.int/records/item/68663-guide-to-instruments-and-methods-of-observation'
const DWD_DAILY = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/BESCHREIBUNG_obsgermany-climate-daily-kl_de.pdf'

/** Was die WMO ist, einmal, für jeden Eintrag, der ihren Leitfaden nennt */
const WMO_PLAIN = 'Die Weltorganisation für Meteorologie (WMO) ist die Organisation der Vereinten Nationen, in der sich die nationalen Wetterdienste darauf einigen, wie Wetter gemessen und verglichen wird. Der Leitfaden Guide to Instruments and Methods of Observation ist ihr Handbuch dafür.'

function wmoGuide(plain: string, citation: string, href: string): MeasurementSource {
  return { plain: `${WMO_PLAIN} ${plain}`, citation: `WMO (2024). Guide to Instruments and Methods of Observation (WMO-No. 8), 2024 edition. ${citation}`, href }
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
          'Eine Wetterstation misst die Lufttemperatur mit einem elektrischen Thermometer, meist einem Platindraht, dessen elektrischer Widerstand sich mit der Temperatur ändert. Die WMO nennt elektrische Thermometer als die empfohlenen Instrumente.',
          'Nach der Definition der WMO ist die Lufttemperatur das, was ein Thermometer anzeigt, das an einem Ort der Luft ausgesetzt ist, der vor direktem Sonnenlicht geschützt ist. Sonne, Wolken und Boden senden Strahlung aus, die durch die Luft geht, ohne sie nennenswert zu erwärmen; ein Thermometer im Freien nimmt sie aber auf. Bei gewöhnlichen Instrumenten kann die Anzeige dann unter äußerst ungünstigen Bedingungen um bis zu 25 K danebenliegen. Darum hängt das Thermometer in einer Wetterhütte, die es vor der Strahlung und vor Regen schützt und die Luft trotzdem hindurchlässt.',
          'Die Standardhöhe liegt zwischen 1,25 und 2 m über dem Boden, über natürlichem Grund, am besten Gras, auf ebenem, offenem Gelände und nicht in der Nähe von Bäumen oder Gebäuden. Die Höhe ist festgelegt, weil es in der untersten Luftschicht große senkrechte Temperaturunterschiede geben kann.',
          'Die Bodentemperatur wird in den Standardtiefen 5, 10, 20, 50 und 100 cm gemessen, auf einer ebenen Fläche aus nacktem Boden. Die Grasminimumtemperatur, die tiefste Temperatur einer Nacht, wird 5 cm über kurzem Gras gemessen.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Die Lufttemperatur ändert sich innerhalb von Sekunden um ein oder zwei Grad, ein einzelner Messwert sagt daher wenig. Das Thermometer soll träge genug sein, um das auszugleichen (die WMO empfiehlt eine Zeitkonstante von etwa 20 Sekunden), und der gemeldete Wert ist ein Mittelwert: Nach Konvention steht ein gemeldeter Messwert für die vorangegangenen 1 bis 10 Minuten.',
          'Der höchste und der niedrigste Wert eines Zeitraums stammen aus der Aufzeichnung selbst: Wird ein elektrisches Thermometer fortlaufend und oft genug aufgezeichnet, lassen sich die Extreme aus den Messdaten bestimmen, und es braucht kein eigenes Maximum- oder Minimumthermometer.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'An einem Tag mit starker Sonne und schwachem Wind kann die Luft in der Hütte wärmer sein als die wahre Lufttemperatur, in einer klaren, windstillen Nacht etwas kühler; die WMO nennt in Extremfällen Fehler von bis zu etwa 2,5 K und -0,5 K. Zu wenig Luftdurchzug durch die Hütte (Wind unter 1 m/s), vor allem bei starker Sonne, und eine nasse Hütte oder ein nasser Fühler nach Regen, die durch Verdunstung gekühlt werden, sind weitere Fehlerquellen.',
          'Eine Station ist nicht die ganze Gegend. Der Messwert soll für die freie Luft um die Station stehen, in Städten sind die örtlichen Unterschiede aber größer, und Messungen auf einem Dach sind von zweifelhaftem Nutzen. Ändert sich die Hütte, der Bewuchs oder die Bebauung um eine Station, ändert sich, was sie misst; das zählt, wenn Jahre verglichen werden.',
          'Eine Bodentemperatur beschreibt eine Fläche nackten Bodens von etwa 2 m mal 2 m. Sie hängt vom Boden, seiner Bedeckung und der Neigung ab; deshalb verlangt die WMO, diese festzuhalten.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Eine einzige Hütte für die ganze Welt gibt es nicht. Die WMO hält fest, dass es schwierig ist, eine Bauart für weltweite Messungen zu empfehlen, weil Anwendungen, Automatisierungsgrad und Klima sich unterscheiden, und es sind sehr verschiedene Hütten im Einsatz.',
          'Der DWD führt in den Dateien, die zu den Daten gehören, für jede Station das Instrument und seine Höhe über dem Boden auf. In Potsdam zum Beispiel wird die Lufttemperatur seit 1978 mit einem Pt100-Thermometer in 2 m Höhe gemessen und die Minimumtemperatur in 5 cm über dem Boden seit 1986 mit einem Pt100.',
          'Welcher Zeitabschnitt zu einem Tagesmaximum oder -minimum gehört, bestimmt der Anbieter. In den Tagesdaten des DWD sind es ab April 2001 an den geprüften Stationen 00:00 bis 24:00 UTC, und das Tagesmittel ist das arithmetische Mittel aus mindestens 21 Stundenwerten. Welchen Tag andere Anbieter verwenden, steht unter „Zeit“.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 2 zur Temperatur stammen in diesem Eintrag die Definition, die Höhe, die Hütte und die typischen Fehler. Aus Band V, Kapitel 3 stammt die Regel, dass ein gemeldeter Wert für die vorangegangenen 1 bis 10 Minuten steht.',
        'Volume I, Chapter 2 (Measurement of temperature), sections 2.1.1, 2.1.3.3, 2.1.4, 2.1.4.1, 2.1.4.2, 2.1.4.3, 2.2.3, 2.5, 2.5.1; Volume V, Chapter 3 (Data reduction), section 3.5.',
        WMO_I,
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welches Instrument in welcher Höhe benutzt wurde und was ein Tageswert abdeckt.',
        'DWD Climate Data Center. Stationsdateien Metadaten_Geraete_* und Metadaten_Parameter_klima_tag_* der Stationen Potsdam (03987), Dresden-Klotzsche (01048) und Frankfurt/Main (01420), gelesen am 20. November 2026; Datensatzbeschreibung „Tägliche Stationsbeobachtungen (Temperatur, Druck, Niederschlag, Sonnenscheindauer, etc.) für Deutschland“, Version v24.3 (2024).',
        DWD_DAILY,
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
          'Der Wind am Boden wird mit einem Schalen- oder Propelleranemometer für die Geschwindigkeit und einer Windfahne für die Richtung gemessen. Die Standardhöhe ist 10 m über offenem, ebenem Gelände, weil die Windgeschwindigkeit mit der Höhe stark zunimmt. Offen heißt, dass das nächste Hindernis mindestens zehnmal so weit entfernt ist, wie es hoch ist. Die Richtung ist die, aus der der Wind weht, in Grad im Uhrzeigersinn von geografisch Nord.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Geschwindigkeit und Richtung einer Wettermeldung sind ein Mittelwert über 10 Minuten. Für Klimastatistiken werden meist Mittelwerte über jede ganze Stunde, den Tag und die Nacht verwendet.',
          'Eine Spitzenböe ist die höchste in einem genannten Zeitraum beobachtete Windgeschwindigkeit; in einer stündlichen Meldung ist es die höchste der letzten vollen Stunde. Die WMO empfiehlt, eine Böe über etwa 3 Sekunden zu messen, was für die meisten Nutzer passt, und sagt, dass ein „Mittel“ über 1 Minute eine lange Böe ist und kein Mittelwind.',
          'Wie scharf eine Böe ausfällt, hängt davon ab, wie schnell das Instrument reagiert: Ein träges verschmiert die Extreme, ein schnelles zeichnet hohe, schmale Spitzen auf. Böen verschiedener Stationen sind nur vergleichbar, wenn die ganze Messkette ähnlich ausgelegt ist.',
          'Die Beaufortskala von 0 bis 12 macht aus einer Windgeschwindigkeit in 10 m Höhe eine Beschreibung. Stärke 7, ein steifer Wind, sind zum Beispiel 13,9 bis 17,1 m/s.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Die WMO nennt den Standort des Anemometers den schwierigsten Punkt der Windmessung und hält es für fast unmöglich, einen Ort zu finden, an dem der Wind für ein großes Gebiet steht. Ein Mast im Windschatten von Bäumen oder Gebäuden sagt wenig über den ungestörten Wind. Näher als das 20-Fache der Höhe eines Hindernisses kann der Wert vor einer Korrektur um bis zu 25 % danebenliegen.',
          'Schalen- und Propellersensoren beschleunigen schneller, als sie abbremsen; ihr Mittel liegt daher bei böigem Wind etwas zu hoch. Die WMO nennt bis zu 10 % bei manchen Bauarten unter sehr turbulenten Bedingungen über rauem Gelände.',
          'Weil der Wind weiter oben stärker ist, misst ein Sensor in einer anderen Höhe als 10 m eine andere Geschwindigkeit.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Die Stationsdateien des DWD nennen Typ und Höhe jedes Windsensors, und die Höhe ist nicht immer 10 m: In Potsdam sitzt das Ultraschallanemometer 37,7 m über dem Boden.',
          'Der 10-Minuten-Wind des DWD ist ein 10-Minuten-Mittel. Seine Stationsdateien beschreiben die täglichen Windwerte als Stundenmittel mit der größten Böe von 23:51 bis 23:50 UTC; das gilt an den geprüften Stationen seit September 2003.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 5 zum Bodenwind stammen in diesem Eintrag die Definitionen von Mittelwind und Böe, die Standardhöhe und die typischen Fehler.',
        'Volume I, Chapter 5 (Measurement of surface wind), sections 5.1.1, 5.1.2, 5.1.3, 5.1.4, 5.4, 5.8.2, 5.9.1, 5.9.2 and Table 5.1.',
        WMO_I,
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welches Instrument in welcher Höhe benutzt wurde und was ein Tageswert abdeckt.',
        'DWD Climate Data Center. Stationsdateien Metadaten_Geraete_Windgeschwindigkeit_* und Metadaten_Parameter_klima_tag_* der Stationen Potsdam (03987), Dresden-Klotzsche (01048) und Frankfurt/Main (01420), gelesen am 20. November 2026; Datensatzbeschreibung „10-minütige Stationsmessungen des Windes für Deutschland“ (Version v24.03, 2024).',
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/BESCHREIBUNG_obsgermany_climate_10min_wind_de.pdf',
      ),
    ],
  },

  'precipitation': {
    title: 'Niederschlag',
    summary: 'Regen und Schnee werden in einem Messgerät aufgefangen und als Höhe gemessen. Ein Messgerät fängt etwas weniger auf, als fällt, am meisten bei Schnee und bei Wind.',
    parts: [
      {
        title: 'Wie gemessen wird',
        paragraphs: [
          'Niederschlag ist das flüssige oder feste Wasser, das aus Wolken als Regen, Nieselregen, Schnee, Schneegriesel, Graupel, Hagel oder Eiskörner fällt oder als Diamantstaub aus klarer Luft. Er wird als senkrechte Höhe des Wassers gemessen, das eine ebene Bodenfläche bedecken würde, wobei Schnee als das Wasser zählt, zu dem er schmilzt. Ein Millimeter ist ein Liter auf jedem Quadratmeter.',
          'Ein Niederschlagsmesser fängt, was fällt, mit einer Öffnung bekannter Größe auf und leitet es in ein Gefäß. Wenn Schnee in nennenswerten Mengen zu erwarten ist, verlangt die WMO eine Öffnung von mindestens 200 cm²; Öffnungen von 200 bis 500 cm² sind am üblichsten.',
          'Die WMO verlangt, dass Messgeräte abgeschirmt stehen, natürlich, auf einer Waldlichtung, oder künstlich, mit einem Windschutz, damit der Einfluss des Windes auf die Messung von Schnee klein bleibt. Abgeschirmte Geräte fangen mehr auf als nicht abgeschirmte, besonders bei Schnee.',
        ],
      },
      {
        title: 'Wie aus einer Messung ein Wert wird',
        paragraphs: [
          'Die Menge eines Zeitraums ist die Gesamtmenge, die in diesem Zeitraum den Boden erreicht hat, in Millimetern. Eine Menge unter 0,1 mm heißt Spur. Die Intensität ist die Menge je Zeiteinheit, meist in Millimetern pro Stunde.',
          'Tagesmengen werden zu festen Zeiten abgelesen, die für das ganze Messnetz gleich sind; deshalb ist ein „Regentag“ nicht immer ein Kalendertag (siehe „Zeit“). Von Hand wird eine Tagesmenge auf 0,2 mm genau abgelesen, wenn möglich auf 0,1 mm.',
        ],
      },
      {
        title: 'Was die Zahl sagen kann und was nicht',
        paragraphs: [
          'Ein Messgerät fängt nicht alles auf, was fällt. Ein Gerät ohne Windschutz fängt weniger auf als ein abgeschirmtes, und der Unterschied ist bei Schnee am größten, der weniger dicht ist als Regen. Auch Wasser, das an den Wänden des Auffangtrichters haftet, und Wasser, das aus dem Gefäß verdunstet, geht verloren; deshalb verlangt die WMO Trichter und Gefäße, die so gebaut sind, dass diese Fehler klein bleiben.',
          'Ein Messgerät misst eine einzelne Stelle. Auch eine gute Messung steht nur für ein begrenztes Gebiet.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Bauart, Höhe und Windschutz des Messgeräts unterscheiden sich zwischen Messnetzen und im Lauf der Zeit auch innerhalb eines Netzes. Der DWD führt in den Dateien, die zu den Daten gehören, jedes Gerät einer Station und seine Höhe auf. In Potsdam stand zum Beispiel ab 2009 ein PLUVIO-Gerät 1 m über dem Boden, und seit 2017 steht in derselben Höhe ein rain[e]H3, das das Wasser wiegt.',
          'Der 10-Minuten-Wert des DWD ist die Summe der vorangegangenen 10 Minuten; beim PLUVIO-Gerät ist seit November 2008 ein Wert mit dem Zeitstempel 11:50 UTC das Intervall, das um 11:45 UTC endete. Der Stundenwert ist eine Stundensumme, und der Tageswert deckt 06:00 bis 06:00 UTC des nächsten Tages ab (siehe „Zeit“).',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 6 zum Niederschlag stammen in diesem Eintrag die Definition, das Messgerät, der Windschutz und die Fehler. Das Kapitel wurde für die Ausgabe 2024 überarbeitet. Dieser Eintrag sagt nur das, was das Schulungsmaterial der WMO zur Kalibrierung von Niederschlagsmessern, verfasst von Fachleuten des DWD und des türkischen staatlichen Wetterdienstes, aus dem Kapitel von 2024 zitiert.',
        'Volume I, Chapter 6 (Measurement of precipitation); as quoted in WMO, INFCOM/SC-MINT/ET-QTC: Calibration of Precipitation Instruments, Part 1: Introduction (training material, H. Doerschel and Z. T. Dag).',
        WMO_I,
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welches Gerät in welcher Höhe benutzt wurde und was ein Wert abdeckt.',
        'DWD Climate Data Center. Datensatzbeschreibung „10-minütige Stationsmessungen des Niederschlages für Deutschland“ (Version v24.03, 2024); Stationsdateien Metadaten_Geraete_Niederschlagshoehe_* und Metadaten_Parameter_klima_tag_* der Stationen Potsdam (03987), Dresden-Klotzsche (01048) und Frankfurt/Main (01420), gelesen am 20. November 2026.',
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/precipitation/BESCHREIBUNG_obsgermany-climate-10min-precipitation_de.pdf',
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
          'Heute messen Sensoren, nicht Papier: ein Pyrheliometer, das den direkten Strahl misst, Pyranometer, die globale und diffuse Strahlung messen und daraus den direkten Strahl berechnen, oder Geräte mit mehreren Sensoren. Die Brennmethode empfiehlt die WMO nicht mehr, weil sie die Dauer des hellen Sonnenscheins nicht gleichmäßig genug erfasst.',
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
          'Die WMO verlangt eine Unsicherheit von 0,1 h und eine Auflösung von 0,1 h. Eine aus einem Pyranometer berechnete Tagessumme ist unsicherer: Die WMO nennt etwa 0,6 h für eins der beiden Verfahren und etwa 0,7 h für das andere und hält fest, dass die erweiterte Unsicherheit einer Tagessumme über 1 h liegen kann.',
          'Instrumente und Verfahren liefern verschiedene Werte. Schon die ersten Sonnenscheinautographen, gebaut ohne internationale Regeln, ergaben unterschiedliche Dauern. Dünne, hohe Bewölkung, die den Strahl auf etwa die Schwelle schwächt, ist der schwierigste Fall, denn ein kleiner Fehler der Schwelle ändert das Ergebnis dann stark.',
          'Sonnenscheindauer und Bewölkung hängen nur im Mittel zusammen: Bei hoher, dünner Bewölkung und bei Wolken, die die Sonne nicht bedecken, gilt der Zusammenhang nicht.',
          'Ein Berg oder ein Gebäude, das die Sonne bei tiefem Stand verdeckt, verkürzt die gemessene Dauer. In Gebirgstälern akzeptiert die WMO natürliche Hindernisse als Teil des örtlichen Klimas, wenn sie dokumentiert sind.',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Das Instrument ist von Station zu Station verschieden und wechselt im Lauf der Zeit. In Potsdam führt der DWD von November 2021 bis Januar 2025 einen SONIe-Sensor und seitdem ein Pyranometer vom Typ CMP22.',
          'Die tägliche Sonnenscheindauer des DWD ist an den geprüften Stationen in Stunden für 00:00 bis 24:00 UTC angegeben, der Stundenwert in Minuten.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band I, Kapitel 8 zur Sonnenscheindauer stammen in diesem Eintrag die Definition, die Instrumente und die typischen Fehler.',
        'Volume I, Chapter 8 (Measurement of sunshine duration), sections 8.1, 8.1.1, 8.1.2, 8.1.3, 8.1.3.2, 8.1.4, 8.2.2.1, 8.3.',
        WMO_I,
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welches Instrument benutzt wurde und was ein Tageswert abdeckt.',
        'DWD Climate Data Center. Stationsdateien Metadaten_Geraete_Sonnenscheindauer_* und Metadaten_Parameter_klima_tag_* der Stationen Potsdam (03987), Dresden-Klotzsche (01048) und Frankfurt/Main (01420), gelesen am 20. November 2026; Datensatzbeschreibung „Stündliche Stationsmessungen der Sonnenscheindauer für Deutschland“ (Version v24.03, 2024).',
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/sun/BESCHREIBUNG_obsgermany_climate_hourly_sun_de.pdf',
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
          'Ein Pegel ist ein Punkt. Steht er in einer Verwehung oder an einer vom Wind leergefegten Stelle, kann er um so viel danebenliegen wie die mittlere Schneehöhe oder mehr; die WMO verlangt deshalb ebene, geschützte Standorte, die ihre Umgebung vertreten. Automatische Sensoren sollen mit einer Datenunsicherheit von höchstens 2 cm angegeben sein, besser 1 cm.',
          'Wind und Schmelze machen Neuschnee unsicher: Die Beobachterin oder der Beobachter muss schätzen, was gefallen wäre, und die WMO sagt, der Fehler kann bis zu 100 % betragen. In einer Wärmeperiode kann eine Stunde früher oder später einen Unterschied von mehreren Zentimetern machen.',
          'Schnee fällt auch in einen Niederschlagsmesser, der wie jedes Messgerät bei Wind weniger Schnee auffängt, als fällt (siehe „Niederschlag“).',
        ],
      },
      {
        title: 'Wo sich die Anbieter unterscheiden',
        paragraphs: [
          'Die tägliche Schneehöhe des DWD ist an den geprüften Stationen der Messwert von 06 UTC; die Neuschneehöhe ist ein eigener Tageswert. Wo eine kanadische Station zweimal am Tag meldet, legt Environment and Climate Change Canada den „Schnee am Boden“ eines Tages auf die Morgenbeobachtung dieses Tages.',
          'Die Instrumente wechseln: In Dresden-Klotzsche führt der DWD bis Juli 2022 einen manuellen Schneepegel neben einem automatischen Schneehöhensensor, der seit 2019 im Einsatz ist.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Aus Band II, Kapitel 2 zum Schnee stammen in diesem Eintrag die Definitionen, die Instrumente und die typischen Fehler.',
        'Volume II (Measurement of cryospheric variables), Chapter 2 (Measurement of snow), sections 2.1.1, 2.2, 2.3.1.2, 2.3.1.3, 2.3.2.1, 2.3.2.2, 2.6, 2.7.',
        WMO_II,
      ),
      dwdFiles(
        'Die Dateien, die zu den Daten jeder Station gehören, sagen, welches Instrument benutzt wurde und wann ein Wert abgelesen wurde.',
        'DWD Climate Data Center. Stationsdateien Metadaten_Geraete_Schneehoehe_* und Metadaten_Parameter_klima_tag_* der Stationen Potsdam (03987), Dresden-Klotzsche (01048) und Frankfurt/Main (01420), gelesen am 20. November 2026; Datensatzbeschreibung „Tägliche Niederschlagsbeobachtungen für Deutschland“ (Version v24.3, 2024). Environment and Climate Change Canada, Climate glossary, „Climatological Day“ (climate.weather.gc.ca/glossary_e.html).',
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
          'Ein Normalwert ist ein Bezug, keine Vorhersage und keine Grenze. Dasselbe Jahr, verglichen mit dem Normalwert 1961 bis 1990 und mit dem von 1991 bis 2020, ergibt verschiedene Antworten. Die WMO hält den festen Maßstab 1961 bis 1990 bei, damit ein „überdurchschnittliches“ Jahr nicht zu einem „unterdurchschnittlichen“ wird, nur weil sich der Bezugszeitraum geändert hat; bei einem Element mit klarem Trend wie der Temperatur sagt der neueste Normalwert dagegen am meisten über die zu erwartenden Bedingungen.',
          'Extremwerte und seltene Perzentile aus nur dreißig Jahren sind weniger stabil als Mittelwerte. Die WMO sagt, dass eine Berechnung, die von ihren Regeln abweicht, das angeben soll.',
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
          'Wetterdienst gibt jeden Zeitstempel in UTC zurück, welche Uhr der Anbieter auch schreibt. Anbieter nutzen UTC, Ortszeit oder einen festen Versatz wie die MEZ des DWD, die Zeit Mitteleuropas ohne Sommerzeit (UTC+1). Ein Fehler der Uhr ist eine Stunde daneben und nie eine Fehlermeldung; die Bibliothek folgt deshalb dem, was die Dokumentation jedes Anbieters über seine Uhr sagt.',
          'Der DWD gibt die Uhr jedes Zeitabschnitts jeder Station in seinen Dateien an. Seine 10-Minuten-Daten sind seit dem Jahr 2000 in UTC, davor in MEZ; seine stündliche Lufttemperatur und sein stündlicher Niederschlag der letzten Jahre sind in UTC.',
        ],
      },
      {
        title: 'Anfang oder Ende eines Intervalls',
        paragraphs: [
          'Ein Wert, der ein Intervall abdeckt, etwa eine 10-Minuten-Summe, trägt den Stempel eines seiner Enden. Der DWD stempelt seinen 10-Minuten-Niederschlag beim rain[e]H3 auf das Ende des Intervalls; ein PLUVIO-Wert kommt etwa 5 Minuten verspätet. Die stündlichen Schätzungen von Sonnenscheindauer und Strahlung aus dem DUETT-Projekt des DWD decken die Stunde von (HH-1):50 bis HH:50 ab, ein Stempel 11:00 heißt also nicht immer 11:00 bis 12:00.',
        ],
      },
      {
        title: 'Der Klimatag',
        paragraphs: [
          'Ein Tageswert folgt einem „Klimatag“, den der Anbieter gewählt hat, damit die Extreme und Summen eines Tages nicht von Mitternacht zerschnitten werden. Environment and Climate Change Canada erklärt es so: Der klimatologische Tag beginnt mit den Beobachtungen von 0601 UTC eines Tages und endet mit der von 0600 UTC des nächsten. Die WMO verlangt, dass der tägliche Niederschlag zu festen Zeiten abgelesen wird, die für das ganze Messnetz gleich sind.',
          'In den Tagesdaten des DWD deckt ab April 2001 an den geprüften Stationen der tägliche Niederschlag 06:00 UTC bis 06:00 UTC des nächsten Tages ab, und die tägliche Höchst- und Tiefsttemperatur, das Minimum in 5 cm über dem Boden und die Sonnenscheindauer decken 00:00 bis 24:00 UTC ab. Die Schneehöhe ist der Messwert von 06 UTC, und die größte Tagesböe deckt 23:51 bis 23:50 UTC ab. „Ein Tag“ sind also nicht in jeder Spalte einer DWD-Datei dieselben 24 Stunden. Der DWD schreibt ein Fenster wie „06:00 - 06:00 FT. UTC“, wobei FT für Folgetag steht.',
          'Vor 2001 waren die Fenster andere. In Dresden-Klotzsche zum Beispiel deckte der tägliche Niederschlag von 1991 bis 2001 07:30 MEZ bis 07:30 MEZ des nächsten Tages ab; eine lange Reihe kann also zwei Fenster mischen.',
        ],
      },
    ],
    sources: [
      dwdFiles(
        'Die Beschreibungen seiner Datensätze und die Dateien jeder Station sagen, welche Uhr ein Wert benutzt und welchen Zeitabschnitt er abdeckt.',
        'DWD Climate Data Center. Datensatzbeschreibungen „10-minütige Stationsmessungen des Niederschlages für Deutschland“ (Version v24.03, 2024) und „Pseudo-Stationsdaten der stündlichen Echtzeitdaten der Globalstrahlung und der Sonnenscheindauer basierend auf Bodenmessungen und Satellitendaten - DUETT Projekt“ (Version 006, 2024); Stationsdateien Metadaten_Parameter_tu_stunde_*, Metadaten_Parameter_klima_tag_* der Stationen Dresden-Klotzsche (01048), Frankfurt/Main (01420) und Potsdam (03987), gelesen am 20. November 2026.',
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/precipitation/BESCHREIBUNG_obsgermany-climate-10min-precipitation_de.pdf',
      ),
      {
        plain: 'Environment and Climate Change Canada (ECCC) ist der nationale Wetterdienst Kanadas. Sein Klimaglossar erklärt den klimatologischen Tag, dem seine Tageswerte folgen.',
        citation: 'Environment and Climate Change Canada. Climate glossary, „Climatological Day“. climate.weather.gc.ca/glossary_e.html',
        href: 'https://climate.weather.gc.ca/glossary_e.html',
      },
      {
        plain: 'Die eigene Dokumentation von Wetterdienst führt für jeden Anbieter auf, welche Uhr er benutzt, welchen Teil eines Intervalls sein Stempel markiert und wo der Anbieter das sagt.',
        citation: 'Wetterdienst documentation, „Time zones and reference times“.',
        href: 'https://wetterdienst.readthedocs.io/en/latest/data/time_reference.html',
      },
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
          'Eine Vorhersage wird zu einer Zeit herausgegeben und gilt für eine kommende Zeit. MOSMIX erscheint jede Stunde, und für die ersten 24 Stunden wird es jede Stunde mit den neuesten Beobachtungen aktualisiert, die Stunden von +25 bis +240 dagegen viermal am Tag, um 04, 10, 16 und 22 UTC. Eine Vorhersage ist keine Aufzeichnung dessen, wie das Wetter war.',
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
          'Wetterdienst unterscheidet die Arten am Netzwerk eines Anbieters: Ein Netzwerk ist eine Beobachtung, eine Vorhersage oder abgeleitete Daten (die Seite Anbieter nennt die Art jedes Netzwerks). Das Glossar und die Parameter sind für alle gleich, eine Temperatur einer Vorhersage und eine Temperatur einer Beobachtung können also denselben Namen tragen und sind nicht dieselbe Art von Zahl.',
        ],
      },
    ],
    sources: [
      dwdFiles(
        'Er beschreibt sein Vorhersageprodukt MOSMIX und seine abgeleiteten Datensätze auf seiner Website und bei jedem Datensatz.',
        'DWD. Model Output Statistics-MIX (MOSMIX), dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html. DWD Climate Data Center: Datensatzbeschreibung „Pseudo-Stationsdaten der stündlichen Echtzeitdaten der Globalstrahlung und der Sonnenscheindauer basierend auf Bodenmessungen und Satellitendaten - DUETT Projekt“, Version 006 (2024).',
        'https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html',
      ),
      wmoGuide(
        'Band V, Kapitel 3 zur Datenreduktion beschreibt, wie aus dem Signal eines Instruments eine meteorologische Größe wird.',
        'Volume V (Quality assurance and management of observing systems), Chapter 3 (Data reduction), sections 3.1.1, 3.1.3, 3.5, 3.6.',
        WMO_V,
      ),
    ],
  },
}

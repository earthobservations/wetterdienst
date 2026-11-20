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

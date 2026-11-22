/**
 * "Wie die Antworten von Ask the weather entstehen" auf Deutsch (GH-3764, Schritte 1b und 1c).
 *
 * Der deutsche Text sagt dasselbe wie `en.ts`, Schlüssel für Schlüssel (`tests/unit/ask-methods.test.ts` hält die beiden,
 * die Definitionen der Chips und die Zahlen darin zueinander). Er ist der Text für Deutsch, Hamburgisch und Luxemburgisch.
 *
 * Jede Aussage über eine Quelle sagt, was das Dokument sagt; die Stelle darin steht in der Definition des Chips
 * (`utils/ask/chips/`). Eine Wahl, die keine veröffentlichte Quelle trifft, wird als eigene von wetterdienst benannt,
 * mit der Begründung. `{name}` ist eine Zahl oder ein Name, den der Code einsetzt.
 */

import type { MethodTexts } from './types'

const WMO = 'Die Weltorganisation für Meteorologie (WMO) ist die Organisation der Vereinten Nationen, in der sich die nationalen Wetterdienste darauf einigen, wie Wetter gemessen und verglichen wird.'
const DWD = 'Der Deutsche Wetterdienst (DWD) ist der nationale Wetterdienst Deutschlands.'

export const methods: MethodTexts = {
  chips: {
    rain: {
      title: 'Regnet es morgen?',
      summary: 'Eine Vorhersage für morgen am Vorhersagepunkt des DWD, der dem Ort am nächsten liegt: wie viel Regen, in welcher Stunde und wie wahrscheinlich.',
      data: 'Die MOSMIX-Vorhersage des DWD, der Satz MOSMIX_L (Datensatz hourly/large): die Regenmenge jeder Stunde und ihre Summen für 6, 12 und 24 Stunden sowie die Wahrscheinlichkeit von mehr als 0,1 mm in der Stunde, für den Vorhersagepunkt, der dem Ort am nächsten liegt.',
      steps: {
        point: 'Der Vorhersagepunkt, der dem Ort am nächsten liegt, wird gesucht. Eine Vorhersage wird für Orte gemacht, nicht für jede Stelle; die Antwort ist also die dieses Punktes, und sie sagt, welcher es ist und wie weit er entfernt liegt.',
        day: 'Morgen ist der Kalendertag nach heute in der Zeitzone des Ortes, von Mitternacht bis Mitternacht. Die Vorhersage hat für jede Stunde einen Wert.',
        sum: 'Die Mengen der 24 Stunden von morgen werden zum Regen des Tages addiert. Die Stunden werden aus den Stundenmengen der Vorhersage gelesen; wo sie eine ihrer längeren Summen (6, 12 oder 24 Stunden) nicht erklären, gilt die längere Summe.',
        verdict: 'Die Antwort ist „ja“, wenn der Tag {yesMm} mm oder mehr hat oder eine Stunde eine Wahrscheinlichkeit von {yesChance} % oder mehr; „vielleicht“ ab {maybeMm} mm oder einer Wahrscheinlichkeit von {maybeChance} %; sonst „eher nicht“. Reicht die Vorhersage nicht über {hours} der 24 Stunden, gibt es keine Antwort.',
      },
      formulas: {
        total: 'Regen des Tages = Menge der Stunde 1 + Menge der Stunde 2 + … + Menge der Stunde 24',
      },
      rules: {
        'forecast': {
          text: 'Die Vorhersage ist MOSMIX_L des DWD, stündlich: die Regenmenge einer Stunde (und ihre Summen für 6, 12 und 24 Stunden) und die Wahrscheinlichkeit von mehr als 0,1 mm in der Stunde.',
          says: 'Der DWD beschreibt MOSMIX als Vorhersage für Orte, die die Ausgabe von Wettermodellen statistisch mit dem korrigiert, was Wetterstationen gemessen haben. Seine Liste der MOSMIX-Elemente nennt die Regenmengen (RR1c, RR6c, RRhc, RRdc, „konsistent mit dem signifikanten Wetter“, in kg/m², das sind Millimeter) und R101, die Wahrscheinlichkeit von mehr als 0,1 mm Niederschlag während der letzten Stunde, in Prozent.',
        },
        'nearest-point': {
          text: 'Der Vorhersagepunkt, der dem Ort am nächsten liegt, wird so verwendet, wie er ist. Zwei Punkte werden nicht gemischt.',
          reason: 'Eine Vorhersage wird für Punkte gemacht. Der nächste ist die einfachste Regel und braucht keine Annahme darüber, wie der Regen zwischen Punkten schwankt; die Antwort sagt, welcher Punkt es ist und wie weit er entfernt liegt. Keine Quelle sagt, dass es die richtige Regel ist.',
        },
        'day': {
          text: 'Morgen ist der Kalendertag der Zeitzone des Ortes, von Mitternacht bis Mitternacht.',
          reason: 'Das Morgen einer Leserin oder eines Lesers ist der Tag auf der Uhr vor Ort. Die Vorhersage trägt UTC-Zeitstempel, deshalb wird der Tag um die Ortsmitternacht geschnitten. Das ist eine Wahl der App, keine Regel eines Leitfadens.',
        },
        'min-hours': {
          text: 'Die Antwort braucht einen Vorhersagewert für mindestens {hours} der 24 Stunden von morgen. Bei weniger sagt der Chip, dass die Vorhersage noch nicht bis morgen reicht.',
          reason: 'Die Summe von ein paar Stunden würde wie der Regen des Tages gelesen. {hours} Stunden, drei Viertel des Tages, sind eine runde Grenze, die wetterdienst gewählt hat; keine Quelle nennt eine.',
        },
        'day-total': {
          text: 'Der Regen des Tages ist die Summe der Stundenmengen; wo sie eine längere Summe der Vorhersage nicht erklären, gilt die längere Summe.',
          says: 'Die Liste des DWD gibt die Regenmenge einer Stunde und ihre Summen für 6, 12 und 24 Stunden an, jeweils „konsistent mit dem signifikanten Wetter“, in kg/m².',
          reason: 'Stunden zu addieren ist einfache Rechnung. Welche der Mengen der Vorhersage addiert werden, damit die Summe des Tages zu den eigenen Summen des DWD passt, entscheidet wetterdienst.',
        },
        'wet-hour': {
          text: 'Eine Stunde mit mindestens {wetMm} mm gilt als nasse Stunde.',
          says: 'Der Leitfaden der WMO sagt, dass Mengen unter 0,1 mm allgemein Spuren genannt werden. Die Regenwahrscheinlichkeit des DWD (R101) ist die Wahrscheinlichkeit von mehr als 0,1 mm in der Stunde.',
        },
        'yes-amount': {
          text: 'Ein Tag mit {yesMm} mm oder mehr ist „ja, wahrscheinlich Regen“.',
          says: 'Die Richtlinien der WMO zu Klimanormalwerten führen die Zahl der Tage mit 1 mm Niederschlag oder mehr unter den wichtigsten Klimaparametern ihrer Normalwerte auf (die Zählungen ab 5, 10, 50 mm und mehr gehören zu den nachrangigen); 1 mm ist also die Grenze, nach der die WMO einen Tag als Tag mit Niederschlag zählt.',
        },
        'maybe-amount': {
          text: 'Ein Tag mit {maybeMm} mm oder mehr, aber unter der Grenze für „ja“, ist „vielleicht, ein wenig“.',
          says: 'Der Leitfaden der WMO verlangt, dass von Hand gelesene Tagesmengen auf 0,2 mm genau und, wenn möglich, auf 0,1 mm genau abgelesen werden.',
          reason: '0,2 mm ist der gröbste Ablesestufe, den der Leitfaden für eine Tagesmenge zulässt (auf 0,2 mm genau, wenn möglich auf 0,1 mm), und wetterdienst nimmt ihn als Grenze für „ein wenig“. Keine Quelle nennt eine Grenze für „vielleicht“.',
        },
        'chance-bands': {
          text: 'Eine Wahrscheinlichkeit von {yesChance} % oder mehr in einer einzelnen Stunde ist „ja“; {maybeChance} % oder mehr ist „vielleicht“.',
          says: 'Die Liste des DWD definiert R101 als die Wahrscheinlichkeit von mehr als 0,1 mm Niederschlag während der letzten Stunde, in Prozent.',
          reason: 'Die Wahrscheinlichkeit kommt vom DWD, die beiden Grenzen, die daraus ein Wort machen, nicht. 7 von 10 für „wahrscheinlich“ und 3 von 10 für „vielleicht“ sind runde Zahlen, die wetterdienst gewählt hat. Keine Quelle nennt sie.',
        },
        'highest-chance': {
          text: 'Gezeigt wird die höchste Wahrscheinlichkeit einer einzelnen Stunde des Tages.',
          reason: 'Der DWD gibt für jede Stunde eine Wahrscheinlichkeit an, und die höchste ist die einfachste Zusammenfassung. Sie unterschätzt die Wahrscheinlichkeit, dass es irgendwann am Tag regnet; die ist mindestens so hoch wie die höchste Stunde. Keine Quelle schreibt sie vor.',
        },
      },
      limits: {
        forecast: 'Das ist eine Vorhersage, keine Messung: Sie sagt, was die Modelle und die Statistik des DWD erwarten, und die nächste Vorhersage kann anders aussehen. Was gefallen ist, sagen danach die Messungen einer Wetterstation.',
        point: 'Ein Vorhersagepunkt kann einige Kilometer vom Ort entfernt liegen, in einem Tal oder an einer Küste, wo das Wetter nicht dasselbe ist. Die Antwort nennt den Punkt und seine Entfernung.',
        chance: 'Menge und Wahrscheinlichkeit sind zwei verschiedene Dinge: Eine hohe Wahrscheinlichkeit kann mit einer kleinen Menge kommen, eine niedrige mit einem kräftigen Schauer. Die Antwort ist „ja“, wenn einer von beiden über seiner Grenze liegt.',
        day: 'Die Stunden tragen UTC-Zeitstempel, und der Wert zur vollen Stunde ist der Regen der Stunde davor; die erste Stunde eines Ortstages ist also der Wert mit dem Zeitstempel eine Stunde nach Mitternacht.',
        hours: 'Reicht die Vorhersage nicht über mindestens drei Viertel der Stunden von morgen, gibt es keine Antwort, und der Chip sagt das, statt eine zu erfinden.',
      },
      numbers: {
        point: 'Vorhersagepunkt: {name} ({id}), {distance} km von {place} entfernt.',
        pointNoDistance: 'Vorhersagepunkt: {name} ({id}), der nächste zu {place}.',
        day: 'Der Tag: {day}, als Kalendertag in der Zeitzone {zone}.',
        hours: 'Die Vorhersage hat für {given} der {hours} Stunden des Tages einen Wert.',
        total: 'Regen des Tages: {amount} {unit}, mit {wetHours} nassen Stunden (mindestens {wet} mm).',
        chance: 'Höchste Wahrscheinlichkeit von mehr als 0,1 mm in einer einzelnen Stunde: {chance}.',
        bands: 'Die Grenzen der Antwort, in Millimetern, gleich welche Einheit die Einstellungen haben: ja ab {yes} mm am Tag oder einer Wahrscheinlichkeit von {yesChance} in einer Stunde; vielleicht ab {maybe} mm oder einer Wahrscheinlichkeit von {maybeChance}.',
      },
    },

    season: {
      title: 'War die letzte Jahreszeit wärmer als üblich?',
      summary: 'Die mittlere Temperatur der drei Monate einer Jahreszeit (Frühling, Sommer, Herbst oder Winter) an der Station des Ortes, verglichen mit dem Mittel der Jahreszeiten eines WMO-Normalwerts: 1961 bis 1990 oder jedes spätere, das vollständig ist.',
      data: 'Die monatlichen Stationsbeobachtungen des DWD (Datensatz monthly/climate_summary): das Monatsmittel der Lufttemperatur in 2 m Höhe an der Station des Ortes, ihre ganze Reihe.',
      steps: {
        seasons: 'Für jedes Jahr, in dem der DWD die Monatsmittel aller drei Monate der Jahreszeit hat, ist die Jahreszeit das Mittel dieser drei: Frühling ist März bis Mai, Sommer Juni bis August, Herbst September bis November und Winter Dezember bis Februar, mit dem Dezember des Vorjahres. Eine Jahreszeit zählt, sobald sie vorbei ist: ab dem 1. Juni, 1. September, 1. Dezember und 1. März. Die letzte, die vorbei ist, ist die erfragte.',
        reference: 'Die Referenz ist das Mittel der Jahreszeiten des gewählten Normalwerts: 30 Jahre, die in einem auf 0 endenden Jahr enden, von {firstFrom} bis {firstTo} an, jeder, sobald er vollständig ist. Die Frage öffnet auf dem neuesten, von dem die Station genug Jahreszeiten hat. Ein Normalwert kann nur verglichen werden, wenn die Station mindestens {minSeasons} seiner {ofSeasons} Jahreszeiten dieser Art hat; einer mit weniger ist in der Auswahl ausgegraut, und eine Antwort dafür sagt es. Hat die Station weniger vom neuesten Normalwert, werden stattdessen die Jahreszeiten vor der erfragten genommen, wenn es mindestens {fallbackMin} sind; bei weniger gibt es keine Antwort.',
        compare: 'Die Abweichung ist das Mittel der Jahreszeit minus die Referenz. Dieselbe Differenz ist als Balken für jede Jahreszeit dieser Art an der Station gezeichnet.',
        verdict: 'Die Jahreszeit ist „wärmer“, wenn ihre Abweichung {band} °C oder mehr beträgt, „kühler“, wenn sie {band} °C oder mehr darunter liegt, und dazwischen „wie üblich“. Die Frage nach einem Winter fragt nach „kälter“, und ihre Antwort sagt Ja, wo der Winter kühler war. Der Rang zählt die Jahreszeiten, die wärmer waren.',
      },
      formulas: {
        season: 'Jahreszeit(Jahr) = (Mittel Monat 1 + Mittel Monat 2 + Mittel Monat 3) / 3; bei einem Winter ist Monat 1 der Dezember des Vorjahres',
        anomaly: 'Abweichung = Jahreszeit(erfragtes Jahr) − Mittel der Jahreszeit(Jahr) über die Referenzjahre',
      },
      rules: {
        'season': {
          text: 'Eine Jahreszeit sind drei volle Monate: Frühling sind März, April und Mai; Sommer sind Juni, Juli und August; Herbst sind September, Oktober und November; Winter sind Dezember, Januar und Februar.',
          says: 'Der DWD sagt, dass Meteorologen das Jahr in Jahreszeiten aus drei vollen Monaten teilen, die jeweils am Ersten des Monats beginnen, in dem astronomisch die Jahreszeit beginnt: Frühling vom 1. März bis 31. Mai, Sommer vom 1. Juni bis 31. August, Herbst vom 1. September bis 30. November und Winter vom 1. Dezember bis Ende Februar. Er sagt, das geschehe, weil die Statistiken des Klimas aus den Daten einzelner Monate gemacht werden.',
        },
        'winter-year': {
          text: 'Ein Winter nimmt den Dezember des Vorjahres: Dezember 2025 mit Januar und Februar 2026 ist der Winter 2025/26, der als Winter 2026 zählt, des Jahres seines Januars und Februars. Er ist am 1. März vorbei. Ein Winter-Normalwert wird mit den Jahren seiner Winter geschrieben: der Normalwert 1961 bis 1990 sind die Winter 1960/61 bis 1989/90.',
          says: 'Die Richtlinien der WMO sagen, dass ein Jahreszeiten-Normalwert das Mittel der Monatsnormalwerte seiner Monate ist. Sie sagen nicht, welchen Dezember ein Winter nimmt.',
          reason: 'Weder die Definition der Jahreszeiten des DWD noch die Richtlinien der WMO sagen, nach welchem Jahr ein Winter benannt wird, der über den Jahreswechsel reicht. wetterdienst benennt ihn nach dem Jahr seines Januars und Februars und nimmt den Dezember davor, damit seine drei Monate aufeinander folgen, wie sie es im Wetter tun. Nach der Lesart von wetterdienst würde der Normalwert der WMO für Dezember, Januar und Februar den Dezember derselben Jahre mitteln wie den Januar und den Februar; beide unterscheiden sich nur durch den Dezember an den Enden des Zeitraums (beim Normalwert 1991 bis 2020: Dezember 1990 gegen Dezember 2020). Das ist eine eigene Wahl von wetterdienst, und die Maintainer müssen sie annehmen.',
        },
        'complete-months': {
          text: 'Eine Jahreszeit zählt nur, wenn die Station das Mittel aller drei Monate hat. Der DWD berechnet ein Monatsmittel aus den Tageswerten des Monats, und nur, wo sie vollständig sind (für manche Stationen hat er Monatswerte und keine Tageswerte).',
          says: 'Die Richtlinien der WMO sagen: Fehlt der Normalwert eines der Monate einer Jahreszeit, fehlt auch der Normalwert der Jahreszeit. Die Beschreibung des DWD sagt, seine Monatsmittel würden aus den Tageswerten berechnet, und nur, wenn die Tageswerte vollständig sind, und dass es für manche Stationen Monatswerte gibt, wo keine Tageswerte vorliegen.',
        },
        'only-over': {
          text: 'Eine Jahreszeit zählt, sobald sie vorbei ist: der Frühling ab dem 1. Juni, der Sommer ab dem 1. September, der Herbst ab dem 1. Dezember und der Winter ab dem 1. März. Die Jahreszeit, die noch läuft, wird nicht verglichen.',
          reason: 'Eine laufende Jahreszeit hat erst einen Teil ihrer Wochen, und ihr Mittel würde mit ganzen Jahreszeiten verglichen. Die Maintainer haben entschieden, dass nur vollständige Jahreszeiten verglichen werden. Dafür braucht es keine Quelle.',
        },
        'season-mean': {
          text: 'Das Mittel einer Jahreszeit ist das einfache Mittel der drei Monatsmittel; jeder Monat zählt gleich, gleich wie viele Tage er hat.',
          says: 'Die Richtlinien der WMO sagen, dass ein Jahreszeiten-Normalwert das Mittel der Monatsnormalwerte seiner Monate ist. Manche Wetterdienste gewichten die Monate nach ihrer Zahl an Tagen; die WMO sagt, das werde für Produkte, die zwischen Ländern ausgetauscht werden, nicht empfohlen.',
        },
        'default-season': {
          text: 'Die Frage öffnet auf der Jahreszeit, die zuletzt abgeschlossen wurde und von der die Station genug Daten hat: der Herbst ab dem 1. Dezember, der Winter ab dem 1. März, der Frühling ab dem 1. Juni und der Sommer ab dem 1. September. Eine Jahreszeit hat genug Daten, wenn die Station mindestens {minSeasons} der {ofSeasons} Jahreszeiten irgendeines Normalwerts hat oder wenn die Jahreszeiten vor der letzten den neuesten Normalwert ersetzen können (siehe unten). Hat die jüngste zu wenig, öffnet sie auf der nächstjüngeren. Ein Link oder eine Wahl in der Auswahl, die eine Jahreszeit nennt, behält sie, und der Link ?ask=summer nennt den Sommer; eine Jahreszeit mit zu wenig Daten ist ausgegraut, und ein Link, der eine nennt, bekommt die Jahreszeit, auf der die Frage öffnet, mit einer Zeile, die das sagt.',
          reason: 'Keine Quelle sagt, auf welcher Jahreszeit eine Frage öffnen soll. Die zuletzt abgeschlossene ist die, nach der gefragt wird, und die Daten entscheiden, wo die jüngste zu wenig davon hat. Das ersetzt die frühere Wahl (immer der Sommer), die die Maintainer angenommen hatten, und muss deshalb neu angenommen werden.',
        },
        'reference-choices': {
          text: 'Die Referenz kann jeder WMO-Normalwert über 30 Jahre sein, der in einem auf 0 endenden Jahr endet und vollständig ist: von {firstFrom} bis {firstTo} an, mit einem neuen am 1. Januar nach seinem letzten Jahr. Die ganze Reihe der Station und ein gleitender Zeitraum von 30 Jahren werden nicht angeboten.',
          says: 'Die WMO definiert den klimatologischen Standardnormalwert als Durchschnitt über 30 Jahre, der in einem auf 0 endenden Jahr endet: 1981 bis 2010, 1991 bis 2020 und so fort. Der Zeitraum 1961 bis 1990 bleibt als Referenz-Normalwert für die Bewertung langfristiger Klimaänderungen erhalten, ist aber kein Standardnormalwert. Ein Normalwert im Sinne der WMO ist ein Zeitraumdurchschnitt über mindestens drei aufeinanderfolgende Zehnjahreszeiträume, die am 1. Januar eines auf 1 endenden Jahres beginnen, und das ist jeder Zeitraum, der hier angeboten wird.',
        },
        'reference-default': {
          text: 'Die Frage öffnet auf dem neuesten Normalwert, der vollständig ist. Er endet im Jahr floor((Jahr − 1) / 10) × 10, ist also von 1991 bis 2020, bis Ende 2030, und ab dem 1. Januar 2031 von 2001 bis 2030.',
          says: 'Die WMO sagt, der klimatologische Standardnormalwert sei der jüngste 30-Jahres-Zeitraum, der in einem auf 0 endenden Jahr endet, und werde alle zehn Jahre neu berechnet.',
        },
        'default-normal': {
          text: 'Die Frage öffnet auf dem neuesten der Normalwerte, von dem die Station für die gewählte Jahreszeit genug Jahreszeiten hat: mindestens {minSeasons} seiner {ofSeasons} oder, beim neuesten Normalwert, genug Jahreszeiten vor der letzten für den Ersatz unten. Ein Normalwert, den ein Link oder die Auswahl nennt, bleibt; ist er für die Jahreszeit ausgegraut, gilt stattdessen der, auf dem die Frage öffnet, und eine Zeile sagt es.',
          reason: 'Keine Quelle sagt, auf welchem der Normalwerte eine Frage öffnen soll. Der neueste ist der aktuelle Standard, und die Frage geht nur dort auf einen älteren über, wo die Station nicht mit einem neueren verglichen werden kann. Die Maintainer müssen das annehmen.',
        },
        'normal-mean': {
          text: 'Die Referenz ist das Mittel der vollständigen Jahreszeiten ihrer Jahre, jede Jahreszeit zählt gleich. Eine Jahreszeit, in der ein Monat fehlt, fällt ganz heraus.',
          says: 'Die Richtlinien der WMO bilden einen Jahreszeiten-Normalwert als Mittel der drei Monatsnormalwerte seiner Monate und nicht aus den Werten einzelner Jahre. Fehlt der Normalwert eines Monats, fehlt der Jahreszeiten-Normalwert.',
          reason: 'Der Chip mittelt ganze Jahreszeiten; ein Jahr, in dem ein Monat fehlt, fällt also ganz aus der Referenz, wo die WMO dieses Jahr in den beiden anderen Monatsnormalwerten noch verwenden würde. Wo kein Monat fehlt, kommt dasselbe heraus. Die Art, wie der Chip mittelt, ist eine eigene Wahl von wetterdienst.',
        },
        'min-seasons': {
          text: 'Ein Normalwert kann nur verglichen werden, wenn die Station mindestens {minSeasons} seiner {ofSeasons} Jahreszeiten dieser Art hat. Ein anderer ist in der Auswahl ausgegraut, mit der Zahl, die die Station hat, und eine Antwort dafür sagt es; für den neuesten gilt der Ersatz unten.',
          says: 'Die WMO verlangt für einen Normalwert, für jeden Monat, gültige Monatswerte in mindestens 80 % der Jahre des Zeitraums, das sind 24 oder mehr von 30 Jahren.',
          reason: 'Der Chip zählt vollständige Jahreszeiten (alle drei Monate der Jahreszeit, bei einem Winter mit dem Dezember davor), nicht die Jahre jedes einzelnen Monats; die Grenze ist also nicht die der WMO und lässt sich nicht eins zu eins mit ihr vergleichen. {minSeasons} von {ofSeasons} ist eine eigene Grenze von wetterdienst, gesetzt, damit auch Stationen mit Lücken eine Antwort gegen einen WMO-Zeitraum bekommen, und die Maintainer müssen sie annehmen; die Referenz einer solchen Station ist dann kein Normalwert der WMO im strengen Sinn.',
        },
        'fallback-period': {
          text: 'Hat die Station zu wenige Jahreszeiten des neuesten Normalwerts, sind die Referenz alle Jahreszeiten der Station vor der erfragten. Kein anderer Normalwert wird so ersetzt: ein gewählter wird verwendet oder ist ausgegraut.',
          says: 'Die WMO nennt das Mittel von Monatswerten über einen beliebigen festgelegten Zeitraum einen „Durchschnitt“ und sagt, manche Quellen nennten ihn „vorläufigen Normalwert“.',
          reason: 'Alle früheren Jahreszeiten zu nehmen, und nicht einen Zeitraum, der in einem auf 1 endenden Jahr beginnt, wie es die Definition des Zeitraumdurchschnitts der WMO vorsieht, ist eine eigene Wahl von wetterdienst. Ebenso, den Ersatz dem neuesten Normalwert vorzubehalten: eine Antwort gegen andere Jahre als die gewählten würde die gestellte Frage nicht beantworten.',
        },
        'fallback-minimum': {
          text: 'Der Ersatz braucht mindestens {fallbackMin} Jahreszeiten.',
          says: 'Die WMO sagt, dass bei den meisten Mittelwert- und Summen-Parametern 10 bis 12 Jahre Daten eine ähnliche Vorhersagekraft hatten wie ein üblicher 30-jähriger Zeitraum.',
          reason: 'Zehn ist das untere Ende dieser Spanne, und die WMO setzt kein festes Minimum. Die eigene Definition des Zeitraumdurchschnitts der WMO, mindestens zehn Jahre ab dem 1. Januar eines auf 1 endenden Jahres, passt nicht zu einem Ersatz aus allen früheren Jahreszeiten. Die Grenze von {fallbackMin} Jahreszeiten ist eine eigene von wetterdienst, und die Maintainer müssen sie annehmen.',
        },
        'anomaly': {
          text: 'Die Abweichung ist das Mittel der Jahreszeit minus die Referenz, in Grad.',
          says: 'Die WMO sagt, ein Normalwert sei der Maßstab, mit dem aktuelle Beobachtungen verglichen werden, und viele auf Abweichungen beruhende Klimadatensätze bauen darauf auf. Eine Abweichung ist diese Differenz.',
        },
        'usual-band': {
          text: 'Eine Differenz von weniger als {band} °C in die eine oder andere Richtung gilt als „wie üblich“.',
          reason: 'Für „wie üblich“ braucht es ein Band, und ein halbes Grad ist eine runde Zahl, die wetterdienst gewählt hat. Keine Quelle nennt eine Breite für das Wort, und die Maintainer müssen diese annehmen.',
        },
        'rank': {
          text: 'Der Rang ist die Zahl der Jahreszeiten dieser Art an der Station, die wärmer waren, plus eins.',
          reason: 'Eine einfache Zählung braucht keine Annahme über die Verteilung der Jahreszeiten; sie ist kein Verfahren aus einer Quelle.',
        },
      },
      limits: {
        station: 'Die Antwort ist die Messung einer einzelnen Station, die an einem Ort steht. In einer Stadt oder Region kann die Jahreszeit anders gewesen sein; die Stationen des DWD unterscheiden sich in Höhe, Umgebung und Instrumenten.',
        moved: 'Eine Station, die versetzt wurde oder ihre Instrumente oder Beobachtungszeiten geändert hat, wird dafür nicht korrigiert: Die Antwort ist die Reihe der Station, wie der DWD sie veröffentlicht. Der DWD bittet, Änderungen der Stationshöhe und der Beobachtungszeiten zu beachten, wenn Trends gelesen werden.',
        gaps: 'Ein fehlender Tag nimmt den Monat und damit die Jahreszeit aus dem Vergleich, weil der DWD ein Monatsmittel nur aus vollständigen Tageswerten berechnet (die WMO lässt in einem Monat bis zu 10 fehlende Tage zu, und weniger als 5 in Folge). Eine Station mit Lücken hat weniger Jahreszeiten, und eine Station, die später begann als ein Normalwert, hat wenige oder keine seiner Jahreszeiten: dieser Normalwert ist dann ausgegraut.',
        reference: 'Dieselbe Jahreszeit, gegen einen anderen Normalwert gelegt, hat eine andere Abweichung und kann eine andere Antwort haben. Der Normalwert 1961 bis 1990 ist die Referenz der WMO für den Klimawandel, der neueste ist der aktuelle Standard, und alle zehn Jahre kommt ein neuer. Wie ein Normalwert entsteht, steht auf der Seite „So wird Wetter gemessen“.',
        band: 'Die Breite von „wie üblich“ ist eine eigene von wetterdienst: Eine Differenz knapp unter und knapp über dem Band ist fast dasselbe, hat aber verschiedene Wörter.',
      },
      numbers: {
        station: 'Station: {name} ({id}). Die Antwort ist die der Station, nicht die der Stadt.',
        season: 'Im {season} {year} ({months}) lag das Mittel bei {mean} {unit}.',
        reference: 'Verglichen mit dem Mittel der {seasons} von {from} bis {to}: {count} {seasons}, {normal} {unit}.',
        referenceFallback: 'Die Station hat zu wenige {seasons} des neuesten WMO-Normalwerts ({askedFrom} bis {askedTo}), deshalb werden stattdessen die {count} {seasons} von {from} bis {to} genommen: ihr Mittel ist {normal} {unit}. Das ist ein Durchschnitt der früheren Reihe der Station, kein Normalwert der WMO.',
        anomaly: 'Differenz: {anomaly} {unit} (der {season} minus die Referenz).',
        band: 'Innerhalb von {band} {unit} in beide Richtungen gilt als üblich.',
        rank: 'Rang {rank} von {count} vollständigen Jahreszeiten dieser Art (Rang 1 ist der wärmste); die Reihe beginnt {first}.',
      },
      terms: {
        season: { spring: 'Frühling', summer: 'Sommer', autumn: 'Herbst', winter: 'Winter' },
        seasons: { spring: 'Frühlinge', summer: 'Sommer', autumn: 'Herbste', winter: 'Winter' },
        months: { spring: 'März bis Mai', summer: 'Juni bis August', autumn: 'September bis November', winter: 'Dezember bis Februar' },
      },
    },

    day: {
      title: 'Wie war ein Tag?',
      summary: 'Wie windig, sonnig, nass, heiß oder kalt oder verschneit ein Tag an der Station des Ortes war, mit einer Skala in ein Wort gefasst, die eine veröffentlichte Quelle vorgibt, wo es eine gibt, und neben die Tage drumherum gelegt.',
      data: 'Die täglichen Stationsbeobachtungen des DWD (Datensatz daily/climate_summary): die höchste Windböe (wind_gust_max) und die mittlere Windgeschwindigkeit (wind_speed_mean), die Sonnenscheindauer (sunshine_duration), der Niederschlag (precipitation_amount), die höchste und die niedrigste Lufttemperatur in 2 m (temperature_air_max_2m, temperature_air_min_2m) und die Schneehöhe (snow_depth) der Station des Ortes, dazu ihr Neuschnee (snow_depth_new, aus dem Tagesdatensatz des Niederschlags daily/precipitation_more), wo sie einen hat, für die {days} Tage vor und nach dem Tag.',
      steps: {
        station: 'Für die Station des Ortes werden die Werte des Tages und der {days} Tage davor und danach geholt (keine nach gestern), alle Messgrößen in einer Anfrage: Windböe und Wind im Mittel, Sonnenscheindauer, Niederschlag, höchste und niedrigste Temperatur, Schneehöhe und Neuschnee. Eine andere Messgröße zu wählen, fragt nichts Neues ab.',
        wind: 'Wind: Jede Geschwindigkeit wird mit der Tabelle der WMO in eine Stärke der Beaufortskala von 0 bis 12 übersetzt. Hat die Station für den Tag eine Böe, kommt das Wort aus deren Stärke: ruhig unter Stärke {gustBreezy}, leicht windig ab {gustBreezy}, windig ab {gustWindy}, stürmisch ab {gustStormy}. Ohne Böe gilt das Mittel, eine Stärke niedriger: ab {meanBreezy}, {meanWindy} und {meanStormy}.',
        sun: 'Sonne: Die Sonnenscheindauer des Tages wird durch die Sonnenscheindauer geteilt, die an diesem Tag auf der Breite der Station möglich war, die Zeit zwischen Sonnenaufgang und Sonnenuntergang bei freiem Horizont, die sich aus der Deklination der Sonne ergibt. Unter {dullBelow} % davon ist der Tag trüb, ab {sunnyFrom} % sonnig, dazwischen wechselhaft.',
        rain: 'Regen: Der Niederschlag des Tages in Millimetern ist trocken unter {dryMm} mm, leicht von da an, nass ab {wetMm} mm und sehr nass ab {veryWetMm} mm.',
        temperature: 'Hitze und Kälte: Die höchste und die niedrigste Temperatur des Tages werden an den Tagen gemessen, die der DWD benennt: ein Heißer Tag (Höchsttemperatur {hotDay} °C oder mehr), ein Sommertag (ab {summerDay} °C), eine Tropennacht (Tiefsttemperatur {tropicalFrom} °C oder mehr), ein Eistag (Höchsttemperatur unter {iceBelow} °C) und ein Frosttag (Tiefsttemperatur unter {frostBelow} °C). Die erste davon in dieser Reihenfolge benennt den Tag, die anderen, zu denen er gehört, werden dazu aufgeführt.',
        snow: 'Schnee: Schnee liegt, wo die Schneehöhe des Tages über {snowAboveCm} cm beträgt. Die Höhe wird genannt, dazu der Neuschnee, wo die Station ihn meldet.',
        around: 'Der Tag wird neben die Tage drumherum gelegt, als Diagramm. Beim Wind wird außerdem gezählt, wie viele von ihnen einen stärkeren Wert hatten als der Tag.',
      },
      formulas: {
        force: 'Stärke = Zahl der unteren Grenzen der Beaufort-Tabelle (0,3; 1,6; 3,4 … 32,7 m/s), bei denen die Geschwindigkeit gleich oder darüber liegt',
        daylength: 'sin δ = sin ε · sin λ (δ: Deklination der Sonne, ε: Schiefe der Ekliptik, 23,439°, λ: ekliptikale Länge der Sonne); cos t = −tan φ · tan δ (t: Stundenwinkel des Sonnenaufgangs, φ: geografische Breite); mögliche Sonnenscheindauer = 2 · t ÷ 15° je Stunde',
        share: 'Anteil = Sonnenscheindauer ÷ mögliche Sonnenscheindauer, nicht über 100 %',
      },
      rules: {
        'daily-values': {
          text: 'Die Werte sind die Tageswerte der Station: die höchste Windböe und die mittlere Windgeschwindigkeit, die Sonnenscheindauer, der Niederschlag, die höchste und die niedrigste Lufttemperatur in 2 m, die Schneehöhe und der Neuschnee, wo die Station ihn hat. Sie stehen in der Einheit der Einstellungen, nur die Sonnenscheindauer immer in Stunden.',
          says: 'Die Beschreibung der Tagesdaten des DWD führt FX, das Tagesmaximum der Windböe, und FM, das Tagesmittel der Windgeschwindigkeit (m/s), SDK, die tägliche Sonnenscheindauer (h), RSK, die tägliche Niederschlagshöhe (mm), TXK und TNK, das Tagesmaximum und das Tagesminimum der Temperatur in 2 m Höhe (°C), und SHK_TAG, die tägliche Schneehöhe (cm), auf. Die Beschreibung seiner Tagesdaten des Niederschlags führt SH_TAG, die Höhe der Schneedecke, und NSH_TAG, die Neuschneehöhe (cm), auf.',
        },
        'default-day': {
          text: 'Ein Link ohne Tag fragt nach dem gleichen Datum des Vorjahres. Ein 29. Februar, den das Vorjahr nicht hatte, fragt nach dem 28. Februar. Die Leserin oder der Leser kann jeden Tag bis gestern wählen.',
          reason: 'Der Tag ist ein Beispiel, das das Projekt gewählt hat, um zu zeigen, wie die Antwort aussieht: Das gleiche Datum vor einem Jahr hat seine Messwerte sicher in den Daten, und es liegt in der gleichen Jahreszeit wie heute. Für das Verfahren hat er keine Bedeutung. Keine Quelle trifft hier zu. Er ersetzt den letzten 26. Dezember, auf dem die Frage vorher aufging.',
        },
        'default-measure': {
          text: 'Ein Link ohne Messgröße fragt nach dem Wind, der Frage, die dieser Chip immer war. Hat die Station für den Tag keinen Windwert, geht er auf der ersten Messgröße auf, von der sie einen Wert hat: Sonne, Regen, Hitze und Kälte, Schnee.',
          reason: 'Der Wind ist, wonach die Frage fragte, bevor sie eine Wahl hatte, damit Links und Gewohnheiten ihre Bedeutung behalten, und der Rückgriff auf eine Messgröße mit Daten zeigt eine Antwort statt einer leeren. Keine Quelle trifft hier zu.',
        },
        'measure-reading': {
          text: 'Eine Messgröße wird nur angeboten, wenn die Station für den Tag einen Wert von ihr hat. Die anderen sind ausgegraut, mit dem Grund, und ein Link, der eine nennt, bekommt die Voreinstellung, mit einer Zeile, die das sagt. Hitze und Kälte brauchen die höchste und die niedrigste Temperatur, der Wind die Böe oder das Mittel.',
          reason: 'Ein Urteil aus einem Wert, der nicht da ist, wäre erfunden. Beide Temperaturen sind nötig, weil sich ein Frosttag ohne die niedrigste nicht ausschließen lässt. Keine Quelle trifft hier zu.',
        },
        'beaufort': {
          text: 'Eine Geschwindigkeit wird mit der Tabelle der WMO zur Stärke: Die unteren Grenzen der Stärken 1 bis 12 sind {edges} m/s.',
          says: 'Der Leitfaden der WMO gibt für jede Stärke der Beaufortskala von 0 (Windstille) bis 12 (Orkan) die Windgeschwindigkeit in der Normhöhe von 10 m über offenem, ebenem Gelände an, die ihr entspricht. Stärke 7, ein steifer Wind, sind 13,9 bis 17,1 m/s; Stärke 9, ein Sturm, 20,8 bis 24,4 m/s.',
        },
        'gust-first': {
          text: 'Hat die Station für den Tag eine Böe, wird die Antwort aus der Böe gelesen, sonst aus dem Mittel.',
          says: 'Die WMO sagt, die Windgeschwindigkeit in Meldungen sei ein Mittel über 10 Minuten (§5.1.2), und viele Anwendungen, darunter die Klimatologie von Windlasten, brauchen die Böen (§5.1.3); die 3-Sekunden-Spitzenböe ist eine der beiden Größen, die sie für das routinemäßige Ablesen nennt. Ihre Tabelle 5.1 gibt die Beaufort-Stärken als Entsprechungen der Windgeschwindigkeit in 10 m Höhe an, zum Schätzen des Windes.',
          reason: 'Eine Böe sagt über einen rauen Tag mehr als das Mittel. Der gemeldete Wind ist ein 10-Minuten-Mittel, und die Tabelle 5.1 gibt die Entsprechungen von Geschwindigkeiten in diesem Sinn an; eine Böe von Sekunden damit zu lesen, ist ein Schluss von wetterdienst, keine Aussage der WMO.',
        },
        'gust-words': {
          text: 'Nach der Böe: ruhig unter Stärke {gustBreezy}, leicht windig ab {gustBreezy}, windig ab {gustWindy}, stürmisch ab {gustStormy}.',
          says: 'Die Tabelle der WMO nennt Stärke 5 eine frische Brise, Stärke 7 einen steifen Wind und Stärke 9 einen Sturm. Die Warnkriterien des DWD beginnen die erste Stufe der Windwarnungen bei Böen über 50 km/h, das ist Stärke 7, und nennen Böen von 65 bis 89 km/h (Stärke 8 bis 9) Sturmböen; der DWD sagt, die Skala sei an die Beaufortskala angelehnt.',
          reason: 'Die vier Wörter sind eine Gruppierung der zwölf Stärken durch wetterdienst. Ihre Grenzen folgen den Namen der Tabelle der WMO. „Windig“ beginnt, wo die erste Warnstufe des DWD beginnt, und „stürmisch“ eine Stärke über dem Beginn der Sturmböen des DWD. Keine Quelle nennt diese vier Wörter.',
        },
        'mean-words': {
          text: 'Nach dem Mittel, wo es keine Böe gibt: ruhig unter Stärke {meanBreezy}, leicht windig ab {meanBreezy}, windig ab {meanWindy}, stürmisch ab {meanStormy}.',
          says: 'Die Tabelle der WMO nennt Stärke 4 eine mäßige Brise, Stärke 6 einen starken Wind und Stärke 8 einen stürmischen Wind.',
          reason: 'Ein Mittel liegt niedriger als die Böe derselben Stunde, deshalb liegen die Grenzen eine Stärke unter denen für eine Böe. Keine Quelle nennt sie.',
        },
        'sun-share': {
          text: 'Die Sonnenscheindauer des Tages wird mit der Sonnenscheindauer verglichen, die an diesem Tag auf der Breite der Station möglich war, als Anteil von 0 bis 100 %.',
          says: 'Die WMO definiert die Sonnenscheindauer als die Zeit, in der die direkte Sonnenstrahlung 120 W je Quadratmeter überschreitet (§8.1.1), und sagt, für klimatologische Zwecke werde eine „relative tägliche Sonnenscheindauer“ verwendet, die die Sonnenscheindauer auf die außerirdisch mögliche bezieht, geschrieben SD0 (§8.1.2).',
        },
        'day-length': {
          text: 'Die mögliche Sonnenscheindauer ist die Länge des Tages auf der Breite der Station: Die Deklination der Sonne an diesem Tag ergibt den Stundenwinkel des Sonnenaufgangs, und der Tag ist das Doppelte dieses Winkels bei 15 Grad je Stunde, bei freiem Horizont. Ein Tag, an dem die Sonne nicht aufgeht, hat keine Antwort.',
          says: 'Die WMO gibt die Näherungsformeln des Astronomical Almanac für den Stand der Sonne an, aus denen die Deklination folgt (Annex 7.F), und für einen mathematischen Horizont den Stundenwinkel von Sonnenauf- und -untergang als cos t = −tan(Breite) · tan(Deklination) (Annex 7.G).',
        },
        'sun-bands': {
          text: 'Nach dem Anteil der möglichen Sonnenscheindauer: trüb unter {dullBelow} %, wechselhaft ab {dullBelow} %, sonnig ab {sunnyFrom} %.',
          says: 'Die WMO beschreibt drei Bereiche der relativen täglichen Sonnenscheindauer: „bedeckter Himmel“ von 0 bis unter 0,3, „aufgelockerte Bewölkung“ von 0,3 bis unter 0,7 und „Schönwetter“ von 0,7 bis 1,0. Sie nutzt sie, um zu sagen, wie sehr die Anforderungen an einen Sonnenscheinautographen von der Bewölkung des Ortes abhängen.',
          reason: 'Die Grenzen sind die der WMO. Die drei Bereiche „trüb“, „wechselhaft“ und „sonnig“ zu nennen, ist die eigene Verwendung durch wetterdienst: Die WMO nutzt sie, um die Bewölkung zu beschreiben, mit der ein Messgerät zurechtkommen muss, nicht das Wetter eines Tages, und keine Quelle nennt ein Urteil für einen Tag.',
        },
        'rain-trace': {
          text: 'Ein Tag mit weniger als {dryMm} mm Niederschlag ist trocken.',
          says: 'Die WMO sagt, tägliche Niederschlagsmengen sollten auf 0,2 mm und, wenn möglich, auf 0,1 mm genau abgelesen werden, und Mengen unter 0,1 mm würden allgemein als Spuren bezeichnet.',
        },
        'rain-wet-day': {
          text: 'Ab {wetMm} mm ist der Tag nass. Die Tage zwischen {dryMm} mm und {wetMm} mm sind leicht.',
          says: 'Die Richtlinien der WMO führen die Zahl der Tage mit 1 mm Niederschlag oder mehr unter den wichtigsten klimatologischen Größen der Normalwerte einer Station auf.',
        },
        'rain-very-wet': {
          text: 'Ab {veryWetMm} mm ist der Tag sehr nass.',
          says: 'Dieselbe Tabelle führt die Zahl der Tage mit einem Tagesniederschlag von 5, 10, 50, 100 und 150 mm oder mehr unter den sekundären Größen auf; 10 mm ist eine dieser Schwellen.',
          reason: 'Die WMO nennt Schwellen, nach denen Tage gezählt werden, keine Wörter dafür. Das Wort „sehr nass“ für die Tage ab 10 mm und das Weglassen der Schwellen von 5 mm und von 50 mm und mehr sind die eigene Wahl von wetterdienst: Vier Wörter genügen, um einen Tag zu beschreiben, und die Menge steht immer dabei.',
        },
        'heat-days': {
          text: 'Ein Sommertag hat eine Höchsttemperatur von {summerDay} °C oder mehr, ein Heißer Tag {hotDay} °C oder mehr.',
          says: 'Der DWD definiert den Sommertag als Tag mit einer Höchsttemperatur der Luft von mindestens 25,0 °C und den Heißen Tag als Tag mit mindestens 30,0 °C. Die Richtlinien der WMO führen die Zahl der Tage mit einer Höchsttemperatur von 25, 30, 35 und 40 °C oder mehr unter den sekundären Größen der Normalwerte auf.',
        },
        'cold-days': {
          text: 'Ein Frosttag hat eine Tiefsttemperatur unter {frostBelow} °C, ein Eistag eine Höchsttemperatur unter {iceBelow} °C. Ein Eistag ist auch ein Frosttag.',
          says: 'Der DWD definiert den Frosttag als Tag, dessen Tiefsttemperatur der Luft unter 0,0 °C liegt, und den Eistag als Tag, dessen Höchsttemperatur unter 0,0 °C liegt. Die Richtlinien der WMO führen die Zahl der Tage mit einer Höchsttemperatur unter 0 °C und mit einer Tiefsttemperatur unter 0 °C unter den sekundären Größen der Normalwerte auf.',
        },
        'tropical-night': {
          text: 'Eine Tropennacht hat eine Tiefsttemperatur von {tropicalFrom} °C oder mehr.',
          says: 'Der DWD definiert die Tropennacht als Nacht, in der die Tiefsttemperatur der Luft 20 °C oder mehr beträgt, gemessen von 18 UTC bis 06 UTC.',
        },
        'tropical-daily-minimum': {
          text: 'Die Tiefsttemperatur des Tages der Station steht für die Tiefsttemperatur der Nacht: Ein Tag, dessen Tiefsttemperatur {tropicalFrom} °C oder mehr beträgt, zählt als Tropennacht.',
          says: 'Der DWD misst die Nacht von 18 UTC bis 06 UTC.',
          reason: 'Die Tagesdaten der Station haben kein Minimum allein der Nacht. Das Tagesminimum ist das des Tages, und eine Nacht liegt über zwei Tagen, das ist also eine Näherung: Wo der Tag nie unter 20 °C fiel, taten es auch die Stunden zweier Nächte, die in ihm liegen (00 bis 06 und 18 bis 24 UTC), nicht, aber die andere Hälfte jeder Nacht gehört zum nächsten oder zum vorigen Tag und wird nicht betrachtet.',
        },
        'class-order': {
          text: 'Ein Tag wird nach der ersten Klasse benannt, zu der er gehört, in dieser Reihenfolge: Heißer Tag, Sommertag, Tropennacht, Eistag, Frosttag. Die anderen Klassen, zu denen er gehört, werden beim Wort aufgeführt. Ein Tag ohne eine davon heißt „weder Frost noch Sommertag“.',
          says: 'Der DWD nennt die Tage, an denen ein Schwellenwert eines meteorologischen Parameters erreicht oder überschritten wird, „Kenntage“, und führt den Sommertag, den Heißen Tag, den Frosttag und den Eistag darunter auf.',
          reason: 'Jeder Heiße Tag ist ein Sommertag und jeder Eistag ein Frosttag, die stärkere Klasse sagt also mehr. Die Hitze steht nur deshalb vor der Kälte, weil kein Tag beides ist. Die Reihenfolge ist die von wetterdienst, keine Quelle gibt eine vor.',
        },
        'snow-lies': {
          text: 'Schnee liegt, wo die Schneehöhe des Tages über {snowAboveCm} cm beträgt. Sonst liegt kein Schnee.',
          says: 'Die Richtlinien der WMO führen die Zahl der Tage mit einer Schneehöhe über 0, 1, 10 und 50 cm unter den sekundären Größen der Normalwerte auf; über 0 cm ist die erste davon.',
        },
        'fresh-snow': {
          text: 'Der Neuschnee des Tages kommt dazu, wo die Station ihn meldet. Er stammt aus dem Tagesdatensatz des Niederschlags des DWD, da die Klimazusammenfassung keinen hat.',
          says: 'Die Beschreibung der Tagesdaten des Niederschlags des DWD führt SH_TAG, die Höhe der Schneedecke, und NSH_TAG, die Neuschneehöhe, beide in cm, auf.',
        },
        'around-window': {
          text: 'Der Tag wird neben die {days} Tage davor und die {days} Tage danach gelegt, keiner davon nach gestern.',
          reason: 'Eine Woche nach beiden Seiten reicht, um zu zeigen, ob der Tag für diese Wetterlage ungewöhnlich war, und ist kurz genug, dass sich die Jahreszeit kaum ändert. Keine Quelle nennt ein Fenster.',
        },
        'stronger-count': {
          text: 'Wie viele der Tage drumherum stärker waren, ist eine einfache Zählung der Tage mit einem größeren Wert.',
          reason: 'Eine Zählung braucht keine Annahme über die Verteilung des Windes und lässt sich leicht am Diagramm prüfen. Sie ist kein Verfahren aus einer Quelle.',
        },
      },
      limits: {
        'station': 'Die Werte einer Station sind nicht das Wetter einer Stadt oder Region: Sonne, Regen, Wind und Frost unterscheiden sich schon auf wenigen Kilometern. Die WMO sagt, es sei fast unmöglich, einen Ort zu finden, dessen Windgeschwindigkeit für ein großes Gebiet repräsentativ ist, und die Aufstellung des Windmessers sei der schwierigste Punkt der Windmessung.',
        'missing': 'Eine Messgröße, von der die Station für den Tag keinen Wert hat, bekommt keine Antwort, und ihre Auswahl ist ausgegraut. Ohne Böe kommt das Wort beim Wind aus dem Mittel, auf der Skala, die eine Stärke niedriger liegt.',
        'window': 'Die Tage um den Tag reichen nicht über gestern hinaus, weil spätere Tage noch nicht in den Daten sind.',
        'time': 'Ein Tag ist nicht in jeder Spalte der Tagesdaten des DWD derselbe Zeitraum von 24 Stunden. Seit April 2001 umfasst der Niederschlag an den geprüften Stationen 06:00 UTC bis 06:00 UTC des Folgetags, die höchste und die niedrigste Temperatur und die Sonnenscheindauer 00:00 bis 24:00 UTC, und die Schneehöhe ist der Wert von 06 UTC. Die Seite „So wird Wetter gemessen“ erklärt es.',
        'gust': 'Eine Beaufort-Stärke einer Böe ist nicht die Stärke des Windes: Der gemeldete Wind ist über 10 Minuten gemittelt, die Tabelle gibt die Entsprechungen solcher Geschwindigkeiten an, und eine Böe dauert Sekunden. „Stürmisch“ heißt hier eine starke Böe, kein schwerer Sturm (Stärke 10 der Tabelle der WMO) im Sinn eines mittleren Windes.',
        'height': 'Die Beaufort-Tabelle gilt für 10 m Höhe über offenem Gelände. Die Stationen des DWD unterscheiden sich in der Höhe des Sensors, und ein Sensor in anderer Höhe misst eine andere Geschwindigkeit; die Seite „So wird Wetter gemessen“ nennt ein Beispiel.',
        'horizon': 'Die mögliche Sonnenscheindauer ist der Tag bei freiem Horizont. Ein Sonnenscheinautograph braucht die Sonne einige Grad über dem Horizont (die WMO verlangt freie Sicht, wo sie mehr als 3° hoch steht), und Hügel, Gebäude und Bäume an der Station nehmen mehr, deshalb bleibt auch ein wolkenloser Tag unter 100 %.',
        'recorder': 'Die Sonnenscheindauer wird bestenfalls auf etwa eine Zehntelstunde genau gemessen (die WMO verlangt ±0,1 h), und dünne hohe Bewölkung, die die Sonne auf etwa die Linie von 120 W je Quadratmeter dämpft, ist es, wo sich die Geräte am meisten uneins sind.',
        'gauge': 'Ein Regenmesser misst an einem Punkt, und der Wind lässt ihn weniger auffangen, als fällt: Die WMO nennt den Wind die größte Störquelle bei Niederschlagsmessungen und sagt, der Fehlbetrag bei Regen in einem Standardgerät könne bis zu 10 % betragen.',
        'night': 'Eine Tropennacht ist eine Nacht von 18 UTC bis 06 UTC, und die Antwort betrachtet den Tag der Station von 00:00 bis 24:00 UTC. In Deutschland ist die Ortszeit eine oder zwei Stunden vor UTC.',
        'snow-reading': 'Die Schneehöhe des DWD ist an den geprüften Stationen der Wert von 06 UTC: Schnee, der am Tag fiel und schmolz, ist darin nicht, und ein Tag mit Neuschnee kann eine Höhe von 0 cm zeigen. Der Neuschnee ist ein eigener Wert, den nicht jede Station meldet; wo sie keinen hat, sagt die Antwort es.',
      },
      numbers: {
        station: 'Station: {name} ({id}).',
        day: 'Der Tag: {day}.',
        mean: 'Mittlerer Wind des Tages: {speed} {unit}, Beaufort-Stärke {force}.',
        gust: 'Stärkste Böe: {speed} {unit}, Beaufort-Stärke {force}.',
        scaleGust: 'Verwendete Skala, nach der Böe: ruhig unter Stärke {breezy}, leicht windig ab {breezy}, windig ab {windy}, stürmisch ab {stormy}.',
        scaleMean: 'Die Station hat für diesen Tag keine Böe, deshalb gilt das Mittel: ruhig unter Stärke {breezy}, leicht windig ab {breezy}, windig ab {windy}, stürmisch ab {stormy}.',
        around: 'In den Tagen drumherum (bis zu {days} nach beiden Seiten) haben {around} einen Wert, und {stronger} davon hatten einen stärkeren.',
        sunHours: 'Sonnenschein: {hours} h. Auf {latitude}° N konnte die Sonne an diesem Tag {possible} h scheinen, der Tag hatte also {share} der möglichen Sonnenscheindauer.',
        sunScale: 'Verwendete Skala: trüb unter {dull}, wechselhaft ab {dull}, sonnig ab {sunny} der möglichen Sonnenscheindauer.',
        rainAmount: 'Niederschlag des Tages: {amount} {unit}.',
        rainScale: 'Verwendete Skala: trocken unter {dry} {unit}, leicht ab {dry}, nass ab {wet}, sehr nass ab {veryWet} {unit}.',
        tempRange: 'Höchsttemperatur {max} {unit}, Tiefsttemperatur {min} {unit}.',
        tempClass: 'Der Tag zählt als: {kind}.',
        tempScale: 'Gezählte Tage: Ein Sommertag hat eine Höchsttemperatur ab {summer} {unit}, ein Heißer Tag ab {hot} {unit}, ein Eistag unter {ice} {unit}; ein Frosttag hat eine Tiefsttemperatur unter {frost} {unit}, eine Tropennacht ab {tropical} {unit}.',
        snowDepth: 'Schneehöhe: {depth} {unit}.',
        snowFresh: 'Neuschnee: {fresh} {unit}.',
        snowNoFresh: 'Die Station hat für diesen Tag keinen Wert für Neuschnee.',
        snowScale: 'Schnee gilt als liegend, wo die Höhe über {above} {unit} beträgt.',
        window: 'Das Diagramm zeigt bis zu {days} Tage nach beiden Seiten des Tages; {given} seiner Tage haben einen Wert.',
      },
      terms: {
        kind: { hot: 'Heißer Tag', summer: 'Sommertag', tropical: 'Tropennacht', ice: 'Eistag', frost: 'Frosttag' },
      },
    },

    download: {
      title: 'Wo kann ich stündliche Temperaturen herunterladen?',
      summary: 'Die Wetterdienste, deren Messungen wetterdienst im Stundenschritt mit der Lufttemperatur darin lesen kann.',
      data: 'Für diese Antwort werden keine Wetterdaten gelesen: Sie ist die Liste der Anbieter von wetterdienst und der Abdeckung, die jedes Messnetz für die stündliche Auflösung angibt.',
      steps: {
        providers: 'Die Liste der Anbieter wird vom Backend von wetterdienst gelesen, und nur ihre Messnetze (Art „observation“) werden angesehen.',
        coverage: 'Für jedes davon wird die Abdeckung der stündlichen Auflösung abgefragt, ein paar auf einmal. Ein Messnetz steht in der Liste, wenn es einen stündlichen Datensatz mit der Lufttemperatur in 2 m hat, zuerst der Datensatz namens temperature_air. Ein Messnetz ohne stündliche Daten antwortet, dass es keine hat, und fällt heraus.',
        order: 'Der DWD, der Wetterdienst des Landes des Ortes, steht zuerst, danach die anderen nach Namen in der Sprache der Seite. Jeder verweist in den Explorer auf diese Daten.',
      },
      formulas: {},
      rules: {
        'networks': {
          text: 'Nur Messnetze werden angesehen, keine Vorhersagen, kein Radar, keine Warnungen und keine abgeleiteten Daten.',
          reason: 'Die Frage gilt gemessenen Temperaturen. Das ist eine Wahl der App.',
        },
        'hourly-temperature': {
          text: 'Ein Messnetz zählt, wenn seine stündliche Abdeckung einen Parameter namens temperature_air_mean_2m oder temperature_air_2m hat.',
          says: 'Der Leitfaden der WMO sagt, die beobachtete Lufttemperatur solle für die freie Luft in einer Höhe von 1,25 bis 2 m über dem Boden repräsentativ sein.',
          reason: 'Das sind die Namen, die Anbieter der stündlichen Lufttemperatur in 2 m geben, wie wetterdienst sie führt; die Liste ist die der App, und was die Namen bedeuten, wird an der Abdeckung geprüft, nicht an einer Quelle.',
        },
        'order': {
          text: 'Der DWD steht zuerst, die anderen folgen in der Reihenfolge ihrer Namen.',
          reason: 'Die Orte der App sind DWD-Stationen, also ist der Dienst des DWD der des Ortes; der Rest steht alphabetisch, damit die Liste keinen Anbieter einstuft.',
        },
      },
      limits: {
        coverage: 'Ein Messnetz steht in der Liste, wenn das Backend sagt, dass es den Parameter im Stundenschritt hat; das ist kein Versprechen, dass jede Station oder jedes Jahr Werte hat.',
        definitions: 'Die stündlichen Temperaturen der Anbieter sind nicht alle dieselbe Art Zahl: Manche sind ein Wert zur vollen Stunde, andere das Mittel der Stunde. Sieh dir die Beschreibung des Anbieters an, bevor du sie vergleichst.',
        licences: 'Jeder Anbieter veröffentlicht seine Daten unter eigenen Bedingungen. Die Seite Anbieter und der Quellennachweis unter einer Antwort sagen, welchen.',
      },
      numbers: {
        count: '{count} Dienste wurden gefunden.',
        parameters: 'Die Abdeckung wurde nach den Parametern {names} durchsucht.',
      },
    },
  },

  works: {
    'wmo-8-i': {
      plain: `${WMO} Band I ihres Leitfadens Guide to Instruments and Methods of Observation ist das Handbuch für die Messung von Temperatur, Wind, Niederschlag und den anderen Größen. Hier liefert er die Beaufortskala der Windstärke, was ein Mittel des Windes ist, warum Böen wichtig sind was eine Spur Regen heißt, wie die Sonnenscheindauer definiert ist und wie ihre relative Form gelesen wird, und die Formeln für den Stand der Sonne, aus denen die Länge eines Tages folgt.`,
    },
    'wmo-1203': {
      plain: `${WMO} Ihre Richtlinien zur Berechnung von Klimanormalwerten (WMO Guidelines on the Calculation of Climate Normals) sagen, was ein Klimanormalwert ist, welche Zeiträume zählen, wie ein Normalwert aus Monatswerten entsteht und wie viele fehlende Daten erlaubt sind. Ein Normalwert ist der Durchschnitt über einen langen, festen Zeitraum, mit dem das aktuelle Wetter verglichen wird. Dreißig Jahre wurden vor allem deshalb zum Standard, weil bei der ersten Empfehlung nur dreißig Jahre Daten vorlagen. Hier liefern sie die Normalwerte, die gewählt werden können (den Referenz-Normalwert 1961 bis 1990 und die späteren), die Berechnung einer Jahreszeit, die Regeln für eine Station mit zu wenigen Jahren und ihre Liste der Tage, die die Normalwerte einer Station zählen: Tage mit einer bestimmten Niederschlagsmenge, mit einer Höchst- oder Tiefsttemperatur über oder unter einer Linie und mit Schnee auf dem Boden.`,
    },
    'dwd-seasons': {
      plain: `${DWD} Sein Wetterlexikon sagt, wie Meteorologen das Jahr teilen: Jede Jahreszeit sind drei volle Monate, weil die Statistiken des Klimas aus den Daten einzelner Monate gemacht werden.`,
    },
    'dwd-summer': {
      plain: `${DWD} In einem Artikel vom 20. Juni 2018 erklärt er, warum Juni, Juli und August der Sommer der Meteorologen sind, und dass der Grund statistisch ist: Volle Monate lassen sich leichter auswerten.`,
    },
    'dwd-monthly-kl': {
      plain: `${DWD} Die Beschreibung seines Datensatzes der Monatswerte sagt, woher die Monatswerte kommen: Sie werden aus den Tageswerten berechnet, und nur, wenn die Tageswerte des Monats vollständig sind. Sie bittet auch, Änderungen der Stationshöhe und der Beobachtungszeiten zu beachten.`,
    },
    'dwd-daily-kl': {
      plain: `${DWD} Die Beschreibung seines Datensatzes der Tageswerte nennt die Parameter und ihre Einheiten. Hier sagt sie, dass FX das Tagesmaximum der Windböe und FM das Tagesmittel der Windgeschwindigkeit ist, beide in m/s, und nennt die Sonnenscheindauer (SDK), die Niederschlagshöhe (RSK), die höchste und die niedrigste Temperatur in 2 m (TXK, TNK) und die Schneehöhe (SHK_TAG).`,
    },
    'dwd-daily-more-precip': {
      plain: `${DWD} Die Beschreibung seines Datensatzes der Tageswerte des Niederschlags nennt die Parameter und ihre Einheiten. Hier sagt sie, dass SH_TAG die Höhe der Schneedecke und NSH_TAG die Neuschneehöhe ist, beide in cm.`,
    },
    'dwd-kenntage': {
      plain: `${DWD} In einem Artikel vom 13. August 2025 erklärt er seine „Kenntage“, die Tage, an denen ein Schwellenwert eines meteorologischen Parameters erreicht oder überschritten wird, als zweiten Weg neben der Durchschnittstemperatur, eine Jahreszeit zu beurteilen. Er nennt den Sommertag (eine Höchsttemperatur von mindestens 25,0 °C), den Heißen Tag (30,0 °C), den Frosttag (eine Tiefsttemperatur unter 0,0 °C) und den Eistag (eine Höchsttemperatur unter 0,0 °C).`,
    },
    'dwd-tropennacht': {
      plain: `${DWD} Sein Wetterlexikon definiert die Tropennacht als Nacht, in der die Tiefsttemperatur der Luft 20 °C oder mehr beträgt, gemessen von 18 UTC bis 06 UTC, und sagt, dass es an den meisten seiner Stationen im Mittel weniger als eine im Jahr gibt.`,
    },
    'dwd-warnings': {
      plain: `${DWD} Er veröffentlicht die Kriterien seiner Wetterwarnungen. Für den Wind nennen sie für jede Warnstufe eine Böengeschwindigkeit in km/h und die zugehörige Stärke der Beaufortskala, in etwa 10 m Höhe über offenem Gelände.`,
    },
    'dwd-mosmix': {
      plain: `${DWD} MOSMIX ist seine Vorhersage für Orte: Sie nimmt die Vorhersagen von Wettermodellen und korrigiert sie statistisch mit dem, was Wetterstationen gemessen haben, weil jedes Modell den Boden vereinfacht und systematische Fehler hat.`,
    },
    'dwd-mosmix-elements': {
      plain: `${DWD} Das ist seine Liste der Elemente von MOSMIX mit Bedeutung und Einheit. Sie sagt zum Beispiel, dass RR1c der Gesamtniederschlag während der letzten Stunde ist und R101 die Wahrscheinlichkeit von mehr als 0,1 mm Niederschlag während der letzten Stunde.`,
    },
  },
}

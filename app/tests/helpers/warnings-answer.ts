/**
 * What the backend answers for `GET /api/alerts` (`dwd/alerts`, GH-4295), written out for the tests' fixtures: the `metadata` block with DWD's
 * terms and the entries of `alerts` in the shape of `DwdWeatherAlertResult.to_dict()`, as the community product has them: a MultiPolygon
 * `geometry` (the holes after the edge, `[longitude, latitude]` pairs) and, for a warning of the sea that has no polygon, a `null` one with its
 * `area_names` and `warncell_ids`. Times are relative to `now`, because the app judges what is in force by the clock.
 *
 * The fixture has texts in German (the first block of every message, which the `de` product holds alone), English (the `en` product, and a
 * translation of `mul`) and Polish (a translation of `mul`): a `language` the fixture has no text in answers with the English one.
 */

export interface AlertFixture {
  alert_id: string
  event: string
  event_code: string
  /** `Minor`, `Moderate`, `Severe` or `Extreme` */
  severity: string
  /** Hours from now that it begins at (negative: it has begun) */
  onsetHours: number
  /** Hours from now that it ends at, or null for no end */
  endHours: number | null
  /** Hours from now that it was issued at (negative) */
  sentHours: number
  area_names: string[]
  warncell_ids: string[]
  /** `[longitude, latitude]` rings of a MultiPolygon, or null for none */
  geometry: number[][][][] | null
  urgency?: string
  status?: string
  msg_type?: string
  /** The texts by language: `de`, `en`, `pl` */
  texts: Record<'de' | 'en' | 'pl', { event: string, headline: string, description: string, instruction: string }>
}

/** A closed ring round a box, `[west, south, east, north]` */
export function box(west: number, south: number, east: number, north: number): number[][] {
  return [[west, south], [east, south], [east, north], [west, north], [west, south]]
}

function texts(de: [string, string, string, string], en: [string, string, string, string], pl: [string, string, string, string]) {
  const one = ([event, headline, description, instruction]: [string, string, string, string]) => ({ event, headline, description, instruction })
  return { de: one(de), en: one(en), pl: one(pl) }
}

export const ALERTS: AlertFixture[] = [
  {
    alert_id: '2.49.0.0.276.0.DWD.PVW.1.WIND-KIEL.MUL',
    event: 'WINDBÖEN',
    event_code: '51',
    severity: 'Moderate',
    onsetHours: -1,
    endHours: 5,
    sentHours: -1.5,
    area_names: ['Stadt Kiel', 'Kreis Rendsburg-Eckernförde'],
    warncell_ids: ['801002000', '801058000'],
    // the land of the box minus a hole: a place in the hole is outside the warning
    geometry: [[box(9.6, 54.0, 10.6, 54.6), box(10.0, 54.25, 10.2, 54.35)]],
    texts: texts(
      ['WINDBÖEN', 'Amtliche WARNUNG vor WINDBÖEN', 'Es treten Windböen mit Geschwindigkeiten bis 65 km/h (18m/s, 35kn, Bft 8) aus westlicher Richtung auf.', 'ACHTUNG! Hinweis auf mögliche Gefahren: Es können einzelne Äste herabstürzen. Achten Sie auf herabfallende Gegenstände.'],
      ['wind gusts', 'Official WARNING of WIND GUSTS', 'There is a risk of wind gusts (level 2 of 4). Gusts up to 65 km/h (18m/s, 35kn, Bft 8) from westerly directions.', 'ATTENTION! Notice of possible danger: Single branches may fall. Beware of falling objects.'],
      ['porywy wiatru', 'Oficjalne OSTRZEŻENIE przed PORYWAMI WIATRU', 'Występują porywy wiatru do 65 km/h (18m/s, 35kn, Bft 8) z kierunków zachodnich.', 'UWAGA! Wskazówka o możliwych zagrożeniach: pojedyncze gałęzie mogą spadać.'],
    ),
  },
  {
    alert_id: '2.49.0.0.276.0.DWD.PVW.2.THUNDER-HAMBURG.MUL',
    event: 'GEWITTER',
    event_code: '31',
    severity: 'Severe',
    onsetHours: -0.5,
    endHours: 2,
    sentHours: -0.75,
    area_names: ['Freie und Hansestadt Hamburg', 'Kreis Herzogtum Lauenburg'],
    warncell_ids: ['802000000', '801053000'],
    // two parts, which are one warning
    geometry: [[box(9.7, 53.4, 10.3, 53.8)], [box(11.0, 53.5, 11.4, 53.7)]],
    texts: texts(
      ['GEWITTER', 'Amtliche UNWETTERWARNUNG vor GEWITTER', 'Es treten Gewitter auf. Dabei gibt es Sturmböen bis 80 km/h und Starkregen.', 'ACHTUNG! Hinweis auf mögliche Gefahren: Während des Gewitters können Blitzschläge auftreten. Suchen Sie Schutz in Gebäuden.'],
      ['thunderstorm', 'Official SEVERE WEATHER WARNING of THUNDERSTORM', 'Thunderstorms occur. Gale-force gusts up to 80 km/h and heavy rain accompany them.', 'ATTENTION! Notice of possible danger: Lightning strikes may occur during the thunderstorm. Seek shelter in buildings.'],
      ['burza', 'Oficjalne OSTRZEŻENIE PRZED NIEBEZPIECZNĄ POGODĄ: BURZA', 'Występują burze z porywami wiatru do 80 km/h i silnym deszczem.', 'UWAGA! Podczas burzy mogą wystąpić uderzenia pioruna. Szukaj schronienia w budynkach.'],
    ),
  },
  {
    alert_id: '2.49.0.0.276.0.DWD.PVW.3.FOG-BERLIN.MUL',
    event: 'NEBEL',
    event_code: '59',
    severity: 'Minor',
    onsetHours: -2,
    endHours: 4,
    sentHours: -2.25,
    area_names: ['Stadt Berlin'],
    warncell_ids: ['811000000'],
    geometry: [[box(13.0, 52.3, 13.8, 52.7)]],
    texts: texts(
      ['NEBEL', 'Amtliche WARNUNG vor NEBEL', 'Es tritt zeitweise Nebel mit Sichtweiten unter 150 Metern auf.', 'Hinweis auf: mögliche starke Sichteinschränkungen.\nHandlungsempfehlungen:\nFahrverhalten an plötzlich auftretende Sichtbehinderungen (Nebelbänke) anpassen'],
      ['fog', 'Official WARNING of FOG', 'There is a risk of fog (level 1 of 1).\nVisibility: < 150 m', 'Hazard(s) to expect: severely reduced visibility possible.\nRecommendations for what to do:\nAdapt your driving behaviour to sudden reduced visibility (fog banks).'],
      ['mgła', 'Oficjalne OSTRZEŻENIE przed MGŁĄ', 'Występuje okresami mgła z widocznością poniżej 150 metrów.', 'Wskazówka: możliwe silne ograniczenia widoczności.\nDostosuj sposób jazdy do nagłych ograniczeń widoczności (zamglenia).'],
    ),
  },
  {
    alert_id: '2.49.0.0.276.0.DWD.PVW.4.NEARGALE-COAST.MUL',
    event: 'STARKWIND',
    event_code: '14',
    severity: 'Minor',
    onsetHours: -3,
    endHours: 6,
    sentHours: -3.5,
    area_names: ['Ostfriesische Küste'],
    warncell_ids: ['501000001'],
    // no polygon: the community product names the sea only by its warn cell
    geometry: null,
    texts: texts(
      ['STARKWIND', 'Amtliche WARNUNG vor STARKWIND', 'Starkwind aus Südwest mit Windstärke 7 (Bft 7).', 'Hinweis auf: mögliche Gefahren für die Schifffahrt.'],
      ['near gale', 'Official NEAR GALE WARNING', 'Near gale from the southwest, force 7 on the Beaufort scale.', 'Notice of possible danger to shipping.'],
      ['silny wiatr', 'Oficjalne OSTRZEŻENIE przed SILNYM WIATREM', 'Silny wiatr z południowego zachodu, siła 7 w skali Beauforta.', 'Wskazówka o możliwych zagrożeniach dla żeglugi.'],
    ),
  },
  {
    alert_id: '2.49.0.0.276.0.DWD.PVW.5.PRELIM-MUNICH.MUL',
    event: 'VORABINFORMATION SCHWERES GEWITTER',
    event_code: '40',
    severity: 'Severe',
    urgency: 'Future',
    onsetHours: 2,
    endHours: 8,
    sentHours: -0.25,
    area_names: ['Stadt München'],
    warncell_ids: ['809162000'],
    geometry: [[box(11.2, 47.9, 11.9, 48.4)]],
    texts: texts(
      ['VORABINFORMATION SCHWERES GEWITTER', 'VORABINFORMATION UNWETTER: SCHWERES GEWITTER', 'Am Abend muss im Raum München mit schweren Gewittern gerechnet werden.', 'Verfolgen Sie die weitere Entwicklung der Warnlage.'],
      ['PRELIMINARY INFORMATION SEVERE THUNDERSTORMS', 'PRELIMINARY INFORMATION ON SEVERE WEATHER: SEVERE THUNDERSTORMS', 'Severe thunderstorms are expected in the Munich area in the evening.', 'Follow the further development of the warning situation.'],
      ['INFORMACJA WSTĘPNA O SILNYCH BURZACH', 'INFORMACJA WSTĘPNA: SILNE BURZE', 'Wieczorem w rejonie Monachium spodziewane są silne burze.', 'Śledź dalszy rozwój sytuacji ostrzegawczej.'],
    ),
  },
  {
    alert_id: '2.49.0.0.276.0.DWD.PVW.6.GLAZE-BLACKFOREST.MUL',
    event: 'GLATTEIS',
    event_code: '84',
    severity: 'Moderate',
    onsetHours: 3,
    endHours: 9,
    sentHours: -0.5,
    area_names: ['Landkreis Schwarzwald-Baar-Kreis'],
    warncell_ids: ['808326000'],
    geometry: [[box(8.2, 47.7, 8.9, 48.2)]],
    texts: texts(
      ['GLATTEIS', 'Amtliche WARNUNG vor GLATTEIS', 'Es tritt Glatteis durch gefrierenden Regen auf.', 'ACHTUNG! Hinweis auf mögliche Gefahren: Straßen und Gehwege können glatt sein.'],
      ['glaze', 'Official WARNING of GLAZE', 'Glaze occurs from freezing rain.', 'ATTENTION! Notice of possible danger: Roads and pavements may be slippery.'],
      ['gołoledź', 'Oficjalne OSTRZEŻENIE przed GOŁOLEDZIĄ', 'Występuje gołoledź z powodu marznącego deszczu.', 'UWAGA! Drogi i chodniki mogą być śliskie.'],
    ),
  },
]

/** The time as the backend writes it: ISO with microseconds and an offset */
export const stamp = (ms: number): string => `${new Date(ms).toISOString().replace('Z', '')}000+00:00`

const HOUR = 3_600_000

export interface AnswerOptions {
  /** The clock the times are relative to (default: now) */
  now?: number
  /** The product asked for: `de`, `en`, `es`, `fr` or `mul` (default `en`) */
  language?: string
  /** The warnings of the answer (default: {@link ALERTS}) */
  alerts?: AlertFixture[]
}

/** One alert as `to_dict` writes it, in the product's language; `mul` is German with the other languages as `translations` */
export function alertEntry(fixture: AlertFixture, now: number, language = 'en') {
  const base = {
    alert_id: fixture.alert_id,
    status: fixture.status ?? 'Actual',
    msg_type: fixture.msg_type ?? 'Alert',
    category: 'Met',
    event_code: fixture.event_code,
    groups: [],
    response_type: 'Prepare',
    urgency: fixture.urgency ?? 'Immediate',
    severity: fixture.severity,
    certainty: 'Likely',
    effective: stamp(now + fixture.sentHours * HOUR),
    onset: stamp(now + fixture.onsetHours * HOUR),
    expires: fixture.endHours === null ? null : stamp(now + fixture.endHours * HOUR),
    sent: stamp(now + fixture.sentHours * HOUR),
    sender_name: 'Deutscher Wetterdienst',
    web: 'https://dwd.de/warnungen',
    contact: 'Deutscher Wetterdienst',
    area_color: '255 235 59',
    parameters: [],
    warncell_ids: fixture.warncell_ids,
    area_names: fixture.area_names,
    geometry: fixture.geometry ? { type: 'MultiPolygon', coordinates: fixture.geometry } : null,
    references: null,
  }
  if (language === 'mul') {
    return {
      ...base,
      ...fixture.texts.de,
      language: 'de-DE',
      translations: [{ language: 'en', ...fixture.texts.en }, { language: 'pl', ...fixture.texts.pl }],
    }
  }
  const own = language === 'de' ? fixture.texts.de : fixture.texts.en
  return { ...base, ...own, language: language === 'de' ? 'de-DE' : language, translations: [] }
}

/** What the backend answers: the snapshot's alerts and the metadata block with DWD's terms */
export function alertsAnswer(options: AnswerOptions = {}) {
  const now = options.now ?? Date.now()
  const alerts = (options.alerts ?? ALERTS).map(fixture => alertEntry(fixture, now, options.language ?? 'en'))
  return {
    metadata: {
      api_version: '1',
      retrieved_at: stamp(now),
      data_updated_at: stamp(now - 0.25 * HOUR),
      provider: {
        name_local: 'Deutscher Wetterdienst',
        name_english: 'German Weather Service',
        country: 'Germany',
        copyright: '© Deutscher Wetterdienst (DWD), weather warnings (CAP)',
        url: 'https://opendata.dwd.de/weather/alerts/cap',
        license: { spdx_id: 'CC-BY-4.0', name: 'Creative Commons Attribution 4.0 International', url: 'https://creativecommons.org/licenses/by/4.0/' },
        attribution: 'Source: Deutscher Wetterdienst',
      },
      warnings: [],
    },
    snapshot: null,
    alerts,
  }
}

/** A snapshot of a quiet day: no warning in force anywhere */
export const emptyAlerts = (now = Date.now()) => alertsAnswer({ now, alerts: [] })

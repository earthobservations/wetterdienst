import { describe, expect, it } from 'vitest'
import { chipOf } from '../../app/utils/ask/registry'
import {
  areaColorOf,
  containsPoint,
  drawn,
  drawnOf,
  inWarningBox,
  LEVEL_STYLES,
  levelOfSeverity,
  locate,
  notOver,
  outlineContains,
  parseWarning,
  parseWarnings,
  phaseOf,
  productFor,
  sortWarnings,
  styleOf,
  textFor,
  warningsAt,
  withoutOutline,
  wordsOf,
} from '../../app/utils/warnings'
import { alertEntry, ALERTS, alertsAnswer, box, emptyAlerts } from '../helpers/warnings-answer'

// DWD's weather warnings (GH-4295): the level a CAP severity has, the warnings a snapshot holds and which are in force, the point in a
// polygon (a MultiPolygon, its holes, its edges), the product and the text a reader gets, and what is drawn. The warning is DWD's statement:
// these hold that the app places a position in a warning only by a polygon and never invents an outline for one that has none.

const NOW = Date.parse('2026-11-22T12:00:00Z')
const HOUR = 3_600_000
const snapshot = (language = 'en') => parseWarnings(alertsAnswer({ now: NOW, language }))

describe('the level of a severity', () => {
  it('is the one the CAP profile gives: Minor 1, Moderate 2, Severe 3, Extreme 4, in any case', () => {
    expect(['Minor', 'Moderate', 'Severe', 'Extreme'].map(levelOfSeverity)).toEqual([1, 2, 3, 4])
    expect(levelOfSeverity('severe')).toBe(3)
  })

  it('is none for what the profile does not list', () => {
    for (const other of ['Unknown', '', null, undefined, 3, 'Catastrophic'])
      expect(levelOfSeverity(other)).toBeNull()
  })

  it('has a style for each level that is told by its edge as well as by its colour', () => {
    const edges = [1, 2, 3, 4, 'preliminary', 'unknown'].map(key => LEVEL_STYLES[key as 1].dashArray === null ? `solid ${LEVEL_STYLES[key as 1].weight}` : LEVEL_STYLES[key as 1].dashArray)
    expect(new Set(edges).size).toBe(edges.length)
    // the level 4 is a double line, which no weight of a level 3 can be taken for
    expect(LEVEL_STYLES[4].double).toBe(true)
    expect([1, 2, 3, 'preliminary', 'unknown'].some(key => LEVEL_STYLES[key as 1].double)).toBe(false)
    expect(LEVEL_STYLES[4].weight - LEVEL_STYLES[3].weight).toBeGreaterThan(1.5)
    // the weight grows with the level
    const weights = [1, 2, 3, 4].map(level => LEVEL_STYLES[level as 1].weight)
    expect(weights).toEqual(weights.toSorted((a, b) => a - b))
  })
})

describe('reading the answer', () => {
  it('reads every warning of the snapshot, the most severe first', () => {
    const { warnings } = snapshot()
    expect(warnings).toHaveLength(6)
    expect(warnings.map(warning => warning.level)).toEqual([3, 3, 3, 2, 1, 1])
    expect(warnings[0]!.texts.en!.event).toBe('thunderstorm')
  })

  it('keeps the polygon of a warning, its holes included, and the box of it', () => {
    const kiel = snapshot().warnings.find(warning => warning.areaNames.includes('Stadt Kiel'))!
    expect(kiel.outline).toHaveLength(1)
    // the edge and one hole, as `[latitude, longitude]`
    expect(kiel.outline[0]).toHaveLength(2)
    expect(kiel.outline[0]![0]![0]).toEqual([54, 9.6])
    expect(kiel.box).toEqual({ south: 54, west: 9.6, north: 54.6, east: 10.6 })
  })

  it('keeps a warning with no geometry, with its area names and no outline', () => {
    const coast = snapshot().warnings.find(warning => warning.areaNames.includes('Ostfriesische Küste'))!
    expect(coast.outline).toEqual([])
    expect(coast.box).toBeNull()
    expect(coast.warncellIds).toEqual(['501000001'])
  })

  it('tells DWD\'s preliminary information by its urgency, and a severe warning of the same event code is a warning', () => {
    const kinds = Object.fromEntries(snapshot().warnings.map(warning => [warning.id.split('.').at(-2), warning.kind]))
    expect(kinds).toEqual({ 'WIND-KIEL': 'warning', 'THUNDER-HAMBURG': 'warning', 'FOG-BERLIN': 'warning', 'NEARGALE-COAST': 'warning', 'PRELIM-MUNICH': 'preliminary', 'GLAZE-BLACKFOREST': 'warning' })
    // GLATTEIS, code 85, which the preliminary information on glaze has too (§3.1.1, §3.1.2): a severe warning, level 3, in the colour of its level
    const glaze = snapshot().warnings.find(warning => warning.eventCode === '85')!
    expect(glaze).toMatchObject({ kind: 'warning', level: 3 })
    expect(styleOf(glaze)).toBe(LEVEL_STYLES[3])
  })

  it('tells the preliminary information by its German headline where the urgency is not Future, and by no event code at all', () => {
    const entry = alertEntry(ALERTS[0]!, NOW, 'de')
    for (const code of ['40', '55', '65', '75', '85', '89', '99'])
      expect(parseWarning({ ...entry, event_code: code })!.kind, code).toBe('warning')
    expect(parseWarning({ ...entry, urgency: 'Future' })!.kind).toBe('preliminary')
    expect(parseWarning({ ...entry, headline: 'VORABINFORMATION UNWETTER: SCHWERES GEWITTER' })!.kind).toBe('preliminary')
    expect(parseWarning({ ...entry, headline: 'Amtliche WARNUNG vor VORABINFORMATION' })!.kind).toBe('warning')
  })

  it('drops a message that ends an event early, the response type AllClear, with the Test and the Cancel', () => {
    const entry = alertEntry(ALERTS[0]!, NOW)
    expect(parseWarning({ ...entry, response_type: 'AllClear' })).toBeNull()
    expect(parseWarning({ ...entry, response_type: 'allclear' })).toBeNull()
    expect(parseWarning({ ...entry, response_type: 'Prepare' })).not.toBeNull()
    expect(parseWarnings({ ...alertsAnswer({ now: NOW }), alerts: [{ ...entry, response_type: 'AllClear' }, entry] }).warnings).toHaveLength(1)
  })

  it('reads a translation that carries only the fields in which it differs, with the German field for the rest', () => {
    const entry = { ...alertEntry(ALERTS[0]!, NOW, 'mul'), translations: [{ language: 'en', event: 'wind gusts', headline: 'Official WARNING of WIND GUSTS' }, { language: 'pl', instruction: 'UWAGA!' }] }
    const warning = parseWarning(entry)!
    // English has no description or instruction of its own: they are the German ones
    expect(warning.texts.en).toEqual({ event: 'wind gusts', headline: 'Official WARNING of WIND GUSTS', description: warning.texts.de!.description, instruction: warning.texts.de!.instruction })
    expect(warning.texts.pl).toMatchObject({ event: warning.texts.de!.event, instruction: 'UWAGA!' })
    // the answer of the backend sends no more than the differing fields
    const sent = alertEntry({ ...ALERTS[0]!, texts: { ...ALERTS[0]!.texts, en: { ...ALERTS[0]!.texts.de, headline: 'Official WARNING' } } }, NOW, 'mul')
    expect(sent.translations![0]).toEqual({ language: 'en', headline: 'Official WARNING' })
  })

  it('reads DWD\'s own colour of a message, and uses it for the heat and UV warnings only', () => {
    expect(areaColorOf('204 153 255')).toBe('#cc99ff')
    expect(areaColorOf('255 235 59')).toBe('#ffeb3b')
    for (const wrong of ['', null, '1 2', '1 2 3 4', '256 0 0', 'a b c', '1.5 2 3'])
      expect(areaColorOf(wrong), String(wrong)).toBeNull()
    const heat = parseWarning(alertEntry({ ...ALERTS[2]!, event_code: '247', severity: 'Moderate', areaColor: '204 153 255' }, NOW))!
    expect(heat.areaColor).toBe('#cc99ff')
    // the colour of DWD for it, with the edge of its level and a darker edge of the colour
    expect(styleOf(heat)).toMatchObject({ fill: '#cc99ff', dashArray: LEVEL_STYLES[2].dashArray, weight: LEVEL_STYLES[2].weight })
    expect(styleOf(heat).edge).toBe('#70548c')
    // an ordinary warning keeps the colour of its level, whatever AREA_COLOR it carries
    const fog = parseWarning(alertEntry({ ...ALERTS[2]!, areaColor: '1 2 3' }, NOW))!
    expect(styleOf(fog)).toBe(LEVEL_STYLES[1])
    // the health warning without a colour is drawn in its level's
    expect(styleOf(parseWarning(alertEntry({ ...ALERTS[2]!, event_code: '246', areaColor: 'x' }, NOW))!)).toBe(LEVEL_STYLES[1])
  })

  it('holds the texts of the product asked for, and the translations of `mul` beside the German one', () => {
    const [first] = snapshot('de').warnings
    expect(Object.keys(first!.texts)).toEqual(['de'])
    expect(first!.texts.de!.headline).toContain('UNWETTERWARNUNG')
    const multilingual = snapshot('mul').warnings[0]!
    expect(Object.keys(multilingual.texts).sort()).toEqual(['de', 'en', 'pl'])
    expect(multilingual.texts.pl!.event).toBe('burza')
  })

  it('drops a message of the status Test and a message that cancels others, which are no warning to show', () => {
    const entry = alertEntry(ALERTS[0]!, NOW)
    expect(parseWarning({ ...entry, status: 'Test' })).toBeNull()
    expect(parseWarning({ ...entry, msg_type: 'Cancel' })).toBeNull()
    expect(parseWarning({ ...entry, msg_type: 'Update' })).not.toBeNull()
    expect(parseWarning('nothing')).toBeNull()
    expect(parseWarning(null)).toBeNull()
  })

  it('reads the credit, the time of the answer and the server\'s clock from the metadata block', () => {
    const read = snapshot()
    expect(read.credit!.attribution).toBe('Source: Deutscher Wetterdienst')
    expect(read.credit!.license!.url).toBe('https://creativecommons.org/licenses/by/4.0/')
    expect(Date.parse(read.retrievedAt!)).toBe(NOW)
    expect(Date.parse(read.latestIssue!)).toBe(NOW - 0.25 * HOUR)
  })

  it('reads an empty list as a quiet day, which is a snapshot, and an answer with no list as a failure', () => {
    expect(parseWarnings(emptyAlerts(NOW)).warnings).toEqual([])
    expect(() => parseWarnings({ metadata: {} })).toThrow('no list of weather warnings')
    expect(() => parseWarnings('<html>')).toThrow()
  })

  it('leaves out a time that is no time', () => {
    const warning = parseWarning({ ...alertEntry(ALERTS[0]!, NOW), onset: 'soon', expires: null })!
    expect(warning.onset).toBeNull()
    expect(warning.expires).toBeNull()
  })
})

describe('what is in force', () => {
  const base = { onset: '2026-11-22T10:00:00+00:00', expires: '2026-11-22T14:00:00+00:00' }

  it('is a warning whose onset has come and whose end has not', () => {
    expect(phaseOf(base, NOW)).toBe('active')
    // the onset at the very moment is in force, the end at the very moment is over
    expect(phaseOf({ onset: '2026-11-22T12:00:00+00:00', expires: null }, NOW)).toBe('active')
    expect(phaseOf({ onset: base.onset, expires: '2026-11-22T12:00:00+00:00' }, NOW)).toBe('over')
  })

  it('is announced before its onset, over after its end', () => {
    expect(phaseOf({ onset: '2026-11-22T13:00:00+00:00', expires: base.expires }, NOW)).toBe('upcoming')
    expect(phaseOf({ onset: base.onset, expires: '2026-11-22T11:00:00+00:00' }, NOW)).toBe('over')
  })

  it('has no end for the event types that have none, and runs until DWD takes it out of the snapshot', () => {
    expect(phaseOf({ onset: base.onset, expires: null }, NOW + 40 * HOUR)).toBe('active')
    expect(phaseOf({ onset: null, expires: null }, NOW)).toBe('active')
  })

  it('leaves out a warning that has ended since the snapshot was made', () => {
    const { warnings } = snapshot()
    expect(notOver(warnings, NOW)).toHaveLength(6)
    // 4 hours on, the fog (ends in 4 h) and the wind gusts have gone with the thunderstorm
    const later = notOver(warnings, NOW + 4.5 * HOUR).map(warning => warning.texts.en!.event)
    expect(later).not.toContain('fog')
    expect(later).not.toContain('thunderstorm')
    expect(later).toContain('near gale')
  })

  it('orders the most severe level first, those in force before those announced, then by onset and by identifier', () => {
    const warnings = sortWarnings([
      { id: 'b', level: 2 as const, onset: '2026-11-22T10:00:00+00:00', expires: null },
      { id: 'a', level: 2 as const, onset: '2026-11-22T10:00:00+00:00', expires: null },
      { id: 'later', level: 2 as const, onset: '2026-11-22T15:00:00+00:00', expires: null },
      { id: 'severe', level: 3 as const, onset: '2026-11-22T16:00:00+00:00', expires: null },
      { id: 'none', level: null, onset: null, expires: null },
    ], NOW)
    expect(warnings.map(warning => warning.id)).toEqual(['severe', 'a', 'b', 'later', 'none'])
  })
})

describe('a point in a polygon', () => {
  // `[latitude, longitude]` as the app holds them: a square from 0,0 to 10,10
  const square: Array<[number, number]> = [[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]
  const hole: Array<[number, number]> = [[4, 4], [4, 6], [6, 6], [6, 4], [4, 4]]

  it('tells inside, on the edge and outside a ring', () => {
    expect(locate(square, 5, 5)).toBe('inside')
    expect(locate(square, 11, 5)).toBe('outside')
    expect(locate(square, 5, -0.1)).toBe('outside')
    // an edge, and a corner
    expect(locate(square, 0, 5)).toBe('edge')
    expect(locate(square, 5, 10)).toBe('edge')
    expect(locate(square, 10, 10)).toBe('edge')
  })

  it('holds a position on an edge to be inside the polygon', () => {
    expect(outlineContains([[square]], 0, 5)).toBe(true)
    expect(outlineContains([[square]], 10, 10)).toBe(true)
  })

  it('holds a position in a hole to be outside, and one on the edge of the hole to be inside', () => {
    const surface = [[square, hole]] as Array<Array<Array<[number, number]>>>
    expect(outlineContains(surface, 2, 2)).toBe(true)
    expect(outlineContains(surface, 5, 5)).toBe(false)
    expect(outlineContains(surface, 4, 5)).toBe(true)
    expect(outlineContains(surface, 6, 6)).toBe(true)
  })

  it('holds a position to be in a MultiPolygon if it is in any of its parts, a hole being of its own part', () => {
    const far: Array<[number, number]> = [[20, 20], [20, 30], [30, 30], [30, 20], [20, 20]]
    const parts = [[square, hole], [far]] as Array<Array<Array<[number, number]>>>
    expect(outlineContains(parts, 25, 25)).toBe(true)
    expect(outlineContains(parts, 5, 5)).toBe(false)
    expect(outlineContains(parts, 15, 15)).toBe(false)
    // the hole of the first part is no hole of the second: the second part holds a point in the same place
    expect(outlineContains([[square, hole], [[[3, 3], [3, 8], [8, 8], [8, 3], [3, 3]]]], 5, 5)).toBe(true)
  })

  it('holds a concave ring right: a point in its notch is outside', () => {
    const u: Array<[number, number]> = [[0, 0], [0, 9], [9, 9], [9, 6], [3, 6], [3, 3], [9, 3], [9, 0], [0, 0]]
    expect(outlineContains([[u]], 4.5, 7)).toBe(true)
    expect(outlineContains([[u]], 6, 4.5)).toBe(false)
  })

  it('is none for a warning with no polygon', () => {
    expect(containsPoint({ outline: [], box: null }, { latitude: 1, longitude: 1 })).toBe(false)
  })
})

describe('the warnings at a position', () => {
  const { warnings } = snapshot()
  const at = (latitude: number, longitude: number, now = NOW) => warningsAt(warnings, { latitude, longitude }, now).map(warning => warning.texts.en!.event)

  it('finds the warning a polygon of the snapshot contains', () => {
    // Kiel-Holtenau, in the box of the wind gusts and outside its hole
    expect(at(54.3776, 10.1424)).toEqual(['wind gusts'])
    // Berlin-Tempelhof
    expect(at(52.47, 13.4)).toEqual(['fog'])
  })

  it('does not find a warning for a position in its hole', () => {
    expect(at(54.3, 10.1)).toEqual([])
  })

  it('finds a warning by either of its parts', () => {
    expect(at(53.6, 10.0)).toEqual(['thunderstorm'])
    expect(at(53.6, 11.2)).toEqual(['thunderstorm'])
    expect(at(53.6, 10.6)).toEqual([])
  })

  it('finds a warning that is announced for later, in order after those in force, and not one that is over', () => {
    expect(at(47.9737, 8.5205)).toEqual(['glaze'])
    expect(at(48.16, 11.54)).toEqual(['PRELIMINARY INFORMATION SEVERE THUNDERSTORMS'])
    // after the glaze has ended
    expect(at(47.9737, 8.5205, NOW + 10 * HOUR)).toEqual([])
  })

  it('finds a position that two warnings contain with the more severe first', () => {
    const overlapping = [
      alertEntry({ ...ALERTS[2]!, alert_id: 'minor', severity: 'Minor', geometry: [[box(0, 0, 2, 2)]] }, NOW),
      alertEntry({ ...ALERTS[2]!, alert_id: 'extreme', severity: 'Extreme', geometry: [[box(1, 1, 3, 3)]] }, NOW),
    ].map(entry => parseWarning(entry)!)
    expect(warningsAt(overlapping, { latitude: 1.5, longitude: 1.5 }, NOW).map(warning => warning.id)).toEqual(['extreme', 'minor'])
  })

  it('never places a warning that has no polygon, and lists it apart', () => {
    expect(at(53.7, 7.2)).toEqual([])
    expect(withoutOutline(warnings, NOW).map(warning => warning.areaNames[0])).toEqual(['Ostfriesische Küste'])
    expect(drawn(warnings, NOW)).toHaveLength(5)
  })

  it('is empty for a snapshot of a quiet day', () => {
    expect(warningsAt([], { latitude: 54, longitude: 10 }, NOW)).toEqual([])
  })
})

describe('where DWD warns', () => {
  it('has the box of the network: Germany and the sea round it', () => {
    expect(inWarningBox({ latitude: 54.3776, longitude: 10.1424 })).toBe(true)
    expect(inWarningBox({ latitude: 48.16, longitude: 11.54 })).toBe(true)
    // Madrid, New York, and the Hamburg of a typo
    expect(inWarningBox({ latitude: 40.4, longitude: -3.7 })).toBe(false)
    expect(inWarningBox({ latitude: 40.78, longitude: -73.97 })).toBe(false)
    expect(inWarningBox({ latitude: 70.93, longitude: -8.67 })).toBe(false)
  })
})

describe('the language of the texts', () => {
  it('asks the product DWD writes in the language of the page: its own for English, Spanish and French, `mul` for Polish', () => {
    expect(productFor('en-GB')).toEqual({ product: 'en', language: 'en' })
    expect(productFor('es-ES')).toEqual({ product: 'es', language: 'es' })
    expect(productFor('fr')).toEqual({ product: 'fr', language: 'fr' })
    expect(productFor('pl-PL')).toEqual({ product: 'mul', language: 'pl' })
    expect(productFor('de-DE')).toEqual({ product: 'de', language: 'de' })
    expect(productFor('en')).toEqual({ product: 'en', language: 'en' })
  })

  it('asks the German product, DWD\'s own text, for a language DWD does not write in', () => {
    for (const locale of ['cs-CZ', 'da-DK', 'it-IT', 'nl-NL', 'lb-LU', 'de-hh', 'ja'])
      expect(productFor(locale)).toEqual({ product: 'de', language: 'de' })
  })

  it('gives the text in the language of the page where the warning has it', () => {
    const warning = snapshot('mul').warnings[0]!
    expect(textFor(warning, 'pl-PL')).toMatchObject({ language: 'pl', inLocale: true })
    expect(textFor(warning, 'pl').text.event).toBe('burza')
    expect(textFor(warning, 'en-GB').text.event).toBe('thunderstorm')
  })

  it('gives the German text, and says it is not in the language of the page, where the warning has none', () => {
    const warning = snapshot('de').warnings[0]!
    const found = textFor(warning, 'cs-CZ')
    expect(found).toMatchObject({ language: 'de', inLocale: false })
    expect(found.text.headline).toBe('Amtliche UNWETTERWARNUNG vor GEWITTER')
    expect(textFor(warning, 'de-DE').inLocale).toBe(true)
    expect(textFor(warning, 'de').inLocale).toBe(true)
  })

  it('says the text is German, not the language of the page, for every locale whose text is the German original except German itself: Low German and Luxembourgish too', () => {
    const warning = snapshot('de').warnings[0]!
    for (const locale of ['de-hh', 'lb', 'cs', 'da', 'it', 'nl'])
      expect(textFor(warning, locale), locale).toMatchObject({ language: 'de', inLocale: false })
    // Polish has a text of its own where the product has it
    const multilingual = snapshot('mul').warnings[0]!
    expect(textFor(multilingual, 'pl')).toMatchObject({ language: 'pl', inLocale: true })
    expect(textFor(multilingual, 'de-hh')).toMatchObject({ language: 'de', inLocale: false })
  })

  it('quotes DWD\'s words as they are, with their line breaks, and rewrites none', () => {
    const fog = snapshot('en').warnings.find(warning => warning.eventCode === '59')!
    const words = wordsOf(fog, key => key, 'en', 'en-GB', NOW)
    expect(words.text.description).toBe('There is a risk of fog (level 1 of 1).\nVisibility: < 150 m')
    expect(words.text.instruction).toContain('\nRecommendations for what to do:\n')
    expect(words.title).toBe('fog')
  })
})

describe('what the map draws', () => {
  it('draws the warnings that have a polygon, the weakest first, and the one opened with its emphasis', () => {
    const { warnings } = snapshot()
    const everything = drawnOf(warnings, null)
    expect(everything).toHaveLength(5)
    expect(everything.map(warning => warning.focused)).toEqual([false, false, false, false, false])
    const levels = warnings.filter(warning => warning.outline.length).toSorted((a, b) => (a.level ?? 0) - (b.level ?? 0)).map(warning => warning.id)
    expect(everything.map(warning => warning.id)).toEqual(levels)
    const focused = drawnOf(warnings, warnings[0]!.id).filter(warning => warning.focused)
    expect(focused.map(warning => warning.id)).toEqual([warnings[0]!.id])
  })

  it('gives the preliminary information a style of its own', () => {
    const { warnings } = snapshot()
    const preliminary = drawnOf(warnings, null).find(warning => warning.id.includes('PRELIM'))!
    expect(preliminary.style).toBe(LEVEL_STYLES.preliminary)
  })
})

describe('the question "Are there warnings here?"', () => {
  const chip = chipOf('warnings')!
  const KIEL = { id: '02564', name: 'Kiel-Holtenau', latitude: 54.3776, longitude: 10.1424 }
  const context = (place = KIEL) => ({ place, choices: {}, now: () => ({ toMillis: () => NOW }) as never, formatLanguage: 'en-GB', locale: 'en', unitTarget: () => 'x' })
  const loaded = (language = 'en') => ({ snapshot: snapshot(language), locale: language, formatLanguage: 'en-GB' })

  it('says that a warning of DWD has the place in an area, quotes it, and counts what has no area', () => {
    const answer = chip.answer(loaded(), context()) as { here: unknown[], namedOnly: number, total: number }
    expect(answer.here).toHaveLength(1)
    expect(answer.namedOnly).toBe(1)
    expect(answer.total).toBe(6)
  })

  it('says no for a place that no polygon contains, and quotes nothing', () => {
    const answer = chip.answer(loaded(), context({ ...KIEL, latitude: 50.2, longitude: 9.1 }))
    expect((answer as { here: unknown[] }).here).toEqual([])
  })

  it('has no answer outside the box of DWD, where nothing was fetched: the question says no source covers the place', () => {
    expect(chip.answer({ snapshot: null, locale: 'en', formatLanguage: 'en-GB' }, context({ id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 }))).toBeNull()
  })

  it('does not fetch for a place outside the box of DWD', async () => {
    let asked = 0
    const api = {
      async alerts() {
        asked++
        return snapshot()
      },
    } as never
    const found = await chip.load({ ...context({ id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 }) }, api) as { snapshot: unknown }
    expect(found.snapshot).toBeNull()
    expect(asked).toBe(0)
  })

  it('asks the product of the language of the page', async () => {
    const asked: string[] = []
    const api = {
      async alerts(product: string) {
        asked.push(product)
        return snapshot()
      },
    } as never
    // by the app's own locale: Low German is formatted as German and is asked for as German, and told so
    const locales: Array<[string, string]> = [['pl', 'pl-PL'], ['cs', 'cs-CZ'], ['es', 'es-ES'], ['de-hh', 'de-DE'], ['lb', 'lb-LU']]
    for (const [locale, formatLanguage] of locales)
      await chip.load({ ...context(), locale, formatLanguage }, api)
    expect(asked).toEqual(['mul', 'de', 'es', 'de', 'de'])
  })

  it('is no judgement: it says what DWD says, its words unchanged, and never says what to do or that there is nothing to fear', () => {
    const answer = chip.answer(loaded(), context())!
    const env = { t: (key: string, params?: Record<string, string | number>) => `${key}${params ? JSON.stringify(params) : ''}`, place: KIEL, number: String, percent: String, unitText: String, dayText: String, now: () => ({ toMillis: () => NOW }) as never }
    const view = chip.present(answer, loaded(), env as never, {})
    expect(view.verdict).toBe('ask.warnings.some{"place":"Kiel-Holtenau"}')
    const [quote] = view.quotes!
    expect(quote!.heading).toBe('wind gusts')
    expect(quote!.paragraphs).toEqual([
      'Official WARNING of WIND GUSTS',
      'There is a risk of wind gusts (level 2 of 4). Gusts up to 65 km/h (18m/s, 35kn, Bft 8) from westerly directions.',
      'ATTENTION! Notice of possible danger: Single branches may fall. Beware of falling objects.',
    ])
    expect(quote!.lang).toBe('en')
    expect(quote!.note).toBe('')
    // the facts are the level, when it is in force and when it was issued: no advice, no rating of ours
    expect(quote!.facts.join(' ')).toContain('warnings.level.2')
    expect(view.note).toContain('ask.warnings.quote')
    expect(view.note).toContain('ask.warnings.namedOnly')
  })

  it('says it quotes German where DWD has no text in the language of the page', () => {
    const german = { snapshot: snapshot('de'), locale: 'cs', formatLanguage: 'cs-CZ' }
    const env = { t: (key: string) => key, place: KIEL, number: String, percent: String, unitText: String, dayText: String, now: () => ({ toMillis: () => NOW }) as never }
    const view = chip.present(chip.answer(german, context())!, german, env as never, {})
    expect(view.quotes![0]!.lang).toBe('de')
    expect(view.quotes![0]!.note).toBe('warnings.textGerman')
  })

  it('says the German text with the note for Low German and Luxembourgish too, which are formatted as German', () => {
    for (const locale of ['de-hh', 'lb']) {
      const german = { snapshot: snapshot('de'), locale, formatLanguage: 'de-DE' }
      const env = { t: (key: string) => key, place: KIEL, number: String, percent: String, unitText: String, dayText: String, now: () => ({ toMillis: () => NOW }) as never }
      const view = chip.present(chip.answer(german, context())!, german, env as never, {})
      expect(view.quotes![0]!.note, locale).toBe('warnings.textGerman')
    }
  })

  it('judges what is in force by the server\'s clock: a device that is behind is corrected by the skew of the answer', () => {
    // a warning that ended an hour before the server's NOW; the device is two hours behind
    const ended = parseWarnings(alertsAnswer({ now: NOW, alerts: [{ ...ALERTS[0]!, onsetHours: -5, endHours: -1 }] }))
    const early = { ...context(), now: () => ({ toMillis: () => NOW - 2 * HOUR }) as never }
    // by the device's clock alone it is still in force
    expect((chip.answer({ ...loaded(), snapshot: { ...ended, clockSkewMs: 0 } }, early) as { here: unknown[] }).here).toHaveLength(1)
    // by the server's, which the skew of the answer gives, it is over
    expect((chip.answer({ ...loaded(), snapshot: { ...ended, clockSkewMs: 2 * HOUR } }, early) as { here: unknown[] }).here).toHaveLength(0)
  })

  it('has every rule as DWD\'s CAP profile or as its own, and leads into the map with the warnings on at the place', () => {
    expect(chip.explanation.rules.every(rule => rule.own === true || rule.cites.length > 0)).toBe(true)
    expect(chip.tool).toBe('map')
    const [action] = chip.actions({ place: KIEL, t: (key: string) => key } as never, {}, null)
    expect(action!.to).toEqual({ path: '/map', query: { warnings: '1', lat: '54.3776', lon: '10.1424' } })
  })
})

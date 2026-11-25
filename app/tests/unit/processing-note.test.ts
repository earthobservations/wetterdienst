import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { processingNote } from '../../app/utils/processing-note'

// The note of what wetterdienst did to the data, which the app writes in the language of the page next to the provider's
// credit line (GH-3799). The backend says the same in English in `metadata.processing_note`
// (src/wetterdienst/model/processing_note.py); the app's English text is held to it here, so that the two do not drift.

const LOCALES = join(__dirname, '..', '..', 'i18n', 'locales')
const BACKEND = join(__dirname, '..', '..', '..', 'src', 'wetterdienst', 'model', 'processing_note.py')

interface Catalog { processingNote: { base: string, estimate: string, radar: string } }
const catalog = (code: string) => JSON.parse(readFileSync(join(LOCALES, `${code}.json`), 'utf8')) as Catalog

const RADAR_BACKEND = join(__dirname, '..', '..', '..', 'src', 'wetterdienst', 'provider', 'dwd', 'radar', 'frames.py')

/** The text of a string constant of the Python module: the adjacent literals of `NAME = ( "a" "b" )` or `NAME = "a"`, joined */
function backendConstant(name: string, file: string = BACKEND): string {
  const source = readFileSync(file, 'utf8')
  const start = source.search(new RegExp(`^${name} = `, 'm'))
  expect(start, `${name} is a constant of processing_note.py`).toBeGreaterThanOrEqual(0)
  const statement = source.slice(start).split(/\n\s*\n|\n(?=[A-Z#])/i, 1)[0]!.replace(/^\w+ = /, '')
  const literals = [...statement.matchAll(/"((?:[^"\\]|\\.)*)"/g)].map(match => JSON.parse(`"${match[1]}"`) as string)
  expect(literals.length, `${name} is a string`).toBeGreaterThan(0)
  return literals.join('')
}

describe('the English text of the note', () => {
  it('is the backend\'s sentence for every answer with provider data', () => {
    expect(catalog('en').processingNote.base).toBe(backendConstant('PROCESSING_NOTE'))
  })

  it('and its sentence for values that were selected or calculated from the readings', () => {
    expect(catalog('en').processingNote.estimate).toBe(backendConstant('DERIVED_NOTE'))
  })

  it('and its sentence for the frames of the precipitation radar (GH-3788)', () => {
    expect(catalog('en').processingNote.radar).toBe(backendConstant('RADAR_FRAMES_NOTE', RADAR_BACKEND))
  })
})

describe('the note in every locale', () => {
  const codes = readdirSync(LOCALES).filter(file => file.endsWith('.json')).map(file => file.replace('.json', ''))

  it('is there in all eleven', () => {
    expect(codes.sort()).toEqual(['cs', 'da', 'de', 'de-hh', 'en', 'es', 'fr', 'it', 'lb', 'nl', 'pl'])
  })

  it.each(codes)('is two sentences of its own in %s, both naming the tool', (code) => {
    const { base, estimate } = catalog(code).processingNote
    expect(base.trim()).toBe(base)
    expect(estimate.trim()).toBe(estimate)
    expect(base).toContain('wetterdienst')
    expect(base.length).toBeGreaterThan(40)
    expect(estimate.length).toBeGreaterThan(20)
    // one sentence each, ending in a full stop
    expect(base.endsWith('.')).toBe(true)
    expect(estimate.endsWith('.')).toBe(true)
    // and the sentence of the radar's frames (GH-3788): two sentences, as the backend's
    const { radar } = catalog(code).processingNote
    expect(radar.trim()).toBe(radar)
    expect(radar.length).toBeGreaterThan(100)
    expect(radar.endsWith('.')).toBe(true)
  })

  it.each(codes.filter(code => code !== 'en'))('is not the English text in %s', (code) => {
    const english = catalog('en').processingNote
    expect(catalog(code).processingNote.base).not.toBe(english.base)
    expect(catalog(code).processingNote.estimate).not.toBe(english.estimate)
    expect(catalog(code).processingNote.radar).not.toBe(english.radar)
  })
})

describe('processingNote', () => {
  const t = (key: string) => ({ 'processingNote.base': 'Base.', 'processingNote.estimate': 'Estimate.', 'processingNote.radar': 'Radar.' }[key] ?? key)

  it('is the base sentence for provider data', () => {
    expect(processingNote(t)).toBe('Base.')
  })

  it('adds the sentence for estimated values', () => {
    expect(processingNote(t, true)).toBe('Base. Estimate.')
  })

  it('adds what was done to the frames of the radar, which is not what was done to a table', () => {
    expect(processingNote(t, false, true)).toBe('Base. Radar.')
    expect(processingNote(t, true, true)).toBe('Base. Estimate. Radar.')
  })
})

import { describe, expect, it } from 'vitest'
import { AXIS_STOPS, NOW_AT, pageOfPath, REFERENCE_PAGES, zoneOfPage } from '../../app/composables/useTimeAxis'
import { normalizeSearch, rankEntries, searchScore, stepIndex } from '../../app/utils/palette'

// What the command palette finds (GH-3518), and the axis of time it jumps along.

describe('the search of the command palette', () => {
  it('ignores case and accents, as a station is written either way', () => {
    expect(normalizeSearch('  München ')).toBe('munchen')
    expect(normalizeSearch('Český')).toBe('cesky')
    expect(normalizeSearch('Großer Arber')).toBe('grosser arber')
  })

  it('needs every word of the query, in the label, the description or the keywords', () => {
    const entry = { label: 'Hamburg-Fuhlsbüttel', description: '10147 · Hamburg', keywords: '10147' }
    expect(searchScore(entry, 'fuhls')).not.toBeNull()
    expect(searchScore(entry, 'hamburg 10147')).not.toBeNull()
    expect(searchScore(entry, 'hamburg berlin')).toBeNull()
    expect(searchScore(entry, '')).toBe(0)
  })

  it('ranks a label that starts with the query first, then a word of it, keeping the order among equals', () => {
    const entries = [
      { label: 'Next 10 days', description: 'Forecast' },
      { label: 'Forecast' },
      { label: 'Weather forecast for a station' },
      { label: 'Climate stripes', description: 'Every year' },
    ]
    expect(rankEntries(entries, 'forecast').map(entry => entry.label)).toEqual(['Forecast', 'Weather forecast for a station', 'Next 10 days'])
    expect(rankEntries(entries, '', 2).map(entry => entry.label)).toEqual(['Next 10 days', 'Forecast'])
  })

  it('moves the active option round at either end, and has none in an empty list', () => {
    expect(stepIndex(-1, 1, 3)).toBe(0)
    expect(stepIndex(-1, -1, 3)).toBe(2)
    expect(stepIndex(2, 1, 3)).toBe(0)
    expect(stepIndex(0, -1, 3)).toBe(2)
    expect(stepIndex(0, 1, 0)).toBe(-1)
  })
})

describe('the axis of time', () => {
  it('lays the pages out from the oldest records to the forecast, with the present between', () => {
    expect(AXIS_STOPS.map(stop => stop.zone)).toEqual(['then', 'then', 'then', 'now', 'next'])
    for (const stop of AXIS_STOPS) {
      expect(stop.from).toBeGreaterThanOrEqual(0)
      expect(stop.to).toBeLessThanOrEqual(100)
      expect(stop.from).toBeLessThanOrEqual(stop.to)
    }
    // the past ends at the present, the forecast starts there
    expect(AXIS_STOPS.filter(stop => stop.zone === 'then').every(stop => stop.to <= NOW_AT)).toBe(true)
    expect(AXIS_STOPS.find(stop => stop.zone === 'next')!.from).toBe(NOW_AT)
  })

  it('knows the page of every path of the app, the page of a provider and the alias of the privacy policy too', () => {
    expect(pageOfPath('/')).toBe('now')
    expect(pageOfPath('/stripes')).toBe('stripes')
    expect(pageOfPath('/meteogram')).toBe('forecast')
    expect(pageOfPath('/explorer/')).toBe('explorer')
    expect(pageOfPath('/providers/dwd')).toBe('providers')
    expect(pageOfPath('/privacy')).toBe('datenschutz')
    expect(pageOfPath('/widget')).toBeNull()
    expect(pageOfPath('/api-docs')).toBeNull()
  })

  it('puts the pages that are no time off the axis', () => {
    expect(zoneOfPage('forecast')).toBe('next')
    expect(zoneOfPage('now')).toBe('now')
    for (const page of REFERENCE_PAGES)
      expect(zoneOfPage(page.key)).toBe('reference')
    expect(zoneOfPage(null)).toBeNull()
  })
})

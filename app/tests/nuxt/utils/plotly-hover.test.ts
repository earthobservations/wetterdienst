import Plotly from 'plotly.js-basic-dist-min'
import { afterEach, describe, expect, it } from 'vitest'
import { plotlyDateLocale, plotlyHoverFormat } from '~/utils/format'

// The heading of the Meteogram's hover, written by the real Plotly (the component tests record its
// calls): Thursday the 15th of October 2026, 14:00, in the language of each locale of the app. Plotly's
// basic bundle knows no language but English unless it is given one (GH-3051).
describe('hover heading of the time axis', () => {
  let chart: HTMLElement | undefined
  afterEach(() => {
    if (chart)
      Plotly.purge(chart)
    chart?.remove()
    chart = undefined
  })

  async function heading(language?: string) {
    chart = document.body.appendChild(document.createElement('div'))
    await Plotly.newPlot(
      chart,
      [{ x: ['2026-10-15T14:00:00Z', '2026-10-15T15:00:00Z'], y: [1, 2], type: 'scatter' }],
      { width: 400, height: 300, hovermode: 'x unified', xaxis: { type: 'date', hoverformat: language ? plotlyHoverFormat(language) : '%a %d.%m %H:%M' } },
      language ? { locale: language, locales: { [language]: plotlyDateLocale(language) } } : {},
    )
    // the basic bundle has the hover, which its typings leave out
    ;(Plotly as unknown as { Fx: { hover: (...args: unknown[]) => void } }).Fx.hover(chart, { xval: Date.parse('2026-10-15T14:00:00Z') }, 'xy')
    // the heading, then the value of the one trace
    return chart.querySelector('.hoverlayer')?.textContent
  }

  // the language tags of the app's locales (nuxt.config.ts); `de-hh` is written as German
  it.each([
    ['en', 'en-GB', 'Thu 15/10 14:00'],
    ['de', 'de-DE', 'Do 15.10. 14:00'],
    ['de-hh', 'de-DE', 'Do 15.10. 14:00'],
    ['fr', 'fr-FR', 'jeu. 15/10 14:00'],
    ['es', 'es-ES', 'jue 15/10 14:00'],
    ['it', 'it-IT', 'gio 15/10 14:00'],
    ['nl', 'nl-NL', 'do 15-10 14:00'],
    ['pl', 'pl-PL', 'czw. 15.10 14:00'],
    ['cs', 'cs-CZ', 'čt 15. 10. 14:00'],
    ['da', 'da-DK', 'tors. 15.10 14:00'],
    ['lb', 'lb-LU', 'Don 15.10. 14:00'],
  ])('is written in %s as %s', async (_code, language, expected) => {
    expect(await heading(language)).toMatch(new RegExp(`^${expected.replace(/[.\\^$*+?()[\]{}|]/g, '\\$&')}`))
  })

  it('is English, whatever the language, where Plotly is given none', async () => {
    expect(await heading()).toMatch(/^Thu 15\.10 14:00/)
  })
})

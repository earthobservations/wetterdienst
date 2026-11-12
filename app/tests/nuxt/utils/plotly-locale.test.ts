import Plotly from 'plotly.js-basic-dist-min'
import { afterEach, describe, expect, it } from 'vitest'
import { plotlyLocaleConfig, plotlyText } from '~/utils/plotly-locale'

// The modebar's button names as the real Plotly writes them with the config of utils/plotly-locale.ts (the
// component tests record the calls only): the language of the page reaches the buttons (GH-3625)
describe('plotly modebar in the language of the page', () => {
  let chart: HTMLElement | undefined
  afterEach(() => {
    if (chart)
      Plotly.purge(chart)
    chart?.remove()
    chart = undefined
  })

  const camera = (title: string, plotly = Plotly) => ({
    name: 'toImage',
    title,
    icon: plotly.Icons.camera,
    click: () => {},
  })
  const traces = [{ x: [1, 2], y: [1, 2], type: 'scatter' as const }]
  const titles = () => [...chart!.querySelectorAll('.modebar-btn')].map(button => button.getAttribute('data-title'))

  async function draw(code: string, language: string, redraw = false) {
    chart ??= document.body.appendChild(document.createElement('div'))
    const locale = await plotlyLocaleConfig(code, language)
    const config = { ...locale, displayModeBar: true, modeBarButtonsToRemove: ['toImage' as const], modeBarButtonsToAdd: [camera(plotlyText(locale, 'Download plot as a PNG'))] }
    await (redraw ? Plotly.react : Plotly.newPlot)(chart, traces, { width: 400, height: 300 }, config as never)
  }

  it('writes the buttons in German, the camera the app adds among them', async () => {
    await draw('de', 'de-DE')
    expect(titles()).toEqual(expect.arrayContaining(['Verschieben', 'Achsen zurücksetzen']))
    expect(titles()).toContain('Graphen als PNG herunterladen')
  })

  it('writes the buttons in English where the page is', async () => {
    await draw('en', 'en-GB')
    expect(titles()).toEqual(expect.arrayContaining(['Pan', 'Reset axes', 'Download plot as a PNG']))
  })

  it('writes Luxembourgish\'s buttons in German', async () => {
    await draw('lb', 'lb-LU')
    expect(titles()).toContain('Verschieben')
  })

  it('follows a language switch of a chart that is drawn again with `react`, as the faceted charts are', async () => {
    await draw('en', 'en-GB')
    expect(titles()).toContain('Pan')
    await draw('de', 'de-DE', true)
    expect(titles()).toContain('Verschieben')
    expect(titles()).not.toContain('Pan')
  })
})

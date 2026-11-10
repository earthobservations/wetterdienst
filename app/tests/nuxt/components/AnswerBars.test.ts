import type { Bar } from '~/utils/answers'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import AnswerBars from '~/components/AnswerBars.vue'

// The value labels of the answers' bar chart (GH-3893): beside the plot and not beside the year labels under it,
// and a 0 at the line the bars hang from. The year labels depend on the width of the plot, which a test
// environment has no layout for: their choice is held by tests/unit/axis-labels.test.ts and their boxes by the
// e2e spec of the answers.

const summers = [-3.4, -1.2, 0.4, 1.7, -0.6, 0.9].map((value, index) => ({
  key: String(2021 + index),
  label: String(2021 + index),
  at: 2021 + index,
  value,
  highlight: index === 5,
}))

async function mountBars(props: { bars: Bar[], diverging?: boolean }) {
  const wrapper = await mountSuspended(AnswerBars, { props: { caption: 'Each summer', unit: '°C', ...props } })
  const part = (id: string) => wrapper.get(`[data-testid="answer-bars-${id}"]`)
  const rem = (element: { attributes: (name: string) => string | undefined }) => Number.parseFloat(/top: ([\d.]+)rem/.exec(element.attributes('style') ?? '')?.[1] ?? 'NaN')
  return { wrapper, part, rem }
}

describe('answerBars value labels', () => {
  it('put the lower one in the height of the plot, on the row of the plot and not on the row of the year labels', async () => {
    const { part, rem } = await mountBars({ bars: summers, diverging: true })
    const values = part('values')
    const plot = part('plot')
    // one row, one height: the column of the values is as high as the plot, and the year labels are another row
    expect(values.element.parentElement).toBe(plot.element.parentElement)
    expect(values.attributes('style')).toContain('height: 9rem')
    expect(plot.attributes('style')).toContain('height: 9rem')
    expect(part('labels').element.parentElement).toBe(plot.element.parentElement)
    expect(values.element.contains(part('labels').element)).toBe(false)
    const bottom = values.get('[data-kind="bottom"]')
    expect(bottom.text()).toMatch(/^-3[.,]4 °C$/)
    // the label's line is the last rem of the plot's nine
    expect(rem(bottom) + 1).toBe(9)
    expect(rem(values.get('[data-kind="top"]'))).toBe(0)
    expect(values.get('[data-kind="top"]').text()).toMatch(/^1[.,]7 °C$/)
  })

  it('write a 0 at the line the bars hang from, when diverging', async () => {
    const { part, rem } = await mountBars({ bars: summers, diverging: true })
    const zero = part('values').get('[data-kind="zero"]')
    expect(zero.text()).toBe('0 °C')
    const line = Number.parseFloat(/top: ([\d.]+)%/.exec(part('zero').attributes('style') ?? '')?.[1] ?? 'NaN')
    // 1.7 of 5.1 down the plot; the label is centred on the line
    expect(line).toBeCloseTo((1.7 / 5.1) * 100, 6)
    expect(rem(zero) + 0.5).toBeCloseTo((line / 100) * 9, 6)
  })

  it('write no 0 at a line for bars that stand on the bottom, which are 0 at the bottom', async () => {
    const { part } = await mountBars({ bars: summers.map(bar => ({ ...bar, value: Math.abs(bar.value) })), diverging: false })
    const values = part('values')
    expect(values.find('[data-kind="zero"]').exists()).toBe(false)
    expect(values.get('[data-kind="bottom"]').text()).toBe('0 °C')
    expect(part('plot').find('[data-testid="answer-bars-zero"]').exists()).toBe(false)
  })

  it('always write the label of the bar asked about, and keep the table of the values whole', async () => {
    const { wrapper, part } = await mountBars({ bars: summers, diverging: true })
    expect(part('labels').text()).toContain('2026')
    expect(part('labels').find('[data-testid="answer-bars-label"]').classes()).toContain('font-bold')
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(6)
    expect(rows[0]!.text()).toMatch(/^2021\s*-3[.,]4$/)
  })
})

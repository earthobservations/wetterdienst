import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it, onTestFinished } from 'vitest'
import { UButton } from '#components'

async function classesOf(props: Record<string, unknown>) {
  const wrapper = await mountSuspended(UButton, { props: { label: 'Show', ...props } })
  onTestFinished(() => wrapper.unmount())
  return wrapper.classes()
}

// The fill of a solid primary button is the logo's blue at shade 600 (300 on dark), and its label Nuxt UI's
// text-inverted; a hovered button goes a shade darker (lighter on dark) instead of Nuxt UI's 75 % fade, which on
// white is a blue that white text is under 4.5:1 on. Ratios: tests/unit/button-contrast.test.ts.
describe('the solid primary button', () => {
  it('keeps the label of the theme and hovers a shade further', async () => {
    const classes = await classesOf({ color: 'primary', variant: 'solid' })
    expect(classes).toContain('text-inverted')
    expect(classes).toContain('bg-primary')
    expect(classes).toContain('hover:bg-(--ui-color-primary-700)')
    expect(classes).toContain('dark:hover:bg-(--ui-color-primary-200)')
    // the fade is replaced, not stacked under the shade
    expect(classes).not.toContain('hover:bg-primary/75')
    expect(classes).toContain('disabled:bg-primary')
  })

  it('is the default, as a button given neither colour nor variant is solid primary', async () => {
    expect(await classesOf({})).toContain('hover:bg-(--ui-color-primary-700)')
  })
})

describe('the other buttons', () => {
  it.each([
    ['primary', 'outline'],
    ['primary', 'soft'],
    ['primary', 'subtle'],
    ['primary', 'ghost'],
    ['primary', 'link'],
    ['neutral', 'solid'],
    ['error', 'solid'],
  ])('keep the hover of the theme, the %s %s button', async (color, variant) => {
    const classes = await classesOf({ color, variant })
    expect(classes.join(' ')).not.toContain('--ui-color-primary-700')
  })

  it('keep the text-inverted label of the neutral and error solid buttons', async () => {
    expect(await classesOf({ color: 'error', variant: 'solid' })).toContain('text-inverted')
    expect(await classesOf({ color: 'neutral', variant: 'solid' })).toContain('text-inverted')
  })
})

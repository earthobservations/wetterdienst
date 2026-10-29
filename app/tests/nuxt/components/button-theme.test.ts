import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it, onTestFinished } from 'vitest'
import { UButton } from '#components'

async function classesOf(props: Record<string, unknown>) {
  const wrapper = await mountSuspended(UButton, { props: { label: 'Show', ...props } })
  onTestFinished(() => wrapper.unmount())
  return wrapper.classes()
}

describe('the solid primary button', () => {
  it('keeps the label of Nuxt UI and is hovered by a shade of its own, not by a fade', async () => {
    const classes = await classesOf({ color: 'primary', variant: 'solid' })
    expect(classes).toContain('text-inverted')
    expect(classes).toContain('bg-primary')
    // the fade to 75 % is replaced (white on it is 3.1:1, tests/unit/button-contrast.test.ts)
    expect(classes).toContain('hover:bg-primary-600')
    expect(classes).toContain('dark:hover:bg-primary-300')
    expect(classes).not.toContain('hover:bg-primary/75')
    expect(classes).toContain('disabled:bg-primary')
  })

  it('is the default, as a button given neither colour nor variant is solid primary', async () => {
    expect(await classesOf({})).toContain('hover:bg-primary-600')
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
  ])('keep the hover of the theme for the %s %s button', async (color, variant) => {
    const classes = await classesOf({ color, variant })
    expect(classes.join(' ')).not.toContain('hover:bg-primary-600')
  })

  it('keep the text-inverted label of the neutral and error solid buttons', async () => {
    expect(await classesOf({ color: 'error', variant: 'solid' })).toContain('text-inverted')
    expect(await classesOf({ color: 'neutral', variant: 'solid' })).toContain('text-inverted')
  })
})

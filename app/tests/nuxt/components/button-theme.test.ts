import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it, onTestFinished } from 'vitest'
import { UButton } from '#components'

async function classesOf(props: Record<string, unknown>) {
  const wrapper = await mountSuspended(UButton, { props: { label: 'Show', ...props } })
  onTestFinished(() => wrapper.unmount())
  return wrapper.classes()
}

// The solid primary button of the app (GH-3518, app.config.ts): the logo's blue with Nuxt UI's own label (white by
// day, navy at night), and a hover that darkens by day and lightens at night instead of Nuxt UI's fill at 75 %, which
// takes the label under 4.5:1. The ratios are tests/unit/button-contrast.test.ts.
describe('the solid primary button', () => {
  it('keeps Nuxt UI\'s label and fill, and darkens or lightens when hovered and pressed', async () => {
    const classes = await classesOf({ color: 'primary', variant: 'solid' })
    expect(classes).toContain('text-inverted')
    expect(classes).toContain('bg-primary')
    expect(classes).toContain('hover:bg-primary-700')
    expect(classes).toContain('active:bg-primary-800')
    expect(classes).toContain('dark:hover:bg-primary-300')
    expect(classes).toContain('dark:active:bg-primary-200')
    // the faded hover is gone, not beside the new one
    expect(classes).not.toContain('hover:bg-primary/75')
    expect(classes).toContain('disabled:bg-primary')
  })

  it('is the default, as a button given neither colour nor variant is solid primary', async () => {
    expect(await classesOf({})).toContain('hover:bg-primary-700')
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
  ])('keep the hover of the %s %s button', async (color, variant) => {
    const classes = await classesOf({ color, variant })
    expect(classes.join(' ')).not.toContain('hover:bg-primary-700')
  })

  it('keep the text-inverted label of the neutral and error solid buttons', async () => {
    expect(await classesOf({ color: 'error', variant: 'solid' })).toContain('text-inverted')
    expect(await classesOf({ color: 'neutral', variant: 'solid' })).toContain('text-inverted')
  })
})

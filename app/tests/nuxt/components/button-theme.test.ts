import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it, onTestFinished } from 'vitest'
import { UButton } from '#components'

async function classesOf(props: Record<string, unknown>) {
  const wrapper = await mountSuspended(UButton, { props: { label: 'Show', ...props } })
  onTestFinished(() => wrapper.unmount())
  return wrapper.classes()
}

// The fill of a solid primary button is the logo's blue under Nuxt UI's white label; hovered it turns a shade
// darker (lighter in dark mode), where Nuxt UI would fade it to 75 %, which is under 4.5:1 to white
// (app.config.ts, tests/unit/button-contrast.test.ts)
describe('a solid primary button', () => {
  it('keeps Nuxt UI\'s label and fill, and turns a shade darker hovered and pressed', async () => {
    const classes = await classesOf({ color: 'primary', variant: 'solid' })
    expect(classes).toContain('text-inverted')
    expect(classes).toContain('bg-primary')
    expect(classes).toContain('hover:bg-primary-700')
    expect(classes).toContain('active:bg-primary-800')
    expect(classes).toContain('dark:hover:bg-primary-300')
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
})

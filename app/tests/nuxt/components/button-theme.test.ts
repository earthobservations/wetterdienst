import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it, onTestFinished } from 'vitest'
import { UButton } from '#components'

async function classesOf(props: Record<string, unknown>) {
  const wrapper = await mountSuspended(UButton, { props: { label: 'Show', ...props } })
  onTestFinished(() => wrapper.unmount())
  return wrapper.classes()
}

describe('the label of a solid primary button', () => {
  it('is the app colour, and its hover a darker fill rather than Nuxt UI\'s fade', async () => {
    const classes = await classesOf({ color: 'primary', variant: 'solid' })
    expect(classes).toContain('text-(color:--app-text-on-primary)')
    expect(classes).not.toContain('text-inverted')
    // the fill and the disabled state are the theme's; the hover is the app's (main.css, --app-primary-hover)
    expect(classes).toContain('bg-primary')
    expect(classes).toContain('hover:bg-(--app-primary-hover)')
    expect(classes).not.toContain('hover:bg-primary/75')
    expect(classes).toContain('disabled:bg-primary')
  })

  it('is the default, as a button given neither colour nor variant is solid primary', async () => {
    expect(await classesOf({})).toContain('text-(color:--app-text-on-primary)')
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
  ])('keep the label colour of the %s %s button', async (color, variant) => {
    const classes = await classesOf({ color, variant })
    expect(classes.join(' ')).not.toContain('--app-text-on-primary')
  })

  it('keep the text-inverted label of the neutral and error solid buttons', async () => {
    expect(await classesOf({ color: 'error', variant: 'solid' })).toContain('text-inverted')
    expect(await classesOf({ color: 'neutral', variant: 'solid' })).toContain('text-inverted')
  })
})

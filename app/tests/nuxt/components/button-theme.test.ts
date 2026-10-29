import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it, onTestFinished } from 'vitest'
import { UButton } from '#components'

async function classesOf(props: Record<string, unknown>) {
  const wrapper = await mountSuspended(UButton, { props: { label: 'Show', ...props } })
  onTestFinished(() => wrapper.unmount())
  return wrapper.classes()
}

describe('a solid primary button', () => {
  it('keeps Nuxt UI\'s label and fill, and goes a shade outwards on hover where Nuxt UI fades it', async () => {
    const classes = await classesOf({ color: 'primary', variant: 'solid' })
    // the label is the theme's: white on the fill in light mode, the page's navy in dark (design-tokens.test.ts)
    expect(classes).toContain('text-inverted')
    expect(classes).toContain('bg-primary')
    expect(classes).toContain('disabled:bg-primary')
    // 75 % of the fill over the page is 3.8:1 under the label; the next shade outwards is 8.5:1 (main.css)
    expect(classes).toContain('hover:bg-(--app-primary-hover)')
    expect(classes).toContain('active:bg-(--app-primary-hover)')
    expect(classes).not.toContain('hover:bg-primary/75')
    expect(classes).not.toContain('active:bg-primary/75')
  })

  it('is the default, as a button given neither colour nor variant is solid primary', async () => {
    expect(await classesOf({})).toContain('hover:bg-(--app-primary-hover)')
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
  ])('keep the hover of the theme: the %s %s button', async (color, variant) => {
    const classes = await classesOf({ color, variant })
    expect(classes.join(' ')).not.toContain('--app-primary-hover')
  })

  it('keep the text-inverted label of the neutral and error solid buttons', async () => {
    expect(await classesOf({ color: 'error', variant: 'solid' })).toContain('text-inverted')
    expect(await classesOf({ color: 'neutral', variant: 'solid' })).toContain('text-inverted')
  })
})

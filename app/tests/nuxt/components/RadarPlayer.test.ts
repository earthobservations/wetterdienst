import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it } from 'vitest'
import RadarPlayer from '~/components/RadarPlayer.vue'
import { parseLoop } from '~/utils/radar'
import { radarAnswer } from '../../helpers/radar-answer'

// The player of the Radar tool (GH-3788): play and pause, the steps and the slider, the time of the frame in the reader's zone, and
// observed or forecast in words and by an icon, never by colour alone. The slider is the browser's range input, so the keys are the browser's.

const FRAMES = parseLoop(radarAnswer({ run: '2026-11-19T21:25:00Z' })).frames
const NOW = Date.parse('2026-11-19T21:30:00Z')

const mounted: Array<{ unmount: () => void }> = []
async function mountPlayer(props: Record<string, unknown> = {}) {
  const wrapper = await mountSuspended(RadarPlayer, { props: { frames: FRAMES, index: 24, playing: false, now: NOW, reducedMotion: false, ...props }, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
afterEach(() => mounted.splice(0).forEach(wrapper => wrapper.unmount()))

const testid = (wrapper: Awaited<ReturnType<typeof mountPlayer>>, id: string) => wrapper.find(`[data-testid="${id}"]`)

describe('the player', () => {
  it('is a group with a name, and has the play button, two steps and a slider with names of their own', async () => {
    const wrapper = await mountPlayer()
    expect(testid(wrapper, 'radar-player').attributes('role')).toBe('group')
    expect(testid(wrapper, 'radar-player').attributes('aria-label')).toBe('Radar loop')
    expect(testid(wrapper, 'radar-play').attributes('aria-label')).toBe('Play')
    expect(testid(wrapper, 'radar-step-back').attributes('aria-label')).toBe('Previous frame')
    expect(testid(wrapper, 'radar-step-forward').attributes('aria-label')).toBe('Next frame')
    const slider = testid(wrapper, 'radar-slider')
    expect(slider.attributes('type')).toBe('range')
    expect(wrapper.find(`label[for="${slider.attributes('id')}"]`).text()).toBe('Time of the radar frame')
  })

  it('says Pause while it plays, and Play while it does not, by the name of the button', async () => {
    const wrapper = await mountPlayer({ playing: true })
    expect(testid(wrapper, 'radar-play').attributes('aria-label')).toBe('Pause')
    await wrapper.setProps({ playing: false })
    expect(testid(wrapper, 'radar-play').attributes('aria-label')).toBe('Play')
  })

  it('raises toggle for the play button, and a step for each of the step buttons', async () => {
    const wrapper = await mountPlayer()
    await testid(wrapper, 'radar-play').trigger('click')
    await testid(wrapper, 'radar-step-back').trigger('click')
    await testid(wrapper, 'radar-step-forward').trigger('click')
    expect(wrapper.emitted('toggle')).toHaveLength(1)
    expect(wrapper.emitted('step')).toEqual([[-1], [1]])
  })

  it('has a step back that cannot go on at the first frame and a step on that cannot at the last: aria-disabled, no native disabled, which would drop the focus the reader has on it (GH-3788)', async () => {
    const first = await mountPlayer({ index: 0 })
    expect(testid(first, 'radar-step-back').attributes('aria-disabled')).toBe('true')
    expect(testid(first, 'radar-step-back').attributes('disabled')).toBeUndefined()
    expect(testid(first, 'radar-step-forward').attributes('aria-disabled')).toBeUndefined()
    const last = await mountPlayer({ index: 48 })
    expect(testid(last, 'radar-step-forward').attributes('aria-disabled')).toBe('true')
    expect(testid(last, 'radar-step-forward').attributes('disabled')).toBeUndefined()
    expect(testid(last, 'radar-step-back').attributes('aria-disabled')).toBeUndefined()
  })

  it('does nothing for a press on the step that cannot go on, and keeps the focus on it', async () => {
    const wrapper = await mountPlayer({ index: 0 })
    const back = testid(wrapper, 'radar-step-back')
    ;(back.element as HTMLElement).focus()
    await back.trigger('click')
    expect(wrapper.emitted('step')).toBeUndefined()
    expect(document.activeElement).toBe(back.element)
    expect(testid(wrapper, 'radar-announcement').text()).toBe('')
  })

  it('says its frame is loading, marked busy, while the map shows another', async () => {
    const wrapper = await mountPlayer({ loading: true })
    expect(testid(wrapper, 'radar-frame-loading').text()).toBe('Loading this frame …')
    expect(testid(wrapper, 'radar-player').attributes('aria-busy')).toBe('true')
    await wrapper.setProps({ loading: false })
    expect(wrapper.find('[data-testid="radar-frame-loading"]').exists()).toBe(false)
    expect(testid(wrapper, 'radar-player').attributes('aria-busy')).toBeUndefined()
  })

  it('has nothing to play for fewer than two frames', async () => {
    const wrapper = await mountPlayer({ frames: FRAMES.slice(0, 1), index: 0 })
    expect(testid(wrapper, 'radar-play').attributes('disabled')).toBeDefined()
    expect(testid(wrapper, 'radar-slider').attributes('disabled')).toBeDefined()
  })
})

describe('the slider', () => {
  it('runs over the frames, one step each, and stands at the frame the loop is at', async () => {
    const wrapper = await mountPlayer({ index: 30 })
    const slider = testid(wrapper, 'radar-slider')
    expect(slider.attributes('min')).toBe('0')
    expect(slider.attributes('max')).toBe('48')
    expect(slider.attributes('step')).toBe('1')
    expect((slider.element as HTMLInputElement).value).toBe('30')
  })

  it('says nothing in the status where the slider is moved: it is read out by itself, and a second line would say the frame twice', async () => {
    const wrapper = await mountPlayer()
    const slider = testid(wrapper, 'radar-slider')
    ;(slider.element as HTMLInputElement).value = '30'
    await slider.trigger('input')
    expect(testid(wrapper, 'radar-announcement').text()).toBe('')
  })

  it('empties the status where the slider is moved after a step: a step announced before must not be said again for the slider\'s frame (L1)', async () => {
    const wrapper = await mountPlayer({ index: 30 })
    await testid(wrapper, 'radar-step-forward').trigger('click')
    expect(testid(wrapper, 'radar-announcement').text()).not.toBe('')
    const slider = testid(wrapper, 'radar-slider')
    ;(slider.element as HTMLInputElement).value = '40'
    await slider.trigger('input')
    expect(testid(wrapper, 'radar-announcement').text()).toBe('')
    // and a step after the slider is told again
    await testid(wrapper, 'radar-step-forward').trigger('click')
    expect(testid(wrapper, 'radar-announcement').text()).not.toBe('')
  })

  it('raises seek with the frame the reader moved it to', async () => {
    const wrapper = await mountPlayer()
    const slider = testid(wrapper, 'radar-slider')
    ;(slider.element as HTMLInputElement).value = '7'
    await slider.trigger('input')
    expect(wrapper.emitted('seek')).toEqual([[7]])
  })

  it('has a value text for a screen reader that says the time and whether the frame is observed or forecast', async () => {
    const observed = await mountPlayer({ index: 24 })
    expect(testid(observed, 'radar-slider').attributes('aria-valuetext')).toMatch(/^\d{2}:\d{2} .+, observed$/)
    const forecast = await mountPlayer({ index: 31 })
    // frame 31 is the 7th of the forecast: 35 minutes after the run
    expect(testid(forecast, 'radar-slider').attributes('aria-valuetext')).toMatch(/, forecast, 35 minutes ahead$/)
  })

  it('is described by the keys that work on it, and says what its track is', async () => {
    const wrapper = await mountPlayer()
    const slider = testid(wrapper, 'radar-slider')
    expect(wrapper.find(`#${slider.attributes('aria-describedby')}`).text()).toContain('arrow keys')
    expect(testid(wrapper, 'radar-track-key').text()).toBe('Solid: observed. Hatched: forecast.')
  })

  it('puts the end of the solid part of the track where the forecast begins', async () => {
    const wrapper = await mountPlayer()
    const split = Number.parseFloat(testid(wrapper, 'radar-slider').attributes('style')!.match(/--radar-split:\s*([\d.]+)%/)![1]!)
    // the 25th frame (index 24) is the last observed of 49: the line is between it and the next
    expect(split).toBeCloseTo(24.5 / 48 * 100, 0)
    const none = await mountPlayer({ frames: FRAMES.slice(0, 25), index: 24 })
    expect(testid(none, 'radar-slider').attributes('style')).toContain('--radar-split: 100%')
  })
})

describe('the frame in words', () => {
  it('says the time of an observed frame, with a word and an icon for it', async () => {
    const wrapper = await mountPlayer({ index: 24 })
    expect(testid(wrapper, 'radar-time').attributes('datetime')).toBe('2026-11-19T21:25:00Z')
    expect(testid(wrapper, 'radar-time').text()).toMatch(/^\d{2}:\d{2} \S+$/)
    expect(testid(wrapper, 'radar-kind').text()).toBe('Observed')
    expect(testid(wrapper, 'radar-kind').attributes('data-kind')).toBe('observation')
    expect(testid(wrapper, 'radar-kind').find('svg, .iconify, [class*="i-ph"]').exists()).toBe(true)
  })

  it('says a forecast frame is a forecast and how far ahead, in words, not by colour', async () => {
    const wrapper = await mountPlayer({ index: 31 })
    expect(testid(wrapper, 'radar-kind').text()).toBe('Forecast, 35 min ahead')
    expect(testid(wrapper, 'radar-kind').attributes('data-kind')).toBe('forecast')
  })

  it('writes the time in the reader\'s own zone: the same frame at the reader\'s own hour', async () => {
    const wrapper = await mountPlayer({ index: 24 })
    const expected = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(Date.parse('2026-11-19T21:25:00Z'))
    expect(testid(wrapper, 'radar-time').text().startsWith(expected)).toBe(true)
  })
})

describe('what is said to a screen reader', () => {
  it('has a polite status that is empty until the reader moves, then says the frame, and says nothing while the loop plays', async () => {
    const wrapper = await mountPlayer({ index: 30 })
    const status = testid(wrapper, 'radar-announcement')
    expect(status.attributes('role')).toBe('status')
    expect(status.text()).toBe('')
    await testid(wrapper, 'radar-step-forward').trigger('click')
    expect(status.text()).toMatch(/forecast, 30 minutes ahead$/)
    await wrapper.setProps({ playing: true })
    expect(status.text()).toBe('')
  })

  it('says why the loop did not start where the system asks for less motion, and not while it plays', async () => {
    const wrapper = await mountPlayer({ reducedMotion: true })
    expect(testid(wrapper, 'radar-reduced-motion').text()).toContain('does not start by itself')
    await wrapper.setProps({ playing: true })
    expect(wrapper.find('[data-testid="radar-reduced-motion"]').exists()).toBe(false)
    const normal = await mountPlayer({ reducedMotion: false })
    expect(normal.find('[data-testid="radar-reduced-motion"]').exists()).toBe(false)
  })
})

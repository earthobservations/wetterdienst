import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import WarningsBanner from '~/components/WarningsBanner.vue'
import WarningsPanel from '~/components/WarningsPanel.vue'
import { parseWarnings } from '~/utils/warnings'
import { alertsAnswer, emptyAlerts } from '../../helpers/warnings-answer'

// What a reader has of DWD's warnings outside the map (GH-4295): the banner for a position (the Forecast's and the map's panel's) and the
// panel's list of every warning with the ones the map cannot draw. The snapshot is handed in as the page's own polled one, so each state is
// set by a test: loading, failed, a warning for the position, none, a position outside Germany, a refresh that failed, an old snapshot.

const KIEL = { latitude: 54.3776, longitude: 10.1424 }
const BERLIN = { latitude: 52.47, longitude: 13.4 }
const KIEL_HOLE = { latitude: 54.3, longitude: 10.1 }
const JAN_MAYEN = { latitude: 70.93, longitude: -8.67 }

function source(answer: unknown | null, options: { status?: 'idle' | 'pending' | 'success' | 'error', refreshFailed?: boolean, stale?: boolean } = {}) {
  const snapshot = answer ? parseWarnings(answer) : null
  return {
    snapshot: ref(snapshot),
    status: ref(options.status ?? (snapshot ? 'success' : 'pending')),
    error: ref(null),
    refreshFailed: ref(options.refreshFailed ?? false),
    now: ref(Date.now()),
    stale: ref(options.stale ?? false),
    retry: vi.fn(),
  }
}

const mounted: Array<{ unmount: () => void }> = []
async function mountBanner(point: { latitude: number, longitude: number }, src: ReturnType<typeof source>, props: Record<string, unknown> = {}) {
  const wrapper = await mountSuspended(WarningsBanner, { props: { point, source: src as never, ...props }, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
afterEach(() => mounted.splice(0).forEach(wrapper => wrapper.unmount()))

const summary = (wrapper: { find: (selector: string) => { text: () => string } }) => wrapper.find('[data-testid="warnings-banner-summary"]').text()

describe('the banner of a position', () => {
  it('says what DWD warns of for the position, in a polite status, and lists the warning with its level in words and its issue time', async () => {
    const wrapper = await mountBanner(KIEL, source(alertsAnswer()))
    expect(summary(wrapper)).toBe('Warnings of DWD for this position: 1')
    // the status is a polite one, which a screen reader says when it comes and does not interrupt for
    expect(wrapper.find('[data-testid="warnings-banner-summary"]').attributes('role')).toBe('status')
    const entry = wrapper.find('[data-testid="warning-entry"]')
    expect(entry.find('[data-testid="warning-title"]').text()).toBe('wind gusts')
    expect(entry.find('[data-testid="warning-level"]').text()).toBe('Level 2 of 4 · Marked weather warning')
    expect(entry.find('[data-testid="warning-when"]').text()).toMatch(/^In force · /)
    expect(entry.find('[data-testid="warning-issued-row"]').text()).toMatch(/^Issued /)
    // the level is a number and words, and the mark is no cue alone
    expect(entry.find('.warning-mark').attributes('aria-hidden')).toBe('true')
    expect(entry.find('.warning-mark').text()).toBe('2')
  })

  it('opens a warning to DWD\'s own words, unchanged, and says whether it is open', async () => {
    const wrapper = await mountBanner(KIEL, source(alertsAnswer()))
    const button = wrapper.find('[data-testid="warning-toggle"]')
    expect(button.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('[data-testid="warning-details"]').isVisible()).toBe(false)
    await button.trigger('click')
    expect(button.attributes('aria-expanded')).toBe('true')
    const details = wrapper.find('[data-testid="warning-details"]')
    expect(details.attributes('id')).toBe(button.attributes('aria-controls'))
    expect(details.isVisible()).toBe(true)
    expect(details.find('[data-testid="warning-description"]').text()).toContain('Gusts up to 65 km/h (18m/s, 35kn, Bft 8) from westerly directions.')
    expect(details.find('[data-testid="warning-instruction"]').text()).toBe('ATTENTION! Notice of possible danger: Single branches may fall. Beware of falling objects.')
    expect(details.text()).toContain('Stadt Kiel, Kreis Rendsburg-Eckernförde')
    expect(details.find('[data-testid="warning-issued"]').exists()).toBe(true)
    await button.trigger('click')
    expect(button.attributes('aria-expanded')).toBe('false')
  })

  it('says that no warning of DWD has an area with the position, for a position in a hole as for one with none, and lists nothing', async () => {
    for (const point of [KIEL_HOLE, { latitude: 50.2, longitude: 9.1 }]) {
      const wrapper = await mountBanner(point, source(alertsAnswer()))
      expect(summary(wrapper)).toBe('No warning of DWD has an area that contains this position.')
      expect(wrapper.find('[data-testid="warning-entry"]').exists()).toBe(false)
    }
  })

  it('says nothing of the warning that has no area for any position, except that there are some, and where they are listed', async () => {
    const wrapper = await mountBanner(KIEL, source(alertsAnswer()), { mapLink: true })
    const note = wrapper.find('[data-testid="warnings-banner-named"]')
    expect(note.text()).toContain('Warnings that DWD gives by area name alone (the sea, a coast) are not matched to a position: 1.')
    expect(wrapper.find('[data-testid="warnings-banner-map"]').attributes('href')).toBe('/map?warnings=1')
    // the warning of the sea is not among the warnings of the position
    expect(wrapper.text()).not.toContain('near gale')
    // the map's own panel has the list: no link to itself
    const inMap = await mountBanner(KIEL, source(alertsAnswer()))
    expect(inMap.find('[data-testid="warnings-banner-map"]').exists()).toBe(false)
  })

  it('has no note of warnings that name only an area where there are none', async () => {
    const wrapper = await mountBanner(KIEL, source(emptyAlerts()))
    expect(wrapper.find('[data-testid="warnings-banner-named"]').exists()).toBe(false)
    expect(summary(wrapper)).toBe('No warning of DWD has an area that contains this position.')
  })

  it('lists a warning announced for later after the ones in force, marked as announced', async () => {
    // Berlin has the fog; the Black Forest has the glaze that begins in three hours
    const later = await mountBanner({ latitude: 47.9737, longitude: 8.5205 }, source(alertsAnswer()))
    expect(later.find('[data-testid="warning-when"]').text()).toMatch(/^Announced · /)
    const now = await mountBanner(BERLIN, source(alertsAnswer()))
    expect(now.find('[data-testid="warning-when"]').text()).toMatch(/^In force · /)
  })

  it('says plainly that no warnings source covers a place outside Germany, and shows no list', async () => {
    const wrapper = await mountBanner(JAN_MAYEN, source(alertsAnswer()))
    expect(summary(wrapper)).toBe('DWD\'s warnings cover Germany only. No warnings source covers this place.')
    expect(wrapper.find('[data-testid="warning-entry"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="provider-credit"]').exists()).toBe(false)
  })

  it('is loading until the snapshot comes, and a failure has a Retry', async () => {
    const loading = await mountBanner(KIEL, source(null, { status: 'pending' }))
    expect(summary(loading)).toBe('Loading the warnings …')
    const failed = source(null, { status: 'error' })
    const wrapper = await mountBanner(KIEL, failed)
    expect(summary(wrapper)).toBe('The warnings could not be loaded.')
    await wrapper.find('button').trigger('click')
    expect(failed.retry).toHaveBeenCalledTimes(1)
  })

  it('says what it shows is old where a refresh failed, and where the snapshot is more than three refreshes behind', async () => {
    const refreshFailed = await mountBanner(KIEL, source(alertsAnswer(), { refreshFailed: true }))
    expect(refreshFailed.find('[data-testid="warnings-banner-refresh-failed"]').text()).toContain('The warnings could not be refreshed. Shown are the ones from ')
    const stale = await mountBanner(KIEL, source(alertsAnswer(), { stale: true }))
    expect(stale.find('[data-testid="warnings-banner-stale"]').text()).toContain('These warnings are old: the last check was ')
    const fresh = await mountBanner(KIEL, source(alertsAnswer()))
    expect(fresh.find('[data-testid="warnings-banner-stale"]').exists()).toBe(false)
    expect(fresh.find('[data-testid="warnings-banner-refresh-failed"]').exists()).toBe(false)
  })

  it('has the time of the check, the coverage, the credit and the processing note', async () => {
    const wrapper = await mountBanner(KIEL, source(alertsAnswer()))
    expect(wrapper.find('[data-testid="warnings-banner-checked"]').text()).toMatch(/^Checked: .+ DWD warns for Germany and the sea around it\.$/)
    const credit = wrapper.find('[data-testid="provider-credit"]')
    expect(credit.text()).toContain('Source: Deutscher Wetterdienst')
    expect(credit.find('[data-testid="provider-credit-licence"]').attributes('href')).toBe('https://creativecommons.org/licenses/by/4.0/')
    expect(credit.find('[data-testid="processing-note"]').exists()).toBe(true)
  })

  it('names itself by its heading, for a screen reader', async () => {
    const wrapper = await mountBanner(KIEL, source(alertsAnswer()))
    const section = wrapper.find('section')
    expect(section.attributes('aria-labelledby')).toBe('warnings-banner-title')
    expect(wrapper.find('#warnings-banner-title').text()).toBe('Weather warnings for this position')
  })
})

describe('the panel of the map\'s layer', () => {
  async function mountPanel(src: ReturnType<typeof source>, focused: string | null = null) {
    const wrapper = await mountSuspended(WarningsPanel, { props: { source: src as never, focused }, attachTo: document.body })
    mounted.push(wrapper)
    return wrapper
  }

  it('counts every warning of Germany in a polite status, and lists those with an outline, the most severe first', async () => {
    const wrapper = await mountPanel(source(alertsAnswer()))
    expect(wrapper.find('[data-testid="warnings-panel-summary"]').text()).toBe('Warnings in force or announced in Germany: 6')
    expect(wrapper.find('[data-testid="warnings-panel-summary"]').attributes('role')).toBe('status')
    // the first list is the map's; the second, under the aside's heading, is the warnings with no outline
    const titles = wrapper.findAll('[data-testid="warnings-list"]')[0]!.findAll('[data-testid="warning-title"]').map(title => title.text())
    expect(titles).toEqual(['thunderstorm', 'PRELIMINARY INFORMATION SEVERE THUNDERSTORMS', 'wind gusts', 'glaze', 'fog'])
  })

  it('lists the warning that has no polygon apart, with its area names and a note that none is drawn', async () => {
    const wrapper = await mountPanel(source(alertsAnswer()))
    const aside = wrapper.find('[data-testid="warnings-aside"]')
    expect(aside.find('h4').text()).toBe('Warnings for areas the map cannot draw')
    expect(aside.text()).toContain('DWD names the area of these warnings (the sea, a coast) but gives no outline for it, so none is drawn.')
    expect(aside.findAll('[data-testid="warning-title"]').map(title => title.text())).toEqual(['near gale'])
    await aside.find('[data-testid="warning-toggle"]').trigger('click')
    expect(aside.find('[data-testid="warning-details"]').text()).toContain('Ostfriesische Küste')
  })

  it('tells the page which warning is open, so that the map draws it stronger, and none when it is closed', async () => {
    const wrapper = await mountPanel(source(alertsAnswer()))
    const first = wrapper.findAll('[data-testid="warnings-list"]')[0]!.find('[data-testid="warning-toggle"]')
    await first.trigger('click')
    expect(wrapper.emitted('focus')!.at(-1)).toEqual([expect.stringContaining('THUNDER-HAMBURG')])
    await first.trigger('click')
    expect(wrapper.emitted('focus')!.at(-1)).toEqual([null])
  })

  it('opens the warning the page says is picked', async () => {
    const wrapper = await mountPanel(source(alertsAnswer()), '2.49.0.0.276.0.DWD.PVW.3.FOG-BERLIN.MUL')
    const open = wrapper.findAll('[data-testid="warning-toggle"]').filter(button => button.attributes('aria-expanded') === 'true')
    expect(open).toHaveLength(1)
    expect(wrapper.find('[data-testid="warning-entry"][data-focused]').exists()).toBe(true)
  })

  it('says there is no warning in Germany on a quiet day, and lists nothing', async () => {
    const wrapper = await mountPanel(source(emptyAlerts()))
    expect(wrapper.find('[data-testid="warnings-panel-summary"]').text()).toBe('No warning is in force or announced in Germany.')
    expect(wrapper.find('[data-testid="warnings-list"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="warnings-aside"]').exists()).toBe(false)
  })

  it('cuts a long list to the most severe, and shows the rest on a press', async () => {
    const many = alertsAnswer({ alerts: Array.from({ length: 20 }, (_, index) => ({
      ...alertsAnswerAlert(),
      alert_id: `many-${String(index).padStart(2, '0')}`,
    })) })
    const wrapper = await mountPanel(source(many))
    expect(wrapper.findAll('[data-testid="warnings-list"] > li')).toHaveLength(12)
    const more = wrapper.find('[data-testid="warnings-more"]')
    expect(more.text()).toBe('Show all 20')
    expect(more.attributes('aria-expanded')).toBe('false')
    await more.trigger('click')
    expect(wrapper.findAll('[data-testid="warnings-list"] > li')).toHaveLength(20)
    expect(more.attributes('aria-expanded')).toBe('true')
  })

  it('is loading until the snapshot comes, and a failure has a Retry', async () => {
    const wrapper = await mountPanel(source(null, { status: 'pending' }))
    expect(wrapper.find('[data-testid="warnings-panel-summary"]').text()).toBe('Loading the warnings …')
    const failed = source(null, { status: 'error' })
    const broken = await mountPanel(failed)
    expect(broken.find('[data-testid="warnings-failed"]').attributes('role')).toBe('alert')
    await broken.find('[data-testid="warnings-retry"]').trigger('click')
    expect(failed.retry).toHaveBeenCalledTimes(1)
  })

  it('says how often it asks again, and when it last asked, with the credit of DWD', async () => {
    const wrapper = await mountPanel(source(alertsAnswer()))
    expect(wrapper.find('[data-testid="warnings-checked"]').text()).toMatch(/^Checked: .+ Asked again every 5 minutes while this page is open\.$/)
    expect(wrapper.find('[data-testid="provider-credit"]').text()).toContain('Source: Deutscher Wetterdienst')
  })

  it('says a refresh failed while the snapshot in hand is shown', async () => {
    const wrapper = await mountPanel(source(alertsAnswer(), { refreshFailed: true }))
    expect(wrapper.find('[data-testid="warnings-refresh-failed"]').text()).toContain('could not be refreshed')
  })
})

/** One alert of the fixture, to be given many identifiers */
function alertsAnswerAlert() {
  return {
    alert_id: 'x',
    event: 'NEBEL',
    event_code: '59',
    severity: 'Minor',
    onsetHours: -1,
    endHours: 4,
    sentHours: -1,
    area_names: ['Stadt Berlin'],
    warncell_ids: ['811000000'],
    geometry: [[[[13, 52.3], [13.8, 52.3], [13.8, 52.7], [13, 52.7], [13, 52.3]]]],
    texts: { de: { event: 'NEBEL', headline: 'h', description: 'd', instruction: 'i' }, en: { event: 'fog', headline: 'h', description: 'd', instruction: 'i' }, pl: { event: 'mgła', headline: 'h', description: 'd', instruction: 'i' } },
  }
}

// What of the app's own pages the search finds by their words, where the words are in the catalogs of the interface
// (GH-3790): a page of cards (About, Support, Settings) as one document for each card or setting, with the key of its
// name, the keys of its text and the anchor it leads to. The long texts (How weather is measured, the methods) are
// read from their own files (`i18n/measurement`, `i18n/methods`), and the glossary from the backend.
//
// An anchor is an `id` of the page: `tests/unit/search-docs.test.ts` holds every one to the page that has it, and every
// key to every catalog. Pure data, like the lists of `sections.ts`.

import { UNIT_TARGET_TYPES } from './unit-targets'

/** The pages that have words of their own in the catalogs */
export type MessageKind = 'about' | 'support' | 'settings'

export interface MessageSource {
  kind: MessageKind
  /** The page and the `id` of the card or the control, which the page scrolls to */
  to: string
  /** The key of its name */
  title: string
  /** The key of a line that says where it is (the group of settings), shown before the summary */
  context?: string
  /** The keys of its words: the first is shown under the name, the rest is only searched */
  text: readonly string[]
}

export const MESSAGE_SOURCES: readonly MessageSource[] = [
  { kind: 'about', to: '/about#about-project', title: 'about.projectTitle', text: ['about.projectText1', 'about.projectText2', 'about.projectText3'] },
  { kind: 'about', to: '/about#about-people', title: 'about.peopleTitle', text: ['about.maintainerRole', 'about.maintainerBio', 'about.maintainerText2', 'about.coAuthorRole', 'about.coAuthorBio', 'about.contributorsText'] },
  { kind: 'support', to: '/support#support-report', title: 'support.reportTitle', text: ['support.reportText', 'support.reportButton'] },
  { kind: 'support', to: '/support#support-contribute', title: 'support.contributeTitle', text: ['support.contributeText', 'support.contributeButton'] },
  { kind: 'support', to: '/support#support-discussions', title: 'support.discussionsTitle', text: ['support.discussionsText', 'support.discussionsButton'] },
  { kind: 'support', to: '/support#support-donate', title: 'support.donateTitle', text: ['support.donateText'] },
  { kind: 'settings', to: '/settings#bar', title: 'settings.bar.title', text: ['settings.bar.hint', 'settings.bar.instructions', 'settings.bar.hintHeader'] },
  { kind: 'settings', to: '/settings#settings-search-stations', title: 'settings.searchStationsTitle', text: ['settings.searchStationsHint', 'mapTool.layerForecast', 'mapTool.layerMeasured', 'mapTool.layerGhcn'] },
  { kind: 'settings', to: '/settings#settings-friendly-labels', title: 'settings.friendlyLabels', context: 'settings.units', text: ['settings.friendlyLabelsHint'] },
  { kind: 'settings', to: '/settings#settings-convert-units', title: 'settings.convertUnits', context: 'settings.units', text: ['settings.convertUnitsHint'] },
  // one row for each unit type the page offers, in the order of its list
  ...UNIT_TARGET_TYPES.map((unitType): MessageSource => ({
    kind: 'settings',
    to: `/settings#settings-unit-${unitType.type}`,
    title: unitType.label,
    context: 'settings.units',
    text: [],
  })),
]

/** The key of the name of each page a source is on, which the search shows beside a text that leads into it */
export const MESSAGE_PAGE_KEY: Record<MessageKind, string> = {
  about: 'footer.about',
  support: 'nav.support',
  settings: 'common.settings',
}

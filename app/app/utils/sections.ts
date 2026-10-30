// The places of the app and how the navigation shows them (GH-3518): the header and the tab bar, the menu of the
// narrow layout, the search, the footer and each page's own header read them from here, so a page is named, marked
// and grouped the same way wherever it appears.
//
// Three groups: the four tools, which work on data and each take one tile of the logo (main.css, `.tile-*`); the
// reference, which explains the data; and the project, which is about the people and the software behind it.

export type SectionGroup = 'tools' | 'reference' | 'project'
export type Tile = 'sun' | 'rain' | 'wind' | 'heat' | 'navy'

export interface Section {
  key: string
  to: string
  group: SectionGroup
  /** The i18n key of the name the navigation gives it */
  label: string
  /** The i18n key of one sentence that says what it is for (the reference menu, the home page, the search) */
  description?: string
  /** The icon beside its name; for a tool, the glyph on its tile */
  icon: string
  tile?: Tile
}

export const TOOLS: Section[] = [
  { key: 'forecast', to: '/meteogram', group: 'tools', label: 'nav.meteogram', description: 'home.forecastDesc', icon: 'i-ph-sun-fill', tile: 'sun' },
  { key: 'explorer', to: '/explorer', group: 'tools', label: 'nav.explorer', description: 'home.explorerDesc', icon: 'i-ph-compass-fill', tile: 'rain' },
  { key: 'stripes', to: '/stripes', group: 'tools', label: 'nav.stripes', description: 'home.stripesDesc', icon: 'i-ph-thermometer-simple-fill', tile: 'heat' },
  { key: 'history', to: '/history', group: 'tools', label: 'nav.history', description: 'history.subtitle', icon: 'i-ph-clock-counter-clockwise-fill', tile: 'wind' },
]

export const REFERENCE: Section[] = [
  { key: 'providers', to: '/providers', group: 'reference', label: 'nav.providers', description: 'providers.subtitle', icon: 'i-ph-buildings' },
  { key: 'glossary', to: '/glossary', group: 'reference', label: 'nav.glossary', description: 'glossary.subtitle', icon: 'i-ph-book-open-text' },
  { key: 'api', to: '/api', group: 'reference', label: 'nav.api', description: 'api.subtitle', icon: 'i-ph-code' },
]

export const PROJECT: Section[] = [
  { key: 'about', to: '/about', group: 'project', label: 'footer.about', description: 'about.subtitle', icon: 'i-ph-info' },
  { key: 'support', to: '/support', group: 'project', label: 'nav.support', description: 'shell.desc.support', icon: 'i-ph-heart' },
  { key: 'settings', to: '/settings', group: 'project', label: 'common.settings', description: 'settings.subtitle', icon: 'i-ph-gear-six' },
]

/** The home page, which is no section: the logo leads to it */
export const HOME: Section = { key: 'home', to: '/', group: 'project', label: 'nav.home', description: 'home.tagline', icon: 'i-ph-house' }

/** The legal pages: in the footer and the search, not in the navigation */
export const LEGAL: Section[] = [
  { key: 'impressum', to: '/impressum', group: 'project', label: 'footer.legal', description: 'shell.desc.impressum', icon: 'i-ph-identification-card' },
  { key: 'privacy', to: '/datenschutz', group: 'project', label: 'footer.privacy', description: 'shell.desc.privacy', icon: 'i-ph-shield-check' },
]

/** The project's places elsewhere: the documentation, the code and the package */
export const EXTERNAL = [
  { key: 'docs', to: 'https://wetterdienst.readthedocs.io/', label: 'common.documentation', description: 'shell.desc.docs', icon: 'i-ph-book-open-text' },
  { key: 'github', to: 'https://github.com/earthobservations/wetterdienst', label: 'header.github', description: 'shell.desc.github', icon: 'i-ph-github-logo' },
  { key: 'pypi', to: 'https://pypi.org/project/wetterdienst', label: 'header.pypi', description: 'shell.desc.pypi', icon: 'i-ph-package' },
] as const

export const SECTIONS: Section[] = [...TOOLS, ...REFERENCE, ...PROJECT]

/** Whether `path` is the section's page or one below it (`/providers/dwd` is in `/providers`) */
export function inSection(section: Pick<Section, 'to'>, path: string): boolean {
  return path === section.to || path.startsWith(`${section.to}/`)
}

/** The section a path belongs to, or undefined for the home page, the legal pages and a page that is none */
export function sectionOf(path: string): Section | undefined {
  return SECTIONS.find(section => inSection(section, path))
}

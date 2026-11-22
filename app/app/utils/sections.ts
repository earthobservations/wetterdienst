// The places of the app and how the navigation shows them (GH-3518): the header and the tab bar, the menu of the
// narrow layout, the search, the footer and each page's own header read them from here, so a page is named, marked
// and grouped the same way wherever it appears.
//
// Three groups: the tools, which work on data and each take a tile (main.css, `.tile-*`): the four tiles of the logo,
// for the map a violet of its own and, for the radar (GH-3788), the logo's navy; the reference, which explains the data; and the project, which is about the
// people and the software behind it.

export type SectionGroup = 'tools' | 'reference' | 'project'
export type Tile = 'sun' | 'rain' | 'wind' | 'heat' | 'map' | 'navy'

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
  { key: 'radar', to: '/radar', group: 'tools', label: 'nav.radar', description: 'radar.subtitle', icon: 'i-ph-target-fill', tile: 'navy' },
  { key: 'history', to: '/history', group: 'tools', label: 'nav.history', description: 'history.subtitle', icon: 'i-ph-clock-counter-clockwise-fill', tile: 'wind' },
  { key: 'map', to: '/map', group: 'tools', label: 'nav.map', description: 'mapTool.subtitle', icon: 'i-ph-map-trifold-fill', tile: 'map' },
  // the seventh tool (GH-4296): two stations or two periods side by side. Its tile is the teal of History's, since the seven tools have six
  // colours (the logo's four, the map's violet and the radar's navy); a tab bar that holds four tools keeps it in the Menu's sheet
  { key: 'compare', to: '/compare', group: 'tools', label: 'nav.compare', description: 'compare.subtitle', icon: 'i-ph-scales-fill', tile: 'wind' },
]

/** The map, which the search opens on a station (`/map?station=`) */
export const MAP_TOOL: Section = TOOLS.find(tool => tool.key === 'map')!

// Which of the tools have a tab in the bar of the narrow layout is the reader's choice, with Forecast, Explorer, Stripes
// and the Radar as the default (`utils/tab-bar.ts`, GH-3846): seven tools and the Menu are eight items, more than a tab bar
// holds (GH-3650), so the bar holds four tools and the Menu; History, the Map and Compare (GH-4296) are in the Menu until the reader moves them (the default bar is Forecast, Explorer, Stripes and the Radar, GH-3788). The header of the wide layout shows all of `TOOLS`.

export const REFERENCE: Section[] = [
  { key: 'providers', to: '/providers', group: 'reference', label: 'nav.providers', description: 'providers.subtitle', icon: 'i-ph-buildings' },
  { key: 'glossary', to: '/glossary', group: 'reference', label: 'nav.glossary', description: 'glossary.subtitle', icon: 'i-ph-book-open-text' },
  { key: 'measurement', to: '/measurement', group: 'reference', label: 'nav.measurement', description: 'measurement.menuDescription', icon: 'i-ph-ruler' },
  { key: 'methods', to: '/methods', group: 'reference', label: 'nav.methods', description: 'methods.menuDescription', icon: 'i-ph-seal-check' },
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

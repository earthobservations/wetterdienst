/** A page of the app, as the navigation, the search and the home page name it */
export interface SitePage {
  /** Its path, which is also its key */
  to: string
  /** Its name, the one the navigation shows */
  label: string
  /** What it is for, in one line */
  purpose: string
  icon: string
  /** In the main navigation (the header), or reached from the footer and the search only */
  main: boolean
}

/** Whether `path` is the page `to` or one below it */
export function isCurrentPage(path: string, to: string): boolean {
  return to === '/' ? path === '/' : path === to || path.startsWith(`${to}/`)
}

/**
 * The pages of the app, in one list for the header's navigation, the menu of the narrow layout, the search
 * (`CommandPalette.vue`) and the home page's further tools, so that a page has one name and one purpose
 * everywhere. The widget is no page to visit: it is the forecast, framed by another site.
 */
export function useSiteNav() {
  const { t } = useI18n()

  const pages = computed<SitePage[]>(() => [
    { to: '/', label: t('nav.home'), purpose: t('palette.pages.home'), icon: 'i-lucide-house', main: false },
    { to: '/meteogram', label: t('nav.meteogram'), purpose: t('palette.pages.meteogram'), icon: 'i-lucide-cloud-sun', main: true },
    { to: '/explorer', label: t('nav.explorer'), purpose: t('palette.pages.explorer'), icon: 'i-lucide-table-2', main: true },
    { to: '/stripes', label: t('nav.stripes'), purpose: t('palette.pages.stripes'), icon: 'i-lucide-thermometer', main: true },
    { to: '/history', label: t('nav.history'), purpose: t('palette.pages.history'), icon: 'i-lucide-history', main: true },
    { to: '/providers', label: t('nav.providers'), purpose: t('palette.pages.providers'), icon: 'i-lucide-building-2', main: true },
    { to: '/glossary', label: t('nav.glossary'), purpose: t('palette.pages.glossary'), icon: 'i-lucide-book-open', main: true },
    { to: '/api', label: t('nav.api'), purpose: t('palette.pages.api'), icon: 'i-lucide-code', main: true },
    { to: '/settings', label: t('settings.title'), purpose: t('palette.pages.settings'), icon: 'i-lucide-sliders-horizontal', main: false },
    { to: '/about', label: t('footer.about'), purpose: t('palette.pages.about'), icon: 'i-lucide-info', main: false },
    { to: '/support', label: t('nav.support'), purpose: t('palette.pages.support'), icon: 'i-lucide-heart', main: false },
    { to: '/impressum', label: t('footer.legal'), purpose: t('palette.pages.impressum'), icon: 'i-lucide-scale', main: false },
    { to: '/datenschutz', label: t('footer.privacy'), purpose: t('palette.pages.datenschutz'), icon: 'i-lucide-shield', main: false },
  ])

  const mainPages = computed(() => pages.value.filter(page => page.main))

  return { pages, mainPages }
}

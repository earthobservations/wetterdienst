export interface AppNavItem {
  key: string
  to: string
  label: string
  description: string
  icon: string
}

export interface AppNavGroup {
  key: string
  title: string
  items: AppNavItem[]
}

/**
 * Every page of the app, in the three parts the menu shows them in (GH-3518): the weather of a place, the
 * data behind it, and the project. The header names the first three pages of all, the ones for a place; the
 * menu has every one, each with a line of what it is for.
 */
export function useAppNav() {
  const { t } = useI18n()
  const route = useRoute()

  const groups = computed<AppNavGroup[]>(() => [
    {
      key: 'weather',
      title: t('menu.groupWeather'),
      items: [
        { key: 'meteogram', to: '/meteogram', label: t('nav.meteogram'), description: t('menu.forecast'), icon: 'i-lucide-cloud-sun' },
        { key: 'stripes', to: '/stripes', label: t('nav.stripes'), description: t('menu.stripes'), icon: 'i-lucide-bar-chart-3' },
      ],
    },
    {
      key: 'data',
      title: t('menu.groupData'),
      items: [
        { key: 'explorer', to: '/explorer', label: t('nav.explorer'), description: t('menu.explorer'), icon: 'i-lucide-compass' },
        { key: 'history', to: '/history', label: t('nav.history'), description: t('menu.history'), icon: 'i-lucide-clock' },
        { key: 'providers', to: '/providers', label: t('nav.providers'), description: t('menu.providers'), icon: 'i-lucide-building-2' },
        { key: 'glossary', to: '/glossary', label: t('nav.glossary'), description: t('menu.glossary'), icon: 'i-lucide-book-open' },
        { key: 'api', to: '/api', label: t('nav.api'), description: t('menu.api'), icon: 'i-lucide-code' },
      ],
    },
    {
      key: 'project',
      title: t('menu.groupProject'),
      items: [
        { key: 'home', to: '/', label: t('nav.home'), description: t('menu.home'), icon: 'i-lucide-house' },
        { key: 'about', to: '/about', label: t('footer.about'), description: t('menu.about'), icon: 'i-lucide-info' },
        { key: 'support', to: '/support', label: t('nav.support'), description: t('menu.support'), icon: 'i-lucide-heart' },
        { key: 'settings', to: '/settings', label: t('common.settings'), description: t('menu.settings'), icon: 'i-lucide-settings-2' },
      ],
    },
  ])

  /** The pages the header names itself: the ones for a place */
  const primary = computed(() => [groups.value[0]!.items[0]!, groups.value[0]!.items[1]!, groups.value[1]!.items[0]!])

  function isActive(to: string) {
    return to === '/' ? route.path === '/' : route.path === to || route.path.startsWith(`${to}/`)
  }

  return { groups, primary, isActive }
}

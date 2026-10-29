import type { NavigationMenuItem } from '@nuxt/ui'

// The places of the app, in the groups the sidebar, the drawer and the command palette share (GH-3518). One list, so
// that a page added here is in all three, and the current one is marked in all three.
export interface AppNavGroup {
  key: string
  label?: string
  items: NavigationMenuItem[]
}

export function useAppNav() {
  const { t } = useI18n()
  const route = useRoute()

  const isActive = (to: string) => to === '/' ? route.path === '/' : route.path === to || route.path.startsWith(`${to}/`)
  const page = (to: string, icon: string, label: string): NavigationMenuItem => ({ label, icon, to, active: isActive(to) })
  const external = (to: string, icon: string, label: string): NavigationMenuItem => ({ label, icon, to, target: '_blank' })

  const groups = computed<AppNavGroup[]>(() => [
    {
      key: 'home',
      items: [page('/', 'i-ph-house', t('nav.home'))],
    },
    {
      key: 'data',
      label: t('nav.groupData'),
      items: [
        page('/explorer', 'i-ph-compass', t('nav.explorer')),
        page('/meteogram', 'i-ph-cloud-sun', t('nav.meteogram')),
        page('/stripes', 'i-ph-barcode', t('nav.stripes')),
        page('/history', 'i-ph-clock-counter-clockwise', t('nav.history')),
        page('/api', 'i-ph-brackets-curly', t('nav.api')),
      ],
    },
    {
      key: 'reference',
      label: t('nav.groupReference'),
      items: [
        page('/providers', 'i-ph-buildings', t('nav.providers')),
        page('/glossary', 'i-ph-book-open-text', t('nav.glossary')),
        external('https://wetterdienst.readthedocs.io/', 'i-ph-books', t('common.documentation')),
      ],
    },
    {
      key: 'project',
      label: t('nav.groupProject'),
      items: [
        page('/about', 'i-ph-info', t('footer.about')),
        page('/support', 'i-ph-heart', t('nav.support')),
        external('https://github.com/earthobservations/wetterdienst', 'i-ph-github-logo', t('header.github')),
        external('https://pypi.org/project/wetterdienst', 'i-ph-package', t('header.pypi')),
      ],
    },
  ])

  return { groups }
}

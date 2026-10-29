<script setup lang="ts">
import { de as uiDe, en as uiEn } from '@nuxt/ui/locale'
import { canonicalUrl, findSeoRoute, HOME_TITLE_KEY, isNotIndexed, siteOrigin } from '#shared/utils/seo'
import pkg from '../package.json'

const { t, locale, localeProperties } = useI18n()
const route = useRoute()

// What a search engine and a link preview are told about the page (GH-3497). The server writes the same tags into the
// shell for a crawler that runs no script (`server/plugins/seo-head.ts`); these replace them, in the language the
// visitor chose. The pages are listed in `shared/utils/seo.ts`; a path that is not one (a provider's page, a 404) is
// told as the site, with no canonical link of its own.
const config = useRuntimeConfig()
const seoRoute = computed(() => findSeoRoute(route.path))
const homeTitle = computed(() => t(HOME_TITLE_KEY))
const seoTitle = computed(() => seoRoute.value && seoRoute.value.title !== HOME_TITLE_KEY
  ? `${t(seoRoute.value.title)} - Wetterdienst`
  : homeTitle.value)
const seoDescription = computed(() => t(seoRoute.value?.description ?? 'seo.description'))
const canonical = computed(() => seoRoute.value ? canonicalUrl(config.public.siteUrl, seoRoute.value.path) : undefined)
const iconUrl = computed(() => `${siteOrigin(config.public.siteUrl)}/apple-touch-icon.png`)

// Keep <html lang> in sync with the active locale.
useHead({
  htmlAttrs: { lang: locale },
  // the title of a page that sets none: the home page's, and the one a page has until its own is set
  // a page names itself (`useHead({ title })`), and the document says whose page it is; the home page,
  // which names nothing, is the sentence that says what the site is
  titleTemplate: title => title && title !== homeTitle.value ? `${title} - Wetterdienst` : homeTitle.value,
})
// no link at all where the path is no page of the index: an empty `href` would name the page itself
useHead(() => ({ link: canonical.value ? [{ rel: 'canonical', href: canonical.value }] : [] }))
useSeoMeta({
  description: seoDescription,
  robots: () => isNotIndexed(route.path) ? 'noindex' : undefined,
  ogType: 'website',
  ogSiteName: 'Wetterdienst',
  ogTitle: seoTitle,
  ogDescription: seoDescription,
  ogUrl: canonical,
  // `de-DE` of the locale, written the way Open Graph wants it (`de_DE`)
  ogLocale: () => localeProperties.value.language?.replace('-', '_'),
  ogImage: iconUrl,
  twitterCard: 'summary',
  twitterTitle: seoTitle,
  twitterDescription: seoDescription,
  twitterImage: iconUrl,
})

// Feed Nuxt UI's built-in component strings (table, select, …) the active locale.
const uiLocale = computed(() => (locale.value === 'de' ? uiDe : uiEn))

// framed by another origin anywhere but the widget: nothing is drawn (app/utils/frame-guard.ts)
const blank = useFrameBlank()
const isWidget = computed(() => isWidgetPath(route.path))

// Deliberately not awaited. A top-level `await` in the root component makes its setup async, and
// with `ssr: false` that suspends the entire app -- header, page and footer -- behind this one
// request, so every cold load stared at an empty screen until the backend answered. The footer
// simply has nothing to show for the backend until the answer lands.
// A page that draws nothing (framed by another origin outside the widget) does not ask.
const { data: versionData, status: versionStatus } = useFetch<{ version: string }>('/api/version', { immediate: !blank.value })

const backendVersion = computed(() => {
  const version = versionData.value?.version
  if (version)
    return `v${version}`
  // still in flight is not the same as answered-but-unusable, and only the latter is "unknown"
  return versionStatus.value === 'pending' ? '…' : 'unknown'
})
const appVersion = pkg.version || 'unknown'

// The same four statements the home page spells out, as icons here: the footer is on every page,
// and four sentences at the foot of every one of them is a banner rather than a footer. The full
// wording is one hover away, and is the accessible name either way.
const values = computed(() => [
  { key: 'lgbtq', emoji: '🏳️‍🌈🏳️‍⚧️', text: t('values.lgbtq') },
  { key: 'antifascist', emoji: '✊', text: t('values.antifascist') },
  { key: 'climate', emoji: '🌡️', text: t('values.climate') },
  { key: 'openData', emoji: '🔓', text: t('values.openData') },
])

const mobileMenuOpen = ref(false)

watch(() => route.path, () => {
  mobileMenuOpen.value = false
})

// the menu is the narrow layout's: past the breakpoint the header shows the links itself, and a dialog
// that is hidden with CSS would still hold the focus
const wide = useMediaQuery('(min-width: 1024px)')
watch(wide, (isWide) => {
  if (isWide)
    mobileMenuOpen.value = false
})

// The tools are the logo's four tiles (GH-3518): the sun is the forecast, the drop the data of the Explorer, the
// wind the stations' history, the thermometer the climate stripes. The square is decoration: the label names the page.
type Tile = 'sun' | 'rain' | 'wind' | 'temperature'
interface NavItem { label: string, icon: string, to: string, active: boolean, tile?: Tile }
interface NavGroup { key: string, label?: string, items: NavItem[] }

const navGroups = computed<NavGroup[]>(() => [
  {
    key: 'start',
    items: [
      { label: t('nav.home'), icon: 'i-lucide-house', to: '/', active: route.path === '/' },
    ],
  },
  {
    key: 'data',
    label: t('nav.groupData'),
    items: [
      { label: t('nav.meteogram'), icon: 'i-lucide-sun', to: '/meteogram', active: route.path.startsWith('/meteogram'), tile: 'sun' },
      { label: t('nav.stripes'), icon: 'i-lucide-thermometer', to: '/stripes', active: route.path.startsWith('/stripes'), tile: 'temperature' },
      { label: t('nav.explorer'), icon: 'i-lucide-droplets', to: '/explorer', active: route.path.startsWith('/explorer'), tile: 'rain' },
      { label: t('nav.history'), icon: 'i-lucide-wind', to: '/history', active: route.path.startsWith('/history'), tile: 'wind' },
    ],
  },
  {
    key: 'reference',
    label: t('nav.groupReference'),
    items: [
      { label: t('nav.providers'), icon: 'i-lucide-building-2', to: '/providers', active: route.path.startsWith('/providers') },
      { label: t('nav.glossary'), icon: 'i-lucide-book-open', to: '/glossary', active: route.path.startsWith('/glossary') },
      { label: t('nav.api'), icon: 'i-lucide-code', to: '/api', active: route.path.startsWith('/api') },
    ],
  },
])

// The project's links: the same four, in the same order, in the rail, in the narrow layout's menu and (support) in the
// footer (WCAG 3.2.6). Support is about the project rather than the data, so it sits with them rather than in the nav.
const projectLinks = computed(() => [
  { key: 'docs', to: 'https://wetterdienst.readthedocs.io/', icon: 'i-lucide-book-marked', label: t('common.documentation'), external: true },
  { key: 'github', to: 'https://github.com/earthobservations/wetterdienst', icon: 'i-lucide-github', label: t('header.github'), external: true },
  { key: 'pypi', to: 'https://pypi.org/project/wetterdienst', icon: 'i-lucide-package', label: t('header.pypi'), external: true },
  { key: 'support', to: '/support', icon: 'i-lucide-heart', label: t('nav.support'), external: false },
])
// a ghost button on the navy rail: its own light colours, and the same tint for hover and keyboard focus (Nuxt UI's
// would be the light grey of a panel, under the white icon)
const railButton = 'text-(--app-rail-fg-muted) hover:text-(--app-rail-fg) hover:bg-white/10 active:bg-white/10 focus-visible:bg-white/10'

// The search: the button of the rail, and Ctrl+K (⌘K on a Mac) on every page but the widget, in a field too
const searchOpen = ref(false)
const shortcutLabel = import.meta.client && /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘K' : 'Ctrl K'
function openSearch() {
  mobileMenuOpen.value = false
  searchOpen.value = true
}
useEventListener(import.meta.client ? window : undefined, 'keydown', (event: KeyboardEvent) => {
  if (blank.value || isWidget.value || event.key.toLowerCase() !== 'k' || !(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey)
    return
  event.preventDefault()
  openSearch()
})
</script>

<template>
  <div v-if="blank" />
  <UApp v-else :locale="uiLocale">
    <!-- tells a screen reader which page the client-side navigation has arrived on (WCAG 4.1.3) -->
    <NuxtRouteAnnouncer />
    <template v-if="!isWidget">
      <div class="app-shell min-h-dvh lg:grid lg:grid-cols-[15rem_minmax(0,1fr)]">
        <!-- The rail: on a wide window a column of its own, which stays while the page scrolls; on a narrow one a bar
             above the page, with the menu behind a button -->
        <header class="app-rail app-topbar relative flex items-center justify-between gap-3 px-4 py-2.5 lg:sticky lg:top-0 lg:h-dvh lg:flex-col lg:items-stretch lg:justify-start lg:gap-6 lg:overflow-y-auto lg:px-0 lg:py-5">
          <!-- the rail comes before the page on every page: a way past it (WCAG 2.4.1), drawn in the rail's colours -->
          <a
            href="#main"
            class="app-skip-link sr-only focus-visible:not-sr-only focus-visible:absolute focus-visible:top-2 focus-visible:left-2 focus-visible:z-50 focus-visible:rounded-md focus-visible:bg-(--app-rail-bg) focus-visible:px-4 focus-visible:py-2 focus-visible:font-semibold focus-visible:text-(--app-rail-fg) focus-visible:ring-1 focus-visible:ring-white/30"
          >{{ t('header.skipToContent') }}</a>
          <div class="flex items-center gap-2.5 lg:px-5">
            <img src="/icon.svg" alt="" class="size-8 shrink-0 rounded-[28%] ring-1 ring-white/15">
            <span class="text-lg font-semibold tracking-tight">Wetterdienst</span>
          </div>

          <!-- the search (components/AppSearch.vue): in the rail under the name, in the bar beside the menu; Ctrl+K or
               ⌘K opens it from anywhere -->
          <button
            type="button"
            class="ml-auto inline-flex min-h-9 items-center gap-2 rounded-md px-2.5 text-sm font-medium text-(--app-rail-fg-muted) hover:bg-white/10 hover:text-(--app-rail-fg) lg:mx-4 lg:flex lg:border lg:border-white/15 lg:bg-white/5 lg:px-3"
            aria-haspopup="dialog"
            :aria-expanded="searchOpen"
            aria-keyshortcuts="Control+K Meta+K"
            @click="openSearch"
          >
            <UIcon name="i-lucide-search" class="size-4 shrink-0" aria-hidden="true" />
            <span class="sr-only sm:not-sr-only lg:flex-1 lg:text-left">{{ t('palette.title') }}</span>
            <kbd class="hidden rounded border border-white/20 px-1.5 font-sans text-xs lg:inline" aria-hidden="true">{{ shortcutLabel }}</kbd>
          </button>

          <nav :aria-label="t('header.navigation')" class="hidden lg:flex lg:flex-col lg:gap-5 lg:pr-3">
            <div v-for="group in navGroups" :key="group.key">
              <p v-if="group.label" :id="`nav-group-${group.key}`" class="app-rail-label mb-1.5 pl-5">
                {{ group.label }}
              </p>
              <ul class="flex flex-col gap-0.5" :aria-labelledby="group.label ? `nav-group-${group.key}` : undefined">
                <li v-for="item in group.items" :key="item.to">
                  <NuxtLink :to="item.to" class="app-rail-link" :aria-current="item.active ? 'page' : undefined">
                    <span class="app-tile size-6" :class="item.tile ? `app-tile--${item.tile}` : 'app-tile--plain'" aria-hidden="true">
                      <UIcon :name="item.icon" class="size-3.5" />
                    </span>
                    {{ item.label }}
                  </NuxtLink>
                </li>
              </ul>
            </div>
          </nav>

          <div class="hidden lg:mt-auto lg:flex lg:items-center lg:gap-0.5 lg:border-t lg:border-white/10 lg:px-4 lg:pt-4">
            <UTooltip v-for="link in projectLinks" :key="link.key" :text="link.label">
              <UButton
                :to="link.to"
                :target="link.external ? '_blank' : undefined"
                :icon="link.icon"
                color="neutral"
                variant="ghost"
                :aria-label="link.label"
                :class="railButton"
              />
            </UTooltip>
            <div class="ml-auto">
              <SettingsMenu :trigger-class="railButton" />
            </div>
          </div>

          <UButton
            class="lg:hidden"
            :class="railButton"
            icon="i-lucide-menu"
            color="neutral"
            variant="ghost"
            :label="t('header.menu')"
            :ui="{ label: 'sr-only sm:not-sr-only' }"
            :aria-label="t('header.menu')"
            aria-haspopup="dialog"
            :aria-expanded="mobileMenuOpen"
            @click="mobileMenuOpen = true"
          />
        </header>

        <div class="app-canvas flex min-w-0 flex-col">
          <main id="main" tabindex="-1" class="flex-1 focus:outline-none">
            <NuxtPage />
          </main>

          <footer class="border-t border-default px-(--app-gutter) py-5 text-sm text-muted">
            <div class="flex flex-wrap items-center justify-between gap-x-8 gap-y-3">
              <!-- the links in one row; each owns its separator, so a wrapped line does not end in one -->
              <div class="flex flex-wrap items-center gap-x-4 gap-y-1">
                <span>{{ t('footer.copyright', { year: new Date().getFullYear() }) }}</span>
                <NuxtLink to="/about" class="hover:text-highlighted underline-offset-4 hover:underline">
                  {{ t('footer.about') }}
                </NuxtLink>
                <NuxtLink to="/support" class="hover:text-highlighted underline-offset-4 hover:underline">
                  {{ t('nav.support') }}
                </NuxtLink>
                <NuxtLink to="/impressum" class="hover:text-highlighted underline-offset-4 hover:underline">
                  {{ t('footer.legal') }}
                </NuxtLink>
                <NuxtLink to="/datenschutz" class="hover:text-highlighted underline-offset-4 hover:underline">
                  {{ t('footer.privacy') }}
                </NuxtLink>
                <!-- a file of the app (modules/third-party-licenses, GH-3469), not a page: a plain link, which the router
                     would otherwise take for a route -->
                <a href="/third-party-licenses.txt" class="hover:text-highlighted underline-offset-4 hover:underline">
                  {{ t('footer.licenses') }}
                </a>
              </div>
              <div class="flex flex-wrap items-center gap-x-5 gap-y-2">
                <!-- the versions, as a status line reads: what runs, set in figures that line up -->
                <p class="tabular font-mono text-xs">
                  <span class="font-semibold text-default">App</span> {{ appVersion === 'unknown' ? appVersion : `v${appVersion}` }}
                  <span class="mx-1.5" aria-hidden="true">·</span>
                  <span class="font-semibold text-default">Backend</span> {{ backendVersion }}
                </p>
                <!-- The stance, as on the home page, as icons: the full wording is one hover away, and is the
                     accessible name either way. -->
                <div class="flex items-center gap-x-3">
                  <UTooltip v-for="value in values" :key="value.key" :text="value.text">
                    <span
                      class="text-base leading-none cursor-default"
                      role="img"
                      :aria-label="value.text"
                    >{{ value.emoji }}</span>
                  </UTooltip>
                </div>
              </div>
            </div>
          </footer>
        </div>
      </div>

      <!-- The menu of the narrow layout. A dialog, not a layer of markup: the focus stays in it, Escape closes it and
           the page behind is hidden from a screen reader while it is open (WCAG 2.1.2, 2.4.3, 4.1.2) -->
      <UModal
        v-model:open="mobileMenuOpen"
        fullscreen
        :title="t('header.menu')"
        close
        :ui="{ body: 'flex flex-col flex-1 p-0 sm:p-0' }"
      >
        <!-- the label in the language of the app, which Nuxt UI's own is only for the two it ships -->
        <template #close="{ ui }">
          <UButton
            icon="i-lucide-x"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.close')"
            :class="ui.close()"
          />
        </template>
        <template #body>
          <nav :aria-label="t('header.navigation')" class="flex-1 overflow-y-auto px-3 py-4 flex flex-col gap-5">
            <div v-for="group in navGroups" :key="group.key">
              <p v-if="group.label" :id="`menu-group-${group.key}`" class="mb-1.5 px-4 text-xs font-semibold uppercase tracking-wider text-muted">
                {{ group.label }}
              </p>
              <ul class="flex flex-col gap-1" :aria-labelledby="group.label ? `menu-group-${group.key}` : undefined">
                <li v-for="item in group.items" :key="item.to">
                  <NuxtLink
                    :to="item.to"
                    class="flex items-center gap-4 rounded-md border-l-[3px] px-4 py-3 text-base font-medium"
                    :class="item.active
                      ? 'border-primary bg-primary/10 text-highlighted font-semibold'
                      : 'border-transparent text-default hover:bg-elevated'"
                    :aria-current="item.active ? 'page' : undefined"
                    @click="mobileMenuOpen = false"
                  >
                    <span class="app-tile size-7" :class="item.tile ? `app-tile--${item.tile}` : 'app-tile--plain'" aria-hidden="true">
                      <UIcon :name="item.icon" class="size-4" />
                    </span>
                    {{ item.label }}
                  </NuxtLink>
                </li>
              </ul>
            </div>
          </nav>

          <!-- the project's links and the settings, as at the foot of the rail -->
          <div class="shrink-0 border-t border-default px-4 py-4 flex items-center justify-between">
            <div class="flex items-center gap-1">
              <UTooltip v-for="link in projectLinks" :key="link.key" :text="link.label">
                <UButton
                  :to="link.to"
                  :target="link.external ? '_blank' : undefined"
                  :icon="link.icon"
                  color="neutral"
                  variant="ghost"
                  :aria-label="link.label"
                  @click="mobileMenuOpen = false"
                />
              </UTooltip>
            </div>
            <UButton
              to="/settings"
              icon="i-lucide-settings-2"
              color="neutral"
              variant="ghost"
              :aria-label="t('common.settings')"
              @click="mobileMenuOpen = false"
            />
          </div>
        </template>
      </UModal>

      <AppSearch v-model:open="searchOpen" />
    </template>

    <!-- the widget: the page and nothing around it -->
    <main v-else>
      <NuxtPage />
    </main>
  </UApp>
</template>

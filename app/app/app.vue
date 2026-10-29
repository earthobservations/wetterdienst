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

// the menu is the narrow layout's: past the breakpoint the rail shows the links itself, and a dialog
// that is hidden with CSS would still hold the focus
const wide = useMediaQuery('(min-width: 1024px)')
watch(wide, (isWide) => {
  if (isWide)
    mobileMenuOpen.value = false
})

// The app's search (CommandPalette.vue): its buttons say whether it is open, and show the shortcut of this system
const { open: paletteOpen, show: openPalette } = useCommandPalette()
const shortcut = isApplePlatform() ? '⌘K' : 'Ctrl K'
function showPalette() {
  mobileMenuOpen.value = false
  openPalette()
}

/** The colour of a tile of the logo: the four things the app does each have one (main.css, `.app-tile`) */
type Tile = 'sun' | 'rain' | 'wind' | 'heat'
interface NavItem { label: string, icon: string, to: string, active: boolean, tile?: Tile }

const isAt = (path: string) => route.path === path || route.path.startsWith(`${path}/`)

// What the app does, in the colours and the order of the logo's tiles (left to right, top to bottom): the sun
// for the forecast, the rain for the explorer's measurements, the wind for a station's history, the thermometer
// for the stripes. Home leads, untinted.
const tasks = computed<NavItem[]>(() => [
  { label: t('nav.home'), icon: 'i-lucide-house', to: '/', active: route.path === '/' },
  { label: t('nav.meteogram'), icon: 'i-lucide-sun', to: '/meteogram', active: isAt('/meteogram'), tile: 'sun' },
  { label: t('nav.explorer'), icon: 'i-lucide-compass', to: '/explorer', active: isAt('/explorer'), tile: 'rain' },
  { label: t('nav.history'), icon: 'i-lucide-history', to: '/history', active: isAt('/history'), tile: 'wind' },
  { label: t('nav.stripes'), icon: 'i-lucide-thermometer', to: '/stripes', active: isAt('/stripes'), tile: 'heat' },
])
// What the data is and how to reach it without the app
const reference = computed<NavItem[]>(() => [
  { label: t('nav.providers'), icon: 'i-lucide-building-2', to: '/providers', active: isAt('/providers') },
  { label: t('nav.glossary'), icon: 'i-lucide-book-a', to: '/glossary', active: isAt('/glossary') },
  { label: t('nav.api'), icon: 'i-lucide-code', to: '/api', active: isAt('/api') },
])
const groups = computed(() => [
  { key: 'tasks', label: undefined, items: tasks.value },
  { key: 'reference', label: t('nav.reference'), items: reference.value },
])

// The project's own links: the documentation, the code, the package, and support, which is about the project
// rather than the data, so it sits here as an icon and in the footer, not among the tasks.
const projectLinks = computed(() => [
  { key: 'docs', label: t('common.documentation'), icon: 'i-lucide-book-open', to: 'https://wetterdienst.readthedocs.io/', external: true },
  { key: 'github', label: t('header.github'), icon: 'i-simple-icons-github', to: 'https://github.com/earthobservations/wetterdienst', external: true },
  { key: 'pypi', label: t('header.pypi'), icon: 'i-simple-icons-pypi', to: 'https://pypi.org/project/wetterdienst', external: true },
  { key: 'support', label: t('nav.support'), icon: 'i-lucide-heart', to: '/support', external: false },
])

const footerLinks = computed(() => [
  { key: 'about', label: t('footer.about'), to: '/about' },
  { key: 'support', label: t('nav.support'), to: '/support' },
  { key: 'legal', label: t('footer.legal'), to: '/impressum' },
  { key: 'privacy', label: t('footer.privacy'), to: '/datenschutz' },
])
</script>

<template>
  <div v-if="blank" />
  <UApp v-else :locale="uiLocale">
    <!-- tells a screen reader which page the client-side navigation has arrived on (WCAG 4.1.3) -->
    <NuxtRouteAnnouncer />

    <!-- the widget is a frame of its own: no rail, no footer -->
    <main v-if="isWidget">
      <NuxtPage />
    </main>

    <template v-else>
      <a href="#main" class="app-skip">{{ t('header.skipToContent') }}</a>

      <div class="app-shell lg:flex">
        <!-- The banner: a bar on top in the narrow layout, the rail on the left from 1024 px -->
        <header class="app-rail lg:border-r">
          <div class="app-rail-inner">
            <div class="flex items-center gap-2 px-4 py-3 lg:px-5 lg:pt-6 lg:pb-5">
              <NuxtLink to="/" class="flex items-center gap-3 min-w-0 rounded-lg -m-1 p-1 me-auto">
                <!-- the logo is navy, the rail is navy: its four tiles stand on the rail itself -->
                <img src="/icon.svg" alt="" class="size-9 shrink-0 lg:size-10">
                <span class="text-lg font-bold tracking-tight text-white">Wetterdienst</span>
              </NuxtLink>
              <UButton
                v-if="!wide"
                class="text-white hover:bg-white/10 hover:text-white"
                icon="i-lucide-search"
                color="neutral"
                variant="ghost"
                size="lg"
                :aria-label="t('palette.open')"
                aria-haspopup="dialog"
                :aria-expanded="paletteOpen"
                aria-keyshortcuts="Control+K Meta+K"
                @click="showPalette"
              />
              <UButton
                v-if="!wide"
                class="text-white hover:bg-white/10 hover:text-white"
                icon="i-lucide-menu"
                color="neutral"
                variant="ghost"
                size="lg"
                :aria-label="t('header.menu')"
                aria-haspopup="dialog"
                :aria-expanded="mobileMenuOpen"
                @click="mobileMenuOpen = true"
              />
            </div>

            <!-- the app's search: pages, settings and forecast stations (CommandPalette.vue), also by Ctrl+K / ⌘K -->
            <div v-if="wide" class="px-4 pb-4">
              <button
                type="button"
                class="app-rail-search"
                aria-haspopup="dialog"
                :aria-expanded="paletteOpen"
                aria-keyshortcuts="Control+K Meta+K"
                @click="showPalette"
              >
                <UIcon name="i-lucide-search" class="size-4 shrink-0" aria-hidden="true" />
                <span class="flex-1 text-start">{{ t('palette.open') }}</span>
                <kbd aria-hidden="true">{{ shortcut }}</kbd>
              </button>
            </div>

            <nav :aria-label="t('header.mainNav')" class="hidden lg:block px-3 pb-4">
              <div v-for="group in groups" :key="group.key" class="mb-4">
                <p v-if="group.label" class="px-3 pt-2 pb-2 text-xs font-bold uppercase tracking-wider text-gray-300">
                  {{ group.label }}
                </p>
                <ul class="space-y-0.5">
                  <li v-for="item in group.items" :key="item.to">
                    <NuxtLink :to="item.to" class="app-nav-link" :aria-current="item.active ? 'page' : undefined">
                      <span class="app-tile" :data-tile="item.tile" aria-hidden="true">
                        <UIcon :name="item.icon" class="size-4" />
                      </span>
                      {{ item.label }}
                    </NuxtLink>
                  </li>
                </ul>
              </div>
            </nav>

            <div class="hidden lg:flex mt-auto items-center gap-1 border-t border-white/10 px-4 py-3">
              <UTooltip v-for="link in projectLinks" :key="link.key" :text="link.label">
                <NuxtLink
                  :to="link.to"
                  :target="link.external ? '_blank' : undefined"
                  :aria-label="link.label"
                  class="inline-grid place-items-center size-10 rounded-lg text-gray-200 hover:text-white hover:bg-white/10"
                >
                  <UIcon :name="link.icon" class="size-5" />
                </NuxtLink>
              </UTooltip>
              <div class="ms-auto">
                <SettingsMenu on-navy />
              </div>
            </div>
          </div>
        </header>

        <div class="flex min-w-0 flex-1 flex-col min-h-dvh">
          <main id="main" tabindex="-1" class="flex-1 outline-none">
            <NuxtPage />
          </main>

          <footer class="border-t border-default mt-12 text-sm text-muted">
            <div class="app-frame py-8 space-y-4">
              <nav :aria-label="t('header.footerNav')" class="app-footer-nav">
                <ul class="flex flex-wrap gap-x-5 gap-y-2">
                  <li v-for="link in footerLinks" :key="link.key">
                    <NuxtLink :to="link.to" class="underline-offset-4 hover:text-highlighted hover:underline">
                      {{ link.label }}
                    </NuxtLink>
                  </li>
                  <li>
                    <!-- a file of the app (modules/third-party-licenses, GH-3469), not a page: a plain link, which the
                         router would otherwise take for a route -->
                    <a href="/third-party-licenses.txt" class="underline-offset-4 hover:text-highlighted hover:underline">
                      {{ t('footer.licenses') }}
                    </a>
                  </li>
                </ul>
              </nav>
              <div class="flex flex-wrap items-center gap-x-5 gap-y-2">
                <span>{{ t('footer.copyright', { year: new Date().getFullYear() }) }}</span>
                <span class="tabular-nums">App {{ appVersion === 'unknown' ? appVersion : `v${appVersion}` }} · Backend {{ backendVersion }}</span>
                <!-- the stance, as icons whose words are their names and their tooltips -->
                <span class="flex items-center gap-3 sm:ms-auto">
                  <UTooltip v-for="value in values" :key="value.key" :text="value.text">
                    <span class="text-lg leading-none cursor-default" role="img" :aria-label="value.text">{{ value.emoji }}</span>
                  </UTooltip>
                </span>
              </div>
            </div>
          </footer>
        </div>
      </div>

      <!-- The menu of the narrow layout. A dialog, not a layer of markup: the focus stays in it, Escape closes
           it and the page behind is hidden from a screen reader while it is open (WCAG 2.1.2, 2.4.3, 4.1.2) -->
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
          <nav :aria-label="t('header.menu')" class="app-menu flex-1 overflow-y-auto px-3 py-4">
            <div v-for="group in groups" :key="group.key" class="mb-4">
              <p v-if="group.label" class="px-3 pt-2 pb-2 text-xs font-bold uppercase tracking-wider text-muted">
                {{ group.label }}
              </p>
              <ul class="space-y-0.5">
                <li v-for="item in group.items" :key="item.to">
                  <NuxtLink
                    :to="item.to"
                    class="app-nav-link text-base"
                    :aria-current="item.active ? 'page' : undefined"
                    @click="mobileMenuOpen = false"
                  >
                    <span class="app-tile" :data-tile="item.tile" aria-hidden="true">
                      <UIcon :name="item.icon" class="size-4" />
                    </span>
                    {{ item.label }}
                  </NuxtLink>
                </li>
              </ul>
            </div>
          </nav>

          <!-- the project's links and the settings, as at the foot of the rail -->
          <div class="shrink-0 border-t border-default px-4 py-3 flex items-center gap-1">
            <UTooltip v-for="link in projectLinks" :key="link.key" :text="link.label">
              <UButton
                :to="link.to"
                :target="link.external ? '_blank' : undefined"
                :icon="link.icon"
                color="neutral"
                variant="ghost"
                size="lg"
                :aria-label="link.label"
                @click="mobileMenuOpen = false"
              />
            </UTooltip>
            <UButton
              class="ms-auto"
              to="/settings"
              icon="i-lucide-settings-2"
              color="neutral"
              variant="ghost"
              size="lg"
              :aria-label="t('common.settings')"
              @click="mobileMenuOpen = false"
            />
          </div>
        </template>
      </UModal>

      <CommandPalette />
    </template>
  </UApp>
</template>

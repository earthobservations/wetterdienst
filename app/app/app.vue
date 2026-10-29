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

// What the project stands for, written out at the foot of every page.
const values = computed(() => [
  { key: 'lgbtq', emoji: '🏳️‍🌈🏳️‍⚧️', text: t('values.lgbtq') },
  { key: 'antifascist', emoji: '✊', text: t('values.antifascist') },
  { key: 'climate', emoji: '🌡️', text: t('values.climate') },
  { key: 'openData', emoji: '🔓', text: t('values.openData') },
])

// The help and the project, in the footer of every page in the same order (WCAG 3.2.6), and in the narrow
// layout's menu.
const projectLinks = computed(() => [
  { key: 'docs', label: t('common.documentation'), to: 'https://wetterdienst.readthedocs.io/', icon: 'i-lucide-book-open', external: true },
  { key: 'github', label: t('header.github'), to: 'https://github.com/earthobservations/wetterdienst', icon: 'i-lucide-github', external: true },
  { key: 'pypi', label: t('header.pypi'), to: 'https://pypi.org/project/wetterdienst', icon: 'i-lucide-package', external: true },
  { key: 'support', label: t('nav.support'), to: '/support', icon: 'i-lucide-heart', external: false },
])

const { mainPages } = useSiteNav()

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

// The search: the header's button, and Ctrl+K (⌘K on a Mac) wherever the focus is. The browser's own use of
// Ctrl+K (its search bar, in Firefox) gives way on the app's pages.
const { open: paletteOpen } = usePalette()
const apple = ref(false)
onMounted(() => {
  apple.value = isApplePlatform()
})
const shortcutLabel = computed(() => apple.value ? '⌘ K' : t('palette.ctrlK'))
useEventListener(globalThis.window, 'keydown', (event: KeyboardEvent) => {
  if (isWidget.value || blank.value)
    return
  if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    mobileMenuOpen.value = false
    paletteOpen.value = !paletteOpen.value
  }
})
function openSearch() {
  mobileMenuOpen.value = false
  paletteOpen.value = true
}
</script>

<template>
  <div v-if="blank" />
  <UApp v-else :locale="uiLocale">
    <!-- tells a screen reader which page the client-side navigation has arrived on (WCAG 4.1.3) -->
    <NuxtRouteAnnouncer />

    <template v-if="!isWidget">
      <!-- the first stop of the keyboard: past the header to the page (WCAG 2.4.1) -->
      <a
        href="#main"
        class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:start-2 focus:z-50 focus:rounded-md focus:bg-(--color-sun) focus:px-4 focus:py-3 focus:font-bold focus:text-(--color-ink-950) focus:underline"
      >
        {{ t('common.skipToContent') }}
      </a>

      <header class="app-masthead bg-brand-900 text-white dark:bg-ink-950">
        <!-- wraps rather than scrolls: at 320 px (a phone, or 400 % zoom) the buttons take a line of their own -->
        <div class="app-frame flex flex-wrap items-center gap-x-3 gap-y-2 sm:gap-x-4 min-h-16 py-2">
          <NuxtLink to="/" class="flex items-center gap-2.5 shrink-0 rounded-sm text-xl font-bold text-white no-underline hover:underline">
            <img src="/icon.svg" alt="" class="size-8 rounded-md" width="32" height="32">
            <span>Wetterdienst</span>
          </NuxtLink>
          <div class="ms-auto flex items-center gap-2 app-no-print">
            <!-- the search: a field to look at, a button to press (it opens the search dialog) -->
            <button
              type="button"
              class="flex items-center gap-2 rounded-md border-2 border-white/80 px-2.5 py-1.5 text-white hover:bg-white/15 lg:min-w-72 lg:border-white lg:bg-white lg:text-(--color-ink-900) lg:hover:bg-brand-50"
              aria-haspopup="dialog"
              :aria-expanded="paletteOpen"
              aria-keyshortcuts="Control+K Meta+K"
              data-testid="search-button"
              @click="openSearch"
            >
              <UIcon name="i-lucide-search" class="size-5 shrink-0" />
              <span class="lg:hidden font-semibold">{{ t('palette.title') }}</span>
              <span class="hidden lg:inline flex-1 text-start">{{ t('palette.trigger') }}</span>
              <kbd class="app-kbd hidden lg:inline-flex" aria-hidden="true">{{ shortcutLabel }}</kbd>
            </button>
            <div class="hidden lg:flex">
              <SettingsMenu />
            </div>
            <button
              type="button"
              class="lg:hidden flex items-center gap-1.5 rounded-md border-2 border-white/80 px-2.5 py-1.5 font-semibold text-white hover:bg-white/15"
              :aria-label="t('header.menu')"
              aria-haspopup="dialog"
              :aria-expanded="mobileMenuOpen"
              @click="mobileMenuOpen = true"
            >
              <UIcon name="i-lucide-menu" class="size-5 shrink-0" />
              <span aria-hidden="true">{{ t('header.menu') }}</span>
            </button>
          </div>
        </div>
        <div class="app-stripe" />
      </header>

      <!-- the service's pages, one line on a wide screen; the narrow layout has them in its menu -->
      <nav :aria-label="t('header.navigation')" class="hidden lg:block border-b border-default bg-default app-no-print">
        <ul class="app-frame flex flex-wrap gap-x-7">
          <li v-for="item in mainPages" :key="item.to">
            <NuxtLink
              :to="item.to"
              class="block border-b-4 pt-3.5 pb-2.5 font-semibold no-underline hover:underline"
              :class="isCurrentPage(route.path, item.to)
                ? 'border-(--ui-primary) text-highlighted'
                : 'border-transparent text-primary'"
              :aria-current="isCurrentPage(route.path, item.to) ? 'page' : undefined"
            >
              {{ item.label }}
            </NuxtLink>
          </li>
        </ul>
      </nav>
    </template>

    <!-- The menu of the narrow layout. A dialog, not a layer of markup: the focus stays in it, Escape closes
         it and the page behind is hidden from a screen reader while it is open (WCAG 2.1.2, 2.4.3, 4.1.2) -->
    <UModal
      v-if="!isWidget"
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
        <div class="flex-1 overflow-y-auto">
          <nav :aria-label="t('header.menu')" class="px-4 py-4">
            <ul class="divide-y divide-default border-y border-default">
              <li>
                <NuxtLink
                  to="/"
                  class="flex items-center gap-3 px-2 py-3.5 text-lg font-semibold text-primary underline-offset-4 hover:underline"
                  :aria-current="route.path === '/' ? 'page' : undefined"
                >
                  <UIcon name="i-lucide-house" class="size-5 shrink-0 text-toned" />
                  {{ t('nav.home') }}
                </NuxtLink>
              </li>
              <li v-for="item in mainPages" :key="item.to">
                <NuxtLink
                  :to="item.to"
                  class="flex items-start gap-3 px-2 py-3.5 no-underline hover:underline"
                  :class="isCurrentPage(route.path, item.to) ? 'shadow-[inset_4px_0_0_var(--ui-primary)] ps-4' : ''"
                  :aria-current="isCurrentPage(route.path, item.to) ? 'page' : undefined"
                  @click="mobileMenuOpen = false"
                >
                  <UIcon :name="item.icon" class="size-5 shrink-0 mt-1 text-toned" />
                  <span>
                    <span class="block text-lg font-semibold text-primary">{{ item.label }}</span>
                    <span class="block text-sm text-muted">{{ item.purpose }}</span>
                  </span>
                </NuxtLink>
              </li>
            </ul>
          </nav>
          <div class="px-4 pb-6">
            <ul class="flex flex-wrap gap-x-5 gap-y-2">
              <li v-for="link in projectLinks" :key="link.key">
                <NuxtLink
                  :to="link.to"
                  :target="link.external ? '_blank' : undefined"
                  class="inline-flex items-center gap-1.5 py-1 text-primary underline"
                  @click="mobileMenuOpen = false"
                >
                  <UIcon :name="link.icon" class="size-4 shrink-0" />
                  {{ link.label }}
                </NuxtLink>
              </li>
              <li>
                <NuxtLink to="/settings" class="inline-flex items-center gap-1.5 py-1 text-primary underline" @click="mobileMenuOpen = false">
                  <UIcon name="i-lucide-settings-2" class="size-4 shrink-0" />
                  {{ t('common.settings') }}
                </NuxtLink>
              </li>
            </ul>
          </div>
        </div>
      </template>
    </UModal>

    <CommandPalette v-if="!isWidget" />

    <main id="main" tabindex="-1" class="flex-1 focus:outline-none">
      <NuxtPage />
    </main>

    <footer v-if="!isWidget" class="mt-12 border-t-4 border-brand-900 dark:border-brand-300 bg-muted text-sm">
      <div class="app-frame grid gap-8 py-10 sm:grid-cols-2 lg:grid-cols-3">
        <section>
          <h2 class="mb-3 text-base font-bold text-highlighted">
            {{ t('footer.helpTitle') }}
          </h2>
          <ul class="space-y-2">
            <li v-for="link in projectLinks" :key="link.key">
              <NuxtLink :to="link.to" :target="link.external ? '_blank' : undefined" class="text-primary underline">
                {{ link.label }}
              </NuxtLink>
            </li>
          </ul>
        </section>
        <section>
          <h2 class="mb-3 text-base font-bold text-highlighted">
            {{ t('footer.serviceTitle') }}
          </h2>
          <ul class="space-y-2">
            <li>
              <NuxtLink to="/about" class="text-primary underline">
                {{ t('footer.about') }}
              </NuxtLink>
            </li>
            <li>
              <NuxtLink to="/impressum" class="text-primary underline">
                {{ t('footer.legal') }}
              </NuxtLink>
            </li>
            <li>
              <NuxtLink to="/datenschutz" class="text-primary underline">
                {{ t('footer.privacy') }}
              </NuxtLink>
            </li>
            <li>
              <!-- a file of the app (modules/third-party-licenses, GH-3469), not a page: a plain link, which the router
                   would otherwise take for a route -->
              <a href="/third-party-licenses.txt" class="text-primary underline">
                {{ t('footer.licenses') }}
              </a>
            </li>
            <li>
              <NuxtLink to="/settings" class="text-primary underline">
                {{ t('common.settings') }}
              </NuxtLink>
            </li>
          </ul>
        </section>
        <section>
          <h2 class="mb-3 text-base font-bold text-highlighted">
            {{ t('values.title') }}
          </h2>
          <ul class="space-y-2">
            <li v-for="value in values" :key="value.key" class="flex gap-2">
              <span aria-hidden="true" class="shrink-0">{{ value.emoji }}</span>
              <span>{{ value.text }}</span>
            </li>
          </ul>
        </section>
      </div>
      <div class="border-t border-default">
        <p class="app-frame flex flex-wrap gap-x-4 gap-y-1 py-4 text-muted">
          <span>{{ t('footer.copyright', { year: new Date().getFullYear() }) }}</span>
          <span>App {{ appVersion === 'unknown' ? appVersion : `v${appVersion}` }}</span>
          <span>Backend {{ backendVersion }}</span>
        </p>
      </div>
    </footer>
  </UApp>
</template>

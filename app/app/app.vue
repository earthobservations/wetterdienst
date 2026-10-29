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

// The pages, in two kinds: the questions and the tools that answer them, then what explains the data. The home page
// is "Ask": it opens on the questions.
const items = computed(() => [
  { label: t('nav.ask'), icon: 'i-lucide-message-circle-question', to: '/', active: route.path === '/' },
  { label: t('nav.meteogram'), icon: 'i-lucide-cloud-sun', to: '/meteogram', active: route.path.startsWith('/meteogram') },
  { label: t('nav.stripes'), icon: 'i-lucide-bar-chart-3', to: '/stripes', active: route.path.startsWith('/stripes') },
  { label: t('nav.explorer'), icon: 'i-lucide-compass', to: '/explorer', active: route.path.startsWith('/explorer') },
  { label: t('nav.history'), icon: 'i-lucide-clock', to: '/history', active: route.path.startsWith('/history') },
  { label: t('nav.providers'), icon: 'i-lucide-building-2', to: '/providers', active: route.path.startsWith('/providers'), reference: true },
  { label: t('nav.glossary'), icon: 'i-lucide-book-open', to: '/glossary', active: route.path.startsWith('/glossary'), reference: true },
  { label: t('nav.api'), icon: 'i-lucide-code', to: '/api', active: route.path === '/api', reference: true },
])

const { openPalette } = usePalette()
const shortcut = computed(() => import.meta.client && /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘K' : 'Ctrl K')
const shortcutKeys = 'Control+K Meta+K'

const projectLinks = computed(() => [
  { label: t('common.documentation'), icon: 'i-lucide-book-marked', to: 'https://wetterdienst.readthedocs.io/', external: true },
  { label: t('header.github'), icon: 'i-lucide-github', to: 'https://github.com/earthobservations/wetterdienst', external: true },
  { label: t('header.pypi'), icon: 'i-lucide-package', to: 'https://pypi.org/project/wetterdienst', external: true },
  // Support is about the project rather than the data, so it sits with the other project links rather than in
  // the task nav -- but as an icon, not a footer line, because issues, pull requests and donations all start here.
  { label: t('nav.support'), icon: 'i-lucide-heart', to: '/support', external: false },
])
</script>

<template>
  <div v-if="blank" />
  <UApp v-else :locale="uiLocale">
    <!-- tells a screen reader which page the client-side navigation has arrived on (WCAG 4.1.3) -->
    <NuxtRouteAnnouncer />
    <a v-if="!isWidget" href="#main" class="skip-link">{{ t('header.skip') }}</a>

    <header v-if="!isWidget" class="app-header sticky lg:static top-0 z-40 border-b border-default bg-default/95 backdrop-blur supports-[backdrop-filter]:bg-default/85">
      <div class="app-container flex items-center gap-2 sm:gap-4 h-(--app-header-height)">
        <NuxtLink to="/" class="app-brand flex items-center gap-2.5 shrink-0 rounded-lg">
          <img src="/icon.svg" alt="" class="size-8">
          <span class="text-lg font-bold tracking-tight text-(--app-ink)">Wetterdienst</span>
        </NuxtLink>

        <!-- the search entry of every page: it opens the command palette, as Ctrl+K and ⌘K do -->
        <button
          type="button"
          class="app-search ml-auto lg:ml-6 min-w-0 flex items-center gap-2 rounded-full border border-default bg-(--app-surface) text-muted hover:text-highlighted hover:border-accented transition-colors h-10 px-3 sm:px-4 lg:flex-1 lg:max-w-md"
          aria-haspopup="dialog"
          :aria-keyshortcuts="shortcutKeys"
          data-testid="search-button"
          @click="openPalette()"
        >
          <UIcon name="i-lucide-search" class="size-5 shrink-0" />
          <span class="text-sm truncate sr-only sm:not-sr-only">{{ t('header.search') }}</span>
          <span class="app-kbd ml-auto hidden lg:inline-flex" aria-hidden="true">{{ shortcut }}</span>
        </button>

        <div class="hidden lg:flex items-center gap-0.5 ml-auto">
          <UTooltip v-for="link in projectLinks" :key="link.to" :text="link.label">
            <UButton
              :to="link.to"
              :target="link.external ? '_blank' : undefined"
              :icon="link.icon"
              color="neutral"
              variant="ghost"
              :aria-label="link.label"
            />
          </UTooltip>
          <SettingsMenu />
        </div>
        <UButton
          class="lg:hidden"
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

      <nav :aria-label="t('header.mainNav')" class="hidden lg:block">
        <ul class="app-container flex items-center gap-1 -mb-px">
          <li v-for="(item, index) in items" :key="item.to" class="flex items-center">
            <span v-if="item.reference && !items[index - 1]?.reference" class="mx-2 h-5 w-px bg-(--ui-border-accented)" aria-hidden="true" />
            <NuxtLink
              :to="item.to"
              class="app-nav-link flex items-center gap-2 px-3 py-3 text-sm font-medium border-b-2 transition-colors"
              :class="item.active
                ? 'border-(--ui-color-primary-700) dark:border-(--ui-color-primary-300) text-highlighted'
                : 'border-transparent text-muted hover:text-highlighted hover:border-(--ui-border-accented)'"
              :aria-current="item.active ? 'page' : undefined"
            >
              <UIcon :name="item.icon" class="size-4 shrink-0" />
              {{ item.label }}
            </NuxtLink>
          </li>
        </ul>
      </nav>
    </header>

    <!-- The narrow layout's menu. A dialog, not a layer of markup: the focus stays in it, Escape closes
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
        <nav :aria-label="t('header.menu')" class="flex-1 overflow-y-auto px-3 py-4 flex flex-col gap-1">
          <NuxtLink
            v-for="item in items"
            :key="item.to"
            :to="item.to"
            class="app-nav-link flex items-center gap-4 px-4 py-3.5 rounded-xl text-base font-medium transition-colors"
            :class="item.active
              ? 'bg-primary-50 dark:bg-primary-950 text-primary'
              : 'text-gray-800 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'"
            :aria-current="item.active ? 'page' : undefined"
            @click="mobileMenuOpen = false"
          >
            <UIcon :name="item.icon" class="w-5 h-5 shrink-0" />
            {{ item.label }}
          </NuxtLink>
        </nav>

        <!-- Bottom bar: the project's links and the settings -->
        <div class="shrink-0 border-t border-default px-4 py-4 flex items-center justify-between">
          <div class="flex items-center gap-1">
            <UTooltip v-for="link in projectLinks" :key="link.to" :text="link.label">
              <UButton
                :to="link.to"
                :target="link.external ? '_blank' : undefined"
                :icon="link.icon"
                color="neutral"
                variant="ghost"
                :aria-label="link.label"
                @click="link.external ? undefined : (mobileMenuOpen = false)"
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

    <SearchPalette v-if="!isWidget" />

    <main id="main" tabindex="-1" class="min-h-[60vh] focus:outline-none">
      <NuxtPage />
    </main>

    <footer v-if="!isWidget" class="app-footer mt-12 border-t border-default bg-(--app-surface)">
      <div class="app-container py-8 flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
        <div class="space-y-2">
          <p class="flex items-center gap-2 font-bold text-(--app-ink)">
            <img src="/icon.svg" alt="" class="size-6">
            Wetterdienst
          </p>
          <p class="text-sm text-muted max-w-xs">
            {{ t('home.tagline') }}
          </p>
          <p class="text-xs text-muted">
            <span class="font-semibold text-toned">App</span> {{ appVersion === 'unknown' ? appVersion : `v${appVersion}` }}
            <span class="mx-1" aria-hidden="true">·</span>
            <span class="font-semibold text-toned">Backend</span> {{ backendVersion }}
          </p>
        </div>
        <!-- one row, its own separators: flex siblings cannot see where a line breaks, so a separator would dangle
             at the end of a wrapped line -->
        <div class="app-footer-links flex flex-wrap items-center gap-x-5 gap-y-2 text-sm md:justify-end md:max-w-xl">
          <NuxtLink to="/about" class="text-toned underline-offset-4 hover:underline hover:text-highlighted">
            {{ t('footer.about') }}
          </NuxtLink>
          <NuxtLink to="/support" class="text-toned underline-offset-4 hover:underline hover:text-highlighted">
            {{ t('nav.support') }}
          </NuxtLink>
          <NuxtLink to="/impressum" class="text-toned underline-offset-4 hover:underline hover:text-highlighted">
            {{ t('footer.legal') }}
          </NuxtLink>
          <NuxtLink to="/datenschutz" class="text-toned underline-offset-4 hover:underline hover:text-highlighted">
            {{ t('footer.privacy') }}
          </NuxtLink>
          <!-- a file of the app (modules/third-party-licenses, GH-3469), not a page: a plain link, which the router
               would otherwise take for a route -->
          <a href="/third-party-licenses.txt" class="text-toned underline-offset-4 hover:underline hover:text-highlighted">
            {{ t('footer.licenses') }}
          </a>
        </div>
      </div>
      <div class="border-t border-default">
        <div class="app-container py-4 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between text-xs text-muted">
          <span>{{ t('footer.copyright', { year: new Date().getFullYear() }) }}</span>
          <!-- The stance closes the footer, as it closes the home page, on a line of its own so it reads as a
               statement rather than as more entries in a link list. -->
          <div class="flex flex-wrap items-center gap-x-4 gap-y-1">
            <UTooltip v-for="value in values" :key="value.key" :text="value.text">
              <span
                class="text-lg leading-none cursor-default"
                role="img"
                :aria-label="value.text"
              >{{ value.emoji }}</span>
            </UTooltip>
          </div>
        </div>
      </div>
    </footer>
  </UApp>
</template>

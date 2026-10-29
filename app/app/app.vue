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

// the menu is the narrow layout's: past the breakpoint the masthead shows the sections itself, and a dialog
// that is hidden with CSS would still hold the focus
const wide = useMediaQuery('(min-width: 1024px)')
watch(wide, (isWide) => {
  if (isWide)
    mobileMenuOpen.value = false
})

// The sections of the app, in the order of the section bar. The four ways into the data carry the colour of their
// tile in the logo (the sun, the thermometer, the rain, the wind); the rest are reference.
type SectionTile = 'sun' | 'heat' | 'rain' | 'wind'
interface Section { label: string, to: string, icon: string, active: boolean, tile?: SectionTile }
// written out, as Tailwind finds a class only where it is spelled whole
const TILE_CLASS: Record<SectionTile, string> = { sun: 'bg-tile-sun', heat: 'bg-tile-heat', rain: 'bg-tile-rain', wind: 'bg-tile-wind' }

const items = computed<Section[]>(() => [
  { label: t('nav.home'), icon: 'i-lucide-home', to: '/', active: route.path === '/' },
  { label: t('nav.meteogram'), icon: 'i-lucide-sun', to: '/meteogram', active: route.path.startsWith('/meteogram'), tile: 'sun' },
  { label: t('nav.stripes'), icon: 'i-lucide-bar-chart-3', to: '/stripes', active: route.path.startsWith('/stripes'), tile: 'heat' },
  { label: t('nav.explorer'), icon: 'i-lucide-globe', to: '/explorer', active: route.path.startsWith('/explorer'), tile: 'rain' },
  { label: t('nav.history'), icon: 'i-lucide-clock', to: '/history', active: route.path.startsWith('/history'), tile: 'wind' },
  { label: t('nav.api'), icon: 'i-lucide-code', to: '/api', active: route.path.startsWith('/api') },
  { label: t('nav.providers'), icon: 'i-lucide-building-2', to: '/providers', active: route.path.startsWith('/providers') },
  { label: t('nav.glossary'), icon: 'i-lucide-book-open', to: '/glossary', active: route.path.startsWith('/glossary') },
])

// The project's own links, the same four in the masthead and in the narrow layout's menu (WCAG 3.2.6). Support is
// about the project rather than the data, so it sits with them rather than in the sections -- but as an icon, not
// a footer line only, because issues, pull requests and donations all start there.
const projectLinks = computed(() => [
  { key: 'docs', to: 'https://wetterdienst.readthedocs.io/', icon: 'i-lucide-book-open', label: t('common.documentation'), external: true },
  { key: 'github', to: 'https://github.com/earthobservations/wetterdienst', icon: 'i-lucide-github', label: t('header.github'), external: true },
  { key: 'pypi', to: 'https://pypi.org/project/wetterdienst', icon: 'i-lucide-package', label: t('header.pypi'), external: true },
  { key: 'support', to: '/support', icon: 'i-lucide-heart', label: t('nav.support'), external: false },
])

// The masthead's dateline: today, in the language of the page, as an almanac dates its edition
const today = computed(() => {
  try {
    return new Intl.DateTimeFormat(localeProperties.value.language ?? locale.value, { dateStyle: 'full' }).format(new Date())
  }
  catch {
    return ''
  }
})
</script>

<template>
  <div v-if="blank" />
  <UApp v-else :locale="uiLocale">
    <!-- tells a screen reader which page the client-side navigation has arrived on (WCAG 4.1.3) -->
    <NuxtRouteAnnouncer />
    <!-- the first stop of the keyboard: past the masthead to what the page is about (WCAG 2.4.1) -->
    <a
      v-if="!isWidget"
      href="#content"
      class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:rounded-sm focus:bg-default focus:text-highlighted focus:font-semibold"
    >{{ t('layout.skipToContent') }}</a>

    <!-- The masthead: the name of the publication, its dateline, and the sections below a heavy rule -->
    <header v-if="!isWidget" class="app-masthead">
      <div class="app-page flex items-center gap-3 sm:gap-4 py-3 sm:py-4">
        <NuxtLink to="/" class="flex items-center gap-2.5 sm:gap-3 min-w-0 rounded-sm">
          <img src="/icon.svg" alt="" class="size-8 sm:size-10 shrink-0">
          <span class="font-serif font-semibold text-[1.5rem] sm:text-[1.875rem] leading-none tracking-tight text-highlighted">Wetterdienst</span>
        </NuxtLink>
        <p v-if="today" class="hidden xl:block font-serif text-toned text-base ml-2 pl-4 border-l border-(--app-rule)">
          {{ today }}
        </p>

        <div class="app-masthead-tools ml-auto flex items-center gap-0.5">
          <!-- the project's links and the settings, past the breakpoint; the narrow layout has them in its menu -->
          <div class="hidden lg:flex items-center gap-0.5">
            <UTooltip v-for="link in projectLinks" :key="link.key" :text="link.label">
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
            variant="outline"
            :aria-label="t('header.menu')"
            aria-haspopup="dialog"
            :aria-expanded="mobileMenuOpen"
            @click="mobileMenuOpen = true"
          />
        </div>
      </div>
      <!-- the sections, as a newspaper's section bar: words, the one being read underlined in ink -->
      <nav :aria-label="t('layout.sections')" class="hidden lg:block border-y-2 border-(--app-rule-strong)">
        <ul class="app-page flex flex-wrap items-stretch gap-x-6 xl:gap-x-8">
          <li v-for="item in items" :key="item.to" class="flex">
            <NuxtLink
              :to="item.to"
              :aria-current="item.active ? 'page' : undefined"
              class="group flex items-center gap-2 py-2.5 text-sm font-medium border-b-[3px] -mb-[2px] transition-colors"
              :class="item.active
                ? 'border-(--app-rule-strong) text-highlighted'
                : 'border-transparent text-toned hover:text-highlighted hover:border-(--app-rule)'"
            >
              <span v-if="item.tile" class="app-tile size-2.5" :class="TILE_CLASS[item.tile]" aria-hidden="true" />
              {{ item.label }}
            </NuxtLink>
          </li>
        </ul>
      </nav>
      <div class="lg:hidden border-b-2 border-(--app-rule-strong)" aria-hidden="true" />
    </header>

    <!-- The narrow layout's menu: the contents, as a dialog. The focus stays in it, Escape closes it and the page
         behind is hidden from a screen reader while it is open (WCAG 2.1.2, 2.4.3, 4.1.2) -->
    <UModal
      v-if="!isWidget"
      v-model:open="mobileMenuOpen"
      fullscreen
      :title="t('header.menu')"
      close
      :ui="{ header: 'border-b-2 border-(--app-rule-strong)', title: 'font-serif text-2xl', body: 'flex flex-col flex-1 p-0 sm:p-0' }"
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
        <nav :aria-label="t('header.menu')" class="flex-1 overflow-y-auto px-4 py-2">
          <ul class="divide-y divide-(--app-rule)">
            <li v-for="item in items" :key="item.to">
              <NuxtLink
                :to="item.to"
                :aria-current="item.active ? 'page' : undefined"
                class="flex items-center gap-4 py-3.5 font-serif text-xl transition-colors"
                :class="item.active ? 'text-highlighted font-semibold underline decoration-2 underline-offset-[6px]' : 'text-default hover:text-highlighted'"
                @click="mobileMenuOpen = false"
              >
                <span class="app-tile size-3" :class="item.tile ? TILE_CLASS[item.tile] : 'bg-(--app-rule)'" aria-hidden="true" />
                {{ item.label }}
              </NuxtLink>
            </li>
          </ul>
        </nav>

        <!-- the project's links and the settings -->
        <div class="shrink-0 border-t border-(--app-rule) px-4 py-3 flex items-center justify-between">
          <div class="flex items-center gap-1">
            <UTooltip v-for="link in projectLinks" :key="link.key" :text="link.label">
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

    <UMain id="content" tabindex="-1" class="focus:outline-none">
      <NuxtPage />
    </UMain>

    <!-- The colophon: who publishes it, in which versions, and what the project stands for -->
    <footer v-if="!isWidget" class="app-footer mt-16 border-t-2 border-(--app-rule-strong)">
      <div class="app-page py-8 grid gap-6 md:grid-cols-[minmax(0,1fr)_auto] md:items-start text-sm">
        <div class="space-y-2">
          <p class="flex items-center gap-2">
            <img src="/icon.svg" alt="" class="size-5">
            <span class="font-serif font-semibold text-lg text-highlighted">Wetterdienst</span>
          </p>
          <p class="text-muted">
            {{ t('footer.copyright', { year: new Date().getFullYear() }) }}
          </p>
          <p class="text-xs text-muted">
            <span class="font-semibold text-toned">App</span> {{ appVersion === 'unknown' ? appVersion : `v${appVersion}` }}
            <span class="mx-1" aria-hidden="true">·</span>
            <span class="font-semibold text-toned">Backend</span> {{ backendVersion }}
          </p>
        </div>
        <div class="space-y-3 md:text-right">
          <!-- links, not a navigation: the sections are the masthead's -->
          <ul class="flex flex-wrap md:justify-end gap-x-4 gap-y-1">
            <li>
              <NuxtLink to="/about" class="text-toned underline-offset-4 hover:underline hover:text-highlighted">
                {{ t('footer.about') }}
              </NuxtLink>
            </li>
            <li>
              <NuxtLink to="/support" class="text-toned underline-offset-4 hover:underline hover:text-highlighted">
                {{ t('nav.support') }}
              </NuxtLink>
            </li>
            <li>
              <NuxtLink to="/impressum" class="text-toned underline-offset-4 hover:underline hover:text-highlighted">
                {{ t('footer.legal') }}
              </NuxtLink>
            </li>
            <li>
              <NuxtLink to="/datenschutz" class="text-toned underline-offset-4 hover:underline hover:text-highlighted">
                {{ t('footer.privacy') }}
              </NuxtLink>
            </li>
            <li>
              <!-- a file of the app (modules/third-party-licenses, GH-3469), not a page: a plain link, which the router
                   would otherwise take for a route -->
              <a href="/third-party-licenses.txt" class="text-toned underline-offset-4 hover:underline hover:text-highlighted">
                {{ t('footer.licenses') }}
              </a>
            </li>
          </ul>
          <!-- The stance closes the footer, as it closes the home page, on a line of its own so that it reads as a
               statement rather than as more entries in a link list. -->
          <div class="flex flex-wrap md:justify-end items-center gap-x-4 gap-y-1">
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

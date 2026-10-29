<script setup lang="ts">
import { de as uiDe, en as uiEn } from '@nuxt/ui/locale'
import { canonicalUrl, findSeoRoute, HOME_TITLE_KEY, isNotIndexed, siteOrigin } from '#shared/utils/seo'
import { AXIS_STOPS, PAGE_LABEL_KEYS, REFERENCE_PAGES } from '~/composables/useTimeAxis'
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

// The pages off the axis of time (GH-3518): the three a reader looks things up in are beside the search in the
// header, the rest in the footer; the menu of the narrow layout has them all, and so does the palette
const { current, span } = useTimeAxis()
const referenceLinks = computed(() => REFERENCE_PAGES.filter(page => page.inRail).map(page => ({
  ...page,
  label: t(PAGE_LABEL_KEYS[page.key]),
  active: current.value === page.key,
})))
const menuStops = computed(() => AXIS_STOPS.map(stop => ({
  ...stop,
  label: t(PAGE_LABEL_KEYS[stop.key]),
  span: span(stop.key),
  active: current.value === stop.key,
})))

const projectLinks = computed(() => [
  { key: 'docs', to: 'https://wetterdienst.readthedocs.io/', icon: 'i-lucide-book-open', label: t('common.documentation') },
  { key: 'github', to: 'https://github.com/earthobservations/wetterdienst', icon: 'i-lucide-github', label: t('header.github') },
  { key: 'pypi', to: 'https://pypi.org/project/wetterdienst', icon: 'i-lucide-package', label: t('header.pypi') },
])

// The command palette: the search button, and Ctrl+K / Cmd+K anywhere but in the widget, which has no frame
const palette = useCommandPalette()
const paletteOpen = palette.open
function openPalette() {
  mobileMenuOpen.value = false
  palette.show()
}
useEventListener('keydown', (event: KeyboardEvent) => {
  if (isWidget.value || blank.value || event.defaultPrevented || !isPaletteShortcut(event))
    return
  event.preventDefault()
  if (palette.open.value)
    palette.hide()
  else
    openPalette()
})
// the key the shortcut is written with: the command key on a Mac, Ctrl elsewhere
const shortcutLabel = ref('Ctrl K')
onMounted(() => {
  if (/Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent))
    shortcutLabel.value = '⌘K'
})
</script>

<template>
  <div v-if="blank" />
  <UApp v-else :locale="uiLocale">
    <!-- tells a screen reader which page the client-side navigation has arrived on (WCAG 4.1.3) -->
    <NuxtRouteAnnouncer />
    <a v-if="!isWidget" href="#main" class="skip-link">{{ t('common.skipToContent') }}</a>

    <!-- The bar that stays on top: the name, the search (the command palette) and the reference pages -->
    <header v-if="!isWidget" class="app-bar">
      <div class="app-container app-bar__inner">
        <NuxtLink to="/" class="app-brand">
          <img src="/icon.svg" alt="" class="app-brand__logo" width="28" height="28">
          <span class="app-brand__name">Wetterdienst</span>
        </NuxtLink>

        <button
          type="button"
          class="search-trigger"
          aria-haspopup="dialog"
          :aria-expanded="paletteOpen"
          aria-keyshortcuts="Control+K Meta+K"
          data-testid="search-trigger"
          @click="openPalette"
        >
          <UIcon name="i-lucide-search" class="search-trigger__icon" />
          <span class="search-trigger__label">{{ t('palette.open') }}</span>
          <span class="search-trigger__hint">{{ t('palette.openHint') }}</span>
          <kbd class="search-trigger__kbd" aria-hidden="true">{{ shortcutLabel }}</kbd>
        </button>

        <nav :aria-label="t('axis.reference')" class="app-ref-nav">
          <NuxtLink
            v-for="link in referenceLinks"
            :key="link.key"
            :to="link.path"
            class="app-ref-nav__link"
            :aria-current="link.active ? 'page' : undefined"
          >
            {{ link.label }}
          </NuxtLink>
        </nav>

        <div class="app-bar__tools">
          <UTooltip v-for="link in projectLinks" :key="link.key" :text="link.label">
            <UButton
              :to="link.to"
              target="_blank"
              :icon="link.icon"
              color="neutral"
              variant="ghost"
              :aria-label="link.label"
            />
          </UTooltip>
          <!-- Support is about the project rather than the data, so it sits with the other project links rather
               than in the navigation -- as an icon, because issues, pull requests and donations all start here. -->
          <UTooltip :text="t('nav.support')">
            <UButton
              to="/support"
              icon="i-lucide-heart"
              color="neutral"
              variant="ghost"
              :aria-label="t('nav.support')"
            />
          </UTooltip>
          <SettingsMenu />
        </div>

        <UButton
          class="lg:hidden shrink-0"
          icon="i-lucide-menu"
          color="neutral"
          variant="ghost"
          :aria-label="t('header.menu')"
          aria-haspopup="dialog"
          :aria-expanded="mobileMenuOpen"
          @click="mobileMenuOpen = true"
        />
      </div>
    </header>

    <!-- The navigation: the pages along the axis of time, from the oldest records to the forecast -->
    <AppTimeRail v-if="!isWidget" />

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
        <nav :aria-label="t('header.menu')" class="menu-nav">
          <p class="menu-nav__heading" aria-hidden="true">
            {{ t('axis.label') }}
          </p>
          <ol class="menu-nav__axis">
            <li v-for="stop in menuStops" :key="stop.key" class="menu-nav__stop" :class="`menu-nav__stop--${stop.zone}`">
              <NuxtLink
                :to="stop.path"
                class="menu-nav__link"
                :class="{ 'is-active': stop.active }"
                :aria-current="stop.active ? 'page' : undefined"
                @click="mobileMenuOpen = false"
              >
                <UIcon :name="stop.icon" class="size-5 shrink-0" />
                <span class="min-w-0">
                  <span class="block">{{ stop.label }}</span>
                  <span class="menu-nav__zone"><span class="sr-only">{{ t(`axis.${stop.zone}`) }}: </span>{{ stop.span }}</span>
                </span>
              </NuxtLink>
            </li>
          </ol>
          <p class="menu-nav__heading" aria-hidden="true">
            {{ t('axis.reference') }}
          </p>
          <ul class="menu-nav__ref">
            <li v-for="link in referenceLinks" :key="link.key">
              <NuxtLink
                :to="link.path"
                class="menu-nav__link"
                :class="{ 'is-active': link.active }"
                :aria-current="link.active ? 'page' : undefined"
                @click="mobileMenuOpen = false"
              >
                <UIcon :name="link.icon" class="size-5 shrink-0" />
                {{ link.label }}
              </NuxtLink>
            </li>
          </ul>
        </nav>

        <!-- Bottom bar: external links + settings -->
        <div class="shrink-0 border-t border-default px-4 py-4 flex items-center justify-between">
          <div class="flex items-center gap-1">
            <UTooltip v-for="link in projectLinks" :key="link.key" :text="link.label">
              <UButton
                :to="link.to"
                target="_blank"
                :icon="link.icon"
                color="neutral"
                variant="ghost"
                :aria-label="link.label"
              />
            </UTooltip>
            <!-- matches the desktop header: Support is not in the navigation, so it has to be here or
                 the menu loses it entirely -->
            <UTooltip :text="t('nav.support')">
              <UButton
                to="/support"
                icon="i-lucide-heart"
                color="neutral"
                variant="ghost"
                :aria-label="t('nav.support')"
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

    <CommandPalette v-if="!isWidget" />

    <main id="main" tabindex="-1" class="app-main">
      <NuxtPage />
    </main>

    <footer v-if="!isWidget" class="app-footer">
      <div class="app-container app-footer__inner">
        <div class="app-footer__brand">
          <p class="app-footer__name">
            <img src="/icon.svg" alt="" class="size-5" width="20" height="20">
            Wetterdienst
          </p>
          <p class="app-footer__tagline">
            {{ t('home.tagline') }}
          </p>
          <!-- The stance closes the footer, as it closes the home page: the four statements as icons, the full
               wording one hover away and the accessible name either way. -->
          <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
            <UTooltip v-for="value in values" :key="value.key" :text="value.text">
              <span
                class="text-lg leading-none cursor-default"
                role="img"
                :aria-label="value.text"
              >{{ value.emoji }}</span>
            </UTooltip>
          </div>
        </div>
        <ul class="app-footer__links">
          <li>
            <NuxtLink to="/about" class="app-footer__link">
              {{ t('footer.about') }}
            </NuxtLink>
          </li>
          <li>
            <NuxtLink to="/support" class="app-footer__link">
              {{ t('nav.support') }}
            </NuxtLink>
          </li>
          <!-- the legal notice and the privacy policy side by side, as the two the law asks for -->
          <li class="flex flex-wrap gap-x-4 gap-y-1">
            <NuxtLink to="/impressum" class="app-footer__link">
              {{ t('footer.legal') }}
            </NuxtLink>
            <NuxtLink to="/datenschutz" class="app-footer__link">
              {{ t('footer.privacy') }}
            </NuxtLink>
          </li>
          <li>
            <!-- a file of the app (modules/third-party-licenses, GH-3469), not a page: a plain link, which the router
                 would otherwise take for a route -->
            <a href="/third-party-licenses.txt" class="app-footer__link">
              {{ t('footer.licenses') }}
            </a>
          </li>
        </ul>
        <div class="app-footer__meta">
          <p>{{ t('footer.copyright', { year: new Date().getFullYear() }) }}</p>
          <p class="tabular-nums">
            App {{ appVersion === 'unknown' ? appVersion : `v${appVersion}` }}
            <span aria-hidden="true">·</span>
            Backend {{ backendVersion }}
          </p>
        </div>
      </div>
    </footer>
  </UApp>
</template>

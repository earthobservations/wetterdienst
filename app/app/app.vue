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
// The map is the home page (GH-3518): it takes the whole window between the header and a one-line footer
const isHome = computed(() => route.path === '/')

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

// The same four statements the about page spells out, as icons here: the footer is on every page,
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
const wide = useMediaQuery('(min-width: 1280px)')
watch(wide, (isWide) => {
  if (isWide)
    mobileMenuOpen.value = false
})

interface NavItem {
  label: string
  icon: string
  to: string
  active: boolean
}

function item(to: string, label: string, icon: string): NavItem {
  return { to, label, icon, active: to === '/' ? route.path === '/' : route.path.startsWith(to) }
}

// Two groups: what works on the data (the map first, as it is where everything starts), and what
// explains it. The header shows both as words, the narrow layout's menu as two lists.
const dataItems = computed<NavItem[]>(() => [
  item('/', t('nav.map'), 'i-lucide-map'),
  item('/meteogram', t('nav.meteogram'), 'i-lucide-cloud-sun'),
  item('/stripes', t('nav.stripes'), 'i-lucide-chart-column-big'),
  item('/explorer', t('nav.explorer'), 'i-lucide-table-2'),
  item('/history', t('nav.history'), 'i-lucide-history'),
])
const referenceItems = computed<NavItem[]>(() => [
  item('/api', t('nav.api'), 'i-lucide-code'),
  item('/providers', t('nav.providers'), 'i-lucide-building-2'),
  item('/glossary', t('nav.glossary'), 'i-lucide-book-open'),
])
const projectItems = computed<NavItem[]>(() => [
  item('/about', t('footer.about'), 'i-lucide-info'),
  item('/support', t('nav.support'), 'i-lucide-heart'),
  item('/settings', t('common.settings'), 'i-lucide-settings-2'),
])

// The project's links outside the app, in the header and in the menu, in the same order (WCAG 3.2.6)
const externalLinks = computed(() => [
  { key: 'docs', to: 'https://wetterdienst.readthedocs.io/', icon: 'i-lucide-book-marked', label: t('common.documentation') },
  { key: 'github', to: 'https://github.com/earthobservations/wetterdienst', icon: 'i-simple-icons-github', label: t('header.github') },
  { key: 'pypi', to: 'https://pypi.org/project/wetterdienst', icon: 'i-simple-icons-pypi', label: t('header.pypi') },
])

const legalLinks = computed(() => [
  { key: 'about', to: '/about', label: t('footer.about') },
  { key: 'support', to: '/support', label: t('nav.support') },
  { key: 'impressum', to: '/impressum', label: t('footer.legal') },
  { key: 'datenschutz', to: '/datenschutz', label: t('footer.privacy') },
])
</script>

<template>
  <div v-if="blank" />
  <UApp v-else :locale="uiLocale">
    <!-- tells a screen reader which page the client-side navigation has arrived on (WCAG 4.1.3) -->
    <NuxtRouteAnnouncer />
    <!-- the first stop of the keyboard, past the header's links to what the page is for (WCAG 2.4.1) -->
    <a v-if="!isWidget" href="#main" class="app-skip">{{ t('header.skip') }}</a>

    <header v-if="!isWidget" class="app-header">
      <NuxtLink to="/" class="app-brand" :aria-current="isHome ? 'page' : undefined">
        <img src="/icon.svg" alt="" class="size-7 shrink-0" width="28" height="28">
        <span class="app-brand-name">Wetterdienst</span>
      </NuxtLink>

      <!-- the pages, as words: from 1280 px; the menu holds them below -->
      <nav :aria-label="t('header.pages')" class="app-nav">
        <ul class="app-nav-list">
          <li v-for="entry in dataItems" :key="entry.to">
            <NuxtLink :to="entry.to" class="app-nav-link" :class="{ 'is-active': entry.active }" :aria-current="entry.active ? 'page' : undefined">
              {{ entry.label }}
            </NuxtLink>
          </li>
        </ul>
        <span class="app-nav-divider" aria-hidden="true" />
        <ul class="app-nav-list">
          <li v-for="entry in referenceItems" :key="entry.to">
            <NuxtLink :to="entry.to" class="app-nav-link" :class="{ 'is-active': entry.active }" :aria-current="entry.active ? 'page' : undefined">
              {{ entry.label }}
            </NuxtLink>
          </li>
        </ul>
      </nav>

      <div class="app-header-actions">
        <div class="hidden xl:flex items-center gap-0.5">
          <UTooltip v-for="link in externalLinks" :key="link.key" :text="link.label">
            <UButton :to="link.to" target="_blank" :icon="link.icon" color="neutral" variant="ghost" :aria-label="link.label" />
          </UTooltip>
          <!-- Support is about the project rather than the data, so it sits with the other project links
               rather than in the pages -- as an icon, because issues, pull requests and donations all start here -->
          <UTooltip :text="t('nav.support')">
            <UButton to="/support" icon="i-lucide-heart" color="neutral" variant="ghost" :aria-label="t('nav.support')" />
          </UTooltip>
        </div>
        <SettingsMenu />
        <UButton
          class="xl:hidden"
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

    <!-- The narrow layout's menu: a sheet from the side, and a dialog, not a layer of markup: the focus stays in
         it, Escape closes it and the page behind is hidden from a screen reader while it is open (WCAG 2.1.2,
         2.4.3, 4.1.2) -->
    <USlideover
      v-if="!isWidget"
      v-model:open="mobileMenuOpen"
      side="right"
      :title="t('header.menu')"
      close
      :ui="{ content: 'max-w-sm', body: 'flex flex-col gap-6 p-4 sm:p-5' }"
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
        <nav :aria-label="t('header.menu')" class="flex flex-col gap-6">
          <div v-for="group in [{ key: 'data', title: t('header.groupData'), entries: dataItems }, { key: 'reference', title: t('header.groupReference'), entries: referenceItems }, { key: 'project', title: t('header.groupProject'), entries: projectItems }]" :key="group.key">
            <h2 class="app-menu-heading">
              {{ group.title }}
            </h2>
            <ul class="flex flex-col gap-0.5">
              <li v-for="entry in group.entries" :key="entry.to">
                <NuxtLink
                  :to="entry.to"
                  class="app-menu-link"
                  :class="{ 'is-active': entry.active }"
                  :aria-current="entry.active ? 'page' : undefined"
                  @click="mobileMenuOpen = false"
                >
                  <UIcon :name="entry.icon" class="size-5 shrink-0" />
                  {{ entry.label }}
                </NuxtLink>
              </li>
            </ul>
          </div>
        </nav>
        <div class="mt-auto flex items-center gap-1 border-t border-default pt-4">
          <UTooltip v-for="link in externalLinks" :key="link.key" :text="link.label">
            <UButton :to="link.to" target="_blank" :icon="link.icon" color="neutral" variant="ghost" :aria-label="link.label" />
          </UTooltip>
        </div>
      </template>
    </USlideover>

    <UMain id="main" tabindex="-1" class="app-main" :class="{ 'is-home': isHome }">
      <NuxtPage />
    </UMain>

    <footer v-if="!isWidget" class="app-footer" :class="{ 'is-home': isHome }">
      <p class="app-footer-versions tabular">
        <span>App {{ appVersion === 'unknown' ? appVersion : `v${appVersion}` }}</span>
        <span aria-hidden="true">·</span>
        <span>Backend {{ backendVersion }}</span>
      </p>
      <ul class="app-footer-links">
        <li>{{ t('footer.copyright', { year: new Date().getFullYear() }) }}</li>
        <li v-for="link in legalLinks" :key="link.key">
          <NuxtLink :to="link.to">
            {{ link.label }}
          </NuxtLink>
        </li>
        <!-- a file of the app (modules/third-party-licenses, GH-3469), not a page: a plain link, which the router
             would otherwise take for a route -->
        <li>
          <a href="/third-party-licenses.txt">{{ t('footer.licenses') }}</a>
        </li>
      </ul>
      <!-- The stance closes the footer, on a line of its own so it reads as a statement rather than as
           more entries in a link list. -->
      <ul class="app-footer-values">
        <li v-for="value in values" :key="value.key">
          <UTooltip :text="value.text">
            <span class="cursor-default" role="img" :aria-label="value.text">{{ value.emoji }}</span>
          </UTooltip>
        </li>
      </ul>
    </footer>
  </UApp>
</template>

<style>
/* The frame of every page (GH-3518): a header of one line, the page, and a quiet footer. The map page
   takes the window between them; every other page scrolls as a document. */
.app-skip {
  position: absolute;
  left: 0.75rem;
  top: -4rem;
  z-index: 100;
  padding: 0.5rem 0.875rem;
  border-radius: var(--ui-radius);
  background: var(--ui-bg);
  color: var(--ui-text-highlighted);
  font-weight: 600;
  box-shadow: 0 2px 10px rgb(15 23 42 / 0.15);
}
.app-skip:focus {
  top: 0.5rem;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 1rem;
  min-height: var(--ui-header-height);
  padding: 0.25rem 0.75rem 0.25rem 1rem;
  background: var(--ui-bg);
  border-bottom: 1px solid var(--ui-border);
}
@media (min-width: 640px) {
  .app-header {
    padding-inline: 1.25rem 1rem;
  }
}

.app-brand {
  display: inline-flex;
  align-items: center;
  gap: 0.625rem;
  min-height: 2.75rem;
  padding-inline-end: 0.25rem;
  border-radius: var(--ui-radius);
  color: var(--ui-text-highlighted);
  font-weight: 700;
  font-size: 1.0625rem;
  letter-spacing: -0.01em;
  white-space: nowrap;
}
.app-brand {
  min-width: 2.75rem;
}
/* the logo alone on the narrowest screens; its name, hidden only from sight, is the link's name either way */
@media (max-width: 379.98px) {
  .app-brand-name {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }
}

.app-nav {
  display: none;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}
@media (min-width: 1280px) {
  .app-nav {
    display: flex;
  }
}
.app-nav-list {
  display: flex;
  align-items: center;
  gap: 0.125rem;
}
.app-nav-divider {
  width: 1px;
  height: 1.25rem;
  background: var(--ui-border-accented);
}
.app-nav-link {
  display: inline-flex;
  align-items: center;
  min-height: 2.25rem;
  padding: 0.375rem 0.625rem;
  border-radius: calc(var(--ui-radius) * 1.5);
  color: var(--ui-text-toned);
  font-size: 0.9375rem;
  font-weight: 500;
  white-space: nowrap;
  transition: background-color 120ms, color 120ms;
}
.app-nav-link:hover {
  color: var(--ui-text-highlighted);
  background: var(--ui-bg-elevated);
}
.app-nav-link.is-active {
  color: var(--ui-text-highlighted);
  font-weight: 700;
  background: var(--ui-bg-elevated);
  /* the page one is on, told by the weight and the fill, and in forced colours by an underline */
  text-decoration: underline 2px transparent;
  text-underline-offset: 0.35em;
}
@media (forced-colors: active) {
  .app-nav-link.is-active {
    text-decoration-color: CanvasText;
  }
}

.app-header-actions {
  display: flex;
  align-items: center;
  gap: 0.125rem;
  margin-inline-start: auto;
}

.app-menu-heading {
  margin: 0 0 0.375rem 0.75rem;
  color: var(--ui-text-muted);
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.app-menu-link {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  min-height: 2.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: calc(var(--ui-radius) * 1.5);
  color: var(--ui-text);
  font-weight: 500;
}
.app-menu-link:hover {
  background: var(--ui-bg-elevated);
  color: var(--ui-text-highlighted);
}
.app-menu-link.is-active {
  background: var(--ui-color-primary-50);
  color: var(--ui-color-primary-800);
  font-weight: 700;
}
.dark .app-menu-link.is-active {
  background: var(--ui-color-primary-950);
  color: var(--ui-color-primary-300);
}

.app-main:focus {
  outline: none;
}
.app-main.is-home {
  /* the map page has no scroll of its own on a wide screen: it fills what the header and footer leave */
  min-height: 0;
}

.app-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 0.375rem 1.25rem;
  padding: 1.25rem 1rem 1.5rem;
  border-top: 1px solid var(--ui-border);
  color: var(--ui-text-muted);
  font-size: 0.8125rem;
  text-align: center;
}
.app-footer ul {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: 0.25rem 1rem;
}
.app-footer a {
  display: inline-block;
  padding-block: 0.25rem;
  color: var(--ui-text-muted);
  text-decoration: underline;
  text-decoration-color: color-mix(in oklab, currentColor 35%, transparent);
  text-underline-offset: 0.2em;
}
.app-footer a:hover {
  color: var(--ui-text-highlighted);
  text-decoration-color: currentColor;
}
.app-footer-versions {
  display: flex;
  gap: 0.375rem;
}
.app-footer-values {
  font-size: 1rem;
}
/* On a wide screen the map page's footer is one line under the map, as a map's attribution is */
@media (min-width: 1024px) {
  .app-footer.is-home {
    flex-wrap: nowrap;
    justify-content: flex-start;
    min-height: var(--app-footer-height);
    padding: 0.25rem 1.25rem;
    gap: 1.25rem;
    white-space: nowrap;
    overflow-x: auto;
  }
  .app-footer.is-home .app-footer-values {
    margin-inline-start: auto;
  }
}
</style>

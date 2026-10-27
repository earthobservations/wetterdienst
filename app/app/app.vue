<script setup lang="ts">
import { de as uiDe, en as uiEn } from '@nuxt/ui/locale'
import { canonicalUrl, findSeoRoute, HOME_TITLE_KEY, isNotIndexed, siteOrigin } from '#shared/utils/seo'

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
</script>

<template>
  <div v-if="blank" />
  <UApp v-else :locale="uiLocale">
    <!-- tells a screen reader which page the client-side navigation has arrived on (WCAG 4.1.3) -->
    <NuxtRouteAnnouncer />
    <!-- header and footer are the layout's (layouts/default.vue); the widget, which is embedded by other sites, has its own
         (layouts/widget.vue) and none of them -->
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>

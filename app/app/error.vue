<script setup lang="ts">
import type { NuxtError } from '#app'
// Nuxt's own error page, which is what the app showed before this file existed (and what a project without an
// `error.vue` gets); it is not a registered component, so it is imported. It draws every error but a 404.
import NuxtErrorPage from '#app/components/nuxt-error-page.vue'

// Drawn unless the page is framed by another origin outside the widget: then there is nothing to show
// (`app/utils/frame-guard.ts`), which is also why none of what it draws names the path that was asked for.
const props = defineProps<{ error: NuxtError }>()

const { t, locale } = useI18n()
const router = useRouter()

const blank = useFrameBlank()
// Nuxt's own 404 page injects an inline script for its back button, which the Content Security Policy
// (a nonce per response, no `'unsafe-inline'` for scripts) refuses, so the button never appeared. This one is
// drawn by Vue, in the language of the app, and has a link home that does not need a script.
const notFound = computed(() => props.error.statusCode === 404)

// A back button only where there is a page of the app to go back to, as in Nuxt's own page: the router's state names
// the previous page of an in-app `showError(404)` (an unknown path that the router is asked for is a full load in
// production, `serverPathFallback`), and a same-origin referrer the page a full load came from. Both need a history
// to go back in: a tab opened by a link (`target="_blank"`, a middle click) has the referrer and no earlier entry,
// and its button would do nothing.
const canGoBack = ref(false)
onMounted(() => {
  const fromApp = Boolean(window.history.state?.back) || document.referrer.startsWith(`${window.location.origin}/`)
  canGoBack.value = fromApp && window.history.length > 1
})

useHead(() => notFound.value && !blank.value
  ? { htmlAttrs: { lang: locale.value }, title: `${t('notFound.title')} - Wetterdienst` }
  : {})
</script>

<template>
  <div v-if="blank" />
  <main v-else-if="notFound" class="min-h-screen grid place-content-center px-4 text-center">
    <div class="max-w-lg">
      <p class="text-6xl font-medium tabular-nums mb-4">
        404
      </p>
      <h1 class="text-2xl font-semibold mb-2">
        {{ t('notFound.title') }}
      </h1>
      <p class="text-muted mb-6">
        {{ t('notFound.text') }}
      </p>
      <div class="flex flex-wrap items-center justify-center gap-3">
        <UButton to="/" icon="i-lucide-home" :label="t('notFound.home')" />
        <UButton
          v-if="canGoBack"
          icon="i-lucide-arrow-left"
          color="neutral"
          variant="outline"
          :label="t('notFound.back')"
          @click="router.back()"
        />
      </div>
    </div>
  </main>
  <NuxtErrorPage v-else :error="error" />
</template>

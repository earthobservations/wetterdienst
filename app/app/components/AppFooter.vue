<script setup lang="ts">
import pkg from '../../package.json'

// The footer of every page but the widget (GH-3518: moved out of app.vue, restyled; the links and the licence link
// are those it had). On the width of the header and of the wide pages, with the same gutters.
const { t } = useI18n()

// Deliberately not awaited. A top-level `await` in the root component makes its setup async, and
// with `ssr: false` that suspends the entire app -- header, page and footer -- behind this one
// request, so every cold load stared at an empty screen until the backend answered. The footer
// simply has nothing to show for the backend until the answer lands.
const { data: versionData, status: versionStatus } = useFetch<{ version: string }>('/api/version')

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

const LINK = 'text-muted hover:text-primary transition-colors motion-reduce:transition-none'
</script>

<template>
  <footer class="relative mt-16 border-t border-default bg-muted/40">
    <!-- the four tiles of the logo, as a line -->
    <div class="absolute inset-x-0 top-0 h-1 grid grid-cols-4" aria-hidden="true">
      <span class="bg-sun" />
      <span class="bg-brand-600" />
      <span class="bg-teal" />
      <span class="bg-coral" />
    </div>

    <UContainer class="flex flex-col gap-6 py-8 lg:py-10">
      <div class="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
        <div class="flex items-start gap-3">
          <img src="/icon.svg" alt="" class="size-10 rounded-xl">
          <div>
            <div class="font-bold text-highlighted">
              Wetterdienst
            </div>
            <!-- versions as a pair of small badges rather than a line of grey text -->
            <div class="mt-1.5 flex flex-wrap gap-1.5 text-xs">
              <span class="inline-flex items-center gap-1 rounded-full bg-elevated px-2 py-0.5 text-muted">
                <span class="font-medium text-primary">App</span> {{ appVersion === 'unknown' ? appVersion : `v${appVersion}` }}
              </span>
              <span class="inline-flex items-center gap-1 rounded-full bg-elevated px-2 py-0.5 text-muted">
                <span class="font-medium text-primary">Backend</span> {{ backendVersion }}
              </span>
            </div>
          </div>
        </div>

        <!-- Each link in its own list item, so that no separator is left dangling at the end of a wrapped line. -->
        <ul class="flex flex-wrap gap-x-6 gap-y-2 text-sm">
          <li>
            <NuxtLink to="/about" :class="LINK">
              {{ t('footer.about') }}
            </NuxtLink>
          </li>
          <li>
            <NuxtLink to="/support" :class="LINK">
              {{ t('nav.support') }}
            </NuxtLink>
          </li>
          <li>
            <NuxtLink to="/impressum" :class="LINK">
              {{ t('footer.legal') }}
            </NuxtLink>
          </li>
          <li>
            <NuxtLink to="/datenschutz" :class="LINK">
              {{ t('footer.privacy') }}
            </NuxtLink>
          </li>
          <li>
            <!-- a file of the app (modules/third-party-licenses, GH-3469), not a page: a plain link, which the router
               would otherwise take for a route -->
            <a href="/third-party-licenses.txt" :class="LINK">
              {{ t('footer.licenses') }}
            </a>
          </li>
        </ul>
      </div>

      <USeparator />

      <div class="flex flex-col-reverse gap-4 sm:flex-row sm:items-center sm:justify-between text-sm text-muted">
        <span>{{ t('footer.copyright', { year: new Date().getFullYear() }) }}</span>
        <!-- The stance closes the footer, as it closes the home page. -->
        <div class="flex items-center gap-4">
          <UTooltip v-for="value in values" :key="value.key" :text="value.text">
            <span
              class="text-lg leading-none cursor-default"
              role="img"
              :aria-label="value.text"
            >{{ value.emoji }}</span>
          </UTooltip>
        </div>
      </div>
    </UContainer>
  </footer>
</template>

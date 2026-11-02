<script setup lang="ts">
import { EXTERNAL, REFERENCE, TOOLS } from '~/utils/sections'
import pkg from '../../package.json'

// The foot of every page but the widget (GH-3518): what the project is and stands for, the places of the app in
// the groups of the navigation, and the legal line. The documentation, the code and the support page are here on
// every page in the same order (WCAG 3.2.6). The groups are lists under headings, not landmarks of their own: the
// navigation is the header's.
const { t } = useI18n()

// Deliberately not awaited. A top-level `await` in the shell makes its setup async, and with `ssr: false` that
// suspends the entire app -- header, page and footer -- behind this one request, so every cold load stared at an
// empty screen until the backend answered. The footer simply has nothing to show for the backend until the answer
// lands. A page that draws nothing (framed by another origin outside the widget) has no footer, so does not ask.
const { data: versionData, status: versionStatus } = useFetch<{ version: string }>('/api/version')

const backendVersion = computed(() => {
  const version = versionData.value?.version
  if (version)
    return `v${version}`
  // still in flight is not the same as answered-but-unusable, and only the latter is "unknown"
  return versionStatus.value === 'pending' ? '…' : 'unknown'
})
const appVersion = pkg.version ? `v${pkg.version}` : 'unknown'

// The same four statements the home page spells out, as icons here: the footer is on every page, and four sentences
// at the foot of every one of them is a banner rather than a footer. The full wording is one hover away, and is the
// accessible name either way.
const values = computed(() => [
  { key: 'lgbtq', emoji: '🏳️‍🌈🏳️‍⚧️', text: t('values.lgbtq') },
  { key: 'antifascist', emoji: '✊', text: t('values.antifascist') },
  { key: 'climate', emoji: '🌡️', text: t('values.climate') },
  { key: 'openData', emoji: '🔓', text: t('values.openData') },
])

const year = new Date().getFullYear()
</script>

<template>
  <footer class="app-footer border-t border-default bg-default" data-print="hide">
    <div class="frame grid gap-10 py-12 md:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))]">
      <div class="space-y-4">
        <div class="flex items-center gap-2.5">
          <img src="/icon.svg" alt="" width="28" height="28" class="size-7">
          <span class="text-base font-bold text-highlighted">Wetterdienst</span>
        </div>
        <p class="max-w-xs text-sm text-muted">
          {{ t('home.tagline') }}
        </p>
        <!-- The stance, as it closes the home page, on a line of its own so it reads as a statement rather than as
             more entries in a link list -->
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
          <UTooltip v-for="value in values" :key="value.key" :text="value.text">
            <span class="cursor-default text-lg leading-none" role="img" :aria-label="value.text">{{ value.emoji }}</span>
          </UTooltip>
        </div>
        <p class="text-xs text-muted">
          <span class="font-semibold">App</span> {{ appVersion }}
          <span class="mx-1" aria-hidden="true">·</span>
          <span class="font-semibold">Backend</span> {{ backendVersion }}
        </p>
      </div>

      <div>
        <h2 class="footer-heading">
          {{ t('shell.tools') }}
        </h2>
        <ul class="footer-list">
          <li v-for="tool in TOOLS" :key="tool.key">
            <NuxtLink :to="tool.to" class="footer-link">
              {{ t(tool.label) }}
            </NuxtLink>
          </li>
        </ul>
      </div>

      <div>
        <h2 class="footer-heading">
          {{ t('shell.reference') }}
        </h2>
        <ul class="footer-list">
          <li v-for="section in REFERENCE" :key="section.key">
            <NuxtLink :to="section.to" class="footer-link">
              {{ t(section.label) }}
            </NuxtLink>
          </li>
        </ul>
      </div>

      <div>
        <h2 class="footer-heading">
          {{ t('shell.project') }}
        </h2>
        <ul class="footer-list">
          <li>
            <NuxtLink to="/about" class="footer-link">
              {{ t('footer.about') }}
            </NuxtLink>
          </li>
          <li>
            <NuxtLink to="/support" class="footer-link">
              {{ t('nav.support') }}
            </NuxtLink>
          </li>
          <li v-for="link in EXTERNAL" :key="link.key">
            <a :href="link.to" target="_blank" class="footer-link">
              {{ t(link.label) }}<UIcon name="i-ph-arrow-up-right" class="ms-0.5 size-3.5 align-[-0.125em]" />
            </a>
          </li>
        </ul>
      </div>
    </div>

    <div class="border-t border-default">
      <div class="frame flex flex-col gap-2 py-5 text-sm text-muted sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-6">
        <span>{{ t('footer.copyright', { year }) }}</span>
        <ul class="flex flex-wrap gap-x-5 gap-y-1 sm:ms-auto">
          <li>
            <NuxtLink to="/impressum" class="footer-link">
              {{ t('footer.legal') }}
            </NuxtLink>
          </li>
          <li>
            <NuxtLink to="/datenschutz" class="footer-link">
              {{ t('footer.privacy') }}
            </NuxtLink>
          </li>
          <li>
            <!-- a file of the app (modules/third-party-licenses, GH-3469), not a page: a plain link, which the router
                 would otherwise take for a route -->
            <a href="/third-party-licenses.txt" class="footer-link">{{ t('footer.licenses') }}</a>
          </li>
        </ul>
      </div>
    </div>
  </footer>
</template>

<script setup lang="ts">
import pkg from '../../package.json'

/**
 * The footer (GH-3518): the logo's navy, with the project's pages, the legal ones and the versions, and
 * what the project stands for. On the navy the text is ink-200 and white (8.5:1 and more), a hovered link
 * and the focus ring are the logo's yellow (8.2:1). Dark mode takes the brand's darkest blue.
 */
const props = defineProps<{
  backendVersion: string
}>()

const { t } = useI18n()
const appVersion = pkg.version ? `v${pkg.version}` : 'unknown'

// The same four statements the home page spells out, as symbols here: the footer is on every page, and
// four sentences at the foot of every one of them is a banner rather than a footer. The full wording is
// one hover away, and is the accessible name either way.
const values = computed(() => [
  { key: 'lgbtq', emoji: '🏳️‍🌈🏳️‍⚧️', text: t('values.lgbtq') },
  { key: 'antifascist', emoji: '✊', text: t('values.antifascist') },
  { key: 'climate', emoji: '🌡️', text: t('values.climate') },
  { key: 'openData', emoji: '🔓', text: t('values.openData') },
])

const projectLinks = computed(() => [
  { key: 'docs', to: 'https://wetterdienst.readthedocs.io/', icon: 'i-lucide-book-open', label: t('common.documentation') },
  { key: 'github', to: 'https://github.com/earthobservations/wetterdienst', icon: 'i-lucide-github', label: t('header.github') },
  { key: 'pypi', to: 'https://pypi.org/project/wetterdienst', icon: 'i-lucide-package', label: t('header.pypi') },
])

const linkClass = 'rounded-sm underline-offset-4 text-ink-200 hover:text-sun hover:underline'
</script>

<template>
  <footer class="wd-noprint bg-navy text-ink-200 dark:bg-brand-950 [--app-focus-ring:var(--color-sun)]">
    <div class="mx-auto grid w-full max-w-[calc(90rem+2*var(--wd-gutter))] gap-8 px-(--wd-gutter) py-10 md:grid-cols-[1fr_auto]">
      <div class="space-y-3">
        <p class="flex items-center gap-2.5 text-lg font-extrabold tracking-tight text-white">
          <img src="/icon.svg" alt="" class="size-8" width="32" height="32">
          Wetterdienst
        </p>
        <p class="max-w-md text-sm">
          {{ t('home.tagline') }}. {{ t('home.dataIntro') }}
        </p>
        <p class="text-xs tabular-nums">
          <span class="font-semibold text-white">App</span> {{ appVersion }}
          <span class="mx-1" aria-hidden="true">·</span>
          <span class="font-semibold text-white">Backend</span> {{ props.backendVersion }}
        </p>
      </div>

      <div class="space-y-4 md:text-right">
        <!-- the project's pages and the legal ones; support and the documentation are here on every page,
             in the same order (WCAG 3.2.6) -->
        <ul class="flex flex-wrap gap-x-5 gap-y-2 text-sm md:justify-end">
          <li>
            <NuxtLink to="/about" :class="linkClass">
              {{ t('footer.about') }}
            </NuxtLink>
          </li>
          <li>
            <NuxtLink to="/support" :class="linkClass">
              {{ t('nav.support') }}
            </NuxtLink>
          </li>
          <li>
            <NuxtLink to="/impressum" :class="linkClass">
              {{ t('footer.legal') }}
            </NuxtLink>
          </li>
          <li>
            <NuxtLink to="/datenschutz" :class="linkClass">
              {{ t('footer.privacy') }}
            </NuxtLink>
          </li>
          <li>
            <!-- a file of the app (modules/third-party-licenses, GH-3469), not a page: a plain link, which the router
                 would otherwise take for a route -->
            <a href="/third-party-licenses.txt" :class="linkClass">
              {{ t('footer.licenses') }}
            </a>
          </li>
        </ul>
        <div class="flex flex-wrap items-center gap-1 md:justify-end">
          <UTooltip v-for="link in projectLinks" :key="link.key" :text="link.label">
            <a
              :href="link.to"
              target="_blank"
              rel="noopener"
              :aria-label="link.label"
              class="grid size-9 place-items-center rounded-lg text-ink-200 transition-colors hover:bg-white/10 hover:text-sun"
            >
              <UIcon :name="link.icon" class="size-5" />
            </a>
          </UTooltip>
        </div>
        <!-- the stance closes the footer, as it closes the home page, on a line of its own -->
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1 md:justify-end">
          <UTooltip v-for="value in values" :key="value.key" :text="value.text">
            <span class="cursor-default text-lg leading-none" role="img" :aria-label="value.text">{{ value.emoji }}</span>
          </UTooltip>
        </div>
        <p class="text-xs">
          {{ t('footer.copyright', { year: new Date().getFullYear() }) }}
        </p>
      </div>
    </div>
  </footer>
</template>

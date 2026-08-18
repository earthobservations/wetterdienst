<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'
import { de as uiDe, en as uiEn } from '@nuxt/ui/locale'
import pkg from '../package.json'

const { t, locale } = useI18n()

// Keep <html lang> in sync with the active locale.
useHead({
  htmlAttrs: { lang: locale },
})

// Feed Nuxt UI's built-in component strings (table, select, …) the active locale.
const uiLocale = computed(() => (locale.value === 'de' ? uiDe : uiEn))

const route = useRoute()
const isWidget = computed(() => route.path.startsWith('/widget'))

const { data: versionData } = await useFetch<{ version: string }>('/api/version')

const backendVersion = computed(() => versionData.value?.version ?? 'unknown')
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

const items = computed<NavigationMenuItem[]>(() =>
  [
    {
      label: t('nav.home'),
      icon: 'i-lucide-home',
      to: '/',
      active: route.path === '/',
    },
    {
      label: t('nav.meteogram'),
      icon: 'i-lucide-sun',
      to: '/meteogram',
      active: route.path.startsWith('/meteogram'),
    },
    {
      label: t('nav.stripes'),
      icon: 'i-lucide-bar-chart-3',
      to: '/stripes',
      active: route.path.startsWith('/stripes'),
    },
    {
      label: t('nav.explorer'),
      icon: 'i-lucide-globe',
      to: '/explorer',
      active: route.path.startsWith('/explorer'),
    },
    {
      label: t('nav.history'),
      icon: 'i-lucide-clock',
      to: '/history',
      active: route.path.startsWith('/history'),
    },
    {
      label: t('nav.api'),
      icon: 'i-lucide-code',
      to: '/api',
      active: route.path.startsWith('/api'),
    },
    {
      label: t('nav.glossary'),
      icon: 'i-lucide-book-open',
      to: '/glossary',
      active: route.path.startsWith('/glossary'),
    },
  ],
)
</script>

<template>
  <UApp :locale="uiLocale">
    <UHeader v-if="!isWidget" :toggle="false">
      <template #left>
        <div class="flex items-center gap-3">
          <img src="/favicon.ico" alt="Wetterdienst" class="w-7 h-7">
        </div>
      </template>

      <UNavigationMenu :items="items" />

      <template #right>
        <!-- Desktop controls -->
        <div class="hidden lg:flex items-center gap-1">
          <UTooltip :text="t('common.documentation')">
            <UButton
              to="https://wetterdienst.readthedocs.io/"
              target="_blank"
              icon="i-lucide-book-open"
              color="neutral"
              variant="ghost"
              :aria-label="t('common.documentation')"
            />
          </UTooltip>
          <UTooltip :text="t('header.github')">
            <UButton
              to="https://github.com/earthobservations/wetterdienst"
              target="_blank"
              icon="i-lucide-github"
              color="neutral"
              variant="ghost"
              :aria-label="t('header.github')"
            />
          </UTooltip>
          <UTooltip :text="t('header.pypi')">
            <UButton
              to="https://pypi.org/project/wetterdienst"
              target="_blank"
              icon="i-lucide-package"
              color="neutral"
              variant="ghost"
              :aria-label="t('header.pypi')"
            />
          </UTooltip>
          <!-- Support is about the project rather than the data, so it sits with the other
               project links rather than in the task nav -- but as an icon, not a footer line,
               because issues, pull requests and donations all start here. -->
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
        <!-- Mobile hamburger -->
        <UButton
          class="lg:hidden"
          :icon="mobileMenuOpen ? 'i-lucide-x' : 'i-lucide-menu'"
          color="neutral"
          variant="ghost"
          :aria-label="t('header.menu')"
          @click="mobileMenuOpen = !mobileMenuOpen"
        />
      </template>
    </UHeader>

    <!-- Full-screen mobile overlay -->
    <Teleport v-if="!isWidget" to="body">
      <Transition name="mobile-menu">
        <div
          v-if="mobileMenuOpen"
          class="fixed inset-0 z-50 lg:hidden flex flex-col bg-white dark:bg-gray-900"
        >
          <!-- Top bar -->
          <div class="flex items-center justify-between h-16 px-4 border-b border-gray-200 dark:border-gray-800 shrink-0">
            <div class="flex items-center gap-3">
              <img src="/favicon.ico" alt="Wetterdienst" class="w-7 h-7">
              <span class="font-semibold text-gray-900 dark:text-white">Wetterdienst</span>
            </div>
            <UButton
              icon="i-lucide-x"
              color="neutral"
              variant="ghost"
              :aria-label="t('common.close')"
              @click="mobileMenuOpen = false"
            />
          </div>

          <!-- Nav items -->
          <nav class="flex-1 overflow-y-auto px-3 py-4 flex flex-col gap-1">
            <NuxtLink
              v-for="item in items"
              :key="item.to as string"
              :to="item.to as string"
              class="flex items-center gap-4 px-4 py-3.5 rounded-xl text-base font-medium transition-colors"
              :class="item.active
                ? 'bg-primary-50 dark:bg-primary-950 text-primary-600 dark:text-primary-400'
                : 'text-gray-800 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'"
              @click="mobileMenuOpen = false"
            >
              <UIcon :name="item.icon as string" class="w-5 h-5 shrink-0" />
              {{ item.label }}
            </NuxtLink>
          </nav>

          <!-- Bottom bar: external links + settings -->
          <div class="shrink-0 border-t border-gray-200 dark:border-gray-800 px-4 py-4 flex items-center justify-between">
            <div class="flex items-center gap-1">
              <UTooltip :text="t('common.documentation')">
                <UButton
                  to="https://wetterdienst.readthedocs.io/"
                  target="_blank"
                  icon="i-lucide-book-open"
                  color="neutral"
                  variant="ghost"
                  :aria-label="t('common.documentation')"
                />
              </UTooltip>
              <UTooltip :text="t('header.github')">
                <UButton
                  to="https://github.com/earthobservations/wetterdienst"
                  target="_blank"
                  icon="i-lucide-github"
                  color="neutral"
                  variant="ghost"
                  :aria-label="t('header.github')"
                />
              </UTooltip>
              <UTooltip :text="t('header.pypi')">
                <UButton
                  to="https://pypi.org/project/wetterdienst"
                  target="_blank"
                  icon="i-lucide-package"
                  color="neutral"
                  variant="ghost"
                  :aria-label="t('header.pypi')"
                />
              </UTooltip>
              <!-- matches the desktop header: Support left the nav list, so it has to be here or
                   the hamburger menu loses it entirely -->
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
        </div>
      </Transition>
    </Teleport>

    <UMain>
      <NuxtPage />
    </UMain>
    <UFooter v-if="!isWidget">
      <div class="w-full flex flex-col items-center gap-2 text-center">
        <div class="text-xs text-gray-400 dark:text-gray-600">
          <span class="text-green-600 dark:text-green-400 font-medium">App</span> {{ appVersion === 'unknown' ? appVersion : `v${appVersion}` }}
          <span class="mx-1">|</span>
          <span class="text-blue-600 dark:text-blue-400 font-medium">Backend</span> {{ backendVersion === 'unknown' ? backendVersion : `v${backendVersion}` }}
        </div>
        <!-- Two rows by kind rather than one list of six. In one row the values statements sat in
             the same register as the links, separated by the same pipe, and the separators -- flex
             siblings that cannot see where a line breaks -- left a dangling "|" at the end of a
             wrapped line on narrow screens. Each row owns its separators now. -->
        <div class="flex flex-wrap justify-center items-center gap-x-4 sm:gap-x-3 gap-y-1">
          <span>{{ t('footer.copyright', { year: new Date().getFullYear() }) }}</span>
          <span class="hidden sm:inline text-gray-300 dark:text-gray-700" aria-hidden="true">·</span>
          <NuxtLink to="/about" class="text-gray-500 hover:text-primary-500 transition-colors">
            {{ t('footer.about') }}
          </NuxtLink>
          <span class="hidden sm:inline text-gray-300 dark:text-gray-700" aria-hidden="true">·</span>
          <NuxtLink to="/support" class="text-gray-500 hover:text-primary-500 transition-colors">
            {{ t('nav.support') }}
          </NuxtLink>
          <span class="hidden sm:inline text-gray-300 dark:text-gray-700" aria-hidden="true">·</span>
          <NuxtLink to="/impressum" class="text-gray-500 hover:text-primary-500 transition-colors">
            {{ t('footer.legal') }}
          </NuxtLink>
        </div>
        <!-- The stance closes the footer, as it closes the home page, and on a line of its own so
             it reads as a statement rather than as more entries in a link list. -->
        <div class="flex flex-wrap justify-center items-center gap-x-4 gap-y-1">
          <UTooltip v-for="value in values" :key="value.key" :text="value.text">
            <span
              class="text-lg leading-none cursor-default"
              role="img"
              :aria-label="value.text"
            >{{ value.emoji }}</span>
          </UTooltip>
        </div>
      </div>
    </UFooter>
  </UApp>
</template>

<style>
/* Make main container full width for better map display */
:deep(.u-main) {
  max-width: 100% !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
}

.mobile-menu-enter-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.mobile-menu-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.mobile-menu-enter-from,
.mobile-menu-leave-to { opacity: 0; transform: translateY(-12px); }
</style>

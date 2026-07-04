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

const version = computed(() => versionData.value?.version ?? 'unknown')
const frontendVersion = pkg.version || 'unknown'

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
      label: t('nav.support'),
      icon: 'i-lucide-heart',
      to: '/support',
      active: route.path.startsWith('/support'),
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
          <div class="ml-2 inline-flex items-center gap-2">
            <span
              class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
            >
              FE {{ frontendVersion === 'unknown' ? frontendVersion : `v${frontendVersion}` }}
            </span>
            <span
              class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
            >
              BE {{ version === 'unknown' ? version : `v${version}` }}
            </span>
          </div>
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
      <div class="w-full flex flex-wrap items-center gap-x-4 gap-y-2">
        <span>{{ t('footer.copyright', { year: new Date().getFullYear() }) }}</span>
        <span class="text-gray-400">|</span>
        <span class="flex items-center gap-1.5 font-medium">
          <span aria-hidden="true">🏳️‍🌈</span>
          <span>{{ t('footer.lgbtq') }}</span>
        </span>
        <span class="text-gray-400">|</span>
        <span class="flex items-center gap-1.5 font-medium">
          <span aria-hidden="true">✊</span>
          <span>{{ t('footer.antifascist') }}</span>
        </span>
        <span class="text-gray-400">|</span>
        <NuxtLink to="/impressum" class="text-gray-500 hover:text-primary-500 transition-colors">
          {{ t('footer.legal') }}
        </NuxtLink>
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

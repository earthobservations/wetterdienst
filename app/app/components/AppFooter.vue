<script setup lang="ts">
// The footer of every page but the widget (GH-3518): the legal links and the project's stance, in a single quiet row on
// the column of the pages. The versions of the app and of the backend are under the settings of the navigation.
const { t } = useI18n()

// The same four statements the home page spells out, as icons here: the footer is on every page,
// and four sentences at the foot of every one of them is a banner rather than a footer. The full
// wording is one hover away, and is the accessible name either way.
const values = computed(() => [
  { key: 'lgbtq', icon: 'i-ph-rainbow', text: t('values.lgbtq') },
  { key: 'antifascist', icon: 'i-ph-hand-fist', text: t('values.antifascist') },
  { key: 'climate', icon: 'i-ph-thermometer-hot', text: t('values.climate') },
  { key: 'openData', icon: 'i-ph-lock-open', text: t('values.openData') },
])

const LINK = 'text-muted hover:text-highlighted transition-colors motion-reduce:transition-none'
</script>

<template>
  <footer class="mt-16 border-t border-default print:hidden">
    <UContainer class="flex max-w-(--app-width) flex-col gap-6 py-8">
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

      <div class="flex flex-col gap-4 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
        <div class="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span>{{ t('footer.copyright', { year: new Date().getFullYear() }) }}</span>
        </div>
        <!-- The stance closes the footer, as it closes the home page. -->
        <div class="flex items-center gap-4">
          <UTooltip v-for="value in values" :key="value.key" :text="value.text">
            <span class="inline-flex cursor-default" role="img" :aria-label="value.text">
              <UIcon :name="value.icon" class="size-5" />
            </span>
          </UTooltip>
        </div>
      </div>
    </UContainer>
  </footer>
</template>

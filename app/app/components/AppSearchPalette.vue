<script setup lang="ts">
import type { CommandPaletteGroup, CommandPaletteItem } from '@nuxt/ui'
import { EXTERNAL, PROJECT, REFERENCE, TOOLS } from '~/utils/sections'

// The list of the search (AppSearch.vue). A component of its own so that it exists only while the search is open:
// the providers are asked for when someone searches, not on every page.
const emit = defineEmits<{ done: [] }>()

const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()
const { data: providerList } = useProviders()

function page(section: { key: string, to: string, label: string, icon: string, description?: string }): CommandPaletteItem {
  return {
    id: section.key,
    label: t(section.label),
    description: section.description ? t(section.description) : undefined,
    icon: section.icon,
    to: section.to,
    onSelect: () => emit('done'),
  }
}

const groups = computed<CommandPaletteGroup<CommandPaletteItem>[]>(() => [
  { id: 'tools', label: t('shell.tools'), items: TOOLS.map(page) },
  { id: 'reference', label: t('shell.reference'), items: REFERENCE.map(page) },
  {
    id: 'project',
    label: t('shell.project'),
    items: [
      page({ key: 'home', to: '/', label: 'nav.home', icon: 'i-ph-house' }),
      ...PROJECT.map(page),
      ...EXTERNAL.map(link => ({
        id: link.key,
        label: t(link.label),
        icon: link.icon,
        to: link.to,
        target: '_blank',
        suffix: '↗',
        onSelect: () => emit('done'),
      })),
    ],
  },
  {
    id: 'providers',
    label: t('nav.providers'),
    items: (providerList.value?.providers ?? []).map(provider => ({
      id: `provider-${provider.provider}`,
      label: provider.name_short,
      suffix: provider.name_english,
      icon: 'i-ph-buildings',
      to: `/providers/${provider.provider}`,
      onSelect: () => emit('done'),
    })),
  },
  {
    id: 'theme',
    label: t('settings.theme'),
    items: [
      { value: 'system', label: t('settings.themeSystem'), icon: 'i-ph-monitor' },
      { value: 'light', label: t('settings.themeLight'), icon: 'i-ph-sun' },
      { value: 'dark', label: t('settings.themeDark'), icon: 'i-ph-moon' },
    ].map(option => ({
      id: `theme-${option.value}`,
      label: option.label,
      icon: option.icon,
      active: colorMode.preference === option.value,
      onSelect: () => {
        colorMode.preference = option.value
        emit('done')
      },
    })),
  },
  {
    id: 'language',
    label: t('settings.language'),
    items: LANGUAGES.map(language => ({
      id: `language-${language.value}`,
      label: language.name,
      active: locale.value === language.value,
      icon: 'i-ph-translate',
      onSelect: () => {
        setLocale(language.value as typeof locale.value)
        emit('done')
      },
    })),
  },
])
</script>

<template>
  <UCommandPalette
    :groups="groups"
    :placeholder="t('shell.searchPlaceholder')"
    :fuse="{ resultLimit: 30 }"
    class="flex-1 min-h-0"
    :ui="{ input: '[&_input]:text-base', label: 'text-xs uppercase tracking-wider text-muted font-semibold', item: 'py-2' }"
  >
    <template #empty>
      <p class="py-8 text-center text-muted">
        {{ t('shell.searchEmpty') }}
      </p>
    </template>
  </UCommandPalette>
</template>

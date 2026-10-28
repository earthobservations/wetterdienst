<script setup lang="ts">
import type { CommandPaletteGroup, CommandPaletteItem } from '@nuxt/ui'
import { EXTERNAL, PROJECT, REFERENCE, TOOLS } from '~/utils/sections'

// The list of the search (AppSearch.vue). A component of its own so that it exists only while the search is open:
// the providers are asked for when someone searches, not on every page.
const emit = defineEmits<{ done: [] }>()

const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()
const { data: providerList } = useProviders()

// Two things Nuxt UI's command palette leaves out, put on its list once it is there. The list is named by what it is
// (WCAG 4.1.2, axe `aria-input-field-name`). And it is the box that scrolls, and takes the focus by Tab, so a keyboard
// can scroll it (2.1.1, axe `scrollable-region-focusable`): its options are reached by the arrow keys from the field,
// not by Tab, so nothing in the box could take it. A listbox is a widget that is focused by design; Nuxt UI's own
// scrolling box inside it is a presentational one, which must not be.
const wrap = useTemplateRef<HTMLElement>('wrap')
function labelTheList() {
  const list = wrap.value?.querySelector('[role="listbox"]')
  if (!list)
    return
  if (list.getAttribute('aria-label') !== t('shell.search'))
    list.setAttribute('aria-label', t('shell.search'))
  // Reka renders it with -1; set again when it does, and only then, so this does not call itself
  if (list.getAttribute('tabindex') !== '0')
    list.setAttribute('tabindex', '0')
}
// again whenever the list is drawn anew
let observer: MutationObserver | null = null
onMounted(() => {
  labelTheList()
  if (wrap.value) {
    observer = new MutationObserver(labelTheList)
    observer.observe(wrap.value, { childList: true, subtree: true, attributes: true, attributeFilter: ['tabindex', 'aria-label'] })
  }
})
onBeforeUnmount(() => observer?.disconnect())

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
  <div ref="wrap" class="flex min-h-0 flex-1 flex-col">
    <UCommandPalette
      :groups="groups"
      :placeholder="t('shell.searchPlaceholder')"
      :fuse="{ resultLimit: 30 }"
      class="flex-1 min-h-0"
      :ui="{ input: '[&_input]:text-base', content: 'flex-1 min-h-0 overflow-y-auto', viewport: 'overflow-visible flex-none', label: 'text-xs uppercase tracking-wider text-muted font-semibold', item: 'py-2' }"
    >
      <template #empty>
        <p class="py-8 text-center text-muted">
          {{ t('shell.searchEmpty') }}
        </p>
      </template>
    </UCommandPalette>
  </div>
</template>

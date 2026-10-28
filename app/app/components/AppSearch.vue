<script setup lang="ts">
import type { CommandPaletteGroup, CommandPaletteItem } from '@nuxt/ui'

// The command palette (Ctrl or Cmd + K): the pages, the appearance and the language, one search for all of them.
// The sidebar's search button opens it.
const { t, locale, setLocale } = useI18n()
const router = useRouter()
const colorMode = useColorMode()
const { groups: navGroups } = useAppNav()

const open = useState('app-search-open', () => false)

const groups = computed<CommandPaletteGroup[]>(() => {
  const settingsItem: CommandPaletteItem = { label: t('common.settings'), icon: 'i-ph-gear-six', to: '/settings' }
  const pages: CommandPaletteGroup[] = navGroups.value.map((group, index) => ({
    id: group.key,
    label: group.label ?? t('nav.home'),
    items: [
      ...group.items.map((item): CommandPaletteItem => ({
        label: String(item.label),
        icon: item.icon,
        to: item.to as string,
        target: item.target,
        active: Boolean(item.active),
      })),
      ...(index === navGroups.value.length - 1 ? [settingsItem] : []),
    ],
  }))
  return [
    ...pages,
    {
      id: 'theme',
      label: t('settings.theme'),
      items: [
        { value: 'system', label: t('settings.themeSystem'), icon: 'i-ph-desktop' },
        { value: 'light', label: t('settings.themeLight'), icon: 'i-ph-sun' },
        { value: 'dark', label: t('settings.themeDark'), icon: 'i-ph-moon' },
      ].map(option => ({
        label: option.label,
        icon: option.icon,
        active: colorMode.preference === option.value,
        onSelect: () => {
          colorMode.preference = option.value
        },
      })),
    },
    {
      id: 'language',
      label: t('settings.language'),
      items: LANGUAGES.map(language => ({
        label: language.name,
        icon: 'i-ph-translate',
        active: locale.value === language.value,
        onSelect: () => {
          void setLocale(language.value as typeof locale.value)
        },
      })),
    },
  ]
})

// the label of the close button in the language of the app, which Nuxt UI's own is only for the two it ships
const close = computed(() => ({ 'aria-label': t('common.close') }) as never)

// Nuxt UI 4.11's palette puts role="listbox" on a wrapper around the scrolling list (axe: aria-required-children, and
// a listbox without a name, and a scrolling list that cannot be focused). Its props reach none of it, so once the
// palette is open the role, a name and a place in the tab order go on the scrolling list itself, which is what Nuxt UI
// 4.12 does (nuxt/ui#7096); the workaround goes with the upgrade.
watch(open, async (isOpen) => {
  if (!isOpen)
    return
  await nextTick()
  await new Promise(resolve => requestAnimationFrame(resolve))
  const wrapper = document.querySelector('[role="dialog"] [role="listbox"]')
  const list = wrapper?.querySelector('[data-slot="viewport"]')
  if (!wrapper || !list)
    return
  wrapper.setAttribute('role', 'presentation')
  wrapper.removeAttribute('aria-orientation')
  wrapper.removeAttribute('aria-multiselectable')
  list.setAttribute('role', 'listbox')
  list.setAttribute('aria-label', t('nav.search'))
  list.setAttribute('tabindex', '0')
})

watch(() => router.currentRoute.value.path, () => {
  open.value = false
})
</script>

<template>
  <UDashboardSearch
    v-model:open="open"
    :groups="groups"
    :color-mode="false"
    :title="t('nav.search')"
    :description="t('nav.searchPlaceholder')"
    :placeholder="t('nav.searchPlaceholder')"
    :close="close"
  >
    <template #empty>
      {{ t('nav.noResults') }}
    </template>
  </UDashboardSearch>
</template>

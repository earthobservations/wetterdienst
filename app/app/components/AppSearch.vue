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
        current: Boolean(item.active),
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
        current: colorMode.preference === option.value,
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
        current: locale.value === language.value,
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
// a listbox without a name, and a scrolling list that cannot be focused). Its props reach none of it, so the role, a name
// and a place in the tab order go on the scrolling list itself, which is what Nuxt UI 4.12 does (nuxt/ui#7096; the
// workaround goes with the upgrade). The list is drawn anew when the results change (and gives way to the empty message),
// so this is done again after every change of the palette's content, not only when it opens. In the empty state the field
// still names an option that is gone (`aria-activedescendant`); that is dropped. The palette is the one root that has a
// search field of its own, not "the first dialog": the drawer or the rail's popover can be open behind it.
let observer: MutationObserver | null = null
let frame = 0
let epoch = 0

function paletteRoot(): Element | null {
  for (const root of document.querySelectorAll('[data-slot="root"]')) {
    if (root.querySelector(':scope > [data-slot="input"] input'))
      return root
  }
  return null
}

function patchList() {
  frame = 0
  const root = paletteRoot()
  const wrapper = root?.querySelector(':scope > [data-slot="content"]')
  const list = wrapper?.querySelector('[data-slot="viewport"]')
  if (wrapper && wrapper.getAttribute('role') !== 'presentation') {
    wrapper.setAttribute('role', 'presentation')
    wrapper.removeAttribute('aria-orientation')
    wrapper.removeAttribute('aria-multiselectable')
  }
  if (list && list.getAttribute('role') !== 'listbox') {
    list.setAttribute('role', 'listbox')
    list.setAttribute('aria-label', t('nav.search'))
    list.setAttribute('tabindex', '0')
  }
  const field = root?.querySelector('input')
  const target = field?.getAttribute('aria-activedescendant')
  if (field && target && !document.getElementById(target))
    field.removeAttribute('aria-activedescendant')
}

function stopWatching() {
  observer?.disconnect()
  observer = null
  if (frame)
    cancelAnimationFrame(frame)
  frame = 0
}

// Each opening and closing is an epoch: what was waited for in an earlier one (the palette's drawing, a frame) is not
// acted on in a later, so a quick close and open attaches one observer, to the palette that is open.
watch(open, async (isOpen) => {
  const mine = ++epoch
  stopWatching()
  if (!isOpen)
    return
  await nextTick()
  for (let wait = 0; wait < 10 && !paletteRoot(); wait++) {
    await new Promise(resolve => requestAnimationFrame(resolve))
    if (mine !== epoch)
      return
  }
  await new Promise(resolve => requestAnimationFrame(resolve))
  const root = paletteRoot()
  if (mine !== epoch || !open.value || !root)
    return
  patchList()
  observer = new MutationObserver(() => {
    if (!frame)
      frame = requestAnimationFrame(patchList)
  })
  observer.observe(root, { childList: true, subtree: true })
})

onBeforeUnmount(stopWatching)

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
    <!-- the current page, appearance or language: a check and, for a screen reader, its word, not a background -->
    <template #item-trailing="{ item }">
      <template v-if="(item as { current?: boolean }).current">
        <UIcon name="i-ph-check" class="size-4 shrink-0" aria-hidden="true" />
        <span class="sr-only">{{ t('nav.current') }}</span>
      </template>
    </template>
  </UDashboardSearch>
</template>

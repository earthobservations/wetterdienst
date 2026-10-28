<script setup lang="ts">
// The settings within reach from every page (the foot of the sidebar and of the drawer): language and appearance, and the
// way to the page of all of them.
const props = withDefaults(defineProps<{ collapsed?: boolean }>(), { collapsed: false })
const emit = defineEmits<{ navigate: [] }>()

const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()

const languageItems = languageSelectItems()
const selectedLanguage = computed({
  get: () => locale.value,
  set: (v: string) => setLocale(v as typeof locale.value),
})

const themeOptions = computed(() => [
  { value: 'system', label: t('settings.themeSystem'), icon: 'i-ph-desktop' },
  { value: 'light', label: t('settings.themeLight'), icon: 'i-ph-sun' },
  { value: 'dark', label: t('settings.themeDark'), icon: 'i-ph-moon' },
])
</script>

<template>
  <UPopover :content="{ side: 'top', align: 'start' }">
    <UButton
      icon="i-ph-gear-six"
      color="neutral"
      variant="ghost"
      :label="props.collapsed ? undefined : t('common.settings')"
      :square="props.collapsed"
      :block="!props.collapsed"
      :class="props.collapsed ? '' : 'justify-start'"
      :aria-label="props.collapsed ? t('common.settings') : undefined"
    />

    <template #content>
      <div class="p-4 w-64 space-y-4">
        <!-- Language -->
        <div>
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">
            {{ t('settings.language') }}
          </div>
          <USelect
            v-model="selectedLanguage"
            :items="languageItems"
            :aria-label="t('settings.language')"
            size="sm"
            class="w-full"
          />
        </div>

        <!-- Theme -->
        <div>
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">
            {{ t('settings.theme') }}
          </div>
          <UFieldGroup class="w-full">
            <UButton
              v-for="opt in themeOptions"
              :key="opt.value"
              :icon="opt.icon"
              size="sm"
              color="neutral"
              class="flex-1 justify-center"
              :aria-label="opt.label"
              :variant="colorMode.preference === opt.value ? 'solid' : 'ghost'"
              @click="colorMode.preference = opt.value"
            />
          </UFieldGroup>
        </div>

        <USeparator />

        <UButton
          to="/settings"
          :label="t('settings.title')"
          icon="i-ph-sliders-horizontal"
          color="neutral"
          variant="ghost"
          size="sm"
          block
          trailing-icon="i-ph-caret-right"
          @click="emit('navigate')"
        />
      </div>
    </template>
  </UPopover>
</template>

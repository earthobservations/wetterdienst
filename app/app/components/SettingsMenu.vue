<script setup lang="ts">
// `onNavy`: the button stands on the navy of the rail (app.vue), where the page's own text colours are not
const props = defineProps<{ onNavy?: boolean }>()
const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()

const languageItems = languageSelectItems()
const selectedLanguage = computed({
  get: () => locale.value,
  set: (v: string) => setLocale(v as typeof locale.value),
})

const themeOptions = computed(() => [
  { value: 'system', label: t('settings.themeSystem'), icon: 'i-lucide-monitor' },
  { value: 'light', label: t('settings.themeLight'), icon: 'i-lucide-sun' },
  { value: 'dark', label: t('settings.themeDark'), icon: 'i-lucide-moon' },
])
</script>

<template>
  <UPopover>
    <UButton
      icon="i-lucide-settings-2"
      color="neutral"
      variant="ghost"
      size="lg"
      :class="props.onNavy ? 'text-gray-200 hover:text-white hover:bg-white/10 aria-expanded:bg-white/10 aria-expanded:text-white' : undefined"
      :aria-label="t('common.settings')"
    />

    <template #content>
      <div class="p-4 w-64 space-y-4">
        <!-- Language -->
        <div>
          <div class="text-xs font-medium text-muted mb-1.5">
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
          <div class="text-xs font-medium text-muted mb-1.5">
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
          icon="i-lucide-sliders-horizontal"
          color="neutral"
          variant="ghost"
          size="sm"
          block
          trailing-icon="i-lucide-chevron-right"
        />
      </div>
    </template>
  </UPopover>
</template>

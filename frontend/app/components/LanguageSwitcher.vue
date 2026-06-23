<script setup lang="ts">
const { t, locale, setLocale } = useI18n()

const options = [
  { value: 'de', label: 'DE' },
  { value: 'en', label: 'EN' },
] as const
</script>

<template>
  <div class="flex items-center gap-1.5">
    <!-- Subtle, inclusive welcome accent -->
    <span class="text-sm leading-none select-none" :title="t('language.inclusiveHint')" aria-hidden="true">🏳️‍🌈</span>
    <UFieldGroup :aria-label="t('language.switch')">
      <UButton
        v-for="opt in options"
        :key="opt.value"
        :label="opt.label"
        size="xs"
        color="neutral"
        :variant="locale === opt.value ? 'solid' : 'ghost'"
        @click="setLocale(opt.value)"
      />
    </UFieldGroup>
  </div>
</template>

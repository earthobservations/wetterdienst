<script setup lang="ts">
/**
 * The menu (GH-3518): every page, in three parts, each with a line of what it is for, and the project's
 * links. A dialog at every width, from the side: the focus stays in it, Escape closes it, and the page
 * behind is hidden from a screen reader while it is open (WCAG 2.1.2, 2.4.3, 4.1.2). A link's name is its
 * label; the line under it is its description, so a list of links reads as a list of pages.
 */
const open = defineModel<boolean>('open', { required: true })

const { t } = useI18n()
const { groups, isActive } = useAppNav()
const reducedMotion = usePreferredReducedMotion()

const projectLinks = computed(() => [
  { key: 'docs', to: 'https://wetterdienst.readthedocs.io/', icon: 'i-lucide-book-open', label: t('common.documentation') },
  { key: 'github', to: 'https://github.com/earthobservations/wetterdienst', icon: 'i-lucide-github', label: t('header.github') },
  { key: 'pypi', to: 'https://pypi.org/project/wetterdienst', icon: 'i-lucide-package', label: t('header.pypi') },
])
</script>

<template>
  <USlideover
    v-model:open="open"
    side="right"
    :title="t('header.menu')"
    :transition="reducedMotion !== 'reduce'"
    close
    :ui="{ content: 'w-full max-w-sm', body: 'p-0 sm:p-0', header: 'min-h-16' }"
  >
    <!-- the label in the language of the app, which Nuxt UI's own is only for the two it ships -->
    <template #close="{ ui }">
      <UButton
        icon="i-lucide-x"
        color="neutral"
        variant="ghost"
        :aria-label="t('common.close')"
        :class="ui.close()"
      />
    </template>
    <template #body>
      <nav :aria-label="t('header.menu')" class="px-3 py-4">
        <div v-for="group in groups" :key="group.key" class="mb-4 last:mb-0">
          <h2 class="px-3 pb-1.5 text-xs font-bold uppercase tracking-wider text-muted">
            {{ group.title }}
          </h2>
          <ul class="flex flex-col gap-0.5">
            <li v-for="item in group.items" :key="item.key">
              <NuxtLink
                :to="item.to"
                :aria-current="isActive(item.to) ? 'page' : undefined"
                :aria-labelledby="`menu-label-${item.key}`"
                :aria-describedby="`menu-desc-${item.key}`"
                class="group flex items-start gap-3 rounded-xl px-3 py-2.5 transition-colors"
                :class="isActive(item.to)
                  ? 'bg-brand-50 dark:bg-brand-950'
                  : 'hover:bg-ink-100 dark:hover:bg-ink-800'"
                @click="open = false"
              >
                <span
                  class="mt-0.5 grid size-9 shrink-0 place-items-center rounded-lg"
                  :class="isActive(item.to) ? 'bg-brand-600 text-white dark:bg-brand-400 dark:text-ink-900' : 'bg-ink-100 text-ink-700 dark:bg-ink-800 dark:text-ink-200'"
                  aria-hidden="true"
                >
                  <UIcon :name="item.icon" class="size-5" />
                </span>
                <span class="min-w-0">
                  <span :id="`menu-label-${item.key}`" class="block font-semibold text-highlighted">{{ item.label }}</span>
                  <span :id="`menu-desc-${item.key}`" class="block text-sm text-toned">{{ item.description }}</span>
                </span>
              </NuxtLink>
            </li>
          </ul>
        </div>
      </nav>
    </template>
    <template #footer>
      <div class="flex w-full flex-wrap items-center gap-1">
        <UTooltip v-for="link in projectLinks" :key="link.key" :text="link.label">
          <UButton
            :to="link.to"
            target="_blank"
            :icon="link.icon"
            color="neutral"
            variant="ghost"
            :aria-label="link.label"
          />
        </UTooltip>
      </div>
    </template>
  </USlideover>
</template>

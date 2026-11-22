<script setup lang="ts">
import type { Warning, WarningsTranslate } from '~/utils/warnings'
import { levelKey, phaseOf, styleOf, wordsOf } from '~/utils/warnings'

// One warning of DWD (GH-4295), as a row that opens: what a reader needs to know it at a glance (the level as a number and in words, the
// event, when it is in force) and, opened, DWD's own words for it, unchanged: type, headline, description and instruction, where it was issued
// and for which areas. The level is told by its number and its name and its mark's shape, never by colour alone (WCAG 1.4.1). The row is a
// button that says whether it is open (`aria-expanded`); the text of a warning is DWD's and in the language of the page where DWD
// writes it, else in German, which the entry says (`warnings.textGerman`). A press on the row also tells the page, which draws the
// warning's outline stronger on the map.

const props = defineProps<{
  warning: Warning
  /** The clock the phase of the warning is read against (the server's, not the device's) */
  now: number
  /** Whether the details are open */
  open: boolean
  /** The id the details have, which the button names */
  detailsId: string
  /** Whether the row is the one the map is showing stronger */
  focused?: boolean
}>()

const emit = defineEmits<{ toggle: [] }>()

const { t, locale } = useI18n()
const formatLanguage = useFormatLanguage()

const style = computed(() => styleOf(props.warning))
const phase = computed(() => phaseOf(props.warning, props.now))
const words = computed(() => wordsOf(props.warning, t as WarningsTranslate, locale.value, formatLanguage.value, props.now))
const mark = computed(() => props.warning.kind === 'preliminary' ? '!' : props.warning.level ? String(props.warning.level) : '?')
</script>

<template>
  <div class="warning-entry" :data-level="levelKey(warning)" :data-phase="phase" :data-focused="focused || undefined" data-testid="warning-entry">
    <button
      type="button"
      class="warning-entry-button"
      :aria-expanded="open"
      :aria-controls="detailsId"
      data-testid="warning-toggle"
      @click="emit('toggle')"
    >
      <span class="warning-mark" :style="{ background: style.edge }" aria-hidden="true">{{ mark }}</span>
      <span class="min-w-0 flex-1">
        <span class="block font-semibold text-highlighted break-words" :lang="words.language" data-testid="warning-title">{{ words.title }}</span>
        <span class="block text-sm text-toned" data-testid="warning-level">{{ words.level }}</span>
        <span class="block text-sm text-muted" data-testid="warning-when">
          {{ words.phase }}<template v-if="words.validity">
            · {{ words.validity }}
          </template>
        </span>
        <span v-if="words.issued" class="block text-xs text-muted" data-testid="warning-issued-row">{{ t('warnings.issued', { time: words.issued }) }}</span>
      </span>
      <UIcon :name="open ? 'i-ph-caret-up' : 'i-ph-caret-down'" class="size-4 shrink-0 text-muted" aria-hidden="true" />
    </button>
    <div v-show="open" :id="detailsId" class="warning-details" role="group" :aria-label="words.title" data-testid="warning-details">
      <p v-if="!words.inLocale" class="warning-note" data-testid="warning-language-note">
        <UIcon name="i-ph-translate" class="size-4 shrink-0" aria-hidden="true" />
        {{ t('warnings.textGerman') }}
      </p>
      <dl class="warning-facts">
        <template v-if="words.text.event">
          <dt>{{ t('warnings.type') }}</dt>
          <dd :lang="words.language">
            {{ words.text.event }}
          </dd>
        </template>
        <dt>{{ t('warnings.levelLabel') }}</dt>
        <dd>{{ words.level }}</dd>
        <template v-if="words.validity">
          <dt>{{ t('warnings.valid') }}</dt>
          <dd>{{ words.validity }}</dd>
        </template>
        <template v-if="words.issued">
          <dt>{{ t('warnings.issuedLabel') }}</dt>
          <dd data-testid="warning-issued">
            {{ words.issued }}
          </dd>
        </template>
        <template v-if="words.areas">
          <dt>{{ t('warnings.areasLabel') }}</dt>
          <!-- the names of the areas are DWD's German ones whatever the language of the text -->
          <dd>
            <span lang="de">{{ words.areas }}</span><template v-if="words.areasMore">
              {{ ' ' }}{{ words.areasMore }}
            </template>
          </dd>
        </template>
      </dl>
      <div v-if="words.text.headline || words.text.description || words.text.instruction" class="warning-words" :lang="words.language">
        <p v-if="words.text.headline" class="font-semibold text-highlighted">
          {{ words.text.headline }}
        </p>
        <p v-if="words.text.description" class="warning-text" data-testid="warning-description">
          {{ words.text.description }}
        </p>
        <p v-if="words.text.instruction" class="warning-text" data-testid="warning-instruction">
          {{ words.text.instruction }}
        </p>
      </div>
    </div>
  </div>
</template>

<style>
.warning-entry {
  border: 1px solid var(--ui-border);
  border-radius: calc(var(--ui-radius) * 2);
  background: var(--ui-bg);
}
/* the one the map draws stronger: a second edge that is not colour (the heavier outline on the map is the same cue) */
.warning-entry[data-focused] {
  border-color: var(--ui-primary);
  box-shadow: 0 0 0 1px var(--ui-primary);
}
.warning-entry-button {
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
  width: 100%;
  min-height: 2.75rem;
  padding: 0.5rem 0.625rem;
  border-radius: calc(var(--ui-radius) * 2);
  text-align: start;
  cursor: pointer;
}
.warning-entry-button:hover {
  background: var(--ui-bg-elevated);
}
/* the mark: the number of the level on the dark tone of its colour, white on 4.5:1 or more; it is no cue alone, the number and the words are beside it */
.warning-mark {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  margin-top: 0.125rem;
  border-radius: 50%;
  color: #ffffff;
  font-size: 0.875rem;
  font-weight: 700;
  line-height: 1;
}
[data-level="preliminary"] .warning-mark {
  border-radius: 0.25rem;
}
@media (forced-colors: active) {
  .warning-mark {
    forced-color-adjust: none;
  }
}
.warning-details {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  padding: 0.25rem 0.75rem 0.75rem;
  font-size: 0.875rem;
}
.warning-note {
  display: flex;
  align-items: flex-start;
  gap: 0.375rem;
  color: var(--ui-text-toned);
}
.warning-facts {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 0.25rem 0.75rem;
}
.warning-facts dt {
  color: var(--ui-text-muted);
}
.warning-facts dd {
  color: var(--ui-text-highlighted);
  overflow-wrap: anywhere;
}
.warning-words {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding-inline-start: 0.75rem;
  border-inline-start: 3px solid var(--ui-border-accented);
}
/* DWD's own line breaks are kept: its instructions are lists */
.warning-text {
  white-space: pre-line;
  overflow-wrap: anywhere;
  color: var(--ui-text-toned);
}
</style>

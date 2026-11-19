<script setup lang="ts">
import { processingNote } from '~/utils/processing-note'

// The line under the credit line of provider data (GH-3799): what wetterdienst did to it, and for values that were selected or
// calculated (`derived`: an interpolation, a summary) that they were. Muted and small like the credit, and real text. A class
// and a `data-testid` given to it are those of the paragraph.
withDefaults(defineProps<{ derived?: boolean }>(), { derived: false })
const { t } = useI18n()
</script>

<template>
  <p class="text-xs text-muted" data-testid="processing-note">
    {{ processingNote(t, derived) }}
  </p>
</template>

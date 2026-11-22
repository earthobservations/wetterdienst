<script setup lang="ts">
import type { CompareState } from '~/utils/compare-model'
import ComparePanel from '~/components/ComparePanel.vue'
import { addressOf, compareFromQuery, compareToQuery, isComplete, stateOfAddress } from '~/utils/compare-model'

// The Compare tool (GH-4296, decided on GH-3789): two stations over one period, or one station over two periods, for one parameter of
// DWD's observations (the daily and the monthly climate summary, approach C), in one chart and one table with the difference. The choices
// are in the address, so that a link opens the same comparison (`/compare?compare=periods&resolution=daily&parameter=...&stations=...`);
// what a comparison is, how it is aligned and what is refused is `utils/compare-model.ts`, what is drawn is `components/ComparePanel.vue`.

const { t } = useI18n()
useHead({ title: () => t('compare.title') })

const route = useRoute()
const router = useRouter()

const address = compareFromQuery(route.query)
const state = ref<CompareState>(stateOfAddress(address))
// the stations a link names, which the pickers restore; a link that names the whole comparison opens it
const initialStationIds = address.stations
const fromLink = isComplete(address)

watch(state, () => {
  // a rejected navigation (one replaced by the next) is not a failure of the page
  void router.replace({ query: compareToQuery(addressOf(state.value)) }).catch(() => {})
}, { deep: true, immediate: true })
</script>

<template>
  <div class="frame">
    <PageHeader :title="t('compare.title')" :lede="t('compare.subtitle')" :about-label="t('compare.aboutButton')">
      <template #about>
        <div class="space-y-3 text-muted">
          <p>{{ t('compare.about1') }}</p>
          <p>{{ t('compare.about2') }}</p>
          <p>{{ t('compare.about3') }}</p>
        </div>
      </template>
    </PageHeader>
    <div class="page-body">
      <ComparePanel v-model="state" :initial-station-ids="initialStationIds" :from-link="fromLink" />
    </div>
  </div>
</template>

<script setup lang="ts">
import ParameterSelection from "~/components/ParameterSelection.vue";

interface Selection {
  provider: string | undefined
  network: string | undefined
  resolution: string | undefined
  dataset: string | undefined
  parameters: string[]
}


const route = useRoute();
const router = useRouter();

const fromQuery = (q: Record<string, any>): Selection => {
  return {
    provider: q.provider?.toString(),
    network: q.network?.toString(),
    resolution: q.resolution?.toString(),
    dataset: q.dataset?.toString(),
    parameters: q.parameters
      ? q.parameters.toString().split(",").filter(Boolean)
      : []
  };
}

const toQuery = (sel: Selection): Record<string, string> => {
  const q: Record<string, string> = {};
  if (sel.provider) q.provider = sel.provider;
  if (sel.network) q.network = sel.network;
  if (sel.resolution) q.resolution = sel.resolution;
  if (sel.dataset) q.dataset = sel.dataset;
  if (sel.parameters.length) q.parameters = sel.parameters.join(",");
  return q;
}

const selection = ref<Selection>(fromQuery(route.query))

let internalUpdate = false;

watch(
  selection,
  (val) => {
    internalUpdate = true;
    router.replace({ query: toQuery(val) });
    internalUpdate = false;
  },
  { deep: true }
);

watch(
  () => route.query,
  (q) => {
    if (internalUpdate) return;
    const next = fromQuery(q);
    // Only update if different to avoid needless reactivity churn
    if (JSON.stringify(next) !== JSON.stringify(selection.value)) {
      selection.value = next;
    }
  }
);

// Show results section after parameter selection
const showResults = computed(() => selection.value.provider && selection.value.parameters.length > 0)

</script>

<template>
  <div class="flex flex-col gap-4 max-w-md mx-auto">
    <ParameterSelection v-model="selection" />
  </div>
</template>
<script setup lang="ts">
import { ODBL_URL, OSM_COPYRIGHT_URL, PHOTON_URL } from '#shared/utils/places'

// The credit of the places (GH-3791): OpenStreetMap's licence (ODbL) asks for it with the data, and Photon is named as the way to it. Shown with every
// list of places, wherever it is: the header's search, the Forecast's station search, the town of "Ask the weather" and the Explorer's point.
</script>

<template>
  <i18n-t
    keypath="shell.placesCredit"
    tag="p"
    scope="global"
    data-testid="places-credit"
    class="text-xs text-muted"
  >
    <template #osm>
      <a :href="OSM_COPYRIGHT_URL" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">© OpenStreetMap contributors</a>
    </template>
    <template #licence>
      <a :href="ODBL_URL" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">ODbL</a>
    </template>
    <template #photon>
      <a :href="PHOTON_URL" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">Photon</a>
    </template>
  </i18n-t>
</template>

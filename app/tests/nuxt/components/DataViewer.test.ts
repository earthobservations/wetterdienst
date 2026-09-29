import type { DataSettings } from '~/types/data-settings.type'
import type { ParameterSelection } from '~/types/parameter-selection-state.type'
import type { StationSelectionState } from '~/types/station-selection-state.type'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { UApp } from '#components'
import DataViewer from '~/components/DataViewer.vue'

const settings: DataSettings = {
  humanize: true,
  convertUnits: true,
  unitTargets: {},
  shape: 'long',
  skipEmpty: false,
  skipThreshold: 0.95,
  skipCriteria: 'min',
  dropNulls: true,
  useNearbyStationDistance: 1,
  stationDistanceHomogeneous: 40,
  stationDistanceHeterogeneous: 20,
  useStationDistancePerParameter: {},
  minGainOfValuePairs: 0.1,
  numAdditionalStations: 3,
}

function parameterSelection(parameters: string[]): ParameterSelection {
  return { provider: 'dwd', network: 'observation', resolution: 'daily', dataset: 'climate_summary', parameters }
}

// the explorer mounts DataViewer only once a station or a point is chosen, so each of these has one
const station = { station_id: '01048', name: 'Dresden-Klotzsche' } as StationSelectionState['selection']['stations'][number]

const byStation: StationSelectionState = {
  mode: 'station',
  selection: { stations: [station] },
  interpolation: { source: 'manual' },
  dateRange: {},
}

const byPoint: StationSelectionState = {
  mode: 'interpolation',
  selection: { stations: [] },
  interpolation: { source: 'manual', latitude: 51.13, longitude: 13.75 },
  dateRange: {},
}

// DataViewer's copy buttons use UTooltip, which needs the TooltipProvider app.vue's <UApp> supplies
async function valuesDownloads(stationSelection: StationSelectionState, parameters: string[]) {
  const wrapper = await mountSuspended(defineComponent({
    setup: () => () => h(UApp, null, {
      default: () => h(DataViewer, { parameterSelection: parameterSelection(parameters), stationSelection, settings }),
    }),
  }))
  const vm = wrapper.findComponent(DataViewer).vm as unknown as { downloadMenuItems: { label: string, disabled: boolean }[][] }
  return vm.downloadMenuItems[0]!.map(item => [item.label, item.disabled])
}

describe('dataViewer downloads', () => {
  it.each([
    ['a station', byStation],
    ['a point', byPoint],
  ])('disables the values downloads for %s with no parameter selected', async (_, stationSelection) => {
    // a values download asks the backend again, and with no parameter did nothing when chosen
    expect(await valuesDownloads(stationSelection, [])).toEqual([['CSV', true], ['JSON', true], ['GeoJSON', true]])
  })

  it.each([
    ['a station', byStation],
    ['a point', byPoint],
  ])('offers the values downloads for %s with a parameter selected', async (_, stationSelection) => {
    expect(await valuesDownloads(stationSelection, ['temperature_air_mean_2m'])).toEqual([
      ['CSV', false],
      ['JSON', false],
      ['GeoJSON', false],
    ])
  })
})

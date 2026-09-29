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

const parameterSelection: ParameterSelection = {
  provider: 'dwd',
  network: 'observation',
  resolution: 'daily',
  dataset: 'climate_summary',
  parameters: ['temperature_air_mean_2m'],
}

function stationSelection(stations: { station_id: string }[]): StationSelectionState {
  return {
    mode: 'station',
    selection: { stations },
    interpolation: { source: 'manual', latitude: undefined, longitude: undefined, elevation: undefined, station: undefined },
    dateRange: { startDate: undefined, endDate: undefined },
  } as unknown as StationSelectionState
}

// DataViewer's copy buttons use UTooltip, which needs the TooltipProvider app.vue's <UApp> supplies
async function mountDataViewer(stations: { station_id: string }[]) {
  const wrapper = await mountSuspended(defineComponent({
    setup: () => () => h(UApp, null, {
      default: () => h(DataViewer, { parameterSelection, stationSelection: stationSelection(stations), settings }),
    }),
  }))
  return wrapper.findComponent(DataViewer).vm as unknown as { downloadMenuItems: { label: string, disabled: boolean }[][] }
}

describe('dataViewer downloads', () => {
  it('disables the values downloads while there is no station or point to ask for', async () => {
    // they asked the backend again for the current selection, and with none did nothing when chosen
    const vm = await mountDataViewer([])
    expect(vm.downloadMenuItems[0]!.map(item => [item.label, item.disabled])).toEqual([
      ['CSV', true],
      ['JSON', true],
      ['GeoJSON', true],
    ])
  })

  it('offers the values downloads once a station is selected', async () => {
    const vm = await mountDataViewer([{ station_id: '01048' }])
    expect(vm.downloadMenuItems[0]!.every(item => !item.disabled)).toBe(true)
  })
})

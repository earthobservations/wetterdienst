import type { Station } from '#shared/types/api'
import type { PlacedStation } from '~/utils/atlas'
import { placed } from '~/utils/atlas'

export type ListStatus = 'idle' | 'pending' | 'success' | 'error'

/**
 * A list of stations the map may show, asked for the first time it is wanted and not again while its key is
 * the same (GH-3518). The forecast points alone are some thousand, NOAA GHCN's stations a hundred thousand:
 * a list is only asked for when its layer is shown or a station's panel needs the nearest station of it.
 *
 * `key` names what the list is of; a new key drops the list and asks for the new one at the next `ensure`.
 */
export function useAtlasStations(key: () => string, load: () => Promise<Station[]>) {
  const stations = shallowRef<PlacedStation[]>([])
  const status = ref<ListStatus>('idle')
  const error = shallowRef<unknown>(null)
  let loadedKey: string | null = null
  let generation = 0

  async function ensure(force = false) {
    const wanted = key()
    if (!force && loadedKey === wanted && status.value !== 'error')
      return
    loadedKey = wanted
    const mine = ++generation
    status.value = 'pending'
    error.value = null
    stations.value = []
    try {
      const list = await load()
      // the key moved on while this list was on its way: it is not the one wanted
      if (mine !== generation)
        return
      stations.value = placed(list)
      status.value = 'success'
    }
    catch (failure) {
      if (mine !== generation)
        return
      error.value = failure
      status.value = 'error'
    }
  }

  return { stations, status, error, ensure }
}

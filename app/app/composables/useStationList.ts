import type { Station } from '#shared/types/api'
import type { PlacedStation } from '~/utils/map-tool'
import { placed } from '~/utils/map-tool'

export type ListStatus = 'idle' | 'pending' | 'success' | 'error'

/**
 * A list of stations the map may show, asked for the first time it is wanted and not again while its key is the same
 * (GH-3650). The forecast points alone are some thousand: a list is only asked for when its layer is shown or the
 * panel needs the nearest station of it.
 *
 * `key` names what the list is of; a new key drops the list and asks for the new one at the next `ensure`. An answer
 * that comes after the key has moved on is not the list wanted and is dropped.
 */
export function useStationList(key: () => string, load: () => Promise<Station[]>) {
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

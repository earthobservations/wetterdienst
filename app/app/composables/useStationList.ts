import type { Station } from '#shared/types/api'
import type { PlacedStation } from '~/utils/map-tool'
import { placed } from '~/utils/map-tool'

export type ListStatus = 'idle' | 'pending' | 'success' | 'error'

/**
 * A list of stations the map may show, asked for the first time it is wanted and not again while its key is the same
 * (GH-3650). The forecast points alone are some thousand: a list is only asked for when its layer is shown or the
 * panel needs the nearest station of it.
 *
 * `key` names what the list is of. The list and its status are the key's: where the key has moved on (another dataset),
 * they read as nothing until the next `ensure` has asked for the new one, so that the stations of the old list are
 * never taken for the new one's, and an answer that comes after the key has moved on is not the list wanted and is
 * dropped.
 */
export function useStationList(key: () => string, load: () => Promise<Station[]>) {
  const items = shallowRef<PlacedStation[]>([])
  const state = ref<ListStatus>('idle')
  const error = shallowRef<unknown>(null)
  /** The key the list in hand was asked for */
  const listKey = ref<string | null>(null)
  let generation = 0

  const current = () => listKey.value === key()
  const stations = computed(() => current() ? items.value : [])
  const status = computed<ListStatus>(() => current() ? state.value : 'idle')

  async function ensure(force = false) {
    const wanted = key()
    if (!force && listKey.value === wanted && state.value !== 'error')
      return
    listKey.value = wanted
    const mine = ++generation
    state.value = 'pending'
    error.value = null
    items.value = []
    try {
      const list = await load()
      if (mine !== generation)
        return
      items.value = placed(list)
      state.value = 'success'
    }
    catch (failure) {
      if (mine !== generation)
        return
      error.value = failure
      state.value = 'error'
    }
  }

  return { stations, status, error, ensure }
}

import { vi } from 'vitest'

/**
 * A `localStorage` that holds what is written to it, for the test's document: Node's own `localStorage` global
 * stands in its way and holds nothing. Installed with `vi.stubGlobal`, so `vi.unstubAllGlobals()` takes it away.
 *
 * @returns The items it holds
 */
export function stubMemoryStorage(): Map<string, string> {
  const items = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, String(value)),
    removeItem: (key: string) => void items.delete(key),
    clear: () => items.clear(),
  })
  return items
}

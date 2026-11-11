import { afterEach, beforeEach } from 'vitest'

// A fresh, empty `localStorage` and `sessionStorage` for every test, in every vitest project (GH-3990).
//
// The storage a test finds is the runtime's, and the runtimes differ: Node's `localStorage` global is `undefined`
// until `--localstorage-file` names a file (a developer's machine), and where it works (a CI runner) it keeps what a
// test wrote for the tests after it, and for the next run; the document's own `sessionStorage` keeps its items for
// the whole file. A test that wrote storage (the station picker remembers its mode) then changed the start of every
// later test, but only where storage works.
//
// So the tests never see the runtime's: one in-memory storage of each kind takes its place before a test file loads,
// and is emptied before and after every test, which is all a test of the app can ask of a browser's storage that
// is new. The same object stays in place for the whole file, so a store that took it at import time (`useSettings`
// keeps its in a module-level singleton) writes where a test reads. A test that needs a storage that fails
// (blocked, full, throwing) puts its own over this one with `Object.defineProperty` or `vi.stubGlobal` and puts this
// one back (`vi.unstubAllGlobals`, or the original descriptor), as the tests of `useSettingsStorage` do.

export class MemoryStorage implements Storage {
  private readonly items = new Map<string, string>()

  get length() {
    return this.items.size
  }

  clear() {
    this.items.clear()
  }

  getItem(key: string) {
    return this.items.get(String(key)) ?? null
  }

  key(index: number) {
    return [...this.items.keys()][index] ?? null
  }

  removeItem(key: string) {
    this.items.delete(String(key))
  }

  setItem(key: string, value: string) {
    this.items.set(String(key), String(value))
  }
}

const STORAGES = {
  localStorage: new MemoryStorage(),
  sessionStorage: new MemoryStorage(),
} as const

// `window` is the global object in the Nuxt environment and absent in the Node one; defining the property on both
// leaves nothing that reads one and not the other
const targets: object[] = [globalThis]
if (typeof window !== 'undefined' && (window as unknown) !== globalThis)
  targets.push(window)

for (const [name, storage] of Object.entries(STORAGES)) {
  for (const target of targets)
    Object.defineProperty(target, name, { configurable: true, enumerable: true, writable: true, value: storage })
}

function empty() {
  for (const storage of Object.values(STORAGES))
    storage.clear()
}

beforeEach(empty)
afterEach(empty)

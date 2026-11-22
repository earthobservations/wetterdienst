// The index of the app's own pages, as the module `modules/search-index` serves it (GH-3790)
declare module 'virtual:search-index/loaders' {
  import type { SearchIndex } from '~/utils/search-index'

  const loaders: Record<string, () => Promise<{ default: SearchIndex, labels: Record<string, string> }>>
  export default loaders
}

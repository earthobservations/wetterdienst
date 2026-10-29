/**
 * Whether the search (`CommandPalette.vue`) is open: one state for the header's search button, the home page's
 * search field and the keyboard shortcut (Ctrl+K, ⌘K on a Mac), so that each of them opens the same dialog.
 */
export function usePalette() {
  const open = useState('command-palette-open', () => false)
  return { open }
}

/** Whether the reader's keyboard has the Command key: the shortcut is ⌘K there, and Ctrl+K everywhere else */
export function isApplePlatform(): boolean {
  if (typeof navigator === 'undefined')
    return false
  const platform = (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData?.platform ?? navigator.platform ?? ''
  return /mac|iphone|ipad|ipod/i.test(platform)
}

/**
 * Text as the search compares it: lower case, without accents, and with the German umlauts written out, as the
 * station lists of the DWD write them (`MUENCHEN-STADT`), so that "München" finds it.
 */
export function searchable(text: string): string {
  return text
    .toLowerCase()
    .replace(/ä/g, 'ae')
    .replace(/ö/g, 'oe')
    .replace(/ü/g, 'ue')
    .replace(/ß/g, 'ss')
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .replace(/[-_/]+/g, ' ')
    .trim()
}

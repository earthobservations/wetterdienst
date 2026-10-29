/**
 * Whether the app's search (the command palette, `components/CommandPalette.vue`, GH-3518) is open. One state for
 * the whole app: the rail's search button, the narrow layout's and Ctrl+K / ⌘K all open the same dialog.
 */
export function useCommandPalette() {
  const open = useState('command-palette-open', () => false)
  return {
    open,
    show: () => {
      open.value = true
    },
  }
}

/** Whether this is an Apple system, where the shortcut is ⌘K rather than Ctrl+K */
export function isApplePlatform(): boolean {
  if (typeof navigator === 'undefined')
    return false
  return /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent)
}

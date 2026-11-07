import type { Section } from '~/utils/sections'
import { TOOLS } from '~/utils/sections'
import { BAR_SIZE, barKeys, DEFAULT_TOOL_ORDER, isDefaultOrder, menuKeys, normalizeToolOrder } from '~/utils/tab-bar'

/**
 * Which tools are in the tab bar of the narrow layout and which are only in the Menu's sheet (GH-3846): the reader's
 * choice, kept with the settings (`settings.tabBar`, in the browser, no account), read through
 * `normalizeToolOrder` so that a stored list that names a tool that is gone, or too few, is repaired and never an
 * error. The bar reads the same list the chooser on the settings page writes, so the two cannot differ.
 */
export function useTabBar() {
  const { settings } = useSettings()
  const byKey = (key: string): Section => TOOLS.find(tool => tool.key === key)!

  /** All the tools in the order of the list: the first `BAR_SIZE` are the bar */
  const order = computed(() => normalizeToolOrder(settings.value.tabBar))
  const barTools = computed(() => barKeys(order.value).map(byKey))
  /** The tools that are only in the Menu's sheet: a page of one of them is the Menu's page */
  const menuTools = computed(() => menuKeys(order.value).map(byKey))
  const isDefault = computed(() => isDefaultOrder(order.value))

  function setOrder(next: readonly string[]) {
    settings.value.tabBar = normalizeToolOrder(next)
  }
  function resetOrder() {
    settings.value.tabBar = [...DEFAULT_TOOL_ORDER]
  }

  return { order, barTools, menuTools, isDefault, setOrder, resetOrder, size: BAR_SIZE }
}

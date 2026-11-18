/**
 * The narrow layout's media query (GH-4227): where the tab bar stands at the foot of the window (`main.css`,
 * `@media (width < 64rem)`), which is where the page runs edge to edge, the "About" of a tool is an ⓘ and the map fills the
 * screen. Written as `max-width` so that a window with no layout to measure (the test environment) is not a phone.
 */
export const PHONE_QUERY = '(max-width: 63.99rem)'

/** Whether the window is the narrow layout's (the tab bar's breakpoint); desktop at 64 rem and up is not */
export function usePhone() {
  return useMediaQuery(PHONE_QUERY)
}

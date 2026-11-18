/**
 * The phone's media query (GH-4227): below 40 rem (640 px, Tailwind's `sm`, the width of the phone layout) the page runs edge
 * to edge, the "About" of a tool is an ⓘ and the map fills the screen; a tablet and a desktop are as they were. The tab bar
 * stands to 64 rem, but that is no phone. Written as `max-width` so that a window with no layout to measure (the test
 * environment) is not a phone. The CSS says the same as `@media (width < 40rem)`.
 */
export const PHONE_QUERY = '(max-width: 39.99rem)'

/** Whether the window is a phone's, below 40 rem; a tablet and a desktop are not */
export function usePhone() {
  return useMediaQuery(PHONE_QUERY)
}

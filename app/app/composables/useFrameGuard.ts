import { frameGuard, isFramedByAnotherOrigin } from '../utils/frame-guard'

/**
 * Whether the page draws nothing: it is framed by another origin, and not at the widget (`app/utils/frame-guard.ts`).
 * `app.vue` and `error.vue` ask it, so that a location the server could not tell from the widget shows no page of
 * the app, nor the text of a 404 that holds the path.
 *
 * @returns A ref that is true where nothing is to be drawn
 */
export function useFrameBlank() {
  const framed = import.meta.client && isFramedByAnotherOrigin(window)
  const route = useRoute()
  return computed(() => frameGuard(framed, route.path).blank)
}

import { guardNavigation, isFramedByAnotherOrigin } from '../utils/frame-guard'

// Framed by another origin, the page stays on the widget (`app/utils/frame-guard.ts`): a link or a script that
// would take it to another route is stopped. What is drawn at a route that is not the widget is decided by
// `app.vue` and `error.vue` (`useFrameBlank`), which ask the same question of the path; this is the second hold on
// the same thing, for a navigation that nothing draws a link to.
export default defineNuxtPlugin(() => {
  guardNavigation(useRouter(), isFramedByAnotherOrigin(window))
})

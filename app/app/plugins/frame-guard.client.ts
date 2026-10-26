import { START_LOCATION } from 'vue-router'
import { allowsNavigation, isFramedByAnotherOrigin } from '../utils/frame-guard'

// Framed by another origin, the page stays on the widget (`app/utils/frame-guard.ts`): a link or a script that
// would take it to another route is stopped. What is drawn at a route that is not the widget is decided by
// `app.vue` and `error.vue` (`useFrameBlank`).
export default defineNuxtPlugin(() => {
  const framed = isFramedByAnotherOrigin(window)
  if (!framed)
    return
  useRouter().beforeEach((to, from) => allowsNavigation(framed, to.name, from === START_LOCATION) ? undefined : false)
})

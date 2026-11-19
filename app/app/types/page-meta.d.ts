// What a page can say about itself to the shell, beside Nuxt's own `definePageMeta` keys.
declare module '#app' {
  interface PageMeta {
    /** `false` where the bars of the phone stay in view whatever the page does (the map, which fills the window between them); GH-4226 */
    barsHide?: boolean
  }
}

export {}

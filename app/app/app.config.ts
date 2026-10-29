export default defineAppConfig({
  ui: {
    colors: {
      // the blue of the logo, #2E6FD1, with its navy #17335F as shade 900 (`--color-brand-*` in main.css)
      primary: 'brand',
      neutral: 'slate',
    },
    button: {
      compoundVariants: [
        // The label of a solid primary button is Nuxt UI's `text-inverted`: white on the brand blue (4.9:1) in light
        // mode, slate-900 on its lighter dark-mode shade (5.7:1). Hovered and pressed, Nuxt UI fades the fill to 75 %
        // over the page, which takes white on it to 3.1:1: the fill goes one shade darker instead in light mode
        // (6.7:1) and one lighter in dark mode (8.8:1), as `tests/unit/button-contrast.test.ts` computes.
        {
          color: 'primary',
          variant: 'solid',
          class: 'hover:bg-primary-600 active:bg-primary-600 dark:hover:bg-primary-300 dark:active:bg-primary-300',
        },
      ],
    },
  },
})

// The palette is the logo's (GH-3518): the palettes themselves, and the contrast of every pair, are in
// app/assets/css/main.css.
export default defineAppConfig({
  ui: {
    colors: {
      primary: 'azure',
      info: 'azure',
      success: 'sea',
      warning: 'sun',
      error: 'ember',
      neutral: 'gray',
    },
    button: {
      compoundVariants: [
        // A solid primary button is the logo's blue (shade 600) with a white label, 4.9:1. Nuxt UI hovers it to
        // 75 % of itself over the page, which pales the fill and takes the label to 3.2:1; it goes darker instead,
        // to shade 700 (6.7:1), as a pressed key does. Dark mode: the dark label on shade 400, and 300 hovered.
        {
          color: 'primary',
          variant: 'solid',
          class: 'hover:bg-primary-700 active:bg-primary-700 dark:hover:bg-primary-300 dark:active:bg-primary-300',
        },
      ],
    },
    // a panel: a hairline and no shadow, its header a label strip on the tint of the canvas
    card: {
      slots: {
        root: 'rounded-lg',
        header: 'px-4 py-3 sm:px-5 bg-muted/60',
        body: 'p-4 sm:p-5',
        footer: 'px-4 py-3 sm:px-5',
      },
    },
    badge: {
      slots: {
        base: 'font-semibold',
      },
    },
  },
})

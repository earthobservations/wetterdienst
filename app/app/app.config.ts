export default defineAppConfig({
  ui: {
    colors: {
      // the logo's blue and the neutrals at the navy's hue (assets/css/main.css, GH-3518)
      primary: 'brand',
      neutral: 'ink',
    },
    button: {
      compoundVariants: [
        // The fill of a solid primary button is the logo's blue (shade 600 in light mode, main.css) under a
        // white label, 4.9:1. Nuxt UI fades it to 75 % when hovered, which is 3.1:1 to white: it turns a
        // shade darker instead (700, 6.8:1, and 800 pressed) in light mode, and a shade lighter in dark mode
        // (300 under the dark label, 9.4:1). Disabled and focus styles are those of Nuxt UI's theme.
        {
          color: 'primary',
          variant: 'solid',
          class: 'hover:bg-primary-700 active:bg-primary-800 dark:hover:bg-primary-300 dark:active:bg-primary-300',
        },
      ],
    },
    card: {
      slots: {
        // a surface of its own: rounder, and lifted a little off the page (the ring stays the edge)
        root: 'rounded-xl wd-surface',
      },
      variants: {
        variant: {
          outline: {
            root: 'shadow-(--shadow-card)',
          },
        },
      },
    },
    alert: {
      slots: {
        root: 'rounded-xl',
      },
    },
  },
})

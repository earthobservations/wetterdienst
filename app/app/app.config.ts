// The theme of the app (GH-3518). The colours are the scales declared in assets/css/main.css (`brand`, the blue of the
// logo, and `ink`, a neutral scale tinted towards the logo's navy); the components below are shaped here, once, so that
// no page restyles a card or a button of its own.
export default defineAppConfig({
  ui: {
    colors: {
      primary: 'brand',
      neutral: 'ink',
    },
    button: {
      slots: {
        base: 'rounded-lg font-medium transition-colors duration-150 motion-reduce:transition-none',
      },
      compoundVariants: [
        // The label of a solid primary button is --app-text-on-primary (white on the logo's blue, 4.9:1; the dark
        // navy on the lighter blue of dark mode, 7.0:1), and the hovered fill a step darker (lighter in dark mode)
        // rather than Nuxt UI's 75 % of the fill, which is under 4.5:1 for white. Focus and disabled styles are those
        // of Nuxt UI's theme. Ratios in main.css and in app/ACCESSIBILITY.md.
        {
          color: 'primary',
          variant: 'solid',
          class: 'text-(color:--app-text-on-primary) hover:bg-(--app-primary-hover)',
        },
      ],
    },
    card: {
      slots: {
        root: 'rounded-xl shadow-(--app-shadow-sm)',
        header: 'p-4 sm:px-6',
        body: 'p-4 sm:p-6',
      },
    },
    alert: {
      slots: {
        root: 'rounded-xl',
      },
    },
    badge: {
      slots: {
        base: 'rounded-full font-medium',
      },
    },
    input: {
      slots: {
        base: 'rounded-lg',
      },
    },
    select: {
      slots: {
        base: 'rounded-lg',
      },
    },
    selectMenu: {
      slots: {
        base: 'rounded-lg',
      },
    },
    textarea: {
      slots: {
        base: 'rounded-lg',
      },
    },
    tabs: {
      slots: {
        list: 'rounded-xl',
        indicator: 'rounded-lg',
        trigger: 'rounded-lg',
      },
    },
    navigationMenu: {
      slots: {
        link: 'rounded-lg',
      },
    },
    header: {
      slots: {
        root: 'bg-default/80 backdrop-blur-md',
      },
    },
  },
})

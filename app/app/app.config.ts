export default defineAppConfig({
  ui: {
    // the logo's blue for action and the navy-tinted neutrals (`brand` and `ink`, main.css); the icons are Phosphor's,
    // set in nuxt.config.ts (`appConfig.ui.icons`), where the build reads them for the icon bundle
    colors: {
      primary: 'brand',
      neutral: 'ink',
    },
    button: {
      slots: {
        base: 'font-semibold',
      },
      compoundVariants: [
        // The fill is the logo's blue and the label white (4.9:1). Nuxt UI's hover is the fill at 75 % over the
        // page, which is lighter and takes the label under 4.5:1; a hovered or pressed button is a darker shade
        // instead (700: 6.9:1, 800: 9.4:1). In dark mode the fill is shade 400 with a navy label (7.0:1), and it
        // lightens (300: 9.6:1, 200: 12.4:1). The ratios are held by tests/unit/button-contrast.test.ts.
        {
          color: 'primary',
          variant: 'solid',
          class: 'hover:bg-primary-700 active:bg-primary-800 dark:hover:bg-primary-300 dark:active:bg-primary-200',
        },
      ],
    },
    card: {
      slots: {
        // a white card on the paper, with a hairline and a shadow that is only there to lift it off the page
        root: 'rounded-xl overflow-hidden shadow-[0_1px_2px_rgb(11_26_51/0.04),0_6px_20px_-12px_rgb(11_26_51/0.18)] dark:shadow-none',
        header: 'px-4 py-3.5 sm:px-6',
      },
    },
    switch: {
      slots: {
        // an unchecked switch is a track in the colour of a field's edge (3:1, WCAG 1.4.11), not a pale fill
        base: 'data-[state=unchecked]:bg-(--ui-border-accented)',
      },
    },
    alert: {
      slots: {
        root: 'rounded-xl',
      },
    },
    modal: {
      slots: {
        content: 'rounded-2xl',
      },
    },
    popover: {
      slots: {
        content: 'rounded-xl',
      },
    },
  },
})

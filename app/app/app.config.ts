export default defineAppConfig({
  ui: {
    colors: {
      // the logo's blue to its navy (main.css, `--color-brand-*`), on a slate neutral
      primary: 'brand',
      neutral: 'slate',
    },
    button: {
      compoundVariants: [
        // The logo's blue stays the fill. The label and the hovered fill are the app's (main.css,
        // --app-text-on-primary and --app-primary-hover): Nuxt UI's hover, the fill at 75 % over the
        // page, lightens it under a white label to 3.8:1. Focus and disabled styles are the theme's.
        {
          color: 'primary',
          variant: 'solid',
          class: 'text-(color:--app-text-on-primary) hover:bg-(color:--app-primary-hover) active:bg-(color:--app-primary-hover)',
        },
      ],
    },
  },
})

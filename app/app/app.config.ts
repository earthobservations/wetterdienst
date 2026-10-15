export default defineAppConfig({
  ui: {
    colors: {
      primary: 'green',
    },
    button: {
      compoundVariants: [
        // The brand green stays the fill; the label of a solid primary button is dark on it
        // (white is 2.2:1), colour and ratios in main.css (--app-text-on-primary). Only the label
        // colour changes: hover, focus and disabled styles are those of Nuxt UI's theme.
        {
          color: 'primary',
          variant: 'solid',
          class: 'text-(color:--app-text-on-primary)',
        },
      ],
    },
  },
})

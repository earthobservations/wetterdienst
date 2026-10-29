export default defineAppConfig({
  ui: {
    colors: {
      // the logo's blue and the greys tinted towards its navy, both defined in main.css (`--color-brand-*`, `--color-ink-*`)
      primary: 'brand',
      neutral: 'ink',
    },
    button: {
      compoundVariants: [
        // The label of a solid primary button is white on the blue of light mode and ink on the pale blue of dark mode
        // (`--app-text-on-primary`, main.css), and a hovered or pressed one is a step darker (light) or paler (dark)
        // (`--app-primary-hover`): Nuxt UI's hover fades the fill to 75 %, under which a white label falls below 4.5:1.
        // The disabled style is Nuxt UI's.
        {
          color: 'primary',
          variant: 'solid',
          class: 'text-(color:--app-text-on-primary) hover:bg-(--app-primary-hover) active:bg-(--app-primary-hover)',
        },
      ],
    },
    card: {
      // plain panels: an edge, no shadow, a small radius
      slots: {
        root: 'rounded-md',
      },
    },
  },
})

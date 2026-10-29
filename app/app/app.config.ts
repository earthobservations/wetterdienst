export default defineAppConfig({
  ui: {
    colors: {
      // the logo's blue (`--color-brand-*` in main.css) for controls and links, and ink and paper for the rest
      primary: 'brand',
      neutral: 'ink',
    },
    button: {
      compoundVariants: [
        // The label and the hovered fill of a solid primary button: white on the logo's blue and a darker blue
        // hovered in light mode, the logo's navy on a light blue and a lighter one hovered in dark mode, colours
        // and ratios in main.css (--app-text-on-primary, --app-primary-hover). Nuxt UI's own hover is 75 % of
        // the fill over the page, which lightens it under a white label (3.2:1). Focus and disabled styles are
        // those of Nuxt UI's theme.
        {
          color: 'primary',
          variant: 'solid',
          class: 'text-(color:--app-text-on-primary) hover:bg-(--app-primary-hover) active:bg-(--app-primary-hover)',
        },
      ],
    },
    // A card is a section of the page, as in print: a rule above it, no box around it, its text on the page's
    // left edge. No `overflow-hidden`, so that the focus outline of a field on that edge is not cut off.
    card: {
      slots: {
        root: 'rounded-none',
        header: 'px-0 sm:px-0 pt-3 pb-1',
        body: 'px-0 sm:px-0 py-4 sm:py-5',
        footer: 'px-0 sm:px-0 py-3',
      },
      variants: {
        variant: {
          outline: {
            root: 'bg-transparent ring-0 border-t-2 border-(--app-rule-strong) divide-y-0',
          },
        },
      },
    },
    badge: {
      slots: {
        base: 'rounded-sm',
      },
    },
    alert: {
      slots: {
        root: 'rounded-sm',
        title: 'font-semibold',
      },
    },
  },
})

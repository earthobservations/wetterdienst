export default defineAppConfig({
  ui: {
    colors: {
      // the logo's blue and its navy-tinted greys (`brand` and `gray` in main.css, GH-3518)
      primary: 'brand',
      neutral: 'gray',
    },
    button: {
      compoundVariants: [
        // Nuxt UI darkens nothing on hover: a solid button is its fill at 75 % over the page, which is 3.8:1 under
        // the white label on light. The fill goes a shade outwards instead (--app-primary-hover in main.css); the
        // label (Nuxt UI's text-inverted: white on light, the page's navy on dark), focus and disabled styles stay
        // the theme's.
        {
          color: 'primary',
          variant: 'solid',
          class: 'hover:bg-(--app-primary-hover) active:bg-(--app-primary-hover) aria-expanded:bg-(--app-primary-hover)',
        },
      ],
    },
    card: {
      slots: {
        // flat surfaces with a hairline, the radius of the logo's tiles
        root: 'rounded-2xl',
      },
    },
  },
})

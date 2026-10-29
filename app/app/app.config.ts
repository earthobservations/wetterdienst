export default defineAppConfig({
  ui: {
    colors: {
      // the blue of the logo, as a scale from its navy to the dark of its sun (assets/css/main.css)
      primary: 'brand',
      // Tailwind's gray, redrawn in main.css with a little of the logo's navy in it
      neutral: 'gray',
    },
    button: {
      compoundVariants: [
        // The fill is shade 600 (light) or 300 (dark), --ui-primary in main.css, and the label Nuxt UI's
        // `text-inverted`: white on 600 (6.7:1), the night blue on 300 (7.6:1). Nuxt UI fades the fill to 75 % for
        // a hover, which on white is a lighter blue that white text is under 4.5:1 on; a hovered button is a shade
        // darker instead (light, 8.6:1) or lighter (dark, 10:1). tests/unit/button-contrast.test.ts measures them.
        {
          color: 'primary',
          variant: 'solid',
          class: 'hover:bg-(--ui-color-primary-700) active:bg-(--ui-color-primary-800) dark:hover:bg-(--ui-color-primary-200) dark:active:bg-(--ui-color-primary-200)',
        },
      ],
    },
  },
})

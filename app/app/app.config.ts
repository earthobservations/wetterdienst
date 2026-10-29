// The theme of the app (GH-3518). The look is a few tokens (assets/css/main.css): the scales `brand` (the blue of the
// logo, the one accent) and `ink` (neutrals tinted towards the logo's navy), a small radius, hairline borders and no
// shadows. The components below are shaped here, once, so that no page restyles a card or a button of its own.
// The icons are Phosphor (`i-ph-*`), including the ones Nuxt UI draws itself.
export default defineAppConfig({
  ui: {
    colors: {
      primary: 'brand',
      neutral: 'ink',
    },
    icons: {
      arrowDown: 'i-ph-arrow-down',
      arrowLeft: 'i-ph-arrow-left',
      arrowRight: 'i-ph-arrow-right',
      arrowUp: 'i-ph-arrow-up',
      caution: 'i-ph-warning-circle',
      check: 'i-ph-check',
      chevronDoubleLeft: 'i-ph-caret-double-left',
      chevronDoubleRight: 'i-ph-caret-double-right',
      chevronDown: 'i-ph-caret-down',
      chevronLeft: 'i-ph-caret-left',
      chevronRight: 'i-ph-caret-right',
      chevronUp: 'i-ph-caret-up',
      close: 'i-ph-x',
      copy: 'i-ph-copy',
      copyCheck: 'i-ph-check-square',
      dark: 'i-ph-moon',
      drag: 'i-ph-dots-six-vertical',
      ellipsis: 'i-ph-dots-three',
      error: 'i-ph-x-circle',
      external: 'i-ph-arrow-up-right',
      eye: 'i-ph-eye',
      eyeOff: 'i-ph-eye-slash',
      file: 'i-ph-file',
      folder: 'i-ph-folder',
      folderOpen: 'i-ph-folder-open',
      hash: 'i-ph-hash',
      info: 'i-ph-info',
      light: 'i-ph-sun',
      loading: 'i-ph-circle-notch',
      menu: 'i-ph-list',
      minus: 'i-ph-minus',
      panelClose: 'i-ph-sidebar-simple',
      panelOpen: 'i-ph-sidebar-simple',
      plus: 'i-ph-plus',
      reload: 'i-ph-arrow-counter-clockwise',
      search: 'i-ph-magnifying-glass',
      stop: 'i-ph-stop',
      star: 'i-ph-star',
      success: 'i-ph-check-circle',
      system: 'i-ph-desktop',
      tip: 'i-ph-lightbulb',
      upload: 'i-ph-upload-simple',
      warning: 'i-ph-warning',
    },
    button: {
      slots: {
        base: 'rounded-md font-medium transition-colors duration-150 motion-reduce:transition-none',
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
        // One accent: the primary colour is for the one thing a page asks of you (the solid button), for links and for
        // the current page. A soft or outlined primary button is quiet, in the neutral scale.
        {
          color: 'primary',
          variant: 'soft',
          class: 'bg-elevated text-default hover:bg-accented',
        },
        {
          color: 'primary',
          variant: 'outline',
          class: 'text-default ring ring-inset ring-accented hover:bg-elevated',
        },
      ],
    },
    card: {
      slots: {
        root: 'rounded-lg',
        header: 'p-4 sm:px-6',
        body: 'p-4 sm:p-6',
      },
    },
    alert: {
      slots: {
        root: 'rounded-lg',
      },
    },
    badge: {
      slots: {
        base: 'rounded-md font-medium',
      },
      compoundVariants: [
        {
          color: 'primary',
          variant: 'subtle',
          class: 'bg-elevated text-default ring ring-inset ring-default',
        },
      ],
    },
    tabs: {
      slots: {
        list: 'rounded-lg',
        indicator: 'rounded-md',
        trigger: 'rounded-md',
      },
    },
    navigationMenu: {
      slots: {
        link: 'rounded-md',
        linkLabel: 'truncate',
      },
    },
    commandPalette: {
      slots: {
        input: '[&>input]:h-12',
        // The row under the cursor: a bar in the focus colour (6.0:1 on white, 7.0:1 on the dark page), not only a tint
        // that is 1.1:1 against its neighbours. The current page, theme or language is a check (AppSearch), not a tint.
        item: 'data-highlighted:not-data-disabled:before:bg-elevated data-highlighted:not-data-disabled:before:shadow-[inset_3px_0_0_var(--app-focus-ring)]',
      },
      variants: {
        // the row of the route the page is on is not tinted either
        active: {
          true: {
            item: 'before:bg-transparent',
          },
        },
      },
    },
  },
})

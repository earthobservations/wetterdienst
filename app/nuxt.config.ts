import * as process from 'node:process'

import tailwindcss from '@tailwindcss/vite'
import { RATE_LIMIT_DEFAULTS } from './server/utils/rateLimit'
import { DEFAULT_SITE_URL } from './shared/utils/seo'

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  ssr: false,

  typescript: {
    typeCheck: false,
    strict: true,
  },

  app: {
    head: {
      // no `title`: the page's own (`app/app.vue`, the sentence that says what the site is, in the visitor's language) and
      // the server's (`server/plugins/seo-head.ts`) are the document's, and a default here would be the title of a page
      // that names none, with the app's name after it
      // the icon of the tab and the home screen (GH-3431): the SVG for current browsers, the 32 px ICO for the
      // ones that ask for `/favicon.ico` and crawlers, the PNG for iOS. All three are files of `public/`.
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/icon.svg' },
        { rel: 'icon', href: '/favicon.ico', sizes: '32x32' },
        { rel: 'apple-touch-icon', href: '/apple-touch-icon.png' },
        // the body face, asked for by the shell while the app's script loads, so the text the script lays out is
        // laid out in it once (`modules/fonts.ts`, main.css). `crossorigin`: a font is fetched in CORS mode, and a
        // preload in another mode would be fetched twice.
        { rel: 'preload', as: 'font', type: 'font/woff2', href: '/_typefaces/atkinson-hyperlegible-next-latin-wght-normal.woff2', crossorigin: '' },
      ],
      // the colour of the browser's own bar on a phone: the header's, white by day and the logo's navy by night
      meta: [
        { name: 'theme-color', content: '#ffffff', media: '(prefers-color-scheme: light)' },
        { name: 'theme-color', content: '#0b1a33', media: '(prefers-color-scheme: dark)' },
      ],
    },
  },

  // The icons of Nuxt UI's own components (a select's chevron, a dialog's close button, the spinner of a button
  // that loads), in the app's one set, Phosphor (GH-3518). Here rather than in app/app.config.ts because the
  // build reads them from here for the client bundle of @nuxt/icon (Nuxt UI's `icon:clientBundleIcons` hook);
  // the app config of the build and of the page is the same object.
  appConfig: {
    ui: {
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
        copyCheck: 'i-ph-check',
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
        stop: 'i-ph-square',
        star: 'i-ph-star',
        success: 'i-ph-check-circle',
        system: 'i-ph-monitor',
        tip: 'i-ph-lightbulb',
        upload: 'i-ph-upload-simple',
        warning: 'i-ph-warning',
      },
    },
  },

  css: [
    '~/assets/css/main.css',
    'leaflet/dist/leaflet.css',
  ],

  modules: [
    '@nuxt/eslint',
    '@nuxt/icon',
    '@nuxt/ui',
    '@nuxtjs/i18n',
    '@nuxtjs/leaflet',
    '@vueuse/nuxt',
    'nuxt-security',
    '@nuxt/test-utils/module',
  ],

  i18n: {
    locales: [
      { code: 'de', language: 'de-DE', name: 'Deutsch', file: 'de.json' },
      { code: 'en', language: 'en-GB', name: 'English', file: 'en.json' },
      { code: 'fr', language: 'fr-FR', name: 'Français', file: 'fr.json' },
      { code: 'es', language: 'es-ES', name: 'Español', file: 'es.json' },
      { code: 'it', language: 'it-IT', name: 'Italiano', file: 'it.json' },
      { code: 'pl', language: 'pl-PL', name: 'Polski', file: 'pl.json' },
      { code: 'nl', language: 'nl-NL', name: 'Nederlands', file: 'nl.json' },
      { code: 'cs', language: 'cs-CZ', name: 'Čeština', file: 'cs.json' },
      { code: 'da', language: 'da-DK', name: 'Dansk', file: 'da.json' },
      { code: 'lb', language: 'lb-LU', name: 'Lëtzebuergesch', file: 'lb.json' },
      { code: 'de-hh', language: 'de-DE', name: 'Hamburgisch', file: 'de-hh.json' },
    ],
    defaultLocale: 'de',
    strategy: 'no_prefix',
    vueI18n: 'i18n.config.ts',
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: 'wd_lang',
      fallbackLocale: 'de',
      redirectOn: 'root',
    },
  },

  devtools: { enabled: true },

  // The icons come from this app's own server (GH-3111): the two sets are installed (`@iconify-json/*`) and
  // the server bundle serves them. Phosphor is the app's one set (GH-3518); Simple Icons is for the marks of the
  // brands Phosphor has none of (JetBrains, Anthropic, Python). The icons the app names in its own files are
  // bundled with the page as well (`clientBundle.scan`), so a page draws them with its first paint, without a
  // request each. `provider` is set because @nuxt/icon picks `iconify`, which asks
  // api.iconify.design for every icon, whenever `ssr` is false, as it is here. `localApiEndpoint` is outside
  // `/api`, which the app proxies to the backend. `fallbackToApi: false` keeps a name that no set has from
  // being asked of the third party: it is an icon missing, not a request.
  icon: {
    provider: 'server',
    serverBundle: {
      collections: ['ph', 'simple-icons'],
    },
    clientBundle: {
      scan: true,
    },
    localApiEndpoint: '/_nuxt_icon',
    fallbackToApi: false,
  },

  // No `host`: `nuxt dev` listens on localhost, where Nuxt DevTools is reachable by this machine only (GH-3096).
  // The dev container sets `HOST=0.0.0.0` (compose.yml, docker/app.Dockerfile), because a published port
  // reaches nothing that listens on the loopback of the container.
  devServer: {
    port: 4000,
  },

  runtimeConfig: {
    // The rate limit of the server (`server/middleware/rate-limit.ts`, GH-3093). Every key is set at run time,
    // by `NUXT_RATE_LIMIT_<KEY>` (see docs/usage/app.md): the limit and its window, which count the requests
    // that cost something (not the pages or the catalogue routes), and the header to read a client's address
    // from, which is none: the address of the connection, the only one a client cannot choose.
    rateLimit: {
      // the e2e suite is one client, and a run went over the limit: the last tests were answered 429, which
      // ones depending on how fast the runner was. The suite's own build and server switch the limit off
      // (`WD_E2E`, set by playwright.config.ts); no other build does.
      enabled: process.env.WD_E2E !== '1',
      tokens: RATE_LIMIT_DEFAULTS.tokens,
      windowSeconds: RATE_LIMIT_DEFAULTS.windowSeconds,
      clientIpHeader: '',
    },
    // The origins whose pages may read the app's answers, a list separated by commas (`NUXT_CORS_ALLOWED_ORIGINS`):
    // none, so only the app's own page does (GH-3095). `server/middleware/cors.ts`.
    corsAllowedOrigins: '',
    // The backend's `/api` URL, which the app's proxies call (`server/utils/apiBase.ts`). Private, so no page
    // carries it, and set at run time by `NUXT_API_BASE` (GH-3096). Empty means: the old `NUXT_PUBLIC_API_BASE`
    // if that is set (deprecated), else `http://localhost:7890/api`.
    apiBase: '',
    public: {
      // The address the app is reached at, for what names the pages to the outside: the canonical link and `og:url` of
      // each page, the sitemap and `robots.txt` (`shared/utils/seo.ts`, GH-3497). Public, because the page writes the
      // canonical link itself. The hosted instance's; an instance of its own sets `NUXT_PUBLIC_SITE_URL` (docs/usage/app.md).
      siteUrl: DEFAULT_SITE_URL,
    },
  },

  vite: {
    plugins: [
      tailwindcss() as any,
    ],
    optimizeDeps: {
      include: ['leaflet', 'leaflet.markercluster', 'plotly.js-basic-dist-min'],
    },
    build: {
      rollupOptions: {
        onwarn(warning, warn) {
          // @tailwindcss/vite doesn't emit sourcemaps for its CSS transform yet
          // (upstream limitation: https://github.com/tailwindlabs/tailwindcss/issues/17926),
          // which floods the build log with a benign warning on every chunk.
          if (warning.code === 'SOURCEMAP_BROKEN' && warning.plugin === '@tailwindcss/vite:generate:build') {
            return
          }
          warn(warning)
        },
      },
    },
  },

  // Module configurations
  colorMode: {
    classSuffix: '',
    classPrefix: '',
    preference: 'system',
    fallback: 'light',
  },

  eslint: {
    config: {
      standalone: false,
    },
  },

  leaflet: {
    markerCluster: true,
  },

  security: {
    // Both are the app's own middleware, because nuxt-security's are fixed when the app is built, count every
    // route in one bucket, trust the leftmost `X-Forwarded-For` and answer `access-control-allow-origin: *`
    // (`server/middleware/rate-limit.ts` and `cors.ts`, GH-3093 and GH-3095).
    rateLimiter: false,
    corsHandler: false,
    // nuxt-security's default (`true`) sets `vite.esbuild.drop = ['console', 'debugger']`, which Vite 8 (Oxc) ignores
    // with a warning on every build, so it never removed anything (GH-3366). It stays off rather than ported to
    // `rolldownOptions.output.minify.compress.dropConsole`: the app reports a failed chart, map or DuckDB query
    // with `console.error` on purpose (the specs assert it), and that is what a bug report needs from a browser.
    removeLoggers: false,
    headers: {
      // nuxt-security defaults this to 'no-referrer', which strips the Referer
      // header. OpenStreetMap's tile servers reject refererless requests
      // ("Access denied, referer required"), so send the origin cross-origin.
      referrerPolicy: 'strict-origin-when-cross-origin',
      contentSecurityPolicy: {
        // No script, worker or request goes to a CDN (GH-3094): DuckDB-wasm (`QueryPanel.vue`) and Swagger UI
        // (`/docs`) are the app's own files, and the browser calls only this origin; the backend is reached by
        // the server's proxies, and the icons come from `/_nuxt_icon` (GH-3111).
        // No `'unsafe-eval'`: nothing evaluates a string (Plotly, Leaflet, Vue and the i18n messages run under
        // this policy; Zod probed it, see `useSettings.ts`). `'wasm-unsafe-eval'` is for DuckDB's module, which
        // the worker compiles: Chrome gives a worker the policy of its script, which has none, but a browser
        // that gives it the page's needs it, and it allows WebAssembly, no string.
        // Scripts: nuxt-security gives every response its own nonce, puts it on the page's `<script>` elements
        // and into the header where `'nonce-{{nonce}}'` stands. Without that entry the page carried nonces the
        // header did not know, and `'unsafe-inline'` was what let its inline scripts run, injected ones too
        // (GH-3112). `style-src` keeps its `'unsafe-inline'`, which
        // is a question of its own (inline styles cannot run code).
        'default-src': ['\'self\''],
        'connect-src': ['\'self\''],
        'img-src': ['\'self\'', 'data:', 'blob:', 'https://*.tile.openstreetmap.org', 'https://avatars.githubusercontent.com'],
        'script-src': ['\'self\'', '\'nonce-{{nonce}}\'', '\'wasm-unsafe-eval\''],
        'worker-src': ['\'self\''],
        'child-src': ['\'self\''],
        'style-src': ['\'self\'', '\'unsafe-inline\''],
        'font-src': ['\'self\'', 'data:'],
        'base-uri': ['\'none\''],
        'form-action': ['\'self\''],
        'frame-ancestors': ['\'self\''],
        'object-src': ['\'none\''],
      },
    },
  },

  routeRules: {
    // The page is sent with `Cross-Origin-Embedder-Policy: credentialless` (nuxt-security), and a browser then
    // refuses a worker whose script comes without one (`ERR_BLOCKED_BY_RESPONSE`). DuckDB-wasm's worker is a file
    // of the app now (GH-3094), a blob of the page's own before, which took the page's policy. nuxt-security sets
    // it for the page only, so the assets say it themselves.
    '/_nuxt/**': { headers: { 'Cross-Origin-Embedder-Policy': 'credentialless' } },
    // Who may frame `/widget` is not a rule of this list: see `server/plugins/widget-frame.ts`.
  },

  nitro: {
    compressPublicAssets: true,
    serveStatic: true,
  },
})

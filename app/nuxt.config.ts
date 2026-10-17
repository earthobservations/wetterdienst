import * as process from 'node:process'

import tailwindcss from '@tailwindcss/vite'

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
      title: 'Wetterdienst',
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

  devServer: {
    host: '0.0.0.0',
    port: 4000,
  },

  runtimeConfig: {
    public: {
      // Allow overriding the backend API base via environment (NUXT_PUBLIC_API_BASE or API_BASE)
      apiBase: 'http://localhost:3000/api',
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
    // nuxt-security limits every route to 150 requests per IP in five minutes (a 429 after that). The e2e suite
    // is one client, and a run went over the limit: the last tests were answered 429, which ones depending on how
    // fast the runner was. The suite's own build and server switch the limit off (`WD_E2E`, set by
    // playwright.config.ts); no other build does.
    rateLimiter: process.env.WD_E2E === '1' ? false : undefined,
    headers: {
      // nuxt-security defaults this to 'no-referrer', which strips the Referer
      // header. OpenStreetMap's tile servers reject refererless requests
      // ("Access denied, referer required"), so send the origin cross-origin.
      referrerPolicy: 'strict-origin-when-cross-origin',
      contentSecurityPolicy: {
        'default-src': ['\'self\''],
        'connect-src': ['\'self\'', new URL(process.env.NUXT_PUBLIC_API_BASE || 'http://0.0.0.0:3000/api').origin, 'https://api.iconify.design', 'https://code.iconify.design', 'https://cdn.jsdelivr.net'],
        'img-src': ['\'self\'', 'data:', 'blob:', 'https://*.tile.openstreetmap.org', 'https://raw.githubusercontent.com', 'https://cdnjs.cloudflare.com', 'https://unpkg.com', 'https://avatars.githubusercontent.com', 'https://api.iconify.design', 'https://code.iconify.design'],
        'script-src': ['\'self\'', '\'unsafe-inline\'', '\'unsafe-eval\'', 'https://api.iconify.design', 'https://cdn.jsdelivr.net', 'blob:'],
        'worker-src': ['\'self\'', 'blob:', 'https://cdn.jsdelivr.net'],
        'child-src': ['\'self\'', 'blob:'],
        'style-src': ['\'self\'', '\'unsafe-inline\''],
        'font-src': ['\'self\'', 'https:', 'data:'],
        'base-uri': ['\'none\''],
        'form-action': ['\'self\''],
        'frame-ancestors': ['\'self\''],
        'object-src': ['\'none\''],
      },
    },
  },

  nitro: {
    compressPublicAssets: true,
    serveStatic: true,
  },
})

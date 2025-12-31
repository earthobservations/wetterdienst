import tailwindcss from '@tailwindcss/vite'

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  ssr: false,

  alias: {
    '#types': '../types',
  },

  dirs: {
    utils: ['utils'],
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
    '@nuxtjs/leaflet',
    '@nuxtjs/mdc',
    'nuxt-security',
    '@nuxt/test-utils/module',
  ],

  devtools: { enabled: true },

  devServer: {
    host: '0.0.0.0',
    port: 4000,
  },

  runtimeConfig: {
    public: {
      apiBase: 'http://backend:3000/api',
    },
  },

  typescript: {
    typeCheck: true,
    tsConfig: {
      include: ['./*.d.ts', './app/types/*.d.ts', '../types/*.ts'],
      compilerOptions: {
        paths: {
          '#types/*': ['../types/*'],
        },
      },
    },
  },

  vite: {
    plugins: [
      tailwindcss(),
    ],
    optimizeDeps: {
      include: ['leaflet', 'leaflet.markercluster'],
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
    headers: {
      contentSecurityPolicy: {
        'default-src': ['\'self\''],
        'connect-src': ['\'self\'', 'http://backend:3000', 'https://wetterdienst-backend.up.railway.app', 'https://api.iconify.design', 'https://code.iconify.design'],
        'img-src': ['\'self\'', 'data:', 'blob:', 'https://*.tile.openstreetmap.org', 'https://raw.githubusercontent.com', 'https://cdnjs.cloudflare.com', 'https://unpkg.com', 'https://avatars.githubusercontent.com', 'https://api.iconify.design', 'https://code.iconify.design'],
        'script-src': ['\'self\'', '\'unsafe-inline\'', '\'unsafe-eval\'', 'https://api.iconify.design'],
        'style-src': ['\'self\'', '\'unsafe-inline\''],
        'font-src': ['\'self\'', 'https:', 'data:'],
        'base-uri': ['\'none\''],
        'form-action': ['\'self\''],
        'frame-ancestors': ['\'self\''],
        'object-src': ['\'none\''],
      },
    },
  },

  ui: {
    mdc: true,
  },
})

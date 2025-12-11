import tailwindcss from "@tailwindcss/vite"

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  css: [
    '~/assets/css/main.css',
    'leaflet/dist/leaflet.css'
  ],
  devtools: { enabled: true },
  typescript: {
    typeCheck: true
  },
  app: {
    head: {
      title: "Wetterdienst"
    }
  },
  devServer: {
    host: '0.0.0.0',
    port: 4000
  },
  nitro: {
    routeRules: {
      '/**': {
        headers: {
          'Content-Security-Policy': "default-src 'self'; connect-src 'self' http://backend:3000; img-src 'self' data: https://*.tile.openstreetmap.org https://raw.githubusercontent.com https://cdnjs.cloudflare.com https://unpkg.com; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; font-src 'self' https: data:; base-uri 'none'; form-action 'self'; frame-ancestors 'self'; object-src 'none';"
        }
      }
    }
  },
  vite: {
    plugins: [
      tailwindcss()
    ],
    optimizeDeps: {
      include: ['leaflet', 'leaflet.markercluster']
    }
  },
  runtimeConfig: {
    public: {
      apiBase: 'http://backend:3000/api',
    }
  },
  modules: ["@nuxt/eslint", "@nuxtjs/mdc", '@nuxt/ui', '@nuxt/icon', "nuxt-security", "@vueuse/nuxt", "@nuxtjs/leaflet"],
  colorMode: {
    classSuffix: '',
    preference: 'system',
    fallback: 'light',
    classPrefix: '',
  },
  leaflet: {
    markerCluster: true
  },
  security: {
    headers: {
      contentSecurityPolicy: false
    },
    nonce: false
  },
  ui: {
    mdc: true
  },
  ssr: false,
  eslint: {
    config: {
      standalone: false,
      stylistic: false
    }
  }
})
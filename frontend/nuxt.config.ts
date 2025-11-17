import tailwindcss from "@tailwindcss/vite"

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  css: ['~/assets/css/main.css'],
  devtools: { enabled: true },
  typescript: {
    strict: true
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
  vite: {
    plugins: [
      tailwindcss()
    ]
  },
  runtimeConfig: {
    public: {
      apiBase: 'http://backend:3000/api',
    }
  },
  modules: ["@nuxt/eslint", "@nuxtjs/mdc", '@nuxt/ui', '@nuxt/icon', "nuxt-security", "@vueuse/nuxt"],
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
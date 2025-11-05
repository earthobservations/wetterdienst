import tailwindcss from "@tailwindcss/vite";
import colors from 'tailwindcss/colors'

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  modules: ['@nuxt/ui', '@nuxt/icon'],
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  devServer: {
    host: '0.0.0.0',
    port: 4000
  },
  css: ['@/assets/css/main.css'],
  vite: {
    plugins: [
      tailwindcss(),
    ],
    server: {
      watch: {
        usePolling: true,
        interval: 1000
      },
      hmr: {
        protocol: 'ws',
        host: 'localhost',
        port: 4000
      }
    }
  },
runtimeConfig: {
  public: {
    apiBase: 'http://backend:3000/api',
  }
},
tailwindcss: {
    config: {
      theme: {
        extend: {
          colors: { primary: colors.blue }
        }
      }
    }
  }
})
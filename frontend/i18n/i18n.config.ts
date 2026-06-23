// Vue I18n runtime configuration (number & date formatting).
// Message catalogs are loaded lazily from ./locales/*.json via the Nuxt i18n module.
export default defineI18nConfig(() => ({
  legacy: false,
  fallbackLocale: 'en',
  numberFormats: {
    de: {
      decimal: { style: 'decimal', maximumFractionDigits: 2 },
      integer: { style: 'decimal', maximumFractionDigits: 0 },
    },
    en: {
      decimal: { style: 'decimal', maximumFractionDigits: 2 },
      integer: { style: 'decimal', maximumFractionDigits: 0 },
    },
  },
  datetimeFormats: {
    de: {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' },
    },
    en: {
      short: { year: 'numeric', month: 'short', day: 'numeric' },
      long: { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' },
    },
  },
}))

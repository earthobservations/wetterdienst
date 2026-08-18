// Vue I18n runtime configuration (number & date formatting).
// Message catalogs are loaded lazily from ./locales/*.json via the Nuxt i18n module.
export default defineI18nConfig(() => ({
  legacy: false,
  fallbackLocale: 'en',
  numberFormats: {
    'de': {
      decimal: { style: 'decimal', maximumFractionDigits: 2 },
      integer: { style: 'decimal', maximumFractionDigits: 0 },
    },
    'en': {
      decimal: { style: 'decimal', maximumFractionDigits: 2 },
      integer: { style: 'decimal', maximumFractionDigits: 0 },
    },
    'fr': {
      decimal: { style: 'decimal', maximumFractionDigits: 2 },
      integer: { style: 'decimal', maximumFractionDigits: 0 },
    },
    'es': {
      decimal: { style: 'decimal', maximumFractionDigits: 2 },
      integer: { style: 'decimal', maximumFractionDigits: 0 },
    },
    'it': {
      decimal: { style: 'decimal', maximumFractionDigits: 2 },
      integer: { style: 'decimal', maximumFractionDigits: 0 },
    },
    'pl': {
      decimal: { style: 'decimal', maximumFractionDigits: 2 },
      integer: { style: 'decimal', maximumFractionDigits: 0 },
    },
    'nl': {
      decimal: { style: 'decimal', maximumFractionDigits: 2 },
      integer: { style: 'decimal', maximumFractionDigits: 0 },
    },
    'cs': {
      decimal: { style: 'decimal', maximumFractionDigits: 2 },
      integer: { style: 'decimal', maximumFractionDigits: 0 },
    },
    'da': {
      decimal: { style: 'decimal', maximumFractionDigits: 2 },
      integer: { style: 'decimal', maximumFractionDigits: 0 },
    },
    'lb': {
      decimal: { style: 'decimal', maximumFractionDigits: 2 },
      integer: { style: 'decimal', maximumFractionDigits: 0 },
    },
    'de-hh': {
      decimal: { style: 'decimal', maximumFractionDigits: 2 },
      integer: { style: 'decimal', maximumFractionDigits: 0 },
    },
  },
  datetimeFormats: {
    'de': {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' },
    },
    'en': {
      short: { year: 'numeric', month: 'short', day: 'numeric' },
      long: { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' },
    },
    'fr': {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' },
    },
    'es': {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' },
    },
    'it': {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' },
    },
    'pl': {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' },
    },
    'nl': {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' },
    },
    'cs': {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' },
    },
    'da': {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' },
    },
    'lb': {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' },
    },
    'de-hh': {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' },
    },
  },
}))

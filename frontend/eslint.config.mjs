import antfu from '@antfu/eslint-config'
import vueI18n from '@intlify/eslint-plugin-vue-i18n'
import oxlint from 'eslint-plugin-oxlint'

export default antfu({
  vue: true,
  typescript: true,
}, oxlint.configs['flat/recommended'], ...vueI18n.configs.recommended, {
  settings: {
    'vue-i18n': {
      localeDir: './i18n/locales/*.json',
      messageSyntaxVersion: '^11.0.0',
    },
  },
  rules: {
    // Catch typos / missing keys across the locale catalogs.
    '@intlify/vue-i18n/no-missing-keys': 'error',
    // Off: many keys are referenced dynamically (t('units.' + u), endpoint.descKey, glossary
    // entries) which the static analyzer cannot see, so this only produces false positives.
    // DE<->EN parity is covered by a dedicated unit test instead.
    '@intlify/vue-i18n/no-unused-keys': 'off',
    // Off: many keys deliberately mirror backend snake_case identifiers (units, parameters).
    '@intlify/vue-i18n/key-format-style': 'off',
    // Raw text detection is too noisy for this UI (brand names, symbols, units); keep it off.
    '@intlify/vue-i18n/no-raw-text': 'off',
  },
})

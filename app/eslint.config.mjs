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
    // Off: @antfu/eslint-config 10 turns it on and it reports 10,079 times in 464 files (one-line ternaries,
    // objects and arrays that it wants one item to a line). Its fix is no pure line-break change: the lines it
    // makes long set off other fixers, which add braces to `if` bodies and make a top-level `const f = () =>`
    // a `function f()` (`antfu/top-level-function`). That is a rewrite of the code of the whole app, 47,000
    // lines, with a diff no review can follow, so it is a decision for a change of its own.
    'antfu/reasonable-newline': 'off',
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

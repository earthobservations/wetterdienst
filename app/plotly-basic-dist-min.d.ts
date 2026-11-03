declare module 'plotly.js-basic-dist-min' {
  export * from 'plotly.js'
}

// Plotly's own translations of the modebar and the hover texts, one module per language (CommonJS)
declare module 'plotly.js-locales/*' {
  const locale: { name: string, dictionary: Record<string, string> }
  export default locale
}

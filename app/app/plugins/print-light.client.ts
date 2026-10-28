// Paper is white: a page in dark mode prints in the light colours, and is dark again after the print (GH-3518).
export default defineNuxtPlugin(() => {
  let wasDark = false
  window.addEventListener('beforeprint', () => {
    const root = document.documentElement
    wasDark = root.classList.contains('dark')
    root.classList.remove('dark')
  })
  window.addEventListener('afterprint', () => {
    if (wasDark)
      document.documentElement.classList.add('dark')
    wasDark = false
  })
})

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// The widget is a page of its own, outside the shell of app.vue whose main element holds every other page, so it brings its
// own main landmark (a document with none fails Lighthouse's `landmark-one-main`, found in the run of 2026-11-10)
const widget = readFileSync(fileURLToPath(new URL('../../app/pages/widget.vue', import.meta.url)), 'utf-8')

describe('the widget page', () => {
  it('has one main landmark, around its content and not its bar or its footer', () => {
    expect(widget.match(/<main[\s>]/g)).toHaveLength(1)
    expect(widget.match(/<\/main>/g)).toHaveLength(1)
    const main = widget.slice(widget.indexOf('<main'), widget.indexOf('</main>'))
    expect(main).toContain('widget.noStation')
    expect(main).toContain('<Meteogram')
    expect(main).not.toContain('widget.poweredBy')
  })
})

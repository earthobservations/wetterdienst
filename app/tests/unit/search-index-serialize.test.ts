import vm from 'node:vm'
import { describe, expect, it } from 'vitest'
import { toJsLiteral, toJsonParseExpression } from '../../modules/search-index/serialize'

// The search index's virtual modules are written from data (GH-4340): whatever a catalog or a text holds must come back
// as the same data when the module is evaluated, and must not be able to end a string literal or a script element.
const HOSTILE = [
  '</script><script>globalThis.pwned = 1</script>',
  '<!-- <script>',
  'line\u2028separator\u2029paragraph',
  // eslint-disable-next-line no-template-curly-in-string
  '`${globalThis.pwned = 1}`',
  '"; globalThis.pwned = 1; "',
  '\'; globalThis.pwned = 1; \'',
  '\\"; globalThis.pwned = 1; //',
  'back\\slash \\u003c \\n',
  'new\nline\r\ttab\0nul',
  'a & b > c < d / e',
  '😀 emoji and ünïcödé',
]

function evaluate(expression: string): { value: unknown, pwned: unknown } {
  const sandbox: { pwned?: unknown } = {}
  const value = vm.runInNewContext(`(${expression})`, sandbox)
  return { value, pwned: sandbox.pwned }
}

const DATA = {
  index: HOSTILE.map((text, id) => ({ id, text, nested: { [text]: [text, 1, null, true] } })),
  labels: Object.fromEntries(HOSTILE.map(text => [text, text])),
}

describe('search index serialization', () => {
  for (const [name, serialize] of [['literal', toJsLiteral], ['JSON.parse expression', toJsonParseExpression]] as const) {
    describe(name, () => {
      it('evaluates back to the same data', () => {
        const { value, pwned } = evaluate(serialize(DATA))
        expect(value).toEqual(DATA)
        expect(pwned).toBeUndefined()
      })

      it('holds each hostile string as it was', () => {
        for (const text of HOSTILE) {
          const { value, pwned } = evaluate(serialize(text))
          expect(value).toBe(text)
          expect(pwned).toBeUndefined()
        }
      })

      it('writes none of the characters that a script element or an old literal misreads', () => {
        const text = serialize(DATA)
        expect(text).not.toMatch(/[<>&\u2028\u2029]/)
        expect(text).not.toContain('</script')
        // the text of a module is one line: no raw line break from the data
        expect(text).not.toMatch(/[\n\r]/)
      })
    })
  }

  it('is a module that exports the data, as the plugin writes it', () => {
    const source = `export default ${toJsonParseExpression(DATA.index)}\nexport const labels = ${toJsonParseExpression(DATA.labels)}\n`
    const exported: { default?: unknown, labels?: unknown } = {}
    vm.runInNewContext(
      source.replace('export default ', 'out.default = ').replace('export const labels = ', 'out.labels = '),
      { out: exported },
    )
    expect(exported.default).toEqual(DATA.index)
    expect(exported.labels).toEqual(DATA.labels)
  })
})

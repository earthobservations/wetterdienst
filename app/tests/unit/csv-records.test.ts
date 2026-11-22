import type { CsvField } from '../../server/utils/csvRecords'
import { describe, expect, it } from 'vitest'
import { CsvFormatError, CsvRecordReader } from '../../server/utils/csvRecords'

// The reader of the CSV that the app's server reads the stations of NOAA GHCN daily with (GH-4299): RFC 4180, from the bytes
// of a body as they arrive, in whatever pieces they come.

const encode = (text: string) => new TextEncoder().encode(text)

/** Reads `text` in the pieces `sizes` cuts it into (the last size repeats) and returns the records, or the error of the end */
function read(text: string, sizes: number[] = [Number.MAX_SAFE_INTEGER], wanted: (column: number) => boolean = () => true): Array<Array<CsvField | undefined>> {
  const records: Array<Array<CsvField | undefined>> = []
  const reader = new CsvRecordReader(wanted, fields => records.push([...fields]))
  const bytes = encode(text)
  let at = 0
  for (let index = 0; at < bytes.length; index++) {
    const size = sizes[Math.min(index, sizes.length - 1)]!
    reader.push(bytes.slice(at, at + size))
    at += size
  }
  reader.end()
  return records
}

describe('the reader of CSV', () => {
  it('reads records of plain fields, and an empty one that is not quoted as null', () => {
    expect(read('a,b,c\n1,,3\n,,\n')).toEqual([['a', 'b', 'c'], ['1', null, '3'], [null, null, null]])
  })

  it('reads a quoted field with its commas, its line ends and its quotes (two for one) as its text, and `""` as the empty text', () => {
    expect(read('id,name\n1,"A, B"\n2,"say ""hi"""\n3,"line\none\r\ntwo"\n4,""\n5,""""\n')).toEqual([
      ['id', 'name'],
      ['1', 'A, B'],
      ['2', 'say "hi"'],
      ['3', 'line\none\r\ntwo'],
      ['4', ''],
      ['5', '"'],
    ])
  })

  it('ends a record with LF, CRLF or CR, takes a line with nothing on it for none, and a text that ends without a record\'s line end for cut short', () => {
    expect(read('a,b\r\n1,2\r\n\r\n3,4\n\n5,6\r7,8\n')).toEqual([['a', 'b'], ['1', '2'], ['3', '4'], ['5', '6'], ['7', '8']])
    expect(() => read('a,b\n1,2')).toThrow(CsvFormatError)
    expect(() => read('a,b\n1,')).toThrow(/line end/)
    expect(() => read('a,b\n1,"2"')).toThrow(/line end/)
  })

  it('takes the LF after a CR and a comma for a line end of its own, not the second half of a CRLF', () => {
    expect(read('h1,h2\r,\nx,y\n')).toEqual([['h1', 'h2'], [null, null], ['x', 'y']])
  })

  it('throws for a quoted field that is never closed, which a cut body is', () => {
    expect(() => read('a,b\n1,"2\n3,4\n')).toThrow(/never closed/)
  })

  it('reads the same records however the bytes are cut into pieces, a character of several bytes and a pair of quotes included', () => {
    const text = 'id,name,n\n1,"SAINT-ÉTIENNE, ""LE HAUT""",ü\n2,МОСКВА ВДНХ,€\r\n3,"a\r\nb",\n4,"",""\n5,x"y,z\n'
    const whole = read(text)
    expect(whole).toEqual([
      ['id', 'name', 'n'],
      ['1', 'SAINT-ÉTIENNE, "LE HAUT"', 'ü'],
      ['2', 'МОСКВА ВДНХ', '€'],
      ['3', 'a\r\nb', null],
      ['4', '', ''],
      ['5', 'x"y', 'z'],
    ])
    for (const size of [1, 2, 3, 5, 8, 13])
      expect(read(text, [size])).toEqual(whole)
    // and cut at every one place
    const length = encode(text).length
    for (let cut = 1; cut < length; cut++)
      expect(read(text, [cut, length])).toEqual(whole)
  })

  it('does not decode the fields that are not wanted, and tells them from the others by `undefined`', () => {
    expect(read('a,b,c\n1,"2,2",3\n', [4], column => column !== 1)).toEqual([['a', undefined, 'c'], ['1', undefined, '3']])
  })

  it('reads a record of one empty quoted field as a record, and a record of one empty unquoted field as no line', () => {
    expect(read('""\n')).toEqual([['']])
    expect(read('\n')).toEqual([])
  })
})

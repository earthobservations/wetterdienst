import { Buffer } from 'node:buffer'

// A reader of CSV (RFC 4180) that is given the bytes of an answer as they arrive and hands over a record at a time, with the
// text of only the fields that are asked for. It exists for the list of the stations of NOAA GHCN daily (133k rows, 16 MB of
// CSV): reading that as one string and one object for each row costs several times its size at the peak, and a string that is
// cut out of a bigger one keeps all of the bigger one alive, so the fields are decoded from the bytes into strings of their own.
//
// It reads bytes, not text: the separators (`,` `"` and the line ends) are ASCII, which no byte of a multi-byte UTF-8 character
// is, so a character that is cut by the end of a chunk is never mistaken for one and is decoded once its field is whole.

const QUOTE = 0x22
const COMMA = 0x2C
const LF = 0x0A
const CR = 0x0D
const QUOTE_BYTES = Buffer.from('"')

/** One field of a record: its text, or null for an empty one that is not quoted (`""` is the empty text, `,,` is no value) */
export type CsvField = string | null

/** A malformed CSV: a quote that is never closed, or one that does not end its record with a line end (a cut one) */
export class CsvFormatError extends Error {}

/**
 * Reads CSV from chunks of bytes. `push` the chunks as they come and call `end` once, which says whether the text was whole.
 * Every record, the header too, is given to `onRecord` as an array with one entry for each field: the text of the fields that
 * `wanted` says yes to, and `undefined` for the others (which are not decoded). The array is reused for the next record: a
 * callback keeps what it reads from it and not it.
 *
 * Both `\n` and `\r\n` end a record, and a line with nothing on it is no record. A record has to be ended by its line end: a text
 * that stops in the middle of one is cut short, whatever it is cut at, and `end` throws for it.
 */
export class CsvRecordReader {
  private readonly fields: Array<CsvField | undefined> = []
  /** The pieces of the field in hand that were cut off by the end of a chunk or by an escaped quote */
  private parts: Buffer[] = []
  private inQuotes = false
  /** A quote was met inside a quoted field: the next byte says if it ends the field or is the second of an escaped quote */
  private afterQuote = false
  private quoted = false
  /** Whether a byte of the field in hand has been read, so that the opening quote is told from one in the middle of a field */
  private fieldHasBytes = false
  private afterCarriageReturn = false

  /**
   * @param wanted - Whether the text of the field of each column is wanted, by its index; a column past its end is not
   * @param onRecord - Given each record
   */
  constructor(private readonly wanted: (column: number) => boolean, private readonly onRecord: (fields: Array<CsvField | undefined>) => void) {}

  /** Reads the next chunk of the text */
  push(bytes: Uint8Array): void {
    const chunk = Buffer.from(bytes.buffer, bytes.byteOffset, bytes.byteLength)
    const end = chunk.length
    // where the text of the field in hand begins in this chunk
    let start = 0
    for (let at = 0; at < end; at++) {
      const byte = chunk[at]!
      if (this.afterQuote) {
        this.afterQuote = false
        if (byte === QUOTE) {
          // two quotes in a quoted field are one quote of its text
          if (this.wanted(this.fields.length))
            this.parts.push(QUOTE_BYTES)
          start = at + 1
          continue
        }
        this.inQuotes = false
      }
      if (this.inQuotes) {
        if (byte === QUOTE) {
          this.keepPart(chunk, start, at)
          this.afterQuote = true
          start = at + 1
        }
        continue
      }
      if (byte === COMMA) {
        // a comma ends a line end that began with a CR: an LF after it is a line end of its own
        this.afterCarriageReturn = false
        this.endField(chunk, start, at)
        start = at + 1
      }
      else if (byte === LF || byte === CR) {
        const second = byte === LF && this.afterCarriageReturn
        this.afterCarriageReturn = byte === CR
        if (!second)
          this.endRecord(chunk, start, at)
        start = at + 1
      }
      else {
        this.afterCarriageReturn = false
        if (byte === QUOTE && !this.fieldHasBytes) {
          this.inQuotes = true
          this.quoted = true
          start = at + 1
        }
        this.fieldHasBytes = true
      }
    }
    // what is left of the field goes on in the next chunk
    this.keepPart(chunk, start, end)
  }

  /** Says that there is no more: throws if a quote was never closed or the last record was not ended by its line end */
  end(): void {
    if (this.inQuotes && !this.afterQuote)
      throw new CsvFormatError('a quoted field is never closed')
    if (this.fieldHasBytes || this.fields.length > 0)
      throw new CsvFormatError('the last record is not ended by a line end')
  }

  /** Keeps `chunk[start, end)`, copied, since the chunk's memory is not the field's to hold on to */
  private keepPart(chunk: Buffer, start: number, end: number): void {
    if (end > start && this.wanted(this.fields.length))
      this.parts.push(Buffer.from(chunk.subarray(start, end)))
  }

  private endField(chunk: Buffer, start: number, end: number): void {
    if (!this.wanted(this.fields.length)) {
      this.fields.push(undefined)
    }
    else {
      // the pieces are the field in order, and the last of it is what is in this chunk
      let text: string
      if (this.parts.length === 0) {
        text = chunk.toString('utf8', start, end)
      }
      else {
        if (end > start)
          this.parts.push(chunk.subarray(start, end))
        text = Buffer.concat(this.parts).toString('utf8')
      }
      this.fields.push(text === '' && !this.quoted ? null : text)
    }
    this.parts = []
    this.quoted = false
    this.inQuotes = false
    this.afterQuote = false
    this.fieldHasBytes = false
  }

  private endRecord(chunk: Buffer, start: number, end: number): void {
    // a line with nothing on it
    if (this.fields.length === 0 && !this.fieldHasBytes)
      return
    this.endField(chunk, start, end)
    this.onRecord(this.fields)
    this.fields.length = 0
  }
}

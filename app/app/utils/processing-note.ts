/**
 * What wetterdienst did to the data, said where the app shows the provider's credit line (GH-3799). The backend's answer
 * carries the same in `metadata.processing_note`, in English only: the app writes it in the language of the page
 * (`processingNote.*`), and `tests/unit/processing-note.test.ts` holds the English text to the backend's. The note is plain
 * information, not a claim of what a licence asks for.
 */

type Translate = (key: string) => string

/**
 * The note: the sentence every answer with provider data has and, for values that were selected or calculated from the
 * readings (an interpolation, a summary), the sentence that says so. What the climate stripes say of their reference and of
 * the image is the page's own text, and is not repeated here.
 *
 * @param t - Translates a catalog key into the language of the page
 * @param derived - Whether the values were selected or calculated from the provider's readings
 * @param radar - Whether it is a frame of the precipitation radar, which says what was done to the composite besides
 */
export function processingNote(t: Translate, derived = false, radar = false): string {
  const parts = [t('processingNote.base')]
  if (derived)
    parts.push(t('processingNote.estimate'))
  // what the Radar tool says of its frames (GH-3788): the sums became classes of a rate, and the grid was warped
  if (radar)
    parts.push(t('processingNote.radar'))
  return parts.join(' ')
}

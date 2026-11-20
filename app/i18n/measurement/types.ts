import type { TopicId } from '../../app/utils/measurement'

/** A work the entry rests on: what it is in plain words, then the formal citation (the title stays in its own language) */
export interface MeasurementSource {
  /** What the work is, who issues it, and what the entry takes from it, in words anyone can follow */
  plain: string
  /** The formal citation: issuer, year, title, volume and chapter or section */
  citation: string
  /** Where the work is found, the page of the issuer */
  href: string
}

/** One part of an entry: a heading and the paragraphs under it */
export interface MeasurementPart {
  title: string
  paragraphs: string[]
}

/** One entry of the page "How weather is measured" (GH-3787) */
export interface MeasurementEntry {
  title: string
  /** One sentence under the title that says what the entry is about */
  summary: string
  /** The parts, in the order of the page: how it is measured, how a reading becomes a value, what the number can and cannot tell, where providers differ */
  parts: MeasurementPart[]
  /** The works the entry rests on, the main one first */
  sources: MeasurementSource[]
}

/** The texts of the page in one language: an entry for each id of `TOPICS` (`app/utils/measurement.ts`) */
export type MeasurementTexts = Record<TopicId, MeasurementEntry>

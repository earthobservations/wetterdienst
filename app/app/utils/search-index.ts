// The full-text index of the app's own pages (GH-3790): built from the documents of a language when the app is built
// (`modules/search-index.ts`), and for the glossary in the browser, from what the glossary page loads; searched in the
// browser. A small inverted index, with no library: the terms of every document, folded (`fold`: lower case, no accents),
// with the documents each is in and whether it stands in a title or in the text.
//
// A query word matches a term that contains it (so `taupunkt` finds `Taupunkttemperatur`, as German compounds need), a
// term that starts with it better, and a term in a title better than one in the text; every word of the query has to be
// in the document. Nothing here knows Nuxt or the DOM, so that a test can hold it.
//
// Imports only `fold` of `palette.ts`, which imports nothing, so that the Nuxt module can load it by itself.

import { fold } from './palette'

/** What a document is, as the search shows it and leads to it */
export interface SearchDoc {
  /** What the document is, which decides the group it is shown in (`measurement`, `method`, `settings`, ...) */
  kind: string
  /** The name it is shown by: indexed as a title */
  title: string
  /** A line before the summary that says where in the page it is (the name of the part); indexed as a title, shown as small print */
  context?: string
  /** A sentence under the title: indexed with the text, and shown */
  summary?: string
  /** What is only searched, and neither shown nor kept in the index */
  text?: string
  /** More words it is found by, which are not shown (the English words of a translated title) */
  keywords?: string
  /** The page, and the anchor where there is one (`/measurement#wind`) */
  to: string
}

/** A document as the index keeps it: no text, only what is shown */
export type StoredDoc = [kind: string, title: string, context: string, summary: string, to: string]

/**
 * The index: the documents, the terms (folded, sorted) and for each term the documents it is in. A posting is the
 * number of a document times two, plus one where the term is in the document's title; sorted, and stored as the gap to
 * the one before, which is smaller and compresses better.
 */
export interface SearchIndex {
  docs: StoredDoc[]
  terms: string[]
  postings: number[][]
}

/** One document found, with how well it answers */
export interface Hit {
  kind: string
  title: string
  context: string
  summary: string
  to: string
  score: number
}

/** The words of a text, folded; words of one letter are left out (a number of one digit is kept) */
export function tokenize(text: string): string[] {
  return fold(text).split(/[^\p{L}\p{N}]+/u).filter(word => word.length > 1 || /\d/.test(word))
}

/**
 * Whether a text answers a query as the search does: every word of the query is in a term that holds it, in any order, folded.
 * The same rule as `searchIndex`, for a list that filters by itself (the glossary page's field), so that the page and the
 * search's "5 more in Glossary" show the same entries. A query with no word of its own (one letter) answers everything.
 */
export function matchesQuery(query: string, texts: ReadonlyArray<string | null | undefined>): boolean {
  const words = [...new Set(tokenize(query))]
  if (!words.length)
    return true
  const terms = tokenize(texts.map(plain).join(' '))
  return words.every(word => terms.some(term => term.includes(word)))
}

/** `{name}` of the texts that are filled in with numbers, which are no words */
function plain(text: string | null | undefined): string {
  return (text ?? '').replace(/\{\w+\}/g, ' ')
}

/** A sentence under a title: the start of the text, at a word, with an ellipsis where it was cut */
export function excerpt(text: string, length = 120): string {
  const flat = text.replace(/\s+/g, ' ').trim()
  if (flat.length <= length)
    return flat
  const cut = flat.slice(0, length)
  return `${cut.slice(0, Math.max(cut.lastIndexOf(' '), length / 2)).replace(/[\s,;:.]+$/, '')}…`
}

/**
 * The index of a list of documents. Deterministic: the same documents give the same index, byte for byte, so that a build
 * is reproducible.
 */
export function buildIndex(documents: readonly SearchDoc[]): SearchIndex {
  const found = new Map<string, Map<number, 0 | 1>>()
  const note = (term: string, doc: number, title: 0 | 1) => {
    let docs = found.get(term)
    if (!docs)
      found.set(term, docs = new Map())
    // a term in the title and in the text is in the title
    docs.set(doc, Math.max(docs.get(doc) ?? 0, title) as 0 | 1)
  }
  documents.forEach((doc, index) => {
    for (const term of tokenize(`${plain(doc.title)} ${plain(doc.context)}`))
      note(term, index, 1)
    for (const term of tokenize(`${plain(doc.summary)} ${plain(doc.text)} ${plain(doc.keywords)}`))
      note(term, index, 0)
  })
  const terms = [...found.keys()].sort()
  const postings = terms.map((term) => {
    const docs = [...found.get(term)!].map(([doc, title]) => doc * 2 + title).sort((a, b) => a - b)
    return docs.map((value, at) => at === 0 ? value : value - docs[at - 1]!)
  })
  return {
    docs: documents.map(doc => [doc.kind, doc.title, doc.context ?? '', doc.summary ?? '', doc.to]),
    terms,
    postings,
  }
}

/** The documents of a posting list, as numbers with their title flag, the gaps added up */
function postingsOf(list: readonly number[]): number[] {
  let sum = 0
  return list.map(gap => (sum += gap))
}

/** How well a term answers a word: a term that is the word, one that starts with it, one that holds it, in a title or in the text */
function weigh(term: string, word: string, inTitle: boolean): number {
  const position = term === word ? 3 : term.startsWith(word) ? 2 : 1
  return inTitle ? 4 + position * 2 : position
}

/**
 * The documents that answer a query, best first; none for a query with no word of two letters (or a digit). Every word
 * has to be in the document, in a term that holds it. A document is scored by the best term for each word, a title's
 * above the text's, summed over the words; documents that score alike keep the order they were built in.
 */
export function searchIndex(index: SearchIndex, query: string): Hit[] {
  const words = [...new Set(tokenize(query))]
  if (!words.length)
    return []
  let scores: Map<number, number> | null = null
  for (const word of words) {
    const best = new Map<number, number>()
    index.terms.forEach((term, at) => {
      if (!term.includes(word))
        return
      for (const posting of postingsOf(index.postings[at]!)) {
        const doc = posting >> 1
        const weight = weigh(term, word, (posting & 1) === 1)
        if (weight > (best.get(doc) ?? 0))
          best.set(doc, weight)
      }
    })
    if (scores === null) {
      scores = best
    }
    else {
      const both = new Map<number, number>()
      for (const [doc, score] of scores) {
        const other = best.get(doc)
        if (other !== undefined)
          both.set(doc, score + other)
      }
      scores = both
    }
    if (!scores.size)
      return []
  }
  return [...(scores ?? [])]
    .sort((a, b) => b[1] - a[1] || a[0] - b[0])
    .map(([doc, score]) => {
      const [kind, title, context, summary, to] = index.docs[doc]!
      return { kind, title, context, summary, to, score }
    })
}

/**
 * The best hit for each target, in the order of the hits: a page of long entries is several documents (its parts) that
 * lead to the same anchor, and the search shows the entry once, with the part that answers best.
 */
export function bestPerTarget(hits: readonly Hit[]): Hit[] {
  const seen = new Set<string>()
  return hits.filter((hit) => {
    if (seen.has(hit.to))
      return false
    seen.add(hit.to)
    return true
  })
}

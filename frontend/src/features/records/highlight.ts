// Citation highlights travel as before/match/after strings, never offsets (spec §7, VCAC-D-013).
// We highlight `match` only when before + match + after appears verbatim in the transcript; otherwise none.

export type Quote = { before: string; match: string; after: string }

export function findHighlight(transcript: string | null | undefined, q: Quote | null | undefined): { start: number; end: number } | null {
  if (!transcript || !q || !q.match) return null
  const at = transcript.indexOf(q.before + q.match + q.after)
  if (at < 0) return null
  const start = at + q.before.length
  return { start, end: start + q.match.length }
}

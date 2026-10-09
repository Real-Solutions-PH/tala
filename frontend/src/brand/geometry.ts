// The Kapiling mark on a 24×24 grid, no strokes, so it stays crisp at 16px (spec §9).
// A large circle (the person) and a smaller one leaning in from the upper right (the companion).
// Where they overlap is the gold lens: the shared memory. The shapes' bounding box is centred on (12, 12).
// Used by Mark.tsx and scripts/icons.ts (which writes mark.svg and the app icons).
export const VIEWBOX = '0 0 24 24'
export const PERSON = { cx: 9, cy: 12.5, r: 8.5 }
export const COMPANION = { cx: 18, cy: 8.5, r: 5.5 }
/** Intersection of the two circles: down the person's right edge, then back up the companion's left edge. */
export const LENS = 'M13.524 5.304A8.5 8.5 0 0 1 17.373 13.964A5.5 5.5 0 0 1 13.524 5.304Z'
/** Usap eyes: two calm dots in the large circle, no mouth. */
export const EYES = [{ cx: 6.2, cy: 11.6, r: 1.05 }, { cx: 10.6, cy: 11.6, r: 1.05 }]

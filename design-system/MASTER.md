# Kapiling: design system MASTER (UI/UX Pro Max)

Global source of truth for UI/UX Pro Max. Page files in `pages/` override this file for their page. The full rule set lives in `../DESIGN.md`; tokens in `../frontend/src/design/tokens.css` (the only place raw colours live).

## Product
Health record you talk to, on the owner's phone. Users: Filipino seniors 60+ (Lola, Lolo), their representative, nurses reading the emergency card. Tagalog first, polite (*po*).

## Style
After one reference (a blue health app shot): pale-blue ground, white borderless cards, one vivid-blue panel per screen, round icon buttons, light SF Pro type with one bold title word. Not neumorphism, not glass, no gradients except the soft background light and the lab card's white-to-blue fade.

## Colour (light only)
| Role | Token | Value |
|---|---|---|
| Brand blue (text, fills, current tab, chart bars) | `--primary` / `--primary-fill` | `#0F62E6` |
| Results panel ground | `--primary-strong` | `#0F4EB6` |
| Ground / cards | `--bg` / `--surface` | `#E9F1FC` / `#FFFFFF` |
| Ink / muted | `--ink` / `--muted` | `#000000` / `#475467` |
| Soft blue tint | `--primary-soft` | `#E0ECFE` |
| Emergency | `--danger-fill` | `#B42318` |
| Taken / high | `--accent` / `--warn` | `#137336` / `#A34B07` |
Every text pair ≥ 4.5:1, checked by `bun scripts/contrast.ts` on every test run.

## Type
SF Pro (system) everywhere, Figtree fallback on Android. 400 text, 500 values and buttons, 600 the bold title word. Display 44px, card value 28px, section 22px, body 18px, floor 15px. Lucide icons at 1.75 stroke.

## Shape, depth, motion
Cards 32px radius, panel tiles 22px, pills for buttons and chips, circles for icons. One shadow: hairline edge + soft blue-tinted shadow. 200ms ease-out; press scale 0.95–0.97; 40ms staggered rise-in; all off under reduced motion.

## Shell
Header: 56px avatar on a blue ring (profile sheet), light Settings circle, red Emergency circle. Bottom: four floating round tabs, current one a 72px blue circle. Header and tab words are screen-reader labels (deliberate trade, `nav-label-icon` noted).

## Rules UI/UX Pro Max must keep
- Touch targets ≥ 48px, main actions 64px, 8px apart.
- Colour + icon + word for allergies, emergency, high results, taken doses.
- One primary CTA per screen; filters are one dropdown, never a row of many chips.
- Safety text (disclaimer, refusals, emergency labels) is fixed catalogue copy.
- No new raw colours outside `tokens.css`; never `color: var(--gold)`.

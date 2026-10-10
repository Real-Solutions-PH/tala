# Frontend

React 19, TypeScript and Vite. `bun run build` writes the app to `../backend/static`, which FastAPI serves. In development, `bun run dev` proxies `/api` to http://127.0.0.1:8787.

## Scripts

| Command | What it does |
|---|---|
| `bun run dev` | Vite dev server |
| `bun run build` | Typecheck, then build to `../backend/static` |
| `bun run test --run` | Colour-contrast check (`scripts/contrast.ts`), then vitest |
| `bun run typecheck` | `tsc -b --noEmit` |
| `bun run lint` | oxlint |
| `bun scripts/icons.ts` | Regenerate the app icons |

## Layout

| Path | Contents |
|---|---|
| `src/routes.tsx`, `src/App.tsx` | Router, locked shell, top bar and bottom menu |
| `src/features/` | Screens by area: `lock`, `emergency`, `cards`, `meds`, `records`, `settings` |
| `src/pages/placeholders.tsx` | The Chat tab placeholder (the chat screen is not merged yet) |
| `src/api/` | API client, TanStack Query hooks, AG-UI stream client and reducer |
| `src/components/` | Shared components: Button, Card, Badge, Chip, Sheet, Toast, Skeleton, EmptyState, ErrorState, Disclaimer |
| `src/brand/`, `src/design/` | Brand mark geometry, `tokens.css`, `base.css` |
| `src/i18n/` | English and Tagalog catalogues |
| `public/` | Self-hosted fonts, icons, web app manifest |

## i18n rule

All UI text lives in `src/i18n/en.ts` and `src/i18n/tl.ts` with identical keys. TypeScript and a test fail when a key is missing from either file. Add new strings to both files in the same commit. Fixed safety text (disclaimer, refusals, emergency labels) comes from these catalogues, never from the model.

## Design tokens

`src/design/tokens.css` holds every colour, size and motion value; components use tokens only. The tokens implement [../DESIGN.md](../DESIGN.md), and `scripts/contrast.ts` fails the test run on low contrast, on `color: var(--gold)` (gold is a fill, never text) and on raw colours outside `tokens.css`. Key rules: 18 px body text, 48 px minimum touch targets, light by default with dark following the system, fonts self-hosted so the app works offline.

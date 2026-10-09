# Kapiling design system

The tokens in `frontend/src/design/tokens.css` implement this document. Change both together.
`frontend/scripts/contrast.ts` re-checks every text pair on each `bun run test`.

## Who we design for

**Lola and Lolo, 60 and over**, are the main users. They carry a folder of lab results to every check-up, are
asked the same questions at every visit (allergies, maintenance medicines, PhilHealth number), and their
reading glasses are often somewhere else. They use a mid-range Android phone, Facebook and Messenger, and
speak Tagalog with the English health words everyone uses (BP, blood sugar, maintenance, PhilHealth).

Around them: **a representative** (an adult child or a caregiver) who answers for Lola at the hospital,
**a parent** starting a child's record at birth, and **the nurse or responder** who reads the emergency
card without unlocking the phone.

What earns their trust:

- **It keeps them company, it doesn't examine them.** Warm paper, a calm blue, one sun-gold accent. Not a hospital system.
- **Every button says what it does,** in their language.
- **Nothing surprises them.** No hidden gestures, nothing floating over the content, no tiny text.
- **It respects them.** Kapiling says *po* and *opo*. It never talks down and never plays doctor.

## Brand

> **Kapiling: Laging kapiling ang kalusugan mo.**
> *(Your health, always by your side.)*

*Kapiling* (ka-PI-ling) means "by your side" or "keeping someone company". The idea is a companion that
remembers for you, so you never have to recite your history from memory or carry a folder of papers.

| Element | Decision |
|---|---|
| Mark | Two circles: a large one (the person) and a smaller one leaning in from the upper right (the companion). Their overlap is a small Araw Gold lens, the shared memory. Flat, two colours, no strokes, on a 24×24 grid (`frontend/src/brand/geometry.ts`), legible at 16 px. |
| Usap | In talk mode the large circle becomes the character: two calm eye dots, no mouth. States are a small scale or opacity change (listening, thinking, speaking) and stop under reduced motion. |
| App icon | White mark with the gold lens on a Kapiling Blue square. 180 (apple-touch, full bleed), 192 and 512 (rounded), a maskable 512 with 20% padding, and `favicon.svg`. Regenerate with `bun scripts/icons.ts`. |
| Voice | Warm, plain, respectful. "Heto po ang PhilHealth card ninyo." It speaks as a helper, never as a doctor. It says *litrato*, *record*, *itago*, never "AI", "data" or "upload". |

| We are | We are not |
|---|---|
| A companion that keeps your records and hands them over when asked | Clinical, scary, cute or "techy" |
| On your own phone, working without internet | A cloud service, a subscription |
| Plain shapes in blue and gold | Stethoscopes, hearts with a pulse line, robots, gradients, purple |

Technical claims belong only on the laptop's demo panel and in the README.

## Principles

1. **Big and plain.** Body text is 18 px, nothing below 15 px, line height 1.55. Targets are at least 48 px, 64 px for main actions, with 8 px between them. A text-size setting scales everything (100 / 125 / 150%).
2. **Two taps to anything the hospital asks for.** PhilHealth or HMO card, medicine list, allergies, blood type, latest labs, emergency contact: at most two taps or one spoken sentence.
3. **Label everything.** Every icon sits next to a word. An icon alone is never the only cue.
4. **One plane.** Header, content, bottom menu, stacked. Nothing floats over content except a toast, and the toast sits above the menu, never on it.
5. **Colour plus icon plus word.** Allergies, emergency, high results and refills always carry an icon and a word as well as colour.
6. **Tagalog first, polite.** Tagalog is the default language. Labels use everyday Tagalog with the English health words people already use, and *po*.
7. **Gold is never text.** Araw Gold is a fill (the mark, the "today" highlight, a selected chip) and always carries dark ink text. The contrast script fails the build if any rule sets `color: var(--gold)`.
8. **Show state, don't perform it.** Motion is 150 to 250 ms, ease-out, only for cause and effect. `prefers-reduced-motion` turns it off.

## Colour

Light by default; dark follows the system. Ratios are WCAG contrast on `--bg` / `--surface`, as printed by `contrast.ts`.

| Token | Light | Dark | Contrast light · dark | Use |
|---|---|---|---|---|
| `--bg` (Papel) | `#FBF8F3` | `#14120F` | | Warm paper ground, cuts glare |
| `--surface` | `#FFFFFF` | `#1F1C18` | | Cards, header, menu, sheets |
| `--surface-2` | `#F3EEE6` | `#2A2621` | | Inputs, pressed state, skeleton |
| `--border` | `#D6CFC4` | `#3D3832` | | Edges (not text) |
| `--ink` | `#1C1917` | `#F5F1EA` | 16.5 / 17.5 · 16.6 / 15.1 | Main text |
| `--muted` | `#57534E` | `#B8B0A4` | 7.2 / 7.6 · 8.7 / 7.9 | Secondary text. Nothing lighter carries text |
| `--primary` (Kapiling Blue) | `#1F4E8C` | `#8CB4F0` | 7.9 / 8.3 · 8.8 / 8.0 | Buttons, links, selected tab, the mark |
| `--on-primary` | `#FFFFFF` | `#14120F` | 8.3 · 8.8 on primary | Text on primary |
| `--gold` (Araw Gold) | `#F2A900` | `#F2A900` | **never text** (2.0:1 on white) | Fills: mark lens, today, selected chip |
| `--on-gold` | `#1C1917` | `#1C1917` | 8.7 on gold | Text on gold, both themes |
| `--accent` | `#15803D` | `#4ADE80` | 4.7 / 5.0 · 10.7 / 9.7 | Taken, success |
| `--warn` | `#B45309` | `#FBBF24` | 4.7 / 5.0 · 11.2 / 10.2 | Refill soon, high |
| `--danger` | `#B42318` | `#F87171` | 6.2 / 6.6 · 6.8 / 6.1 | Emergency, allergy, errors |
| `--on-danger` | `#FFFFFF` | `#14120F` | 6.6 · 6.8 on danger | Text on the Emergency button |
| `--primary-soft` / `--accent-soft` / `--warn-soft` / `--danger-soft` | tints | tints | tone on its tint ≥ 4.6 | Badge and icon backgrounds, selected tab |

Dark `--ink` is light, so text on gold uses `--on-gold` (dark ink) in both themes; the spec's "ink on gold
8.7:1" holds for the light ink value, which is what `--on-gold` is.

## Type

| Role | Face | Sizes |
|---|---|---|
| Body, numbers | **Atkinson Hyperlegible Next** 400/700 | 18 body, 15 small; tabular figures for numbers |
| Headings, buttons | **Figtree** 600/700 | 34 / 28 / 22 |

Atkinson Hyperlegible Next was designed by the Braille Institute for low-vision readers: 1/l/I and 0/O
never look alike, which matters for medicine names and lab values. It covers Tagalog diacritics. Both
faces are self-hosted from `frontend/public/fonts` (latin + latin-ext woff2, `font-display: swap`), so the
app never needs the internet for them. All sizes multiply by `--text-scale`.

## Shape, space and motion

- Radius: 20 px for cards and sheets, 14 px for buttons, fully round for chips and badges.
- Spacing scale: 4, 8, 12, 16, 24, 32, 48.
- Touch: `--tap` 48 px, `--tap-lg` 64 px.
- One shadow level (`--shadow`). Flat cards on paper; no gradients, no glass.
- Focus ring: 3 px solid `--primary` with a 3 px offset, always visible on keyboard focus.
- Motion: `--dur` 200 ms with an ease-out curve; zero under `prefers-reduced-motion`.

## Components

All live in `frontend/src/components/` and use tokens only (the contrast script rejects raw colours outside `tokens.css`).

| Component | Rule |
|---|---|
| `Button` | Variants primary, secondary, danger, ghost. `md` ≥ 48 px, `lg` ≥ 64 px. Optional Lucide icon beside the word. Pressed state scales to 0.97. `loading` shows a spinner, disables the button and sets `aria-busy`. |
| `Card` | Surface, 1 px border, 20 px radius, one shadow. `flat` drops the shadow. |
| `Badge` | Tone ok, warn, danger, info: tone-coloured word (plus icon) on its soft tint. Never colour alone. |
| `Chip` | 48 px pill. Quick actions carry an icon. As a toggle (`selected`), the selected chip is gold with dark ink text. |
| `Sheet` | Bottom sheet on the native modal `<dialog>`: focus trapped, Escape and the labelled Close button dismiss it. |
| `Toast` | `ToastProvider` + `useToast()`. Polite live region, auto-dismiss after 4 s, sits above the bottom menu. Every user action reports its outcome. |
| `Skeleton` | Block on `--surface-2` with a shimmer that stops under reduced motion. Every fetching view has one. |
| `EmptyState` | Icon, title, body, and the next action as a large button. |
| `ErrorState` | Plain-words message and a Retry button (`role="alert"`). |
| `Disclaimer` | The fixed safety reminder from the catalogue, on a warn tint with an icon. Never model wording. |
| `Mark` | The brand mark inline (follows the theme). `eyes` turns it into Usap; `state` is idle, listening, thinking or speaking. |
| Bottom menu | Four equal items, icon above a word: Kausap · Card · Gamot · Talaan (Chat · Cards · Meds · Records). The current one gets a soft blue fill and blue text. The red Emergency button sits in the header on every screen. |

States: every fetching view has a skeleton, an empty state with a next action, and an error state with Retry.

## Voice and copy

- All UI text lives in `frontend/src/i18n/en.ts` and `tl.ts` with identical keys; tsc and a test both fail on a missing key. New strings go into both files in the same commit.
- Greet politely: "Magandang araw po!"
- Name actions by the result: *Ipakita ang PhilHealth*, *Magdagdag ng record*, not "Submit".
- Errors say what to do next: "Hindi ko po narinig. Pakiulit po."
- Fixed safety text (disclaimer, refusals, emergency labels) comes from the catalogue, never from the model.
- Avoid with users: AI, model, data, upload, sync, cloud.

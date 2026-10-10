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

- **It keeps them company, it doesn't examine them.** Blue and white, one sun-gold accent, nothing cold. Not a hospital system.
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
| Usap | In talk mode the large circle becomes the character: two calm eye dots, no mouth. States are a small scale or opacity change (listening, thinking, speaking); while listening, two solid signal rings breathe around it (`.mark-rings`). All stop under reduced motion. |
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

**Option A palette: `#2D59F0` blue, `#FFFFFF`, `#000000`, `#E9F1FC`, `#DDE5EF`.** A pale-blue ground, white cards,
black ink, and one vivid-blue hero card per screen. Clean healthcare at a glance, held to contrast older eyes can
read. Light only, like the reference: every phone shows the same pale-blue and white look. Ratios are WCAG contrast on `--bg` / `--surface`, as printed by `contrast.ts`.

| Token | Light | Contrast | Use |
|---|---|---|---|
| `--bg` (Langit) | `#E9F1FC` | | Pale blue ground |
| `--surface` | `#FFFFFF` | | Cards, header, menu, sheets |
| `--surface-2` / `--border` | `#DDE5EF` | | Inputs, pressed state, skeleton, edges |
| `--ink` | `#000000` | 18.5 / 21 | Main text |
| `--muted` | `#475467` | 6.8 / 7.7 | Secondary text. Nothing lighter carries text |
| `--primary` / `--primary-fill` (Kapiling Blue) | `#2D59F0` | 4.9 / 5.5 | Buttons, links, selected tab, the mark |
| `--on-primary` | `#FFFFFF` | 5.5 on primary | Text on primary |
| `--primary-strong` | `#2D59F0` | | The hero card, once per screen |
| `--on-strong` / `--on-strong-muted` | `#FFFFFF` / `#F0F5FF` | 5.5 / 5.1 on hero | Text on the hero |
| `--gold` (Araw Gold) | `#F2A900` | **never text** (2.0:1 on white) | Fills: mark lens, today, selected chip |
| `--on-gold` | `#000000` | 10.5 on gold | Text on gold |
| `--accent` | `#137336` | 5.2 / 5.9 | Taken, success |
| `--warn` | `#A34B07` | 5.2 / 5.9 | Refill soon, high |
| `--danger` | `#B42318` | 5.8 / 6.6 | Emergency, allergy, errors |
| `--on-danger` | `#FFFFFF` | 6.6 on danger | Text on the Emergency button |
| `--primary-soft` / `--accent-soft` / `--warn-soft` / `--danger-soft` | tints | tone on its tint ≥ 4.5 | Badge and icon backgrounds |

`--muted`, `--accent` and `--warn` are a shade darker than the usual Tailwind values so they hold 4.5:1 on the
blue ground. Gold reads only 3:1 against the vivid blue, so the hero's progress marks are white, not gold.

## Type

| Role | Face | Sizes |
|---|---|---|
| Display, headings, buttons | **SF Pro** (system, on iPhone and Mac) → self-hosted **Figtree** 400/600/700 elsewhere | display 40 (regular with one bold word), 34 / 28 / 22 |
| Body, numbers | **Atkinson Hyperlegible Next** 400/700 | 18 body, 15 small; tabular figures for numbers |

SF Pro is Apple's system face: it is used through `-apple-system`, never shipped, because its licence covers
Apple platforms only. On Android, Lola's usual phone, Figtree stands in. Thin and Light weights are not used:
they vanish for older eyes. Atkinson Hyperlegible Next stays for reading text because 1/l/I and 0/O never look
alike, which matters for medicine names and lab values. All faces work offline. All sizes multiply by `--text-scale`.

## Shape, space and motion

- Radius: 32 px for cards, sheets and the hero card, 16 px for toasts and the disclaimer, fully round (pill) for buttons, chips, badges and icon discs.
- Spacing scale: 4, 8, 12, 16, 24, 32, 48.
- Touch: `--tap` 48 px, `--tap-lg` 64 px.
- One shadow level (`--shadow`), tinted navy so depth reads blue, not grey. No gradients, no glass.
- Layout: calm by default. Three things above the menu: a display greeting, one hero card, two quiet borderless cards under an `.eyebrow`. 28 px between sections, 20 px gutters. Charts and lists live one tap deeper.
- Headings track tight (-0.02em); hero numbers -0.03em.
- Focus ring: 3 px solid `--primary` with a 3 px offset, always visible on keyboard focus.
- Motion: `--dur` 200 ms with an ease-out curve; zero under `prefers-reduced-motion`.

## Components

All live in `frontend/src/components/` and use tokens only (the contrast script rejects raw colours outside `tokens.css`).

| Component | Rule |
|---|---|
| `Button` | Variants primary, secondary, danger, ghost. `md` ≥ 48 px, `lg` ≥ 64 px. Optional Lucide icon beside the word. Pressed state scales to 0.97. `loading` shows a spinner, disables the button and sets `aria-busy`. |
| `Card` | White surface, no border, 32 px radius, one blue-tinted shadow. `flat` drops the shadow. |
| Hero card (`.hero`) | One per screen, one idea, one action. On Kausap it is Usap (`.hero--center`): the talking mark in a white `.orb` with white signal rings, one question, one white Magsalita pill. |
| Meter (`.meter`) | One capsule per dose, filled `--primary-fill` when taken (white on the hero). |
| List card (`.list`) | One white card of quiet rows: icon disc, title, small grey line, chevron or status badge; hairlines between rows. |
| Screens | Kausap: Usap hero + Ngayon. Card: PhilHealth hero + one list. Gamot: next-dose hero + taken list. Talaan: no hero; blood type and allergies, one trend, three latest entries. |
| Bars (`.bars`) | Capsule bar chart for a reading over time: 14 px round-ended bars in `--primary`, dates under each, latest value labelled. |
| Icon disc (`.icon-disc`) | 48 px rounded-square (14 px radius) icon holder, always beside or above a word. Circles are kept for the avatar, Emergency and the CTA end icon only. |
| `Badge` | Tone ok, warn, danger, info: tone-coloured word (plus icon) on its soft tint. Never colour alone. |
| `Chip` | 48 px pill. Quick actions carry an icon. As a toggle (`selected`), the selected chip is gold with dark ink text. |
| `Sheet` | Bottom sheet on the native modal `<dialog>`: focus trapped, Escape and the labelled Close button dismiss it. |
| `Toast` | `ToastProvider` + `useToast()`. Polite live region, auto-dismiss after 4 s, sits above the bottom menu. Every user action reports its outcome. |
| `Skeleton` | Block on `--surface-2` with a shimmer that stops under reduced motion. Every fetching view has one. |
| `EmptyState` | Icon, title, body, and the next action as a large button. |
| `ErrorState` | Plain-words message and a Retry button (`role="alert"`). |
| `Disclaimer` | The fixed safety reminder from the catalogue, on a warn tint with an icon. Never model wording. |
| `Mark` | The brand mark inline (follows the theme). `eyes` turns it into Usap; `state` is idle, listening, thinking or speaking. |
| Bottom menu | The dock, after Orionix and Scanova (Behance): one dark `--dock` capsule centred above the home indicator, four icons (Kausap · Card · Gamot · Talaan). Inactive icons `--dock-icon` grey, the current one white on a faint blue pill with a glowing `--dock-dot` under it. Words are screen-reader labels and tooltips. |
| Header | A 48 px ringed avatar and a two-line greeting ("Kumusta po," / **name**) that opens the profile sheet (switch profile, Profile, Settings); one red round Emergency button on the right, 64 px, on every screen. |
| Display title | `DisplayTitle`: regular words, the last word bold ("Mga **gamot**"). |
| Metric tile | Rounded-square icon on top, label, big number with a small unit, trend word, range badge; the whole tile is the link. On Talaan they form the blue results bento. |
| CTA (`.btn--cta`) | Full-width pill, the word leading and the icon at the end in a white circle. |
| List row | Rounded-square icon thumbnail, title, small grey line, a quiet chevron. |
| Segmented filter | One white pill holding the filter chips, scrolls sideways. |

States: every fetching view has a skeleton, an empty state with a next action, and an error state with Retry.

## Voice and copy

- All UI text lives in `frontend/src/i18n/en.ts` and `tl.ts` with identical keys; tsc and a test both fail on a missing key. New strings go into both files in the same commit.
- Greet politely: "Magandang araw po!"
- Name actions by the result: *Ipakita ang PhilHealth*, *Magdagdag ng record*, not "Submit".
- Errors say what to do next: "Hindi ko po narinig. Pakiulit po."
- Fixed safety text (disclaimer, refusals, emergency labels) comes from the catalogue, never from the model.
- Avoid with users: AI, model, data, upload, sync, cloud.

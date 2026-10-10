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
7. **Gold is never text.** Araw Gold is a fill (the mark lens and the "today" highlight) and always carries dark ink text. The contrast script fails the build if any rule sets `color: var(--gold)`.
8. **Show state, don't perform it.** Motion is 150 to 250 ms, ease-out, only for cause and effect. `prefers-reduced-motion` turns it off.

## Colour

**The prototype's Medical Blue: `#155EEF` blue, `#F5F6F8` ground, white cards, `#1C1C1C` ink.** Source:
`Kapiling-App-Prototype.html` (v5). A grey ground washed with sky blue at the top (`--grad-top` fading into `--bg`),
white cards, one blue for every action. Ratios are WCAG contrast on `--bg` / `--surface`; `contrast.ts` checks
every pair in every theme.

| Token | Blue (light) | Contrast | Use |
|---|---|---|---|
| `--bg` / `--grad-top` | `#F5F6F8` / `#E4ECFE` | | Ground, and the sky wash at the top of each screen |
| `--surface` | `#FFFFFF` | | Cards, dock, sheets |
| `--surface-2` / `--border` | `#F0F2F5` / `#E4E7EC` | | Inputs, pressed state, skeleton / hairlines |
| `--ink` | `#1C1C1C` | 15+ | Main text |
| `--muted` | `#4D4D4D` | 7.8 on bg | Secondary text. Nothing lighter carries text |
| `--primary` / `--primary-fill` | `#155EEF` | 5.0 on bg | Buttons, links, current tab, the mark |
| `--sky` | `#528BFF` | **fill only** | Top of the blue button gradient (the text sits on the darker end) |
| `--on-primary` | `#FFFFFF` | | Text on primary |
| `--gold` (Araw Gold) | `#F2A900` | **never text** | Fills: mark lens |
| `--accent` / `--warn` / `--danger` | `#067647` / `#B54708` / `#B42318` | ≥ 4.5 | Taken / refill, high / emergency, allergy, errors |
| `--danger-fill` / `--on-danger` | `#D92D20` / `#FFFFFF` | 4.8 | Danger buttons |
| `--*-soft` | tints | tone on its tint ≥ 4.5 | Badge, chip, banner and icon backgrounds |

**Themes** (Settings > Tema), as in the prototype: **Blue** (the default; follows the phone's dark mode), **Mint**,
**Night** (dark navy) and **Matingkad** (high contrast, black edges). Each lists every colour in `tokens.css`
under `:root[data-skin="…"]`; the choice is stored per device (`features/settings/theme.ts`). Dark palettes put
dark text on their light-blue buttons.

## Type

One typeface, as in the prototype: **Urbanist**, self-hosted (`public/fonts`, works offline), 400 / 500 / 600 / 700.

- The prototype's scale is 20 / 16 / 14 / 12 px; Kapiling keeps its **15 px floor** for Lola and Lolo: body 18 px,
  small text 15 px, section titles 20 px, screen titles 26 px, one weight (600) per title.
- Icons are Lucide at a 1.75 stroke (2 in the dock and buttons).

## Shape, space and motion

- Radius: 16 px cards and tiles, 12 px icon tiles and inputs, 24 px sheet corners, and the pill for every button, chip, segmented control and the dock. Circles for avatars, the back and Settings buttons, keypad keys and the Kausap button.
- Spacing scale: 4, 8, 12, 16, 24, 32, 48. 16 px gutters, 16 px between blocks.
- Touch: `--tap` 48 px, `--tap-lg` 64 px.
- One soft shadow (`--shadow`), no borders on cards. Gradients only where the prototype has them: the sky wash at the top of the screen and the blue buttons (sky to blue).
- Focus ring: 3 px solid `--primary` with a 3 px offset, always visible on keyboard focus.
- Motion: `--dur` 200 ms with an ease-out curve; zero under `prefers-reduced-motion`.

## Components

All live in `frontend/src/components/` and use tokens only (the contrast script rejects raw colours outside `tokens.css`).

| Component | Rule |
|---|---|
| `Button` | Pill. Primary is the blue gradient (sky to blue) with white text; secondary soft blue with blue text; danger; ghost. `md` ≥ 48 px, `lg` ≥ 64 px. Optional Lucide icon beside the word. Pressed scales to 0.97. `loading` shows a spinner and sets `aria-busy`. |
| `Card` | White surface, no border, 16 px radius, the one soft shadow. `flat` drops the shadow. |
| Hero card (`.hero`) | One per screen, one idea, one action. On Kausap it is Usap (`.hero--center`): the talking mark in a white `.orb` with white signal rings, one question, one white Magsalita pill. |
| Meter (`.meter`) | One capsule per dose, filled `--primary-fill` when taken (white on the hero). |
| List card (`.list`) | One white card of quiet rows: icon disc, title, small grey line, chevron or status badge; hairlines between rows. |
| Screens | Tahanan: headline (doses taken), next-medicine card, Ask Kapiling pill, PhilHealth / Talaan / Emergency quick actions, latest results, privacy line and the Pribado sheet. Talaan: dashed add-a-result tile, vitals, history. Gamot: refill banner, whole-row doses. Card: the wallet. Kausap: chat. |
| Bars (`.bars`) | Capsule bar chart for a reading over time: 14 px round-ended bars in `--primary`, dates under each, latest value labelled. |
| Icon disc (`.icon-disc`) | 48 px rounded-square (14 px radius) icon holder, always beside or above a word. Circles are kept for the avatar, Emergency and the CTA end icon only. |
| `Badge` | Tone ok, warn, danger, info: tone-coloured word (plus icon) on its soft tint. Never colour alone. |
| `Chip` | 48 px borderless pill on white with the hairline shadow. Quick actions carry an icon. Selected (`selected`) is the dark `--dock` pill with white text, matching the bottom menu. |
| `Sheet` | Bottom sheet on the native modal `<dialog>`: focus trapped, Escape and the labelled Close button dismiss it. |
| `Toast` | `ToastProvider` + `useToast()`. Polite live region, auto-dismiss after 4 s, sits above the bottom menu. Every user action reports its outcome. |
| `Skeleton` | Block on `--surface-2` with a shimmer that stops under reduced motion. Every fetching view has one. |
| `EmptyState` | Icon, title, body, and the next action as a large button. |
| `ErrorState` | Plain-words message and a Retry button (`role="alert"`). |
| `Disclaimer` | The fixed safety reminder from the catalogue on a soft amber card; its icon sits in a white rounded square. No coloured side bar. Never model wording. |
| `Mark` | The brand mark inline (follows the theme). `eyes` turns it into Usap; `state` is idle, listening, thinking or speaking. |
| Bottom menu | The prototype's dock: a white pill of four tabs (Tahanan, Talaan, Card, Gamot; icon over a word) and, beside it, the round blue Kausap button with its word underneath. The current tab is an outlined soft-blue pill. A shell row, never fixed over content. |
| Header | Tahanan: the person's round avatar and "Magandang araw po, <name>" (opens the profile switcher), and a white Settings circle. Every other screen: a title bar with a round back button (tabs go to Tahanan, deeper screens go back one step), the screen name centred, and the avatar. Emergency is on Tahanan's quick actions and the lock screen. |
| `BackLink` | 64 px light round arrow button above the display title on every screen opened from the header (Settings, Profile) or one tap deeper. Goes to the previous screen, or a fixed fallback when opened directly. |
| Display title | `DisplayTitle`: regular words, the last word bold ("Mga **gamot**"). |
| Metric tile | White card: tinted circle icon and chevron, the name, the value with its unit, a worded range badge and trend, the date. Two across at 375 px, one column at 125% text. |
| CTA (`.btn--cta`) | Full-width pill, the word leading and the icon at the end in a white circle. |
| List row | Rounded-square icon tile tinted by kind (lab blue, document red, vaccine amber, visit grey), title, small grey line. Dose rows: the whole row is the button, a round tick that fills green, the time, an Inumin / Nainom na chip; taken rows turn soft green and strike the name. |
| Segmented filter | One white pill holding the filter chips, scrolls sideways. |

States: every fetching view has a skeleton, an empty state with a next action, and an error state with Retry.

## Voice and copy

- All UI text lives in `frontend/src/i18n/en.ts` and `tl.ts` with identical keys; tsc and a test both fail on a missing key. New strings go into both files in the same commit.
- Greet politely: "Magandang araw po!"
- Name actions by the result: *Ipakita ang PhilHealth*, *Magdagdag ng record*, not "Submit".
- Errors say what to do next: "Hindi ko po narinig. Pakiulit po."
- Fixed safety text (disclaimer, refusals, emergency labels) comes from the catalogue, never from the model.
- Avoid with users: AI, model, data, upload, sync, cloud.

## Screens after the prototype

| Screen | From `Kapiling-App-Prototype.html` |
|---|---|
| Lock | Mark, title, round PIN dots, round white keys, biometric under the pad, and the Emergency card as a full-width soft-red pill at the bottom (no unlock needed) |
| Tahanan | Greeting header, "0 sa 4 gamot ang nainom na ngayon", next-medicine card with dose bars and Markahang nainom, Ask Kapiling pill, three quick actions, latest results list, "Nasa phone na ito lang" line |
| Talaan | Dashed "Magdagdag ng resulta" scan tile, white vital tiles, allergies and conditions, history with pill filters and typed icon tiles |
| Gamot | Date and "pindutin ang gamot kapag nainom na", refill banner, rows grouped Umaga / Tanghali / Gabi |
| Kausap | Greeting, starter cards with soft-blue icons, gradient user bubbles, white answer cards, pill composer |
| Settings | Wika, Laki ng sulat, Tema (four swatches), then the existing sections |

## Process

UI/UX Pro Max (`ui-ux-pro-max`) is the QA checklist: accessibility, touch, tap delay (`touch-action: manipulation`), press scale, staggered entrance (40 ms, transform and opacity only, off under reduced motion), one primary CTA per screen. Where the prototype and the checklist disagree, the 15 px floor and "label everything" win: the dock keeps its words.

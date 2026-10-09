# Tala design system

The tokens in `static/index.html` (`:root`) implement this document. Change both together.

## Who we design for

The owner of a sari-sari store or small shop. Most are 55 or older. They keep sales in a paper notebook (the *listahan*), use Facebook and Messenger on a mid-range Android phone, and their reading glasses are often somewhere else. They speak Taglish. They distrust things that look like apps that charge money, and they don't care about "AI".

What earns their trust:

- **It looks like it belongs in the store.** It should look like a clean notebook, not a gadget.
- **Every button says what it does,** in their language.
- **Nothing surprises them.** No floating buttons, no things that overlap, nothing hidden behind a gesture.
- **It respects them.** Tala says *po*. It never talks down to them or uses English jargon.

## Positioning

> **Tala: ang katulong sa tindahan na hindi napapagod.** Itala mo kay Tala.
> *(Tala: the store helper who never gets tired. Just tell Tala.)*

| We are | We are not |
|---|---|
| A *listahan* (sales notebook) that writes itself and can answer questions | An "AI app", a POS terminal, or accounting software |
| Free, and it works without internet or load | A subscription or something that eats mobile data |
| Their records, kept on their own device | A cloud service that sees their sales |

The name sets the brand idea. *Tala* means star, and *itala* means "to write down". The mark is a gold star on a green disc. In talk mode Tala becomes a character: the same gold, as a plain circle with eyes.

**On the phone, the copy talks about benefits and never about technology.** Say "Gumagana offline" (works offline), not "AI on your device". Technical claims belong only on the laptop's demo panel, which the shop owner's family or an organiser reads.

## Principles

1. **Big and plain beats clever.** Body text is 18px and nothing is smaller than 14px. Tap targets are at least 48px, and 56 to 64px for main actions.
2. **Label everything.** Every icon button also shows a word ("Boses", "Usap", "Ipakita", "Tapusin"). An icon on its own is never the only cue.
3. **One plane.** The layout stacks top to bottom: header, content, message box, menu. Nothing floats over anything else. *This rule replaced the raised round Talk button, which covered the message box.*
4. **One theme.** We use a single light, high-contrast theme because stores are bright and phones are set to light mode. Every phone shows the same look, so a grandchild's screenshot matches what Lola sees. There is no dark theme. Add one only if users ask for it.
5. **Tagalog first, polite.** Write labels in Tagalog. Keep the English words people already use in the store (Stock, Chat, Coke). The assistant uses *po*.
6. **Show state, don't animate it.** Use a word with a color (Paubos na, Nakikinig…). Keep motion small, and never use it for anything that matters. `prefers-reduced-motion` turns it off.

## Color

| Token | Value | Use |
|---|---|---|
| `--bg` | `#f3f5f2` | Page ground, a faint green-grey like ledger paper |
| `--surface` | `#ffffff` | Cards, header, message box, menu |
| `--surface-2` | `#e8eee9` | Input field, KPI tiles |
| `--border` | `#c9d3cc` | Borders, drawn heavier than usual so older eyes can see the edges |
| `--ink` | `#14201a` | Main text, about 16:1 contrast on white |
| `--muted` | `#3f4c44` | Secondary text, about 9:1 contrast |
| `--faint` | `#56625a` | Tertiary text and placeholders. Still at least 6:1, because no text may fall below WCAG AA |
| `--primary` | `#0a6b3d` | *Tindahan* green, the color of trust, money and "go". Used for buttons, selected tabs and the brand |
| `--primary-soft` | `#dcefe3` | Selected tab, icon chips |
| `--star` | `#f4b400` | The star mark only. Gold sits on green or white, and text is never set in gold |
| `--danger` / `--danger-soft` | `#b42318` / `#fde8e5` | Low stock (Paubos na), errors, the End button |
| `--warn` / `--warn-soft` | `#7a4f00` / `#fff2cc` | Cautions |
| `--c1`…`--c9` | see CSS | Chart series. Series 1 is always the brand green |

## Type

| Role | Face | Sizes |
|---|---|---|
| Display: titles, numbers, brand | **Lexend** 500/600 | 24 to 26 for screen titles, 19 for the store name, 22 to 24 for KPI numbers |
| Body | **Source Sans 3** 400/600 | 18 base, 17 in lists and suggestions, 15 to 16 for secondary text, 14 minimum |

Lexend was designed to make reading easier, which is why it fits this audience. Both font files are bundled in `static/fonts`, so the app never needs the internet for them. Numbers use `tabular-nums`.

## Shape and spacing

- Radius: 16 for cards, 14 for buttons and suggestion rows, 12 for small chips, fully round for the message box.
- Tap sizes: `--tap` is 56px for dialog and laptop-panel buttons, 64px for menu items, 48px for icon buttons inside the message box.
- Focus ring: 3px solid green, always visible.

## Components

| Component | Rule |
|---|---|
| Header | Shows the star mark, the store name (up to two lines) and a status line in plain words. The voice toggle on the right is a labelled button ("Boses"). Pressed means filled green |
| Bottom menu | Five equal labelled items: Chat · Benta · **Usap** · Stock · Payo. Usap (talk mode) is the only filled-green item. It sits *in* the bar and never above it. The selected tab gets a soft green fill as well as green text |
| Message box | Has its own band between the content and the menu, with a 1px rule above it. Holds the camera, the text field, the mic and send. The placeholder gives an example ("Hal. 2 Coke, 1 canton"). The hint under it is one short line |
| Suggestion rows | Each row has a green label stating the action (Itala ang benta) and an example sentence. The whole row is the button |
| Cards / rows | Peso amounts are right-aligned and in tabular figures. Low stock shows a red bar and the words "· low" or "Paubos na", so color is never the only signal |
| Talk mode (Usap) | Full screen on brand green. **Tala the character** is a flat gold circle with two dark oval eyes and nothing else. It blinks every few seconds. *Hold* the character to talk and let go to send; keyboard users hold Space or Enter. While held it squashes slightly and a ring grows with the voice. While thinking the eyes look side to side, and while speaking it bobs. Replies stack *above* the character as chat bubbles: Tala's in white, the owner's in translucent white. Three 64px labelled buttons: Ipakita (photo, sent right away), May boses / Naka-mute (mute toggle), Tapusin (end, red) |

## Voice and copy

- Greet politely: "Magandang araw po!"
- Name actions by the result: *Itala ang benta*, not "Submit".
- Errors say what to do next: "Hindi ko narinig. Try again?"
- Avoid these on the phone: AI, model, device inference, sync, cloud.

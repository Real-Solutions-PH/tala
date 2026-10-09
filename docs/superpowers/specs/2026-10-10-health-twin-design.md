# Kapiling: design spec

Date: 2026-10-10. Status: draft for build. The implementation plan that executes it lives at
`docs/superpowers/plans/2026-10-10-health-twin.md`.

## 1. What it is

Kapiling is a personal health record that you talk to. It keeps a person's health information on their own
device: profile, allergies, conditions, maintenance medicines, vaccines, ID and insurance cards, and
photos and scans of old records and lab results. When a nurse or doctor asks for something, the person
asks Kapiling, and Kapiling finds it, shows it, says it out loud, or fills in the form.

**Kapiling** (ka-PI-ling) means "by your side" or "keeping someone company". The app is a companion that
holds your health history and is always with you: at the clinic, in the emergency room, at home with your
medicines, from a child's first vaccines to a lola's maintenance meds. The brand is defined in §9.

Who it's for:

| Person | What they need from Kapiling |
|---|---|
| **Lola/Lolo (60+), the main user** | Pull up the PhilHealth card, the medicine list and the last blood sugar result in seconds at the clinic, without typing. Get reminders for maintenance meds. |
| **Representative (adult child, caregiver)** | Unlock Lola's record with their own PIN, upload new results, and answer for her at the hospital. |
| **Parent of a child** | Start the record at birth: vaccines, growth, pediatric visits. The record passes to the child later. |
| **Nurse, doctor, emergency responder** | Read the emergency card without unlocking the phone. Get the intake-form answers handed to them. |

## 2. What it does and does not do

| Does | Does not |
|---|---|
| Store and retrieve the person's records, cards and documents | Diagnose, interpret results as a diagnosis, or change medicines |
| Read photos of lab results and old records, and pull out values (for example FBS 132 mg/dL on 2026-03-02) | Say whether a result is "normal for you" beyond the reference range printed on the document |
| Fill in a clinic intake form from a photo, using only what's on record, and mark anything it couldn't answer | Make up an answer that isn't on record |
| Suggest activities, meals and nutrition plans that take the recorded conditions and allergies into account, **always with the disclaimer** | Give medication advice (dose, interaction, stopping or starting) |
| Remind about medicines, refills and vaccine schedules | Send data anywhere. Everything stays on the device. |

**The disclaimer** appears on every reply that recommends something: a fixed card, not left to model
wording. Tagalog: *"Paalala: Hindi ito payo ng doktor. Kumonsulta muna sa inyong doktor bago baguhin ang
pagkain, ehersisyo o gamot."* English: *"Reminder: This is not medical advice. Check with your doctor
before changing your diet, exercise or medicines."* When someone asks for a diagnosis or medicine advice,
the reply is a fixed refusal that points them to their doctor, plus any facts on record that would help
that conversation.

## 3. Locking and the emergency card

The phone's own lock is not enough, because the app is a wallet of sensitive documents and a
representative may share it. A locked app also can't be allowed to block a responder in an emergency.

| Surface | Lock | What's there |
|---|---|---|
| **Emergency card** (`/emergency`) | **Never locked.** Reachable from the lock screen with one red button. | Name, photo, age, blood type, allergies, conditions, current maintenance meds, emergency contacts (tap to call), primary doctor, PhilHealth number (last 4 digits only). Also a QR code holding the same text, so any phone camera can read it without the app. |
| **Everything else** | Locked | Opens with the owner's biometric (WebAuthn platform authenticator: Face ID, Touch ID or Android fingerprint) where the browser allows it, otherwise a 6-digit PIN |
| **Representatives** | Their own PIN | Same access as the owner, and every unlock and every document view is written to an access log the owner can read |

The owner chooses which fields appear on the emergency card (all on by default) in Settings.
The app locks again after 5 minutes in the background.

Biometric unlock needs HTTPS on a real domain or `localhost`. Browsers refuse WebAuthn on a bare LAN IP,
so on the laptop-to-phone LAN setup the PIN is the working path and the biometric button stays hidden.
On the cloud demo it works for real.

## 4. Information architecture

The bottom menu has four tabs, each with an icon and a word. The emergency button sits in the header on
every screen.

| Tab | Purpose | Contents |
|---|---|---|
| **Kausap / Chat** (home) | Ask anything | Voice button, photo-a-form button, quick chips: "Ipakita ang PhilHealth" (show PhilHealth), "Mga gamot ko" (my medicines), "Huling resulta" (latest results), "Sagutan ang form" (answer a form). Replies can contain text, cards, tables, charts, document thumbnails and citations. |
| **Card / Cards** | The wallet | ID and insurance cards as photos (front and back). Tapping one shows it full-screen at full brightness for handing to the nurse. Order: PhilHealth, Senior Citizen ID, HMO, PWD ID, vaccination card, others. |
| **Gamot / Meds** | Today's medicines | Checklist by time of day (morning, noon, night), with a tap to mark each one taken. Refill warnings. The full list with dose, purpose and prescriber. |
| **Talaan / Records** | The history | A "Kalagayan" (health summary) block at the top: conditions, allergies, latest vitals and labs with a trend arrow. Below it, a filterable timeline of visits, lab results, vaccines and documents. Lab result pages draw trend charts with a table alternative. |

Header: profile switcher (for families: Lola, a child), the red **Emergency** button, and Settings
(language EN/TL, text size, emergency card fields, representatives, access log, lock).

**Profile page** (from the header): personal information, family history, representatives.

**The design rule for this IA:** anything a hospital asks for at every visit is at most **two taps or one
spoken sentence** away: PhilHealth/HMO card, medicine list, allergies, blood type, latest labs,
emergency contact.

## 5. Chat behaviour

| Behaviour | Spec |
|---|---|
| Protocol | AG-UI events over server-sent events (RSPH EZ-D-020): RUN_STARTED, STEP_STARTED/STEP_FINISHED, TEXT_MESSAGE_START/CONTENT/END, TOOL_CALL_START/END, CUSTOM (blocks, citations, audio, transcript), RUN_ERROR, RUN_FINISHED. The client sends only the new message plus the conversation id. The server loads history from its own store and creates the conversation id. The assistant message is saved **before** RUN_FINISHED, and RUN_FINISHED carries the saved message id (VCAC-G-022). The HTTP status is settled before the stream starts (G-C-012). |
| Streaming | Text arrives token by token. The first token should appear in under 1.5 s on the M-series laptop for a question that needs no tool. |
| Intermediate steps | Each step shows as a live status line inside the reply as it happens ("Hinahanap sa mga record..." / "Searching your records...", "Binabasa ang larawan..." / "Reading the photo...", "Tinitingnan ang mga gamot..." / "Checking your medicines..."). Steps collapse into a "3 hakbang" ("3 steps") disclosure when the answer finishes. |
| Rich blocks | Typed blocks rendered by the client: `card` (ID card image), `profile_fields`, `med_list`, `lab_table`, `chart`, `document` (thumbnail plus open), `form_answers` (field, answer, source, and "not on record"), `citations`, `disclaimer`. |
| Citations | Any answer that used a document shows numbered source chips. Tapping one opens the document at the cited page. |
| Stop | A Stop button replaces Send while generating, and it cancels the generation on the server. |
| Conversations | Stored on the device in SQLite with an auto title. A history drawer lists them and lets you rename or delete them. A new chat starts empty. |
| Errors | A failed step says what failed and offers Retry. A partially streamed answer is kept and marked incomplete, never silently dropped. |
| Language | The reply language follows the UI language setting, and the user can talk in either language. |

## 6. Voice

Two voice modes:

1. **Push-to-talk in chat:** hold or tap the big voice button, speak, release. The transcript goes in as a message and the reply streams as usual. Reading it aloud is optional.
2. **Usap mode (hands-free conversation):** full-screen, big character, one button to end. The browser
   detects when speech starts and ends (voice activity detection, Silero VAD running in the browser),
   sends each utterance to local whisper, streams the reply from the LLM, cuts it into sentences, and
   synthesises and plays each sentence as soon as it's ready, so the first audio plays before the full
   reply exists. If the user starts talking while Kapiling is speaking (barge-in), playback stops and the
   generation is cancelled.
3. **Listen-in for a consultation:** a variant of Usap mode where Kapiling answers only when the doctor's question is about the record ("Ano ang maintenance niya?"). It shows a visible "Nakikinig" ("Listening") indicator. Audio is never stored. Only the transcript of the questions Kapiling answered goes into the conversation.

Latency target for Usap mode: under 2.5 s from the end of the user's speech to the first audio on the
laptop. This is tighter than VCAC's 3 s target, because there is no network hop. The guessed budget is
VAD end ≈ 0.3 s, whisper ≈ 0.6 s, LLM first sentence ≈ 1.0 s and TTS first sentence ≈ 0.4 s. These are
estimates, not measurements.

Rules carried over from the voice-cloned AI coach project:

- **Sentence aggregation before TTS,** and markdown is cleaned per sentence, never from the raw token stream (G-C-073, VCAC-G-037).
- **Barge-in cancels everything:** generation, queued synthesis and queued audio. An interrupted turn is saved as `interrupted`, not as a failure.
- **Three clocks:** a 20 s composing deadline, an 8 s no-audio watchdog, and a silence clock that counts only while listening (VCAC-G-052).
- **A 0.8 s pre-generation budget** for retrieval. If it runs out, the reply is fixed "I couldn't find that" copy, never an ungrounded answer.
- **Text on screen first:** the reply streams as text while it's spoken, and it's saved whether or not it was played.
- **One timing line per turn** with the stamps `speech_end`, `transcript_final`, `search_done`, `first_token`, `first_sentence`, `first_audio_ready`, `first_audio_played`. These are stored and shown on the laptop's demo panel.

Transport: a voice turn is the same AG-UI run as a chat turn. The utterance audio is uploaded with the
run request, and the server emits a CUSTOM `transcript` event and then CUSTOM `audio` events (one WAV per
sentence, in order). One protocol, one cancel path.

## 7. Documents and retrieval

There are two kinds of information, and they're stored differently on purpose:

| Kind | Examples | Storage | How the assistant gets it |
|---|---|---|---|
| **Structured facts** | Profile, blood type, allergies, conditions, meds, vaccines, cards, emergency contacts, lab values | SQLite tables | Tool calls that return exact rows. Exact recall, no retrieval step. The essential summary is also placed in the system prompt so most questions need no tool. |
| **Documents** | Photos of lab results, scanned old hospital records, discharge summaries, prescriptions, PDFs | Original file on disk plus chunks in a vector index | Hybrid retrieval (keyword plus vector, then reranking) with citations |

Ingesting a document (following RSPH convention G-C-077, adapted for photos):

1. **Parse.** PDFs and images go through Docling, keeping the `DoclingDocument`. Photos of results are first read by the local vision model (Qwen3-VL), which transcribes them to markdown with tables, because Docling's OCR is weak on phone photos of paper. That markdown is loaded back into a `DoclingDocument`, so the next step sees headings and tables.
2. **Chunk** with Docling's `HybridChunker`, with a token budget measured by the embedding model's tokenizer. Metadata: document title, heading path, page, page box.
3. **Build** LangChain `Document` objects carrying that metadata.
4. **Embed in batches** (local embedding model on `llama-server --embedding`) and **write in batches** to `sqlite-vec`, plus an FTS5 keyword index over the same chunks.
5. **Extract structured facts:** the same vision pass returns lab values (test, value, unit, reference range, date, facility) as JSON, which go into `observations` so charts and "latest result" answers are exact. The user confirms extracted values before they're saved.

Retrieval runs FTS5 keyword search and `sqlite-vec` vector search, both filtered by profile inside the
query, fused with reciprocal rank fusion. The top 24 are reranked by a local cross-encoder
(bge-reranker-v2-m3 on `llama-server --reranking`), the top 6 are kept, and a score floor applies.
The floor starts at a placeholder and is **set from the evaluation run**. Without a floor, off-topic
questions get answered and cited from the nearest page (Ezentro's finding). Citations resolve by chunk id
to a document and page, and highlights travel as `before`/`match`/`after` strings, never offsets
(VCAC-D-013). The evaluation questions are kept out of the indexed corpus (EZ-C-055).

The embedded string is the plain newline-joined title plus heading path plus text. A leading line that
repeats the title is dropped. The stored text stays bare. The template version is part of the content
hash. Retrieval quality is measured on a fixed question set over the seeded demo documents before any
tuning (see the plan's evaluation task). No figure is quoted that wasn't measured.

Graph RAG is not built. One person's record is small, and the relationships a graph would hold (which
medicine treats which condition, which result came from which visit) are already columns in the
structured tables.

## 8. Internationalisation

All UI text lives in two catalogues, `en` and `tl`, with identical keys. TypeScript fails the build when a
key is missing from either one, and a test checks that every key used in the code exists. Dates and
numbers use `Intl` with `en-PH` / `fil-PH`. The language switch is in Settings and on first launch. The
assistant's replies follow the setting. Fixed safety text (disclaimer, refusal, emergency labels) comes
from the catalogue, never from the model.

## 9. Brand

| Element | Decision |
|---|---|
| **Name** | Kapiling. It replaces "Tala", whose star mark, green palette and store voice all belonged to the store assistant. |
| **Tagline** | TL: *"Laging kapiling ang kalusugan mo."* EN: *"Your health, always by your side."* |
| **Idea** | A companion, not a hospital system. It keeps you company and remembers for you, so you never have to recite your history from memory or carry a folder of papers. |
| **Mark** | Two rounded forms side by side: a large circle (the person) and a smaller circle leaning in and slightly overlapping it (the companion). The overlap is a small sun-gold lens, the shared memory. It is drawn as flat SVG in two colours (Kapiling Blue and Araw Gold) and stays legible at 16 px. In Usap mode the large circle becomes the character, with two calm eyes and no mouth, the same restraint the old character had. |
| **App icon** | The mark in white and gold on a Kapiling Blue rounded square, with a maskable safe zone. It is generated as 180, 192 and 512 px PNGs plus an SVG favicon. |
| **Voice** | Warm, plain, respectful. In Tagalog it uses *po* and *opo*, and in English it's polite and simple. It speaks as a helper ("Heto po ang PhilHealth card ninyo"), never as a doctor. It doesn't use "AI", "data" or "upload" with users: it says "litrato" (photo), "record" and "itago" (keep). Technical claims appear only on the laptop's demo panel and in the README. |
| **What it isn't** | Clinical, scary, cute, or "techy". No stethoscope or heart-with-pulse clichés, no robot, no gradients. |

## 10. Design system

The design is modern, calm and warm, and readable at arm's length by someone in their 60s. It fully
replaces the store assistant's `DESIGN.md`. Most health apps are cold teal on white. Kapiling uses a warm
paper background, which cuts glare for older eyes, a deep trustworthy blue, and a single sun-gold accent
that carries the brand.

| Token | Light | Dark | Contrast (on bg / surface) |
|---|---|---|---|
| `--bg` (Papel) | `#FBF8F3` | `#14120F` | |
| `--surface` | `#FFFFFF` | `#1F1C18` | |
| `--ink` | `#1C1917` | `#F5F1EA` | 16.5 / 17.5 · 16.6 / 15.1 |
| `--muted` | `#57534E` | `#B8B0A4` | 7.2 / 7.6 · 8.7 / 7.9. Nothing lighter carries text. |
| `--primary` (Kapiling Blue) | `#1F4E8C` | `#8CB4F0` | 7.9 / 8.3 · 8.8 / 8.0. White on primary 8.3. |
| `--gold` (Araw Gold) | `#F2A900` | `#F2A900` | **Never text on a light background** (2.0:1 on white). Used for fills: the mark, the "today" highlight, and the selected chip, always with `--ink` text on it (8.7:1). |
| `--accent` (taken, success) | `#15803D` | `#4ADE80` | 4.7 / 5.0 · 10.7 / 9.7 |
| `--warn` (refill soon, high) | `#B45309` | `#FBBF24` | 4.7 / 5.0 · 11.2 / 10.2 |
| `--danger` (emergency, allergy) | `#B42318` | `#F87171` | 6.2 / 6.6 · 6.8 / 6.1 |

The contrast figures were computed with the WCAG formula for these exact hex values on 2026-10-10. A
script in the frontend re-checks them on every test run.

- **Style:** flat cards on warm paper, one soft shadow level, 20 px radius on cards and 14 px on buttons, generous whitespace. No gradients, no glass effects, no purple.
- **Type:**
  - **Atkinson Hyperlegible Next** for body text. The Braille Institute designed it for low-vision readers: distinct letter shapes stop 1/l/I and 0/O being confused, which matters for medicine names and numbers. It covers Tagalog diacritics.
  - **Figtree** for headings, at weights 600 and 700.
  - Both fonts are **self-hosted**, because the app must work offline.
  - Body text is 18 px, with a 15 px minimum and a line height of 1.55. Numbers use tabular figures.
  - A text-size setting (100 / 125 / 150%) scales the whole UI through one root variable.
- **Touch:** minimum target 48 px, 64 px for primary actions, 8 px minimum gap between targets.
- **Icons:** Lucide, 2 px stroke, always paired with a word.
- **Allergies and emergency** use red plus an icon plus a word, never colour alone.
- **Theme:** light by default, dark follows the system. Both are tested for contrast.
- **Motion:** 150 to 250 ms, ease-out, used only to show cause and effect. `prefers-reduced-motion` turns it off.
- **Charts:** line charts for vitals and labs over time, drawn in Kapiling Blue, with the reference range as a soft shaded band, direct value labels, and a data-table toggle. Fewer than 4 points shows stat cards instead.
- **States:** every fetching view has a skeleton, an empty state with a next action, and an error state with Retry (RSPH G-C-013, G-X-014). Every user action reports its outcome in a toast (G-C-079).

## 11. Deployment

| Mode | How |
|---|---|
| **Local (the product)** | `./run.sh` on the laptop starts llama-server (chat plus vision), a second llama-server for embeddings and reranking, whisper-server, and the app. Phones join over LAN HTTPS with the pairing QR, as now. |
| **Cloud demo (later)** | The same app in a container on a GPU VM with a real domain and TLS, seeded with fictional PHI only, plus a "Reset demo" button. It still uses self-hosted open models, with no cloud AI API. A banner says the data is fictional. |

All endpoints and model paths come from environment variables, so the same build runs in both modes.

## 12. Out of scope for this build

Syncing between devices, importing from hospital systems (HL7/FHIR), insurance claims, telemedicine,
handing a child's record over at 18 (designed as profile ownership, not built), and graph RAG.

# LinkedIn post draft (Kapiling, AppBuildersPH Hackathon 2026)

Required by the hackathon: a video, a tag for Devin / Cognition, and #AppBuildersPH. Type the @ mentions in LinkedIn so they link.

---

Most Filipino families have the envelope. The plastic one with Lola's old lab results, a few prescriptions, and a photocopy of her PhilHealth card that may or may not be current.

At every checkup the nurse asks the same things. Allergies? Maintenance meds? Last blood sugar? And every time someone digs through that envelope, calls a tita, or the test just gets done again.

For the AppBuildersPH Hackathon (theme: Local AI), Ervin Piol and I built Kapiling. It's a health record you talk to, in Tagalog or English.

What works today:
- Ask "Mga gamot ko" and it shows her maintenance meds, with doses and times.
- Ask "Puwede ko bang itigil ang Metformin?" and it won't answer that. It tells her to ask her doctor, on purpose, every time.
- Take a photo of an old lab result and a local model reads it. Values only count after she confirms them.
- The PhilHealth and Senior Citizen cards open full screen for the nurse.
- An emergency card with blood type, allergies and contacts opens without unlocking the phone.

Every model runs on the family's laptop: Qwen3-VL for chat and reading photos, Whisper for speech, Meta's MMS for the Tagalog voice, a small embedding model for search. The phone just connects over home Wi-Fi. Nothing gets uploaded. Health records seemed like the worst possible thing to send to someone else's server, and hospitals are exactly where the signal dies.

It's rough in places. The first answer after startup is slow, and the 8B model's meal suggestions aren't great yet. But the clinic-visit flow works in airplane mode, and that was the part we cared about.

Demo below. Code is open: github.com/Real-Solutions-PH/Kapiling

@Cognition @Devin #AppBuildersPH #LocalAI

---

## Shorter version (if the video caption needs to be brief)

We built Kapiling for the AppBuildersPH Hackathon: a health record Lola can talk to, in Tagalog or English. It shows her meds, opens her PhilHealth card for the nurse, reads photos of old lab results, and refuses to give medicine advice. Every AI model runs on the family laptop, so nothing is uploaded and it works offline.

github.com/Real-Solutions-PH/Kapiling
@Cognition @Devin #AppBuildersPH #LocalAI

## Video

- Live recording of the real app: `docs/video/kapiling-demo-v3.mp4` (59 s, latest design: emergency card, voice, chat answers and refusal, cards in chat, photo upload, Card, Gamot and Talaan). Or record about 1 minute of the live app following `docs/demo-guide.md`, with the phone in airplane mode.
- Backup already made: `docs/video/kapiling-screens-backup.mp4` (34 s, screenshots of the real screens, no audio).

## X version (273 of 280 characters; X counts the link as 23)

Kapiling: a health record Lola can talk to in Tagalog. Shows her meds and PhilHealth card, reads lab photos, opens an emergency card without a PIN, and won't give medicine advice. All AI runs on the family laptop.

github.com/Real-Solutions-PH/Kapiling
@cognition @DevinAI #AppBuildersPH

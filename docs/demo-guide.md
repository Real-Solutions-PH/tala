# Demo guide

Run both demos with the phone in **airplane mode** (Wi-Fi back on only to reach the laptop, if you pair over LAN; the laptop needs no internet). All data is fictional. Owner PIN `123456`, representative PIN `246810`.

> **Check before presenting.** The chat screen and the voice buttons were not merged into the web app at the time of writing; the Chat tab is a placeholder. Steps marked **[chat]** need them. If chat is not in the build you are showing, skip those steps and use the "without chat" substitutes below. Voice latency is to be measured; do not quote a number.

## Preparation

1. `./run.sh`; wait for the URLs and QR code.
2. Scan the QR on the phone and accept the certificate warning. Turn on airplane mode.
3. Open the app once so it is on the lock screen.

## 5-minute live demo

The order below is a proposed running order built from the features in the README; the 1-minute script further down is the one from `docs/submission.md`.

1. (0:00) Say what it is: a health record that Lola talks to, with every model on this laptop and no cloud AI. Show airplane mode.
2. (0:20) On the lock screen tap **Emergency**. Show blood type, allergies, conditions, medicines, contacts and the QR code, with no PIN.
3. (0:50) Go back and unlock with the owner PIN. Show a wrong PIN once to show it is refused.
4. (1:10) **Cards** tab: open PhilHealth full-screen, as for a nurse. Open the back.
5. (1:40) **Gamot** (Meds): tap a dose as taken; point out the refill warning.
6. (2:10) **Talaan** (Records): the health summary, then the FBS trend with the reference band; switch to the table view.
7. (2:50) Open a scanned lab document and show the highlighted source. Open the extraction review: values are "proposed" until confirmed.
8. (3:30) **[chat]** Ask "Ano ang maintenance ko?". The medicine list streams in with live step lines.
9. (3:50) **[chat]** Ask "Puwede ko bang itigil ang Metformin?". A fixed refusal card appears.
10. (4:10) Settings: choose emergency card fields, switch language to English, change text size.
11. (4:30) Sign in as the representative (`246810`), then as the owner open the access log to show the unlock.
12. (4:50) Close: records stay on the device, the AI never leaves it, and Kapiling does not diagnose or advise on medicines.

Without chat: replace steps 8 and 9 with the safety evaluation description in [safety.md](safety.md) and the screenshot of the document citation.

## 1-minute video script (phone in airplane mode)

From `docs/submission.md`.

1. (0:00) Lock screen: "Kapiling keeps Lola's health record on her own device." Tap Emergency: blood type, allergies, QR, no PIN.
2. (0:12) Unlock with PIN. Cards tab: PhilHealth full-screen for the nurse.
3. (0:20) **[chat]** Chat: "Ano ang maintenance ko?" and the medicine list streams in, live steps visible.
4. (0:32) **[chat]** "Puwede ko bang itigil ang Metformin?" and the fixed refusal card appears.
5. (0:40) Records: FBS trend with the normal range; photo of a lab result read by the local model.
6. (0:52) "Everything runs locally. No cloud AI." Show airplane mode.

## If something fails

- `GET /api/health` shows which model server is down. Logs are in `logs/`.
- A wrong PIN five times locks that profile for 60 seconds; wait it out.
- Reset to a clean state by deleting the data folder and re-running `./run.sh` (it reseeds), or use the cloud demo's reset.

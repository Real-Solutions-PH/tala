# Security and privacy

## What stays on the device

All records, files, conversations and voice audio handling happen on the laptop. The only network traffic at runtime is between the browser and the laptop (loopback, or the home LAN for a paired phone) and between the app and the model servers on 127.0.0.1. No cloud AI API is called. The internet is used only for the one-time model download. The data lives in one SQLite file plus uploaded files under `KAPILING_DATA`.

## PIN lock and sessions

- The owner and each representative have a 6-digit PIN, stored as a salted scrypt hash. PINs must be unique within a profile, so an unlock can say who is acting.
- A correct PIN creates an in-memory session (random 32-byte token) in an `HttpOnly`, `SameSite=Strict` cookie, `Secure` over HTTPS. A session dies after 300 seconds without an authorised request. Sessions live in memory only, so restarting the app locks everyone.
- **Lockout.** After 5 failed attempts for a profile within 300 seconds, further attempts get HTTP 429 for 60 seconds. In-flight attempts count, so parallel guessing does not help. The same throttle protects sensitive changes that re-ask for the current PIN.
- **Revocation.** Removing a representative, changing the owner PIN and removing biometrics end the affected sessions (a PIN change or biometric removal keeps only the caller's own session).
- Owner-only actions (PINs, representatives, biometrics, the access log) refuse a representative with 403 and write a `denied` entry to the access log.

## Representatives and the access log

A representative (for example an adult child) unlocks with their own PIN and gets the same access as the owner except the owner-only actions above. Every unlock, failed unlock, card view and denied action is written to `access_log` with the actor's name. Only the owner can read it (up to 500 recent entries).

## Biometric unlock (WebAuthn)

The owner can enrol a platform authenticator after re-entering the current PIN. Enrolment and removal are owner-only. The relying-party id is the request host without its port, and an IP-address host is refused up front, because browsers do not allow WebAuthn there. In practice biometric unlock works on `localhost` or a real domain (the cloud demo behind Caddy), not on a bare LAN address, where the PIN is the path. Credentials are stored in `owner_lock.webauthn`.

## Emergency card

`GET /api/emergency/{pid}` and its QR are deliberately public, so a responder can read them without the PIN. They return only these fields, each switchable by the owner in Settings: name, photo, age, blood type, allergies, conditions, current medicines, emergency contacts, primary doctor, and the last 4 digits of the PhilHealth number. Fields the owner turns off come back empty. Nothing else (documents, labs, full card numbers, conversations) is reachable without a session.

## Phone pairing allow-list

Requests from the laptop itself (127.0.0.1, ::1) need no pairing. Any other client must hold the pairing cookie, obtained by opening the link in the QR code printed by `run.sh`. The key is random per start (`openssl rand -hex 16`), and the cookie is `HttpOnly`, `Secure`, `SameSite=Strict`. An unpaired client can reach only: `/api/health`, `/api/profiles`, `/api/unlock`, a profile photo, and the emergency card and its QR. Everything else returns 403. The LAN server uses a self-signed certificate valid for 30 days. In cloud-demo mode (`KAPILING_DEMO=1`) pairing is off and all data is fictional.

## Upload validation

Files are checked by their bytes, never by the client's content type.

| Upload | Limit and checks |
|---|---|
| Documents | 20 MB; a PDF must parse and have at most 30 pages (413 otherwise); an image must open and verify in Pillow, and formats other than JPEG and PNG (including HEIC) are converted to JPEG; anything else gets 415 |
| Card photos and chat photos | 10 MB; JPEG, PNG or WebP verified by Pillow |
| Chat audio | 25 MB |
| Rendered pages | capped at about 4 megapixels |

## No PHI in logs

Server logging records run ids and exception class names, not message text, record values or file contents (see the comment in `chat/routes.py`). The phone-facing server runs with `--no-access-log`. Record values are never placed in URLs; paths carry only numeric ids.

## Data Privacy Act (RA 10173) context

Health information is sensitive personal information under the Data Privacy Act. Kapiling's approach is to avoid the exposure: the data does not leave the person's device, there is no cloud processor, access is by PIN, and the access log shows who looked. The market research notes NPC Circular 2023-06 (security minimums) and DOH-NPC JMC 2020-0002 as the relevant rules for a future deployment; see [market-and-business.md](market-and-business.md). This repository has not been legally reviewed and makes no compliance claim. Adding sync or cloud backup would change the picture and would need a privacy review first.

## Known limits

- There is no encryption at rest in the app; protect the laptop with disk encryption.
- Backup and sync do not exist, so losing the device loses the data.
- Sessions are in memory; lockout counters reset on restart.
- The demo PINs are public and fictional.

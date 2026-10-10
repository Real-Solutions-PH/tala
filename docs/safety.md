# Safety

Kapiling stores and retrieves a person's own records. It is not a clinician.

## What it will not do

- Diagnose, or interpret a result as a diagnosis.
- Give medicine advice: dose, interactions, stopping or starting.
- Say a result is "normal for you" beyond the reference range printed on the document.
- Make up an answer that is not on record.

## Fixed text, never from the model

The disclaimer and the refusal are catalogue strings in the client (`safety.*` in `frontend/src/i18n/en.ts` and `tl.ts`). The server sends only a block, `{"type":"disclaimer"}` or `{"type":"refusal","kind":"diagnosis"|"medication"}`, and the client renders the catalogue text. The model cannot reword them. Emergency labels come from the catalogue too.

- Disclaimer (English): "Reminder: This is not medical advice. Check with your doctor before changing your diet, exercise or medicines." A Tagalog version exists.
- Refusal: a fixed card pointing to the person's doctor. The model may add one short polite sentence and facts that are on record (for example a listed allergy), without interpreting them.

The disclaimer accompanies replies that recommend something, such as the meal and activity tools. Those tools receive the person's conditions, allergies and medicines so the ideas respect them.

## Deterministic pre-check

Before the model answers, `chat/safety.py` checks the message for whole-word phrases in English and Tagalog: medicine changes (for example `itigil`, `ihinto`, `doblehin`, "stop taking", "double my", "increase my dose") and diagnosis requests ("ano ang sakit ko", "diagnose"). A match shows the fixed refusal and tells the model not to advise, even if the model would not have called `decline_medical_advice`. Phrases were chosen so ordinary record lookups ("Do I have allergies?", "When was I diagnosed with diabetes?") are not caught. The list is short on purpose; the evaluation harness measures it (the planned gate is refusal 5/5 and disclaimer 5/5 on 40 questions; results are not recorded yet, see `backend/eval/README.md`).

## Answers come from the record

The system prompt tells the model to answer only from the record or tool results, and to say when something is not on record. Search results are cited by number. If the records search is unavailable, the tool says so rather than guessing.

## Extracted lab values stay proposed

When a photographed result is read, the model returns values as JSON. A numeric value that does not appear in the transcript is rejected, and a reference limit not written there is dropped. Values are saved as `proposed`. Charts, "latest result" answers and the summary use only `confirmed` values. The person reviews each one against the source image, can edit it, and confirms or removes it.

## The form filler

`chat/form.py` reads a clinic form from a photo and maps each field to the record. Python then checks every answer: its source key must resolve in the record, and the value must actually appear in the record value at that key; otherwise the answer becomes null. Blank fields are shown as "not on record". Checkboxes are ticked only when the record supports it. Status: the module and its tests are merged; it is not yet wired into the chat agent.

// Wire types for the REST API (plan C2) and the AG-UI stream (plan C3).

export type Block =
  | { type: 'card'; card_id: number; label: string; front_url: string; back_url: string | null }
  | { type: 'profile_fields'; fields: { key: string; value: string }[] } // key = i18n "fields.*"
  | { type: 'med_list'; meds: { name: string; strength: string | null; schedule: string[]; purpose: string | null }[] }
  | { type: 'lab_table'; rows: { label: string; value: string; unit: string | null; ref: string | null; date: string; flag: 'low' | 'high' | null }[] }
  | { type: 'chart'; code: string; label: string; unit: string | null; points: { date: string; value: number }[]; ref_low: number | null; ref_high: number | null }
  | { type: 'document'; document_id: number; title: string; date: string | null; thumb_url: string }
  | { type: 'form_answers'; items: { field: string; answer: string | null; source: string | null }[] } // answer null = not on record
  | { type: 'disclaimer' } // text from i18n "safety.disclaimer"
  | { type: 'refusal'; kind: 'diagnosis' | 'medication' } // text from i18n "safety.refusal.*"

export type Source = { n: number; chunk_id: number; document_id: number; title: string; page: number | null; before: string; match: string; after: string }

export type StepName =
  | 'reading_photo' | 'transcribing' | 'search_records' | 'check_profile' | 'check_meds' | 'check_labs'
  | 'check_cards' | 'reading_form' | 'answering_form' | 'planning_meals' | 'planning_activities'

export type RunStatus = 'complete' | 'stopped' | 'interrupted' | 'failed'
export type RunErrorCode = 'llm_unavailable' | 'timeout' | 'cancelled' | 'bad_input' | 'internal'

export type AgUiEvent =
  | { type: 'RUN_STARTED'; threadId: string; runId: string }
  | { type: 'STEP_STARTED'; stepName: string }
  | { type: 'STEP_FINISHED'; stepName: string }
  | { type: 'TOOL_CALL_START'; toolCallId: string; toolCallName: string }
  | { type: 'TOOL_CALL_END'; toolCallId: string }
  | { type: 'TEXT_MESSAGE_START'; messageId: string; role: 'assistant' }
  | { type: 'TEXT_MESSAGE_CONTENT'; messageId: string; delta: string }
  | { type: 'TEXT_MESSAGE_END'; messageId: string }
  | { type: 'CUSTOM'; name: 'transcript'; value: { text: string } }
  | { type: 'CUSTOM'; name: 'block'; value: Block }
  | { type: 'CUSTOM'; name: 'sources'; value: Source[] }
  | { type: 'CUSTOM'; name: 'audio'; value: { seq: number; wav_b64: string } }
  | { type: 'CUSTOM'; name: 'timing'; value: Record<string, number> }
  | { type: 'RUN_ERROR'; message: string; code: RunErrorCode } // message is an i18n key
  | { type: 'RUN_FINISHED'; threadId: string; runId: string; result: { messageId: string; status: RunStatus } }

// ---- REST ----

export type ProfileListItem = { id: number; nickname: string | null; full_name: string; photo_url: string | null }

export type Profile = {
  id: number; full_name: string; nickname: string | null; birth_date: string; sex: 'F' | 'M' | null
  blood_type: string | null; address: string | null; phone: string | null
  philhealth_no: string | null; senior_id_no: string | null; language: 'tl' | 'en'
}

export type Condition = { id: number; name: string; since: string | null; status: 'active' | 'resolved'; notes: string | null }
export type Allergy = { id: number; substance: string; reaction: string | null; severity: 'mild' | 'moderate' | 'severe' | null }
export type Contact = { id: number; name: string; relation: string | null; phone: string; is_emergency: number; is_doctor: number; specialty: string | null; clinic: string | null }

export type Med = {
  id: number; name: string; strength: string | null; form: string | null; purpose: string | null; prescriber: string | null
  schedule: string[]; start_date: string | null; end_date: string | null; supply_left: number | null; active: number
}

export type Observation = {
  id: number; code: string; label: string; value: number | null; value_text: string | null; unit: string | null
  ref_low: number | null; ref_high: number | null; date: string; facility: string | null; document_id: number | null
  status: 'proposed' | 'confirmed'
}

export type Summary = {
  profile: Profile; conditions: Condition[]; allergies: Allergy[]; meds: Med[]
  latest: Record<string, Observation>; contacts: Contact[]
}

export type WalletCard = {
  id: number; kind: 'philhealth' | 'senior' | 'hmo' | 'pwd' | 'vaccination' | 'national_id' | 'other'
  label: string; number_masked: string | null; front_url: string; back_url: string | null; expires: string | null
}

export type MedsDay = { meds: Med[]; today: { med_id: number; slot: string; taken_at: string | null }[] }

export type TimelineKind = 'visit' | 'lab' | 'vaccine' | 'document'
export type TimelineItem = { kind: TimelineKind; date: string; title: string; ref_id: number }

export type DocumentItem = {
  id: number; title: string; kind: 'lab' | 'record' | 'prescription' | 'discharge' | 'imaging' | 'other'
  date: string | null; facility: string | null; pages: number; status: 'queued' | 'reading' | 'indexed' | 'failed'; error: string | null
}

export type ConversationItem = { id: string; title: string; updated: string }

export type Message = {
  id: string; role: 'user' | 'assistant'; content: string; mode: 'text' | 'voice' | 'usap' | 'listen'
  status: RunStatus; blocks: Block[]; steps: string[]; sources: Source[]; attachments: unknown[]; created: string
}

export type Conversation = { id: string; title: string; messages: Message[] }

export type EmergencyCard = {
  profile_id: number; name: string; photo_url: string | null; age: number | null; blood_type: string | null
  allergies: { substance: string; reaction: string | null; severity: string | null }[]
  conditions: string[]
  meds: { name: string; strength: string | null; schedule: string[] }[]
  contacts: { name: string; relation: string | null; phone: string }[]
  doctor: { name: string; clinic: string | null; phone: string | null } | null
  philhealth_last4: string | null
  qr_text: string
}

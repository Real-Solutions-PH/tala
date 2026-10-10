// Document endpoints for the records screens (plan C2). Task 7 owns the backend; these follow its shapes.
//
// Assumed shape of GET /documents/{id} (C2 says "metadata"): the list item's fields plus the transcription
// and the document's own observations, both proposed and confirmed. Missing fields degrade gracefully.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import { keys } from '../../api/queries'
import type { DocumentItem, Observation } from '../../api/types'

export type DocumentDetail = DocumentItem & { transcript_md?: string | null; observations?: Observation[] }

export type ObservationEdit = { value: number | null; unit: string | null; date: string }

export const POLL_MS = 3000
const reading = (d?: DocumentItem) => d?.status === 'queued' || d?.status === 'reading'

export const documentKey = (id: number) => ['document', id] as const

/** Polls every 3 s while Kapiling is still reading the document. */
export function useDocument(id: number) {
  return useQuery({
    queryKey: documentKey(id),
    enabled: Number.isInteger(id) && id > 0,
    queryFn: ({ signal }) => api.get<DocumentDetail>(`/documents/${id}`, signal),
    refetchInterval: q => (reading(q.state.data) ? POLL_MS : false),
    staleTime: 0,
  })
}

export function useUploadDocument(pid: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api.send<{ id: number; status: DocumentItem['status'] }>('POST', `/profiles/${pid}/documents`, form)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.documents(pid) })
      qc.invalidateQueries({ queryKey: ['timeline', pid] })
    },
  })
}

export function useConfirmObservations(docId: number, pid: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { ids: number[]; edits: Record<number, ObservationEdit> }) =>
      api.send('POST', `/documents/${docId}/observations/confirm`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: documentKey(docId) })
      qc.invalidateQueries({ queryKey: keys.summary(pid) })
      qc.invalidateQueries({ queryKey: ['observations', pid] })
    },
  })
}

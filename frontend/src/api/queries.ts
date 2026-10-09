// TanStack Query hooks, one per read endpoint. Keys are [resource, ...ids] so mutations can invalidate them.
import { QueryClient, useQuery } from '@tanstack/react-query'
import { api, ApiError } from './client'
import type {
  Conversation, ConversationItem, DocumentItem, EmergencyCard, MedsDay, Observation, ProfileListItem, Summary,
  TimelineItem, TimelineKind, WalletCard,
} from './types'

type Pid = number | null | undefined

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // 4xx answers will not change on retry (401 already went to /lock, 403/404 show their state).
        retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
        refetchOnWindowFocus: false,
      },
    },
  })
}

export const keys = {
  profiles: ['profiles'] as const,
  summary: (pid: Pid) => ['summary', pid] as const,
  cards: (pid: Pid) => ['cards', pid] as const,
  meds: (pid: Pid, date: string) => ['meds', pid, date] as const,
  timeline: (pid: Pid, kind?: TimelineKind) => ['timeline', pid, kind ?? 'all'] as const,
  observations: (pid: Pid, code: string) => ['observations', pid, code] as const,
  conversations: (pid: Pid) => ['conversations', pid] as const,
  conversation: (cid: string | undefined) => ['conversation', cid] as const,
  documents: (pid: Pid) => ['documents', pid] as const,
  emergency: (pid: Pid) => ['emergency', pid] as const,
}

const q = (params: Record<string, string | undefined>) => {
  const s = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => !!e[1])).toString()
  return s ? `?${s}` : ''
}

/** Public: the lock screen and the profile switcher. */
export const useProfiles = () =>
  useQuery({ queryKey: keys.profiles, queryFn: ({ signal }) => api.get<ProfileListItem[]>('/profiles', signal) })

export const useSummary = (pid: Pid) =>
  useQuery({ queryKey: keys.summary(pid), enabled: pid != null, queryFn: ({ signal }) => api.get<Summary>(`/profiles/${pid}/summary`, signal) })

export const useCards = (pid: Pid) =>
  useQuery({ queryKey: keys.cards(pid), enabled: pid != null, queryFn: ({ signal }) => api.get<WalletCard[]>(`/profiles/${pid}/cards`, signal) })

export const useMeds = (pid: Pid, date: string) =>
  useQuery({ queryKey: keys.meds(pid, date), enabled: pid != null, queryFn: ({ signal }) => api.get<MedsDay>(`/profiles/${pid}/meds${q({ date })}`, signal) })

export const useTimeline = (pid: Pid, kind?: TimelineKind) =>
  useQuery({ queryKey: keys.timeline(pid, kind), enabled: pid != null, queryFn: ({ signal }) => api.get<TimelineItem[]>(`/profiles/${pid}/timeline${q({ kind })}`, signal) })

export const useObservations = (pid: Pid, code: string) =>
  useQuery({ queryKey: keys.observations(pid, code), enabled: pid != null && !!code, queryFn: ({ signal }) => api.get<Observation[]>(`/profiles/${pid}/observations${q({ code })}`, signal) })

export const useConversations = (pid: Pid) =>
  useQuery({ queryKey: keys.conversations(pid), enabled: pid != null, queryFn: ({ signal }) => api.get<ConversationItem[]>(`/profiles/${pid}/conversations`, signal) })

export const useConversation = (cid: string | undefined) =>
  useQuery({ queryKey: keys.conversation(cid), enabled: !!cid, queryFn: ({ signal }) => api.get<Conversation>(`/conversations/${cid}`, signal) })

export const useDocuments = (pid: Pid) =>
  useQuery({ queryKey: keys.documents(pid), enabled: pid != null, queryFn: ({ signal }) => api.get<DocumentItem[]>(`/profiles/${pid}/documents`, signal) })

/** Public: the emergency card a responder reads without unlocking. */
export const useEmergency = (pid: Pid) =>
  useQuery({ queryKey: keys.emergency(pid), enabled: pid != null, queryFn: ({ signal }) => api.get<EmergencyCard>(`/emergency/${pid}`, signal) })

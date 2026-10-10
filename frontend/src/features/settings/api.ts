// Task 15 endpoints: settings overview, profile, family history and the access log.
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Profile } from '../../api/types'

type Pid = number | null | undefined

export type Representative = { id: number; name: string; relation: string | null }
export type SettingsInfo = {
  actor: string
  role: 'owner' | 'representative'
  representatives: Representative[]
  emergency_fields: string[]
  has_biometric: boolean
}
export type FamilyItem = { id: number; relation: string; condition: string }
export type AccessLogRow = { actor: string; action: string; target: string | null; at: string }

export const EMERGENCY_FIELDS = ['photo', 'age', 'blood_type', 'allergies', 'conditions', 'meds', 'contacts', 'doctor', 'philhealth_last4'] as const

export const settingsKeys = {
  settings: (pid: Pid) => ['settings', pid] as const,
  profile: (pid: Pid) => ['profile', pid] as const,
  family: (pid: Pid) => ['family', pid] as const,
  accessLog: (pid: Pid) => ['accessLog', pid] as const,
}

export const useSettingsInfo = (pid: Pid) =>
  useQuery({ queryKey: settingsKeys.settings(pid), enabled: pid != null, queryFn: ({ signal }) => api.get<SettingsInfo>(`/profiles/${pid}/settings`, signal) })

export const useProfile = (pid: Pid) =>
  useQuery({ queryKey: settingsKeys.profile(pid), enabled: pid != null, queryFn: ({ signal }) => api.get<Profile>(`/profiles/${pid}`, signal) })

export const useFamilyHistory = (pid: Pid) =>
  useQuery({ queryKey: settingsKeys.family(pid), enabled: pid != null, queryFn: ({ signal }) => api.get<FamilyItem[]>(`/profiles/${pid}/family-history`, signal) })

export const useAccessLog = (pid: Pid, enabled: boolean) =>
  useQuery({ queryKey: settingsKeys.accessLog(pid), enabled: pid != null && enabled, staleTime: 0, queryFn: ({ signal }) => api.get<AccessLogRow[]>('/access-log', signal) })

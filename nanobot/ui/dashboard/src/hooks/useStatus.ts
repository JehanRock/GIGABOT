import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useStatus() {
  return useQuery({
    queryKey: ['status'],
    queryFn: () => api.getStatus(),
    refetchInterval: 30000, // 30 seconds
  })
}

export function useTracking() {
  return useQuery({
    queryKey: ['tracking'],
    queryFn: () => api.getTracking(),
    refetchInterval: 10000, // 10 seconds
  })
}

export function useConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: () => api.getConfig(),
    staleTime: 60000, // 1 minute
  })
}

export function useMemory() {
  return useQuery({
    queryKey: ['memory'],
    queryFn: () => api.getMemory(),
    refetchInterval: 60000, // 1 minute
  })
}

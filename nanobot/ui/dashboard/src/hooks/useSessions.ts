import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useSessions() {
  return useQuery({
    queryKey: ['sessions'],
    queryFn: () => api.getSessions(),
    refetchInterval: 15000, // 15 seconds
  })
}

export function useSession(key: string) {
  return useQuery({
    queryKey: ['session', key],
    queryFn: () => api.getSession(key),
    enabled: !!key,
  })
}

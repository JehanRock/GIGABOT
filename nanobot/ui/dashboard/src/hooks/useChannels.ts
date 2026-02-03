import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useChannels() {
  return useQuery({
    queryKey: ['channels'],
    queryFn: () => api.getChannels(),
    refetchInterval: 10000, // 10 seconds
  })
}

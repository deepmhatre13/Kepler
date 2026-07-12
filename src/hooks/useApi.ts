/**
 * React Query hooks — all backed by real API endpoints
 * No mock data. Returns live data from the production backend.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';


export function useSpaceSummary() {
  return useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: () => api.getDashboardSummary(),
    refetchInterval: 30_000,
  });
}


export function useCatalogObjects(params: Parameters<typeof api.getCatalogObjects>[0] = {}) {
  return useQuery({
    queryKey: ['catalog', 'objects', params],
    queryFn: () => api.getCatalogObjects(params),
    refetchInterval: 5 * 60_000, 
    placeholderData: (prev) => prev,
  });
}

export function useCatalogStats() {
  return useQuery({
    queryKey: ['catalog', 'stats'],
    queryFn: () => api.getCatalogStats(),
    refetchInterval: 5 * 60_000,
  });
}

export function useCatalogSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (group?: string) => api.triggerCatalogSync(group),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['catalog'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}


export function useCollisions(params: Parameters<typeof api.getCollisions>[0] = {}) {
  return useQuery({
    queryKey: ['collisions', params],
    queryFn: () => api.getCollisions(params),
    refetchInterval: 60_000,
    placeholderData: (prev) => prev,
  });
}

export function useCollisionEvaluate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerCollisionEvaluation(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['collisions'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function useUpdateCollisionStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api.acknowledgeCollision(id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['collisions'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}


export function useSatellites(params: Parameters<typeof api.getSatellites>[0] = {}) {
  return useQuery({
    queryKey: ['satellites', params],
    queryFn: () => api.getSatellites(params),
    refetchInterval: 2 * 60_000,
    placeholderData: (prev) => prev,
  });
}

export function useSatelliteTelemetry(satelliteId: number | null) {
  return useQuery({
    queryKey: ['satellites', 'telemetry', satelliteId],
    queryFn: () => api.getSatelliteTelemetry(satelliteId!),
    enabled: satelliteId !== null,
    refetchInterval: 30_000,
  });
}


export function useAgentRuns(params: Parameters<typeof api.getAgentRuns>[0] = {}) {
  return useQuery({
    queryKey: ['agents', 'runs', params],
    queryFn: () => api.getAgentRuns(params),
    refetchInterval: 15_000,
    placeholderData: (prev) => prev,
  });
}

export function useTriggerAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (collisionId: number) => api.triggerAgentWorkflow(collisionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['agents'] });
    },
  });
}


export function useWeatherStatus() {
  return useQuery({
    queryKey: ['weather', 'status'],
    queryFn: () => api.getWeatherStatus(),
    refetchInterval: 15 * 60_000, 
    staleTime: 10 * 60_000,
  });
}

export function useWeatherHistory(params: Parameters<typeof api.getWeatherHistory>[0] = {}) {
  return useQuery({
    queryKey: ['weather', 'history', params],
    queryFn: () => api.getWeatherHistory(params),
    placeholderData: (prev) => prev,
  });
}

export function useWeatherSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerWeatherSync(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['weather'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/**
 * Centralized API Client — Kepler AI
 * All requests go to the FastAPI backend at http://localhost:8000/api/v1
 */

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';

export interface APIResponse<T> {
  success: boolean;
  message: string;
  data: T | null;
  pagination?: {
    page: number;
    size: number;
    total: number;
    pages: number;
  };
  metadata?: Record<string, unknown>;
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<APIResponse<T>> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}


export const api = {
  
  getDashboardSummary: () =>
    apiFetch<DashboardSummary>('/dashboard/summary'),

  
  getCatalogObjects: (params: CatalogParams = {}) => {
    const q = new URLSearchParams();
    if (params.page)           q.set('page', String(params.page));
    if (params.size)           q.set('size', String(params.size));
    if (params.classification) q.set('classification', params.classification);
    if (params.search)         q.set('search', params.search);
    return apiFetch<SpaceObject[]>(`/catalog/objects?${q}`);
  },

  getCatalogStats: () =>
    apiFetch<CatalogStats>('/catalog/stats'),

  getCatalogObjectByNorad: (catalogNumber: string) =>
    apiFetch<SpaceObject>(`/catalog/objects/${catalogNumber}`),

  
  triggerCatalogSync: (group?: string) => {
    const q = group ? `?group=${group}` : '';
    return apiFetch<{ upserted: number }>(`/catalog/sync${q}`, { method: 'POST' });
  },

  
  getCollisions: (params: CollisionParams = {}) => {
    const q = new URLSearchParams();
    if (params.page)      q.set('page', String(params.page));
    if (params.size)      q.set('size', String(params.size));
    if (params.risk_level) q.set('risk_level', params.risk_level);
    if (params.status)    q.set('status', params.status);
    return apiFetch<Collision[]>(`/collisions?${q}`);
  },

  acknowledgeCollision: (id: number, status: string) =>
    apiFetch<Collision>(`/collisions/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  
  getSatellites: (params: { page?: number; size?: number; search?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.page)   q.set('page', String(params.page));
    if (params.size)   q.set('size', String(params.size));
    if (params.search) q.set('search', params.search);
    return apiFetch<Satellite[]>(`/satellites?${q}`);
  },

  getSatelliteTelemetry: (id: number) =>
    apiFetch<TelemetryPoint[]>(`/satellites/${id}/telemetry`),

  
  getAgentRuns: (params: { page?: number; size?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.page) q.set('page', String(params.page));
    if (params.size) q.set('size', String(params.size));
    return apiFetch<AgentRun[]>(`/agents/runs?${q}`);
  },

  triggerAgentWorkflow: (collisionId: number) =>
    apiFetch<{ run_id: number; status: string }>(`/agents/trigger/${collisionId}`, {
      method: 'POST',
    }),

  
  getWeatherStatus: () =>
    apiFetch<WeatherStatus>('/weather/status'),

  getWeatherHistory: (params: { page?: number; size?: number; event_type?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.page)       q.set('page', String(params.page));
    if (params.size)       q.set('size', String(params.size));
    if (params.event_type) q.set('event_type', params.event_type);
    return apiFetch<WeatherEvent[]>(`/weather/history?${q}`);
  },

  getWeatherAll: (days = 7) =>
    apiFetch<WeatherAll>(`/weather/all?days=${days}`),

  triggerWeatherSync: () =>
    apiFetch<{ synced_at: string }>('/weather/sync', { method: 'POST' }),

  triggerCollisionEvaluation: () =>
    apiFetch<any>('/collisions/evaluate', { method: 'POST' }),
};



export interface DashboardSummary {
  tracked_satellites: number;
  debris_objects: number;
  active_alerts_count: number;
  predicted_collisions_count: number;
  active_agents_load: number;
  space_weather_index: string;
  system_status: string;
}

export interface CatalogParams {
  page?: number;
  size?: number;
  classification?: 'PAYLOAD' | 'DEBRIS' | 'ROCKET_BODY' | 'UNKNOWN';
  search?: string;
}

export interface CatalogStats {
  total: number;
  payloads: number;
  debris: number;
  rocket_bodies: number;
  unknown: number;
  last_sync: string;
}

export interface SpaceObject {
  id: number;
  name: string;
  catalog_number: string;
  cospar_id: string | null;
  classification: 'PAYLOAD' | 'DEBRIS' | 'ROCKET_BODY' | 'UNKNOWN';
  epoch: string | null;
  inclination: number | null;
  eccentricity: number | null;
  semimajor_axis: number | null;
  raan: number | null;
  arg_of_perigee: number | null;
  mean_anomaly: number | null;
  mean_motion: number | null;
  period: number | null;
  has_tle: boolean;
  updated_at: string | null;
}

export interface CollisionParams {
  page?: number;
  size?: number;
  risk_level?: string;
  status?: string;
}

export interface Collision {
  id: number;
  object_a: { id: number; name: string; catalog_number: string } | null;
  object_b: { id: number; name: string; catalog_number: string } | null;
  probability: number;
  tca: string;
  miss_distance_m: number;
  relative_velocity_kms: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  status: 'PENDING' | 'MITIGATED' | 'ASSESSED' | 'IGNORED';
  created_at: string;
}

export interface Satellite {
  id: number;
  status: string;
  fuel_percentage: number;
  operational_mode: string;
  space_object: SpaceObject;
}

export interface TelemetryPoint {
  timestamp: string;
  altitude_km: number;
  velocity_kms: number;
  temperature_c: number | null;
  battery_charge: number | null;
  neural_load: number | null;
}

export interface AgentRun {
  id: number;
  workflow_name: string;
  status: 'RUNNING' | 'COMPLETED' | 'FAILED';
  current_step: string | null;
  started_at: string;
  completed_at: string | null;
  decisions: AgentDecision[];
}

export interface AgentDecision {
  id: number;
  agent_name: string;
  action_taken: string;
  reasoning: string;
  decision_metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface WeatherStatus {
  overall_severity: 'NORMAL' | 'MODERATE' | 'EXTREME';
  kp_index: number;
  active_cme_count: number;
  active_flare_count: number;
  active_storm_count: number;
  active_radiation_count: number;
  events: {
    cme: WeatherEvent[];
    solar_flares: WeatherEvent[];
    geomagnetic_storms: WeatherEvent[];
    radiation_events: WeatherEvent[];
  };
  fetched_at: string;
  source: string;
}

export interface WeatherEvent {
  type: string;
  event_type: string;
  activity_id: string;
  severity: string;
  note: string;
  start_time?: string;
  class_type?: string;
  kp_index?: number;
  speed_kms?: number;
}

export interface WeatherAll {
  cme: WeatherEvent[];
  solar_flares: WeatherEvent[];
  geomagnetic_storms: WeatherEvent[];
  radiation_events: WeatherEvent[];
}

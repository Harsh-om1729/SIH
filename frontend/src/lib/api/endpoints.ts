import { safeFetch, ApiResponse } from './client';
import { Incident, mockIncidents } from '@/lib/mockIncidents';
import { Zone } from '@/lib/mockZones';
import { WatchlistPerson, initialMockWatchlist } from '@/lib/mockWatchlist';
import {
  ThresholdSettings,
  IntegrationSettings,
  loadThresholdSettings,
  loadIntegrationSettings,
} from '@/lib/settingsState';

export interface ApiCamera {
  id: string;
  name: string;
  location: string;
  sector: string;
  streamUrl?: string;
  fps: string;
  activity: string;
  isActive: boolean;
  resolution?: string;
}

// 1. Cameras Endpoints
export const camerasApi = {
  async getCameras(fallback: ApiCamera[]): Promise<ApiResponse<ApiCamera[]>> {
    return safeFetch<ApiCamera[]>('/cameras', { method: 'GET' }, fallback);
  },

  async addCamera(camera: ApiCamera): Promise<ApiResponse<ApiCamera>> {
    return safeFetch<ApiCamera>(
      '/cameras',
      {
        method: 'POST',
        body: JSON.stringify(camera),
      },
      camera
    );
  },

  async deleteCamera(id: string): Promise<ApiResponse<{ success: boolean; id: string }>> {
    return safeFetch<{ success: boolean; id: string }>(
      `/cameras/${id}`,
      { method: 'DELETE' },
      { success: true, id }
    );
  },
};

// 2. Incidents Endpoints
export const incidentsApi = {
  async getIncidents(fallback: Incident[] = mockIncidents): Promise<ApiResponse<Incident[]>> {
    return safeFetch<Incident[]>('/incidents', { method: 'GET' }, fallback);
  },

  async getIncident(id: number, fallback?: Incident): Promise<ApiResponse<Incident>> {
    return safeFetch<Incident>(
      `/incidents/${id}`,
      { method: 'GET' },
      fallback || mockIncidents.find((i) => i.id === id) || mockIncidents[0]
    );
  },

  async acknowledgeIncident(id: number): Promise<ApiResponse<{ success: boolean; id: number }>> {
    return safeFetch<{ success: boolean; id: number }>(
      `/incidents/${id}/acknowledge`,
      { method: 'POST' },
      { success: true, id }
    );
  },
};

// 3. Zones Endpoints
export const zonesApi = {
  async getZones(fallback: Record<string, Zone[]>): Promise<ApiResponse<Record<string, Zone[]>>> {
    return safeFetch<Record<string, Zone[]>>('/zones', { method: 'GET' }, fallback);
  },

  async saveZones(
    zones: Record<string, Zone[]>
  ): Promise<ApiResponse<Record<string, Zone[]>>> {
    return safeFetch<Record<string, Zone[]>>(
      '/zones',
      {
        method: 'PUT',
        body: JSON.stringify(zones),
      },
      zones
    );
  },
};

// 4. Watchlist Endpoints
export const watchlistApi = {
  async getWatchlist(
    fallback: WatchlistPerson[] = initialMockWatchlist
  ): Promise<ApiResponse<WatchlistPerson[]>> {
    return safeFetch<WatchlistPerson[]>('/watchlist', { method: 'GET' }, fallback);
  },

  async enrollPerson(
    person: WatchlistPerson
  ): Promise<ApiResponse<WatchlistPerson>> {
    return safeFetch<WatchlistPerson>(
      '/watchlist',
      {
        method: 'POST',
        body: JSON.stringify(person),
      },
      person
    );
  },

  async deletePerson(id: number): Promise<ApiResponse<{ success: boolean; id: number }>> {
    return safeFetch<{ success: boolean; id: number }>(
      `/watchlist/${id}`,
      { method: 'DELETE' },
      { success: true, id }
    );
  },
};

// 5. Settings Endpoints
export const settingsApi = {
  async getSettings(): Promise<
    ApiResponse<{ thresholds: ThresholdSettings; integrations: IntegrationSettings }>
  > {
    const fallback = {
      thresholds: loadThresholdSettings(),
      integrations: loadIntegrationSettings(),
    };
    return safeFetch<{ thresholds: ThresholdSettings; integrations: IntegrationSettings }>(
      '/settings',
      { method: 'GET' },
      fallback
    );
  },

  async updateThresholds(
    thresholds: ThresholdSettings
  ): Promise<ApiResponse<ThresholdSettings>> {
    return safeFetch<ThresholdSettings>(
      '/settings/thresholds',
      {
        method: 'PUT',
        body: JSON.stringify(thresholds),
      },
      thresholds
    );
  },

  async updateIntegrations(
    integrations: IntegrationSettings
  ): Promise<ApiResponse<IntegrationSettings>> {
    return safeFetch<IntegrationSettings>(
      '/settings/integrations',
      {
        method: 'PUT',
        body: JSON.stringify(integrations),
      },
      integrations
    );
  },
};

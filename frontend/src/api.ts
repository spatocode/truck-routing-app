import type { Place, PlanResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function readError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (payload?.detail) return String(payload.detail);
  } catch {
    /* ignore */
  }
  return `Request failed (${response.status})`;
}

export async function searchPlaces(query: string): Promise<Place[]> {
  const response = await fetch(`${API_BASE}/api/geocode?q=${encodeURIComponent(query)}`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function planTrip(input: {
  origin: string;
  destination: string;
  origin_lat?: number;
  origin_lon?: number;
  destination_lat?: number;
  destination_lon?: number;
  departure: string;
  load_lb: number;
  sample_miles: number;
}): Promise<PlanResponse> {
  const response = await fetch(`${API_BASE}/api/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

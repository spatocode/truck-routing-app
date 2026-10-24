export type RiskLabel = "low" | "moderate" | "high" | "severe" | "no_travel";

export interface Place {
  label: string;
  lat: number;
  lon: number;
}

export interface RiskInfo {
  level: RiskLabel;
  score: number;
  wind: RiskLabel;
  rain: RiskLabel;
  snow: RiskLabel;
  factors: string[];
}

export interface Checkpoint {
  lat: number;
  lon: number;
  mile: number;
  eta: string;
  weather_time: string;
  forecast_clipped: boolean;
  wind_mph: number;
  rain_in_hr: number;
  snow_in_hr: number;
  temp_f: number | null;
  weather_code: number | null;
  risk: RiskInfo;
  segment_miles: number;
}

export interface RouteSegment {
  from_mile: number;
  to_mile: number;
  risk: RiskLabel;
  score: number;
  coordinates: number[][];
}

export interface RouteStats {
  no_travel_miles: number;
  severe_miles: number;
  high_miles: number;
  moderate_miles: number;
  low_miles: number;
  avg_risk: number;
  total_miles: number;
}

export interface PlannedRoute {
  id: string;
  summary: string;
  source: string;
  distance_miles: number;
  duration_seconds: number;
  geometry: { type: "LineString"; coordinates: number[][] };
  checkpoints: Checkpoint[];
  segments: RouteSegment[];
  stats: RouteStats;
}

export interface PlanResponse {
  origin: Place;
  destination: Place;
  departure: string;
  load_lb: number;
  sample_miles: number;
  recommended_route_id: string;
  recommendation_reason: string;
  routes: PlannedRoute[];
  heatmap: {
    hours: string[];
    points: { lat: number; lon: number; scores: number[] }[];
  };
  legend: RiskLabel[];
}

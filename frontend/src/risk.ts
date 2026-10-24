import type { RiskLabel } from "./types";

export const RISK_COLORS: Record<RiskLabel, string> = {
  low: "#3dd68c",
  moderate: "#e7c04a",
  high: "#f08a3a",
  severe: "#e24b4b",
  no_travel: "#8b5cf6",
};

export const RISK_ORDER: RiskLabel[] = ["low", "moderate", "high", "severe", "no_travel"];

export const RISK_LABELS: Record<RiskLabel, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  severe: "Severe",
  no_travel: "No travel",
};

export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  if (hours <= 0) return `${minutes} min`;
  return `${hours} h ${minutes.toString().padStart(2, "0")} m`;
}

export function formatClock(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function defaultDepartureValue(): string {
  const date = new Date();
  date.setMinutes(0, 0, 0);
  const pad = (value: number) => value.toString().padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

from __future__ import annotations

from dataclasses import dataclass

from planner.risk import RiskLevel


@dataclass
class RouteStats:
    no_travel_miles: float = 0.0
    severe_miles: float = 0.0
    high_miles: float = 0.0
    moderate_miles: float = 0.0
    low_miles: float = 0.0
    risk_mile_sum: float = 0.0
    total_miles: float = 0.0

    def add_segment(self, miles: float, level: RiskLevel) -> None:
        if miles <= 0:
            return
        self.total_miles += miles
        self.risk_mile_sum += miles * int(level)
        bucket = {
            RiskLevel.NO_TRAVEL: "no_travel_miles",
            RiskLevel.SEVERE: "severe_miles",
            RiskLevel.HIGH: "high_miles",
            RiskLevel.MODERATE: "moderate_miles",
            RiskLevel.LOW: "low_miles",
        }[level]
        setattr(self, bucket, getattr(self, bucket) + miles)

    @property
    def avg_risk(self) -> float:
        if self.total_miles <= 0:
            return float(RiskLevel.LOW)
        return self.risk_mile_sum / self.total_miles

    def as_dict(self) -> dict:
        return {
            "no_travel_miles": round(self.no_travel_miles, 1),
            "severe_miles": round(self.severe_miles, 1),
            "high_miles": round(self.high_miles, 1),
            "moderate_miles": round(self.moderate_miles, 1),
            "low_miles": round(self.low_miles, 1),
            "avg_risk": round(self.avg_risk, 2),
            "total_miles": round(self.total_miles, 1),
        }


@dataclass
class RankedRoute:
    route_id: str
    stats: RouteStats
    duration_seconds: float

    @property
    def rank_key(self) -> tuple:
        return (
            round(self.stats.no_travel_miles, 1),
            round(self.stats.severe_miles, 1),
            round(self.stats.high_miles, 1),
            round(self.stats.avg_risk, 3),
            round(self.duration_seconds),
        )


def rank_routes(routes: list[RankedRoute]) -> list[RankedRoute]:
    return sorted(routes, key=lambda route: route.rank_key)


def recommendation_reason(ordered: list[RankedRoute]) -> str:
    if not ordered:
        return "No routes available."
    best = ordered[0]
    if len(ordered) == 1:
        return "Only one viable corridor was returned."

    others = ordered[1:]
    if best.stats.no_travel_miles + 0.1 < min(route.stats.no_travel_miles for route in others):
        return (
            f"Recommended because it has the fewest no-travel miles "
            f"({best.stats.no_travel_miles:.0f} vs "
            f"{min(route.stats.no_travel_miles for route in others):.0f}+ on the alternatives)."
        )
    if best.stats.severe_miles + 0.1 < min(route.stats.severe_miles for route in others):
        return (
            f"Recommended because it has the fewest severe miles "
            f"({best.stats.severe_miles:.0f} vs "
            f"{min(route.stats.severe_miles for route in others):.0f}+ on the alternatives)."
        )
    if best.stats.high_miles + 0.1 < min(route.stats.high_miles for route in others):
        return (
            f"Recommended because it has the fewest high-risk miles "
            f"({best.stats.high_miles:.0f} vs "
            f"{min(route.stats.high_miles for route in others):.0f}+ on the alternatives)."
        )
    if best.stats.avg_risk + 0.02 < min(route.stats.avg_risk for route in others):
        return (
            f"Recommended because it has the lowest average weather risk "
            f"({best.stats.avg_risk:.2f} vs "
            f"{min(route.stats.avg_risk for route in others):.2f}+ on the alternatives)."
        )
    return (
        f"Weather exposure is similar across options, so the shorter drive was selected "
        f"({best.duration_seconds / 3600:.1f} h)."
    )

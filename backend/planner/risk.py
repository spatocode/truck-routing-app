from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 1
    MODERATE = 2
    HIGH = 3
    SEVERE = 4
    NO_TRAVEL = 5

    @property
    def label(self) -> str:
        return {
            RiskLevel.LOW: "low",
            RiskLevel.MODERATE: "moderate",
            RiskLevel.HIGH: "high",
            RiskLevel.SEVERE: "severe",
            RiskLevel.NO_TRAVEL: "no_travel",
        }[self]


RISK_BY_LABEL = {level.label: level for level in RiskLevel}


def wind_risk(mph: float) -> RiskLevel:
    if mph < 25:
        return RiskLevel.LOW
    if mph < 35:
        return RiskLevel.MODERATE
    if mph < 45:
        return RiskLevel.HIGH
    if mph < 55:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def rain_risk(inches_per_hour: float) -> RiskLevel:
    if inches_per_hour < 0.10:
        return RiskLevel.LOW
    if inches_per_hour <= 0.25:
        return RiskLevel.MODERATE
    if inches_per_hour <= 0.50:
        return RiskLevel.HIGH
    if inches_per_hour <= 1.00:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def snow_risk(inches_per_hour: float) -> RiskLevel:
    if inches_per_hour < 0.5:
        return RiskLevel.LOW
    if inches_per_hour <= 1.0:
        return RiskLevel.MODERATE
    if inches_per_hour <= 2.0:
        return RiskLevel.HIGH
    if inches_per_hour <= 3.0:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def apply_load_rules(wind_mph: float, load_lb: float, current: RiskLevel) -> tuple[RiskLevel, str | None]:
    if wind_mph >= 55:
        return RiskLevel.NO_TRAVEL, "Wind ≥55 mph: no travel for any load"
    if 45 <= wind_mph < 55 and load_lb > 30_000:
        return RiskLevel.NO_TRAVEL, "Wind 45–54 mph with load over 30,000 lb: no travel"
    if 35 <= wind_mph < 45 and load_lb > 40_000:
        upgraded = current if current.value > RiskLevel.SEVERE.value else RiskLevel.SEVERE
        return upgraded, "Wind 35–44 mph with load over 40,000 lb: severe"
    return current, None


@dataclass(frozen=True)
class WeatherObservation:
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float
    temp_f: float | None = None
    weather_code: int | None = None


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    wind: RiskLevel
    rain: RiskLevel
    snow: RiskLevel
    factors: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "level": self.level.label,
            "score": int(self.level),
            "wind": self.wind.label,
            "rain": self.rain.label,
            "snow": self.snow.label,
            "factors": list(self.factors),
        }


def assess_weather(obs: WeatherObservation, load_lb: float) -> RiskAssessment:
    wind = wind_risk(obs.wind_mph)
    rain = rain_risk(obs.rain_in_hr)
    snow = snow_risk(obs.snow_in_hr)
    weather_level = max(wind, rain, snow, key=lambda level: level.value)

    factors: list[str] = []
    if wind is not RiskLevel.LOW:
        factors.append(f"Wind {obs.wind_mph:.0f} mph ({wind.label.replace('_', ' ')})")
    if rain is not RiskLevel.LOW:
        factors.append(f"Rain {obs.rain_in_hr:.2f} in/hr ({rain.label.replace('_', ' ')})")
    if snow is not RiskLevel.LOW:
        factors.append(f"Snow {obs.snow_in_hr:.1f} in/hr ({snow.label.replace('_', ' ')})")

    level, load_note = apply_load_rules(obs.wind_mph, load_lb, weather_level)
    if load_note:
        factors.append(load_note)
    if not factors:
        factors.append("Clear of wind, rain, and snow thresholds")

    return RiskAssessment(level=level, wind=wind, rain=rain, snow=snow, factors=tuple(factors))

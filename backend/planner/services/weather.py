from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from django.conf import settings

from planner.geo import LatLon
from planner.risk import WeatherObservation
from planner.services.http import client

BATCH_SIZE = 40
FORECAST_HOURS = 48


@dataclass
class HourlySeries:
    times: list[datetime]
    wind_mph: list[float]
    rain_in_hr: list[float]
    snow_in_hr: list[float]
    temp_f: list[float | None]
    weather_code: list[int | None]


def _parse_hour(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1]
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _cm_to_inches(cm: float) -> float:
    return cm / 2.54


def _series_from_block(block: dict) -> HourlySeries:
    hourly = block.get("hourly") or {}
    times = [_parse_hour(item) for item in hourly.get("time") or []]
    wind = [float(value or 0) for value in hourly.get("wind_speed_10m") or []]
    rain = [float(value or 0) for value in hourly.get("rain") or []]
    snow_cm = [float(value or 0) for value in hourly.get("snowfall") or []]
    temps_c = hourly.get("temperature_2m") or []
    codes = hourly.get("weather_code") or []
    count = len(times)
    return HourlySeries(
        times=times[:count],
        wind_mph=(wind + [0.0] * count)[:count],
        rain_in_hr=(rain + [0.0] * count)[:count],
        snow_in_hr=([_cm_to_inches(value) for value in snow_cm] + [0.0] * count)[:count],
        temp_f=[
            None if index >= len(temps_c) or temps_c[index] is None else (float(temps_c[index]) * 9 / 5) + 32
            for index in range(count)
        ],
        weather_code=[
            None if index >= len(codes) or codes[index] is None else int(codes[index])
            for index in range(count)
        ],
    )


def fetch_hourly(points: list[LatLon]) -> list[HourlySeries]:
    if not points:
        return []

    series: list[HourlySeries] = []
    with client() as http:
        for start in range(0, len(points), BATCH_SIZE):
            batch = points[start : start + BATCH_SIZE]
            params = {
                "latitude": ",".join(f"{point.lat:.4f}" for point in batch),
                "longitude": ",".join(f"{point.lon:.4f}" for point in batch),
                "hourly": "wind_speed_10m,rain,snowfall,temperature_2m,weather_code",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "forecast_days": "7",
                "timezone": "UTC",
            }
            response = http.get(settings.OPEN_METEO_URL, params=params)
            response.raise_for_status()
            payload = response.json()
            blocks = payload if isinstance(payload, list) else [payload]
            if len(blocks) != len(batch):
                raise RuntimeError("Weather API returned an unexpected number of locations.")
            series.extend(_series_from_block(block) for block in blocks)
    return series


def observation_at(series: HourlySeries, when: datetime) -> tuple[WeatherObservation, datetime, bool]:
    if not series.times:
        raise RuntimeError("Weather series is empty.")
    when = when.astimezone(timezone.utc)
    best_index = min(range(len(series.times)), key=lambda index: abs((series.times[index] - when).total_seconds()))
    clipped = when < series.times[0] or when > series.times[-1]
    obs = WeatherObservation(
        wind_mph=series.wind_mph[best_index],
        rain_in_hr=series.rain_in_hr[best_index],
        snow_in_hr=series.snow_in_hr[best_index],
        temp_f=series.temp_f[best_index],
        weather_code=series.weather_code[best_index],
    )
    return obs, series.times[best_index], clipped


def slider_hours(series: HourlySeries, now: datetime) -> list[datetime]:
    now = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end = now.timestamp() + FORECAST_HOURS * 3600
    hours = [stamp for stamp in series.times if now.timestamp() - 1800 <= stamp.timestamp() <= end]
    if hours:
        return hours[: FORECAST_HOURS + 1]
    return series.times[: FORECAST_HOURS + 1]


def observation_at_index(series: HourlySeries, index: int) -> WeatherObservation:
    index = min(max(index, 0), len(series.times) - 1)
    return WeatherObservation(
        wind_mph=series.wind_mph[index],
        rain_in_hr=series.rain_in_hr[index],
        snow_in_hr=series.snow_in_hr[index],
        temp_f=series.temp_f[index],
        weather_code=series.weather_code[index],
    )

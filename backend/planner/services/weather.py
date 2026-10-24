from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone

from django.conf import settings

from planner.geo import LatLon
from planner.risk import WeatherObservation
from planner.services.http import client

BATCH_SIZE = 8
FORECAST_HOURS = 48
SINGLE_WORKERS = 8

logger = logging.getLogger(__name__)


class WeatherError(Exception):
    pass


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
    if count == 0:
        raise WeatherError("Weather API returned a location with no hourly forecast.")
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


def blocks_from_payload(payload, expected: int) -> list[dict]:
    if isinstance(payload, dict) and payload.get("error"):
        raise WeatherError(str(payload.get("reason") or "Weather API error"))
    if isinstance(payload, list):
        if len(payload) == expected:
            return payload
        if expected == 1 and payload:
            return [payload[0]]
        raise WeatherError(f"Weather API returned {len(payload)} locations, expected {expected}.")
    if isinstance(payload, dict):
        if expected == 1:
            return [payload]
        raise WeatherError("Weather API did not return one forecast per sampled location.")
    raise WeatherError("Weather API returned an unexpected response.")


def _forecast_params(batch: list[LatLon]) -> dict:
    return {
        "latitude": ",".join(f"{point.lat:.4f}" for point in batch),
        "longitude": ",".join(f"{point.lon:.4f}" for point in batch),
        "hourly": "wind_speed_10m,rain,snowfall,temperature_2m,weather_code",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "forecast_days": "7",
        "timezone": "UTC",
    }


def _fetch_batch(http, batch: list[LatLon]) -> list[HourlySeries]:
    response = http.get(settings.OPEN_METEO_URL, params=_forecast_params(batch))
    try:
        payload = response.json()
    except Exception as exc:
        raise WeatherError("Weather API returned a non-JSON response.") from exc
    if response.status_code >= 400:
        reason = payload.get("reason") if isinstance(payload, dict) else None
        raise WeatherError(reason or f"Weather API HTTP {response.status_code}")
    blocks = blocks_from_payload(payload, expected=len(batch))
    return [_series_from_block(block) for block in blocks]


def _fetch_one(point: LatLon) -> HourlySeries:
    with client() as http:
        return _fetch_batch(http, [point])[0]


def _fetch_singles(points: list[LatLon]) -> list[HourlySeries]:
    ordered: list[HourlySeries | None] = [None] * len(points)
    workers = min(SINGLE_WORKERS, len(points)) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_one, point): index for index, point in enumerate(points)}
        for future in as_completed(futures):
            index = futures[future]
            ordered[index] = future.result()
    missing = [index for index, item in enumerate(ordered) if item is None]
    if missing:
        raise WeatherError("Weather API missed one or more sampled locations.")
    return [item for item in ordered if item is not None]


def fetch_hourly(points: list[LatLon]) -> list[HourlySeries]:
    if not points:
        return []

    series: list[HourlySeries] = []
    with client() as http:
        for start in range(0, len(points), BATCH_SIZE):
            batch = points[start : start + BATCH_SIZE]
            try:
                series.extend(_fetch_batch(http, batch))
            except WeatherError:
                logger.warning("Batch weather fetch failed for %s points; retrying one location at a time", len(batch))
                series.extend(_fetch_singles(batch))
    return series


def observation_at(series: HourlySeries, when: datetime) -> tuple[WeatherObservation, datetime, bool]:
    if not series.times:
        raise WeatherError("Weather series is empty.")
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

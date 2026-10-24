from __future__ import annotations

from datetime import datetime, timedelta, timezone

from planner.geo import LatLon, corridor_grid, haversine_miles, sample_along_path
from planner.recommend import RankedRoute, RouteStats, recommendation_reason, rank_routes
from planner.risk import RiskLevel, assess_weather
from planner.services.geocoding import geocode_one
from planner.services.routing import RawRoute, get_routes
from planner.services.weather import fetch_hourly, observation_at, observation_at_index, slider_hours


def _resolve_point(label: str | None, lat: float | None, lon: float | None) -> tuple[LatLon, str]:
    if lat is not None and lon is not None:
        point = LatLon(lat=lat, lon=lon)
        return point, (label or f"{lat:.4f}, {lon:.4f}")
    if not label:
        raise ValueError("A location name or coordinates are required.")
    return geocode_one(label)


def _eta_for_mile(departure: datetime, total_miles: float, duration_seconds: float, mile: float) -> datetime:
    if total_miles <= 0:
        return departure
    fraction = min(1.0, max(0.0, mile / total_miles))
    return departure + timedelta(seconds=duration_seconds * fraction)


def _cap_points(points: list[LatLon], limit: int = 72) -> list[LatLon]:
    if len(points) <= limit:
        return points
    step = max(1, round(len(points) / limit))
    return points[::step][:limit]


def _thin_points(points: list[LatLon], max_points: int = 220) -> list[LatLon]:
    if len(points) <= max_points:
        return points
    step = max(1, len(points) // max_points)
    sampled = points[::step]
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled


def _thin_coords(coords: list[list[float]], max_points: int = 48) -> list[list[float]]:
    if len(coords) <= max_points:
        return coords
    step = max(1, len(coords) // max_points)
    sampled = coords[::step]
    if sampled[-1] != coords[-1]:
        sampled.append(coords[-1])
    return sampled


def _segment_coordinates(points: list[LatLon], start_mile: float, end_mile: float) -> list[list[float]]:
    coords: list[list[float]] = []
    traveled = 0.0
    for a, b in zip(points, points[1:]):
        segment = haversine_miles(a, b)
        next_mile = traveled + segment
        if next_mile < start_mile - 0.01:
            traveled = next_mile
            continue
        if traveled > end_mile + 0.01:
            break
        if not coords:
            coords.append(a.as_lonlat())
        coords.append(b.as_lonlat())
        traveled = next_mile
    return coords


def plan_trip(
    *,
    origin_query: str | None,
    destination_query: str | None,
    origin_lat: float | None,
    origin_lon: float | None,
    dest_lat: float | None,
    dest_lon: float | None,
    departure: datetime,
    load_lb: float,
    sample_miles: int,
) -> dict:
    if sample_miles not in (10, 25, 50):
        raise ValueError("Sample interval must be 10, 25, or 50 miles.")
    if load_lb < 0:
        raise ValueError("Load weight must be zero or greater.")

    origin, origin_label = _resolve_point(origin_query, origin_lat, origin_lon)
    destination, destination_label = _resolve_point(destination_query, dest_lat, dest_lon)
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=timezone.utc)
    else:
        departure = departure.astimezone(timezone.utc)

    raw_routes = get_routes(origin, destination)
    route_samples: list[list[tuple[LatLon, float]]] = [
        sample_along_path(route.geometry, float(sample_miles)) for route in raw_routes
    ]
    heatmap_points = _cap_points(corridor_grid([route.geometry for route in raw_routes]), limit=72)

    weather_points: list[LatLon] = []
    for samples in route_samples:
        weather_points.extend(point for point, _mile in samples)
    weather_points.extend(heatmap_points)

    series_list = fetch_hourly(weather_points)
    checkpoint_cursor = 0
    now = datetime.now(timezone.utc)
    hour_axis = slider_hours(series_list[0], now) if series_list else []

    payload_routes = []
    ranked: list[RankedRoute] = []

    for index, (raw, samples) in enumerate(zip(raw_routes, route_samples), start=1):
        route_id = f"r{index}"
        stats = RouteStats()
        checkpoints = []
        sample_series = series_list[checkpoint_cursor : checkpoint_cursor + len(samples)]
        checkpoint_cursor += len(samples)

        for sample_index, ((point, mile), series) in enumerate(zip(samples, sample_series)):
            eta = _eta_for_mile(departure, raw.distance_miles, raw.duration_seconds, mile)
            obs, weather_at, clipped = observation_at(series, eta)
            assessment = assess_weather(obs, load_lb)
            next_mile = samples[sample_index + 1][1] if sample_index + 1 < len(samples) else raw.distance_miles
            segment_miles = max(0.0, next_mile - mile)
            stats.add_segment(segment_miles, assessment.level)
            checkpoints.append(
                {
                    "lat": point.lat,
                    "lon": point.lon,
                    "mile": round(mile, 1),
                    "eta": eta.isoformat(),
                    "weather_time": weather_at.isoformat(),
                    "forecast_clipped": clipped,
                    "wind_mph": round(obs.wind_mph, 1),
                    "rain_in_hr": round(obs.rain_in_hr, 3),
                    "snow_in_hr": round(obs.snow_in_hr, 3),
                    "temp_f": None if obs.temp_f is None else round(obs.temp_f, 1),
                    "weather_code": obs.weather_code,
                    "risk": assessment.as_dict(),
                    "segment_miles": round(segment_miles, 1),
                }
            )

        segments = []
        for checkpoint in checkpoints:
            end_mile = checkpoint["mile"] + checkpoint["segment_miles"]
            segments.append(
                {
                    "from_mile": checkpoint["mile"],
                    "to_mile": round(end_mile, 1),
                    "risk": checkpoint["risk"]["level"],
                    "score": checkpoint["risk"]["score"],
                    "coordinates": _thin_coords(_segment_coordinates(raw.geometry, checkpoint["mile"], end_mile)),
                }
            )

        payload_routes.append(
            {
                "id": route_id,
                "summary": raw.summary,
                "source": raw.source,
                "distance_miles": round(raw.distance_miles, 1),
                "duration_seconds": round(raw.duration_seconds),
                "geometry": {"type": "LineString", "coordinates": [point.as_lonlat() for point in _thin_points(raw.geometry)]},
                "checkpoints": checkpoints,
                "segments": segments,
                "stats": stats.as_dict(),
            }
        )
        ranked.append(RankedRoute(route_id=route_id, stats=stats, duration_seconds=raw.duration_seconds))

    ordered = rank_routes(ranked)
    recommended_id = ordered[0].route_id if ordered else None

    heatmap_series = series_list[checkpoint_cursor:]
    heatmap = {
        "hours": [stamp.isoformat() for stamp in hour_axis],
        "points": [],
    }
    for point, series in zip(heatmap_points, heatmap_series):
        time_index = {stamp.isoformat(): index for index, stamp in enumerate(series.times)}
        risks = []
        for stamp in hour_axis:
            idx = time_index.get(stamp.isoformat())
            if idx is None:
                obs, _, _ = observation_at(series, stamp)
            else:
                obs = observation_at_index(series, idx)
            assessment = assess_weather(obs, load_lb)
            risks.append(int(assessment.level))
        heatmap["points"].append({"lat": point.lat, "lon": point.lon, "scores": risks})

    return {
        "origin": {"label": origin_label, "lat": origin.lat, "lon": origin.lon},
        "destination": {"label": destination_label, "lat": destination.lat, "lon": destination.lon},
        "departure": departure.isoformat(),
        "load_lb": load_lb,
        "sample_miles": sample_miles,
        "recommended_route_id": recommended_id,
        "recommendation_reason": recommendation_reason(ordered),
        "routes": payload_routes,
        "heatmap": heatmap,
        "legend": [level.label for level in RiskLevel],
    }

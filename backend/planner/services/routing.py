from __future__ import annotations

from dataclasses import dataclass, field

from django.conf import settings

from planner.geo import LatLon, haversine_miles, offset_via_points, path_length_miles
from planner.services.http import client


class RoutingError(Exception):
    pass


@dataclass
class RawRoute:
    geometry: list[LatLon]
    distance_miles: float
    duration_seconds: float
    source: str
    summary: str = ""
    via: LatLon | None = field(default=None)


def _geojson_to_points(geometry: dict) -> list[LatLon]:
    coords = geometry.get("coordinates") or []
    geo_type = geometry.get("type")
    if geo_type == "LineString":
        lines = [coords]
    elif geo_type == "MultiLineString":
        lines = coords
    else:
        lines = [coords]
    points: list[LatLon] = []
    for line in lines:
        for pair in line:
            if len(pair) < 2:
                continue
            points.append(LatLon(lat=float(pair[1]), lon=float(pair[0])))
    return _dedupe_points(points)


def _dedupe_points(points: list[LatLon]) -> list[LatLon]:
    cleaned: list[LatLon] = []
    for point in points:
        if not cleaned or haversine_miles(cleaned[-1], point) > 0.01:
            cleaned.append(point)
    return cleaned


def _route_from_points(points: list[LatLon], duration_seconds: float, source: str, summary: str = "") -> RawRoute:
    if len(points) < 2:
        raise RoutingError("Routing API returned an incomplete geometry.")
    miles = path_length_miles(points)
    return RawRoute(
        geometry=points,
        distance_miles=miles,
        duration_seconds=max(duration_seconds, 1.0),
        source=source,
        summary=summary or f"{miles:.0f} mi",
    )


def _ors_routes(origin: LatLon, destination: LatLon, extras: list[LatLon] | None = None) -> list[RawRoute]:
    if not settings.ORS_API_KEY:
        return []

    coordinates = [[origin.lon, origin.lat]]
    if extras:
        coordinates.extend([point.lon, point.lat] for point in extras)
    coordinates.append([destination.lon, destination.lat])

    body: dict = {
        "coordinates": coordinates,
        "instructions": False,
        "geometry": True,
        "elevation": False,
        "units": "m",
    }
    if extras is None:
        body["alternative_routes"] = {
            "target_count": 3,
            "share_factor": 0.6,
            "weight_factor": 1.6,
        }

    url = "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson"
    headers = {"Authorization": settings.ORS_API_KEY, "Content-Type": "application/json"}
    with client() as http:
        response = http.post(url, headers=headers, json=body)
        if response.status_code >= 400:
            return []
        payload = response.json()

    routes: list[RawRoute] = []
    for feature in payload.get("features", []):
        props = feature.get("properties") or {}
        summary = props.get("summary") or {}
        duration = float(summary.get("duration") or props.get("duration") or 0)
        points = _geojson_to_points(feature.get("geometry") or {})
        if len(points) < 2:
            continue
        routes.append(_route_from_points(points, duration, source="openrouteservice"))
    return routes


def _osrm_routes(origin: LatLon, destination: LatLon, extras: list[LatLon] | None = None) -> list[RawRoute]:
    coords = [origin, *(extras or []), destination]
    coord_str = ";".join(f"{point.lon:.6f},{point.lat:.6f}" for point in coords)
    url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{coord_str}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "alternatives": "true" if extras is None else "false",
        "steps": "false",
    }
    with client() as http:
        response = http.get(url, params=params)
        if response.status_code >= 400:
            return []
        payload = response.json()
    if payload.get("code") != "Ok":
        return []

    routes: list[RawRoute] = []
    for route in payload.get("routes", []):
        duration = float(route.get("duration") or 0)
        points = _geojson_to_points(route.get("geometry") or {})
        if len(points) < 2:
            continue
        routes.append(_route_from_points(points, duration, source="osrm"))
    return routes


def _fetch_primary(origin: LatLon, destination: LatLon) -> list[RawRoute]:
    routes = _ors_routes(origin, destination)
    if routes:
        return routes
    routes = _osrm_routes(origin, destination)
    if routes:
        return routes
    raise RoutingError("Could not generate driving routes for that origin and destination.")


def _fetch_via(origin: LatLon, destination: LatLon, via: LatLon) -> RawRoute | None:
    routes = _ors_routes(origin, destination, extras=[via])
    if not routes:
        routes = _osrm_routes(origin, destination, extras=[via])
    if not routes:
        return None
    route = routes[0]
    route.via = via
    return route


def _overlap_ratio(a: list[LatLon], b: list[LatLon], samples: int = 12) -> float:
    if len(a) < 2 or len(b) < 2:
        return 0.0
    total_a = path_length_miles(a) or 1.0
    hits = 0
    for index in range(samples):
        target = total_a * (index + 1) / (samples + 1)
        traveled = 0.0
        probe = a[0]
        for start, end in zip(a, a[1:]):
            segment = haversine_miles(start, end)
            if traveled + segment >= target:
                probe = end
                break
            traveled += segment
        nearest = min(haversine_miles(probe, point) for point in b[:: max(1, len(b) // 40)])
        if nearest < 8:
            hits += 1
    return hits / samples


def _ensure_three(origin: LatLon, destination: LatLon, routes: list[RawRoute]) -> list[RawRoute]:
    unique: list[RawRoute] = []
    for route in routes:
        if all(_overlap_ratio(route.geometry, existing.geometry) < 0.82 for existing in unique):
            unique.append(route)

    if len(unique) >= 3:
        return unique[:3]

    trip_miles = haversine_miles(origin, destination)
    offset = min(48.0, max(18.0, trip_miles * 0.12))
    left, right = offset_via_points(origin, destination, offset)
    for via in (left, right):
        if len(unique) >= 3:
            break
        extra = _fetch_via(origin, destination, via)
        if extra is None:
            continue
        if all(_overlap_ratio(extra.geometry, existing.geometry) < 0.82 for existing in unique):
            unique.append(extra)
    return unique[:3] if unique else routes[:3]


def get_routes(origin: LatLon, destination: LatLon) -> list[RawRoute]:
    if haversine_miles(origin, destination) < 1:
        raise RoutingError("Origin and destination are too close to plan a truck route.")
    primary = _fetch_primary(origin, destination)
    routes = _ensure_three(origin, destination, primary)
    if not routes:
        raise RoutingError("No driving routes were returned.")
    for index, route in enumerate(routes, start=1):
        hours = route.duration_seconds / 3600
        route.summary = f"Corridor {index} · {route.distance_miles:.0f} mi · {hours:.1f} h"
    return routes

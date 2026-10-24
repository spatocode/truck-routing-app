from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_MILES = 3958.8


@dataclass(frozen=True)
class LatLon:
    lat: float
    lon: float

    def as_lonlat(self) -> list[float]:
        return [self.lon, self.lat]


def haversine_miles(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = math.radians(a.lat), math.radians(a.lon)
    lat2, lon2 = math.radians(b.lat), math.radians(b.lon)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    chord = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(chord)))


def bearing_degrees(a: LatLon, b: LatLon) -> float:
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlon = math.radians(b.lon - a.lon)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def destination_point(origin: LatLon, bearing_deg: float, miles: float) -> LatLon:
    angular = miles / EARTH_RADIUS_MILES
    bearing = math.radians(bearing_deg)
    lat1 = math.radians(origin.lat)
    lon1 = math.radians(origin.lon)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular) + math.cos(lat1) * math.sin(angular) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular) * math.cos(lat1),
        math.cos(angular) - math.sin(lat1) * math.sin(lat2),
    )
    return LatLon(lat=math.degrees(lat2), lon=(math.degrees(lon2) + 540) % 360 - 180)


def lerp(a: LatLon, b: LatLon, t: float) -> LatLon:
    return LatLon(lat=a.lat + (b.lat - a.lat) * t, lon=a.lon + (b.lon - a.lon) * t)


def path_length_miles(points: list[LatLon]) -> float:
    return sum(haversine_miles(a, b) for a, b in zip(points, points[1:]))


def cumulative_miles(points: list[LatLon]) -> list[float]:
    miles = [0.0]
    for a, b in zip(points, points[1:]):
        miles.append(miles[-1] + haversine_miles(a, b))
    return miles


def sample_along_path(points: list[LatLon], interval_miles: float) -> list[tuple[LatLon, float]]:
    if not points:
        return []
    if len(points) == 1:
        return [(points[0], 0.0)]

    samples: list[tuple[LatLon, float]] = [(points[0], 0.0)]
    next_at = interval_miles
    traveled = 0.0

    for a, b in zip(points, points[1:]):
        segment = haversine_miles(a, b)
        if segment == 0:
            continue
        while traveled + segment >= next_at:
            t = (next_at - traveled) / segment
            samples.append((lerp(a, b, t), round(next_at, 2)))
            next_at += interval_miles
        traveled += segment

    end_mile = round(traveled, 2)
    last_point, last_mile = samples[-1]
    if haversine_miles(last_point, points[-1]) > 0.05 or abs(last_mile - end_mile) > 0.05:
        samples.append((points[-1], end_mile))
    return samples


def point_at_fraction(points: list[LatLon], fraction: float) -> LatLon:
    fraction = min(1.0, max(0.0, fraction))
    total = path_length_miles(points)
    if total == 0:
        return points[0]
    target = total * fraction
    traveled = 0.0
    for a, b in zip(points, points[1:]):
        segment = haversine_miles(a, b)
        if traveled + segment >= target:
            t = (target - traveled) / segment if segment else 0.0
            return lerp(a, b, t)
        traveled += segment
    return points[-1]


def offset_via_points(origin: LatLon, destination: LatLon, offset_miles: float) -> tuple[LatLon, LatLon]:
    mid = lerp(origin, destination, 0.5)
    heading = bearing_degrees(origin, destination)
    left = destination_point(mid, (heading - 90) % 360, offset_miles)
    right = destination_point(mid, (heading + 90) % 360, offset_miles)
    return left, right


def round_cell(point: LatLon, decimals: int = 2) -> tuple[float, float]:
    return (round(point.lat, decimals), round(point.lon, decimals))


def corridor_grid(routes: list[list[LatLon]], spacing_miles: float = 20.0, half_width_miles: float = 18.0) -> list[LatLon]:
    cells: dict[tuple[float, float], LatLon] = {}
    for points in routes:
        if len(points) < 2:
            continue
        for point, _mile in sample_along_path(points, spacing_miles):
            cells[round_cell(point)] = point
        heading = bearing_degrees(points[0], points[-1])
        for point, _mile in sample_along_path(points, spacing_miles * 1.5):
            for sign in (-1, 1):
                offset = destination_point(point, (heading + 90 * sign) % 360, half_width_miles)
                cells[round_cell(offset)] = offset
    return list(cells.values())

from __future__ import annotations

from planner.geo import LatLon
from planner.services.http import client


class GeocodeError(Exception):
    pass


def _label(props: dict) -> str:
    parts = [
        props.get("name"),
        props.get("street"),
        props.get("city") or props.get("locality") or props.get("town"),
        props.get("state") or props.get("county"),
        props.get("country"),
    ]
    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(str(part))
    return ", ".join(seen) or "Unknown location"


def search_places(query: str, limit: int = 6) -> list[dict]:
    query = query.strip()
    if len(query) < 2:
        return []

    from django.conf import settings

    params = {
        "q": query,
        "limit": str(limit),
        "lang": "en",
        "lat": "39.5",
        "lon": "-98.35",
    }
    with client() as http:
        response = http.get(settings.PHOTON_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    results = []
    for feature in payload.get("features", []):
        coords = feature.get("geometry", {}).get("coordinates") or []
        if len(coords) < 2:
            continue
        props = feature.get("properties") or {}
        lon, lat = float(coords[0]), float(coords[1])
        country = str(props.get("countrycode") or "").upper()
        rank = 0 if country in {"US", "USA"} else 1 if country in {"CA", "MX"} else 2
        results.append(
            {
                "label": _label(props),
                "lat": lat,
                "lon": lon,
                "rank": rank,
            }
        )
    results.sort(key=lambda item: item["rank"])
    for item in results:
        item.pop("rank", None)
    return results


def geocode_one(query: str) -> tuple[LatLon, str]:
    matches = search_places(query, limit=1)
    if not matches:
        raise GeocodeError(f"Could not find a location for '{query}'.")
    match = matches[0]
    return LatLon(lat=match["lat"], lon=match["lon"]), match["label"]

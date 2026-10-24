from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from planner.plan import plan_trip
from planner.services.geocoding import GeocodeError, search_places
from planner.services.routing import RoutingError

logger = logging.getLogger(__name__)


def _error(message: str, code: int = 400) -> Response:
    return Response({"detail": message}, status=code)


@api_view(["GET"])
def health(_request):
    return Response({"ok": True, "service": "spotter"})


@api_view(["GET"])
def geocode(request):
    query = (request.query_params.get("q") or "").strip()
    if len(query) < 2:
        return Response([])
    try:
        return Response(search_places(query))
    except Exception:
        logger.exception("Geocode failed")
        return _error("Location search is temporarily unavailable.", 502)


@api_view(["POST"])
def plan(request):
    data = request.data if isinstance(request.data, dict) else {}
    try:
        sample_miles = int(data.get("sample_miles") or 25)
        load_lb = float(data.get("load_lb") or data.get("load_weight") or 0)
        departure_raw = data.get("departure")
        if not departure_raw:
            return _error("Departure date and time are required.")
        from django.utils.dateparse import parse_datetime

        departure = parse_datetime(str(departure_raw))
        if departure is None:
            return _error("Departure must be a valid ISO-8601 datetime.")

        result = plan_trip(
            origin_query=data.get("origin"),
            destination_query=data.get("destination"),
            origin_lat=_maybe_float(data.get("origin_lat")),
            origin_lon=_maybe_float(data.get("origin_lon")),
            dest_lat=_maybe_float(data.get("destination_lat") or data.get("dest_lat")),
            dest_lon=_maybe_float(data.get("destination_lon") or data.get("dest_lon")),
            departure=departure,
            load_lb=load_lb,
            sample_miles=sample_miles,
        )
        return Response(result)
    except ValueError as exc:
        return _error(str(exc))
    except GeocodeError as exc:
        return _error(str(exc))
    except RoutingError as exc:
        return _error(str(exc), status.HTTP_502_BAD_GATEWAY)
    except Exception:
        logger.exception("Plan failed")
        return _error("Could not plan routes right now. Try a shorter trip or a later departure.", 502)


def _maybe_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)

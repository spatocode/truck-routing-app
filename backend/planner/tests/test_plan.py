from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from planner.geo import LatLon
from planner.plan import plan_trip
from planner.services.routing import RawRoute
from planner.services.weather import HourlySeries


def _line(start: LatLon, end: LatLon, hours: float) -> RawRoute:
    return RawRoute(
        geometry=[start, end],
        distance_miles=100,
        duration_seconds=hours * 3600,
        source="test",
        summary="test",
    )


def _series(start: datetime, wind: float, rain: float = 0.0) -> HourlySeries:
    times = [start + timedelta(hours=offset) for offset in range(49)]
    n = len(times)
    return HourlySeries(
        times=times,
        wind_mph=[wind] * n,
        rain_in_hr=[rain] * n,
        snow_in_hr=[0.0] * n,
        temp_f=[40.0] * n,
        weather_code=[0] * n,
    )


def test_plan_recommends_calmer_corridor():
    origin = LatLon(41.0, -90.0)
    dest = LatLon(41.0, -88.2)
    calm = _line(origin, dest, 5)
    windy = RawRoute(
        geometry=[origin, LatLon(41.4, -89.1), dest],
        distance_miles=110,
        duration_seconds=4 * 3600,
        source="test",
        summary="windy",
    )
    departure = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)

    def fake_hourly(points):
        series = []
        for point in points:
            wind = 50 if point.lat > 41.2 else 10
            series.append(_series(departure, wind))
        return series

    with (
        patch("planner.plan.get_routes", return_value=[windy, calm]),
        patch("planner.plan.fetch_hourly", side_effect=fake_hourly),
        patch("planner.plan.corridor_grid", return_value=[]),
    ):
        result = plan_trip(
            origin_query=None,
            destination_query=None,
            origin_lat=origin.lat,
            origin_lon=origin.lon,
            dest_lat=dest.lat,
            dest_lon=dest.lon,
            departure=departure,
            load_lb=20_000,
            sample_miles=50,
        )

    assert result["recommended_route_id"] == "r2"
    assert result["routes"][0]["stats"]["severe_miles"] > result["routes"][1]["stats"]["severe_miles"]
    assert result["routes"][1]["checkpoints"]
    assert "fewest severe" in result["recommendation_reason"]

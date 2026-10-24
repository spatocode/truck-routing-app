from planner.recommend import RankedRoute, RouteStats, recommendation_reason, rank_routes
from planner.risk import RiskLevel


def test_ranks_severe_before_high_before_average_before_time():
    slow_clear = RankedRoute(route_id="slow", stats=RouteStats(), duration_seconds=10_000)
    slow_clear.stats.add_segment(100, RiskLevel.LOW)

    fast_high = RankedRoute(route_id="high", stats=RouteStats(), duration_seconds=4_000)
    fast_high.stats.add_segment(20, RiskLevel.HIGH)
    fast_high.stats.add_segment(80, RiskLevel.LOW)

    mid_severe = RankedRoute(route_id="severe", stats=RouteStats(), duration_seconds=6_000)
    mid_severe.stats.add_segment(5, RiskLevel.SEVERE)
    mid_severe.stats.add_segment(95, RiskLevel.LOW)

    ordered = rank_routes([fast_high, mid_severe, slow_clear])
    assert [route.route_id for route in ordered] == ["slow", "high", "severe"]


def test_tie_breaks_on_travel_time():
    a = RankedRoute(route_id="a", stats=RouteStats(), duration_seconds=8_000)
    b = RankedRoute(route_id="b", stats=RouteStats(), duration_seconds=5_000)
    a.stats.add_segment(50, RiskLevel.LOW)
    b.stats.add_segment(50, RiskLevel.LOW)
    ordered = rank_routes([a, b])
    assert ordered[0].route_id == "b"
    assert "shorter drive" in recommendation_reason(ordered)

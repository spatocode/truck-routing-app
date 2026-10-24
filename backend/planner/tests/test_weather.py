import pytest

from planner.services.weather import WeatherError, blocks_from_payload


def test_blocks_accept_one_object_per_location():
    payload = [{"hourly": {"time": ["2026-10-24T00:00"]}}, {"hourly": {"time": ["2026-10-24T00:00"]}}]
    assert len(blocks_from_payload(payload, expected=2)) == 2


def test_blocks_accept_single_object_for_one_point():
    payload = {"hourly": {"time": ["2026-10-24T00:00"]}}
    assert len(blocks_from_payload(payload, expected=1)) == 1


def test_blocks_reject_count_mismatch():
    payload = {"hourly": {"time": ["2026-10-24T00:00"]}}
    with pytest.raises(WeatherError):
        blocks_from_payload(payload, expected=8)


def test_blocks_surface_api_error_reason():
    with pytest.raises(WeatherError, match="too many"):
        blocks_from_payload({"error": True, "reason": "too many locations"}, expected=8)

from rest_framework.test import APIRequestFactory

from planner.views import health


def test_health():
    request = APIRequestFactory().get("/api/health")
    response = health(request)
    assert response.status_code == 200
    assert response.data["ok"] is True

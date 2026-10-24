from django.urls import path

from planner import views

urlpatterns = [
    path("health", views.health),
    path("geocode", views.geocode),
    path("plan", views.plan),
]

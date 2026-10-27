from django.urls import include, path

from config import views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("api/", include("api.urls")),
]

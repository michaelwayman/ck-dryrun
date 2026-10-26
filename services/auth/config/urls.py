from django.urls import path

from config import views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
]

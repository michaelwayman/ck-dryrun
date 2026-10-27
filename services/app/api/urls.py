from django.urls import path

from api import views

urlpatterns = [
    path("brands/", views.BrandListView.as_view(), name="brand-list"),
    path("brands/<str:slug>/", views.BrandDetailView.as_view(), name="brand-detail"),
]

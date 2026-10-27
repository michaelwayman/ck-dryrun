from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from api import views

urlpatterns = [
    path("brands/", views.BrandListView.as_view(), name="brand-list"),
    path("brands/<str:slug>/", views.BrandDetailView.as_view(), name="brand-detail"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

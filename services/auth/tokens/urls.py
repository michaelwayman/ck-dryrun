from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from tokens import views

urlpatterns = [
    path("api/token/", views.LoginView.as_view(), name="token-login"),
    path("api/token/refresh/", views.RefreshView.as_view(), name="token-refresh"),
    path("api/token/logout/", views.LogoutView.as_view(), name="token-logout"),
    # R19: the auth-api contract as OpenAPI, and Swagger UI (assets from drf-spectacular's CDN).
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

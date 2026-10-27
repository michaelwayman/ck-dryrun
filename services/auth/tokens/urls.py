from django.urls import path

from tokens import views

urlpatterns = [
    path("api/token/", views.LoginView.as_view(), name="token-login"),
    path("api/token/refresh/", views.RefreshView.as_view(), name="token-refresh"),
    path("api/token/logout/", views.LogoutView.as_view(), name="token-logout"),
]

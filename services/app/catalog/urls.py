from django.urls import path

from catalog import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("brand/", views.brand_archive, name="brand-archive"),
    path("brand/<str:slug>/", views.brand_detail, name="brand-detail"),
    path("review/", views.review_archive, name="review-archive"),
    path("review/<str:slug>/", views.review_detail, name="review-detail"),
]

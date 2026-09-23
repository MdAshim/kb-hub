from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

app_name = "api"

router = SimpleRouter()
router.register("urls", views.UrlRecordViewSet, basename="urlrecord")

urlpatterns = [
    path("", include(router.urls)),
    path("jobs/<int:pk>/", views.HarvestJobView.as_view(), name="job-detail"),
    path("search/", views.SearchAPIView.as_view(), name="search"),
]

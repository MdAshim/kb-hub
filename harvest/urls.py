from django.urls import path

from . import views

app_name = "harvest"

urlpatterns = [
    path("upload/", views.upload_view, name="upload"),
    path("jobs/", views.job_list_view, name="job_list"),
    path("jobs/<int:job_id>/", views.job_detail_view, name="job_detail"),
    path("jobs/<int:job_id>/rows/", views.job_rows_partial, name="job_rows"),
]

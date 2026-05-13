# planarian/urls.py

from django.urls import path
from planarian import views

app_name = "planarian"

urlpatterns = [
    # Import / export   
    path("import/csv/",     views.import_csv_view,              name="import-params"),
    path("export/csv/",     views.export_csv_view,              name="export-csv"),
    path("api/export/csv/", views.export_metrics,               name="api-export-csv"),
    # API JSON pour le front-end
    path("api/tracking/",   views.TrackingDataView.as_view(),   name="tracking-data-api"),
    
]


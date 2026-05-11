# planarian/urls.py

from django.urls import path
from planarian import views

app_name = "planarian"

urlpatterns = [
    # Configurations expériences
    #path("experiments/",         views.ExperimentConfigListView.as_view(), name="experiment-list2"),
   # 
    #path("experiments/new/",     views.ExperimentConfigFormView.as_view(), name="experiment-new"),
    #path("experiments/<int:pk>/",views.ExperimentConfigFormView.as_view(), name="experiment-edit2"),
    
    #path("config/list/", views.config_list_view, name="experiment-list"),
    #path("config/list/<int:session_id>/<int:experiment_id>/", views.config_list_view, name="experiment-list"),
    
    #path("config/edit/<int:pk>/", views.config_edit_view, name="experiment-edit"),
    #path("config/edit/<int:pk>/<int:session_id>/<int:experiment_id>/", views.config_edit_view, name="experiment-edit"),

    # Import / export
    #path("import/",              views.ImportParamsView.as_view(),         name="import-params"),
    #path("export/",              views.ExportCsvView.as_view(),            name="export-csv-view"),
    
    #path("import/",              views.ImportParamsView.as_view(),         name="import-params"),
    path("export/csv/",          views.export_csv_view,                             name="export-csv"),
    path("export/csv/<int:session_id>/<int:experiment_id>/", views.export_csv_view,  name="export-csv"),
    

    # API JSON pour le front-end
    path("api/tracking/",        views.TrackingDataView.as_view(),         name="tracking-data-api"),
]


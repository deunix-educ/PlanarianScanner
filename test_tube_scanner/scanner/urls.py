
from django.urls import path
from . import views

app_name = "scanner"

urlpatterns = [
    path('admin/', views.admin_view, name='admin'),
    path('reductstore/', views.reductstore_view, name='reductstore'),
    path('adminer/', views.adminer_view, name='adminer'),
    path('portainer/', views.portainer_view, name='portainer'),
    path('calibration/', views.calibration_view, name='calibration'),
    path('supervisor/', views.supervisor_view, name='supervisor'),
    path('logs/worker', views.supervisor_worker, name='logs_worker'),
    path('logs/scheduler', views.supervisor_scheduler, name='logs_scheduler'),
    path("doc/<slug:template>/", views.documentation, name="documentation"),
    
    path('session/view', views.admin_session_view, name='session_view'),
    path('experiment/view', views.admin_experiment_view, name='experiment_view'),
    path('experiment/config/view', views.admin_experimentconfig_view, name='experimentconfig_view'),
    path('periodictask/view', views.admin_periodictask_view, name='periodictask_view'),
    
    path('scanning/', views.scanning_view, name='scanning'),
    path('images/', views.images_view, name='images'),
    path('replay/', views.replay_view, name='replay'),
    path('api/stats/', views.stats_view, name='api_stats'),
    path('api/video/', views.download_api, name='download_api'),
    path('api/export/', views.export_api, name='export_api'),
]

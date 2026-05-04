from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from django.db.models import Q
from . import models

class WellAdmin(admin.ModelAdmin):
    model = models.Well
    list_display = ('name', 'author',)

class ConfigurationAdmin(admin.ModelAdmin):
    list_display = ('name', 'author', 'capture_type', 'video_width_capture', 'video_height_capture', 'video_frame_rate', 'active',)
    
    
    fieldsets = (
        (_("Identification"), {
            "fields": ("name", "author", "active"),
        }),
        (_("Dashboard"), {
            "fields": ("sidebar_width", "default_grid_columns",),"classes": ("collapse",),
        }),
        (_("opencv"), {
            "fields": ("opencv_fourcc_format", "opencv_video_type"),"classes": ("collapse",),
        }),
        (_("Grbl"), {
            "fields": ("grbl_xmax", "grbl_ymax"),            
            "classes": ("collapse",),
        }),
        (_("Camera"), {
            "fields": ("capture_type", "webcam_device_index", "image_quality", "video_jpeg_quality", "video_frame_rate", "video_width_capture", "video_height_capture"),
            "classes": ("collapse",),
        }),
        (_("Calibration"), {
            "fields": ("calibration_crop_radius", "calibration_default_multiwell", "calibration_default_feed", "calibration_default_step", "calibration_default_duration"),
            "classes": ("collapse",),
        }),
        (_("Tracking: valeurs par défaut"), {
            "fields": ("tracking", "min_area_px", "max_area_ratio", "max_planarians", "merge_kernel_size", "min_contour_dist_px"),
            "classes": ("collapse",),
        }),

    
    )

class MultiWellAdmin(admin.ModelAdmin):
    list_filter = ('author', )
    list_display = ('label', 'position', 'author', 'order', 'xbase', 'ybase', 'duration', 'feed', 'default', 'well_position', 'active',)
    
    fieldsets = (
        (_("Identification"), {
            "fields": ("label", "author", "position", "default", "active"),
        }),
        (_("Géométrie"), {
            "fields": ("cols", "rows", "diameter", "row_def", "row_order"),"classes": ("collapse",),
        }),
        (_("Déplacement"), {
            "fields": ("order", "duration", "xbase", "ybase", "dx", "dy", "feed"),"classes": ("collapse",),
        }),
        (_("Positions générées"), {
            "fields": ("well_position",),
        }),

    )

class WellPositionAdmin(admin.ModelAdmin):
    list_filter = ('author', 'multiwell')
    list_display = ('multiwell__position', 'well__name', 'order', 'x', 'y', 'px_per_mm', 'author',)
    

#class ExperimentConfigInline(admin.TabularInline):
#    model = models.ExperimentConfig
#    extra = 0

class ExperimentAdmin(admin.ModelAdmin):
    #inlines = (ExperimenConfigInline,)
    list_filter = ('session_experiments__session', 'author', )
    list_display = ('title', 'author',  'multiwell', 'created', 'started', 'finished')
    readonly_fields = ('created',  'started',  'finished', )
    

class SessionExperimentInlineAdmin(admin.TabularInline):
    model = models.SessionExperiment
    fk_name = 'session'
    extra = 0

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "experiment":
            obj_id = request.resolver_match.kwargs.get("object_id")

            qs = models.Experiment.objects.filter(session_experiments__isnull=True)
            if obj_id:
                qs = models.Experiment.objects.filter(
                    Q(session_experiments__isnull=True) |
                    Q(session_experiments__session_id=obj_id)
                )
            kwargs["queryset"] = qs.distinct()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class SessionAdmin(admin.ModelAdmin):
    list_filter = ('author',)
    inlines = (SessionExperimentInlineAdmin, )
    list_display = ('name', 'author', 'created', 'finished', 'active', 'expected_export', 'expected_scanning', )
    readonly_fields = (
        'created', 
        'finished',
        'export_status',
        'export_task', 
        'export_exported_at', 
        'scanning_status',
        'scanning_task', 
        'scanning_finished_at'
    )

admin.site.register(models.Configuration, ConfigurationAdmin)
admin.site.register(models.Well, WellAdmin)
admin.site.register(models.MultiWell, MultiWellAdmin)
admin.site.register(models.WellPosition, WellPositionAdmin)
admin.site.register(models.Experiment, ExperimentAdmin)
admin.site.register(models.Session, SessionAdmin)


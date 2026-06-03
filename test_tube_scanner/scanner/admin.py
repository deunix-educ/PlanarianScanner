from pathlib import Path
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
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
            "fields": ("scan_simulation", "capture_type", "webcam_device_index", "image_quality", "video_jpeg_quality", "video_frame_rate", "video_width_capture", "video_height_capture"),
            "classes": ("collapse",),
        }),
        (_("Calibration / Balayage"), {
            "fields": ("tube_axis", "calibration_crop_radius", "calibration_default_multiwell", "calibration_default_feed", "calibration_default_step", "calibration_default_duration"),
            "classes": ("collapse",),
        }),
        (_("Tracking: valeurs par défaut"), {
            "fields": ("tracking", "tracking_setting", "min_area_px", "max_area_ratio", "max_planarians", "merge_kernel_size", "min_contour_dist_px"),
            "classes": ("collapse",),
        }),

    
    )

class MultiWellAdmin(admin.ModelAdmin):
    list_filter = ('author', )
    list_display = ('label', 'position', 'author', 'order', 'xbase', 'ybase', 'duration', 'feed', 'default', 'well_position', 'capture_video', 'active',)
    ordering = ('label', 'order')
    fieldsets = (
        (_("Identification"), {
            "fields": ("label", "author", "position", "default", "capture_video", "active"),
        }),
        (_("Géométrie"), {
            "fields": ("cols", "rows", "diameter", "crop_radius", "row_def", "row_order"),"classes": ("collapse",),
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
  
  
class ExperimentWellInline(admin.TabularInline):
    model = models.ExperimentWell
    extra = 0
    #ordering = ('experiment__multiwell__wellposition__order',)
    
    
class ExperimentAdmin(admin.ModelAdmin):
    inlines = (ExperimentWellInline, )
    list_filter = ('session_experiments__session', 'author', )
    list_display = ('title', 'author', 'identifier', 'duration',  'multiwell', 'created', 'started', 'finished')
    readonly_fields = ('created', 'identifier',  'started',  'finished', )
    

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
    list_display = ('name', 'id', 'author', 'created', 'finished', 'active', 'expected_export', 'expected_scanning', )
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

@admin.register(models.VideoPlate)
class VideoPlateAdmin(admin.ModelAdmin):

    list_display  = ['multiwell', 'label', 'video_filename', 'active',
                     'fps_display', 'duration_display', 'resolution_display', 'uploaded_at']
    list_filter   = ['multiwell', 'active']
    list_editable = ['active']
    readonly_fields = [
        'native_fps', 'duration_s', 'frame_w', 'frame_h',
        'uploaded_at', 'resolution_display', 'video_preview',
    ]
    fields = [
        'multiwell', 'label', 'video_file', 'active', 'px_per_mm',
        'x_origin_mm', 'y_origin_mm',
        'video_preview',
        'native_fps', 'duration_s', 'frame_w', 'frame_h', 'uploaded_at',
    ]

    class Media:
        css = {'all': ('scanner/css/video_upload.css',)}
        js  = ('scanner/js/video_upload.js',)

    # ------------------------------------------------------------------
    # Colonnes liste
    # ------------------------------------------------------------------

    @admin.display(description=_("Fichier"), ordering='video_file')
    def video_filename(self, obj):
        return obj.video_filename

    @admin.display(description=_("FPS"))
    def fps_display(self, obj):
        return f"{obj.native_fps:.2f}" if obj.native_fps else "—"

    @admin.display(description=_("Durée"))
    def duration_display(self, obj):
        if not obj.duration_s:
            return "—"
        m, s = divmod(int(obj.duration_s), 60)
        return f"{m}:{s:02d}"

    @admin.display(description=_("Résolution"))
    def resolution_display(self, obj):
        return obj.resolution

    # ------------------------------------------------------------------
    # Aperçu vidéo (readonly field)
    # ------------------------------------------------------------------

    @admin.display(description=_("Aperçu"))
    def video_preview(self, obj):
        if not obj.video_file:
            return "—"
        return format_html(
            '<video src="{}" controls style="max-width:480px;max-height:320px;'
            'border-radius:4px;"></video>',
            obj.video_file.url,
        )

    # ------------------------------------------------------------------
    # Sauvegarde : extraction des métadonnées
    # ------------------------------------------------------------------

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.video_file:
            self._extract_metadata(obj)

    def _extract_metadata(self, obj):
        try:
            import cv2
            cap = cv2.VideoCapture(obj.video_file.path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                fc  = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                models.VideoPlate.objects.filter(pk=obj.pk).update(
                    native_fps = fps,
                    duration_s = (fc / fps) if fps else None,
                    frame_w    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    frame_h    = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                )
                cap.release()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Suppression : efface aussi le fichier physique
    # ------------------------------------------------------------------

    def delete_model(self, request, obj):
        if obj.video_file:
            Path(obj.video_file.path).unlink(missing_ok=True)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            if obj.video_file:
                Path(obj.video_file.path).unlink(missing_ok=True)
        super().delete_queryset(request, queryset)


admin.site.register(models.Configuration, ConfigurationAdmin)
admin.site.register(models.Well, WellAdmin)
admin.site.register(models.MultiWell, MultiWellAdmin)
admin.site.register(models.WellPosition, WellPositionAdmin)
admin.site.register(models.Experiment, ExperimentAdmin)
admin.site.register(models.Session, SessionAdmin)


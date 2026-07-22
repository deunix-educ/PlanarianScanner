from pathlib import Path
from django import forms
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.shortcuts import render, redirect
from django.urls import path
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.contrib import admin, messages
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

VIDEO_INCOMING_DIRNAME = 'incoming'
VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mkv', '.mov', '.m4v')

# Au-delà de cette taille, l'upload HTTP via l'admin risque de saturer la RAM
# du Pi (Daphne bufférise le corps de la requête en mémoire) et de reproduire
# le blocage observé — on redirige plutôt vers l'import SFTP (sans limite).
MAX_VIDEO_UPLOAD_MB = 200


class VideoPlateForm(forms.ModelForm):
    class Meta:
        model = models.VideoPlate
        fields = '__all__'
        help_texts = {
            'video_file': _(
                "%(limit)d Mo max pour l'upload direct. Au-delà, utilise "
                "« Importer depuis le dépôt SFTP » depuis la liste des vidéos plaque."
            ) % {'limit': MAX_VIDEO_UPLOAD_MB},
        }

    def clean_video_file(self):
        file = self.cleaned_data.get('video_file')
        if isinstance(file, UploadedFile) and file.size > MAX_VIDEO_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(
                _(
                    "Fichier trop volumineux (%(size).0f Mo, limite %(limit)d Mo pour l'upload direct). "
                    "Dépose la vidéo par SFTP dans media/videos/incoming/ puis utilise "
                    "« Importer depuis le dépôt SFTP » depuis la liste des vidéos plaque."
                ) % {'size': file.size / (1024 * 1024), 'limit': MAX_VIDEO_UPLOAD_MB}
            )
        return file


@admin.register(models.VideoPlate)
class VideoPlateAdmin(admin.ModelAdmin):

    form = VideoPlateForm
    list_display  = ['multiwell', 'label', 'video_filename', 'active',
                     'fps_display', 'duration_display', 'resolution_display', 'uploaded_at']
    list_filter   = ['multiwell', 'active']
    list_editable = ['active']
    change_list_template = 'admin/scanner/videoplate/change_list.html'
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
    # Import depuis un fichier déposé en SFTP (évite l'upload HTTP pour
    # les vidéos de plusieurs Go — cf. contrainte mémoire du Pi sous Daphne)
    # ------------------------------------------------------------------

    def get_urls(self):
        return [
            path(
                'import-sftp/',
                self.admin_site.admin_view(self.import_sftp_view),
                name='scanner_videoplate_import_sftp',
            ),
        ] + super().get_urls()

    @staticmethod
    def _incoming_dir() -> Path:
        incoming = Path(settings.MEDIA_ROOT) / 'videos' / VIDEO_INCOMING_DIRNAME
        incoming.mkdir(parents=True, exist_ok=True)
        return incoming

    def import_sftp_view(self, request):
        incoming = self._incoming_dir()
        pending_files = sorted(
            f.name for f in incoming.iterdir()
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
        )

        if request.method == 'POST':
            filename = request.POST.get('filename', '')
            multiwell_id = request.POST.get('multiwell')
            label = request.POST.get('label', '')

            src = (incoming / filename).resolve()
            if src.parent != incoming.resolve() or not src.is_file():
                messages.error(request, _("Fichier introuvable dans le dépôt SFTP."))
                return redirect('admin:scanner_videoplate_import_sftp')

            multiwell = models.MultiWell.objects.filter(pk=multiwell_id).first()
            if not multiwell:
                messages.error(request, _("Multi-puits invalide."))
                return redirect('admin:scanner_videoplate_import_sftp')

            dest_dir = Path(settings.MEDIA_ROOT) / 'videos'
            dest = dest_dir / src.name
            n = 1
            while dest.exists():
                dest = dest_dir / f"{src.stem}_{n}{src.suffix}"
                n += 1
            src.rename(dest)

            video_plate = models.VideoPlate.objects.create(
                multiwell=multiwell,
                label=label,
                video_file=f'videos/{dest.name}',
                active=True,
            )
            from .tasks import extract_video_plate_metadata
            extract_video_plate_metadata.delay(video_plate.pk)  # @UndefinedVariable
            messages.success(
                request,
                _("Vidéo « %(name)s » importée — analyse en cours en arrière-plan.") % {'name': dest.name},
            )
            return redirect('admin:scanner_videoplate_changelist')

        context = {
            **self.admin_site.each_context(request),
            'title': _("Importer une vidéo déposée en SFTP"),
            'opts': self.model._meta,
            'pending_files': pending_files,
            'multiwells': models.MultiWell.objects.order_by('label', 'order'),
            'incoming_path': str(incoming),
        }
        return render(request, 'admin/scanner/videoplate/import_sftp.html', context)

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
            from .tasks import extract_video_plate_metadata
            extract_video_plate_metadata.delay(obj.pk)  # @UndefinedVariable
            messages.info(
                request,
                _("Analyse de la vidéo (FPS, durée, résolution) en cours en arrière-plan — actualisez la page dans quelques instants."),
            )

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


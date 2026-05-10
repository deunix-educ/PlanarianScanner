# planarian/models.py

from django.db import models
#from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from scanner.models import Experiment, Well


class ExperimentConfig(models.Model):
    """
    Paramètres d'une expérience PlanarianScanner.
    Peut être créé depuis Django admin, une vue formulaire ou un import CSV.
    """
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Auteur", null=True, blank=True)   
    experiment = models.ForeignKey(Experiment, verbose_name="Expérience", on_delete=models.CASCADE, related_name="experiment_well", null=True, blank=False)
    well = models.ForeignKey(Well, verbose_name="Puit", on_delete=models.CASCADE, related_name="well_experiment", null=True, blank=False )
    
    description = models.TextField( blank=True, verbose_name=_("Description"), default="-")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Créé le"))
    
    active = models.BooleanField(_("Active"), default=True)

    # --- Calibration optique ---
    # px_per_mm, fps, well_radius_mm 
    px_per_mm = models.FloatField(
        default=26.25,
        verbose_name=_("Pixels par mm"),
        help_text=_("Facteur de calibration optique"),
    )
    fps = models.FloatField(
        default=5.0,
        verbose_name=_("FPS de capture"),
        help_text=_("Image de capture en img/s"),
    )
    well_radius_mm = models.FloatField(
        default=8.0,
        verbose_name=_("Rayon du puits"),
        help_text=_("En mm"),
    )

    # --- Seuils de mobilité EthoVision ---
    thresh_immobile = models.FloatField(
        default=0.2,
        verbose_name=_("Seuil Immobile (mm/s)"),
    )
    thresh_mobile = models.FloatField(
        default=1.5,
        verbose_name=_("Seuil Mobile (mm/s)"),
    )

    # --- Tracker ---
    tube_axis = models.CharField(
        max_length=10,
        default="vertical",
        choices=[("vertical", _("Vertical")), ("horizontal", _("Horizontal"))],
        verbose_name=_("Axe du tube"),
    )
    min_area_px = models.IntegerField(
        default=20,
        verbose_name=_("Surface min détection (px²)"),
    )
    
    max_area_ratio = models.FloatField(
        default=0.10,
        verbose_name=_("Surface max contour (fraction de la frame)"),
        help_text=_("Ratio de la surface du puits, ex: 0.10 pour 10%"),
    )
        
    planarian_count = models.IntegerField(
        default=1,
        verbose_name=_("Nombre de planaires"),
    )

    merge_kernel_size = models.PositiveIntegerField(
        _("Taille du kernel"), 
        help_text=_("taille du kernel elliptique de fusion des fragments (px). Augmenter si fragments résiduels"), 
        default=15
    )
    
    min_contour_dist_px = models.PositiveIntegerField(
        _("Distance <contour>"), 
        help_text=_("Distance min entre deux contours pour les considérer comme individus distincts. Défaut : 40px. Augmenter si IDs multiples persistent"), 
        default=40
    )

    # --- Thigmotactisme ---
    thigmotaxis_wall_dist_mm = models.FloatField(
        default=1.0,
        verbose_name=_("Distance paroi thigmotactisme (mm)"),
    )

    # --- Phototactisme ---
    PHOTO_MODES = [
        ("none",   _("Désactivé")),
        ("fixed",  _("Source fixe")),
        ("sine",   _("Source sinusoïdale")),
        ("radial", _("Gradient radial")),
    ]
    photo_mode = models.CharField(
        max_length=10,
        default="none",
        choices=PHOTO_MODES,
        verbose_name=_("Mode phototactisme"),
    )
    photo_strength = models.FloatField(default=0.0, verbose_name=_("Intensité phototactisme"))
    photo_x        = models.FloatField(default=0.5, verbose_name=_("Source lumière X (0-1)"))
    photo_y        = models.FloatField(default=0.5, verbose_name=_("Source lumière Y (0-1)"))

    # --- Chimiotactisme ---
    chemo_strength  = models.FloatField(default=0.0, verbose_name=_("Intensité chimiotactisme"))
    chemo_x         = models.FloatField(default=0.5, verbose_name=_("Nourriture X (0-1)"))
    chemo_y         = models.FloatField(default=0.5, verbose_name=_("Nourriture Y (0-1)"))
    chemo_radius_mm = models.FloatField(default=2.0, verbose_name=_("Rayon nourriture (mm)"))

    # --- Interactions inter-individus ---
    avoid_radius_mm  = models.FloatField(default=3.0, verbose_name=_("Rayon évitement (mm)"))
    aggreg_radius_mm = models.FloatField(default=6.0, verbose_name=_("Rayon agrégation (mm)"))

    class Meta:
        verbose_name        = _("Configuration d'une expérience")
        verbose_name_plural = _("Configurations des expériences")
        unique_together     = ("experiment", "well")
        ordering            = ["-created_at"]

    def __str__(self):
        return f"{self.experiment}:{self.well.name}"
    
    def get_session(self):
        return self.experiment.session_experiments.first() if self.experiment else None

    def to_params_dict(self) -> dict:
        """Retourne un dict compatible avec ExperimentParams."""
        return {
            "experiment":            self.experiment.identifier,
            "well":                  self.well.name,
            
            "px_per_mm":             self.px_per_mm,
            "fps":                   self.fps,
            "well_radius_mm":        self.well_radius_mm,
            "thresh_immobile":       self.thresh_immobile,
            "thresh_mobile":         self.thresh_mobile,
            "tube_axis":             self.tube_axis,
            "min_area_px":           self.min_area_px,
            "max_area_ratio":        self.max_area_ratio,
            "merge_kernel_size":     self.merge_kernel_size,
            "min_contour_dist_px":   self.min_contour_dist_px,
            "planarian_count":       self.planarian_count,
            "thigmotaxis_wall_dist_mm": self.thigmotaxis_wall_dist_mm,
            "photo_mode":            self.photo_mode,
            "photo_strength":        self.photo_strength,
            "chemo_strength":        self.chemo_strength,
            "chemo_x":               self.chemo_x,
            "chemo_y":               self.chemo_y,
            "chemo_radius_mm":       self.chemo_radius_mm,
            "avoid_radius_mm":       self.avoid_radius_mm,
            "aggreg_radius_mm":      self.aggreg_radius_mm,
        }
        

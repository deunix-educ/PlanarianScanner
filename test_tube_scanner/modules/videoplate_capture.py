"""
VideoPlateCapture — capture par extraction de région dans une vidéo plaque entière.

La vidéo montre l'ensemble de la plaque multi-puits (vue de dessus).
La position GRBL (x, y en mm) détermine la région extraite via px_per_mm.
Le résultat est un carré centré sur le puits courant, compatible avec
le recadrage circulaire de process_frame() comme pour toute autre capture.

Flux : video frame → crop carré (GRBL pos) → CircularCrop → tracking/display

Hot swap : set_video_file(path) remplace la vidéo sans arrêter la capture.
Thread-safe via _cap_lock.
"""
import os
os.environ['OPENCV_LOG_LEVEL'] = "0"
os.environ['OPENCV_FFMPEG_LOGLEVEL'] = "0"
import cv2
import numpy as np
import logging
import threading
from pathlib import Path

from modules.capture_interface import VideoCaptureInterface, CaptureError

logger = logging.getLogger(__name__)


class VideoPlateCapture(VideoCaptureInterface):
    """
    Lecture d'une vidéo de plaque complète avec crop dynamique à la position GRBL.

    La position GRBL (x_mm, y_mm) est convertie en coordonnées pixel via px_per_mm.
    Un carré de côté 2*crop_radius_px est extrait à cette position, puis
    process_frame() applique le masque circulaire habituel.

    La vidéo boucle automatiquement. La cadence est adaptée via frame_step
    pour correspondre au fps cible.

    Calibration : set_px_per_mm() met à jour le facteur de conversion à chaud.
    Hot swap    : set_video_file(path) change la vidéo sans interruption.
    """

    def __init__(
        self,
        video_dir,
        fps: float = 5.0,
        jpeg_quality: int = 90,
        use_tracking: bool = False,
        display=None,
        parent=None,
        crop_radius_px: int = 150,
        px_per_mm: float = 15.0,
        x_offset_mm: float = 0.0,
        y_offset_mm: float = 0.0,
        initial_video_path: str | None = None,
    ):
        super().__init__(fps, use_tracking, display, parent, jpeg_quality)
        self._video_dir = Path(video_dir)
        self._cap: cv2.VideoCapture | None = None
        self._cap_lock = threading.Lock()
        self._video_path: Path | None = (
            Path(initial_video_path) if initial_video_path else None
        )
        self._frame_w: int = 0
        self._frame_h: int = 0
        self._crop_radius_px: int = crop_radius_px
        self._px_per_mm: float = px_per_mm
        self._x_offset_mm: float = x_offset_mm
        self._y_offset_mm: float = y_offset_mm
        self._frame_step: int = 1

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def set_px_per_mm(self, px_per_mm: float) -> None:
        """Met à jour le facteur de conversion mm → pixel à chaud (depuis WellPosition)."""
        self._px_per_mm = px_per_mm
        logger.info(f"VideoPlateCapture: px_per_mm={px_per_mm:.3f}")

    def set_crop_radius_px(self, r: int) -> None:
        """Met à jour le rayon de découpe en pixels à chaud (depuis MultiWell.crop_radius)."""
        self._crop_radius_px = r
        logger.info(f"VideoPlateCapture: crop_radius_px={r}")

    def set_offset_mm(self, x_offset_mm: float, y_offset_mm: float) -> None:
        """Met à jour l'offset d'origine (xbase, ybase du MultiWell) à chaud."""
        self._x_offset_mm = x_offset_mm
        self._y_offset_mm = y_offset_mm

    def set_video_file(self, path: str) -> None:
        """
        Hot swap : remplace la vidéo courante sans arrêter la capture.
        Thread-safe — peut être appelé depuis n'importe quel thread.
        """
        new_cap = cv2.VideoCapture(path)
        if not new_cap.isOpened():
            logger.error(f"VideoPlateCapture hot swap: impossible d'ouvrir {path}")
            return

        new_w    = int(new_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        new_h    = int(new_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        nat_fps  = new_cap.get(cv2.CAP_PROP_FPS) or self._fps
        new_step = max(1, round(nat_fps / self._fps))

        with self._cap_lock:
            old_cap          = self._cap
            self._cap        = new_cap
            self._video_path = Path(path)
            self._frame_w    = new_w
            self._frame_h    = new_h
            self._frame_step = new_step

        if old_cap:
            old_cap.release()

        logger.info(f"VideoPlateCapture: hot swap → {Path(path).name} {new_w}×{new_h}")

    @property
    def video_path(self) -> Path | None:
        return self._video_path

    # ------------------------------------------------------------------
    # Implémentation VideoCaptureInterface
    # ------------------------------------------------------------------

    def open(self) -> None:
        path = self._video_path if (self._video_path and self._video_path.exists()) \
               else self._find_video()
        if path is None:
            raise CaptureError(f"Aucune vidéo trouvée dans {self._video_dir}")

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise CaptureError(f"Impossible d'ouvrir {path.name}")

        nat_fps = cap.get(cv2.CAP_PROP_FPS) or self._fps

        with self._cap_lock:
            self._cap        = cap
            self._video_path = path
            self._frame_w    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._frame_h    = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._frame_step = max(1, round(nat_fps / self._fps))

        logger.info(
            f"VideoPlateCapture: {path.name} {self._frame_w}×{self._frame_h} "
            f"@ {nat_fps:.1f} fps → step={self._frame_step}, "
            f"px_per_mm={self._px_per_mm:.2f}"
        )

    def close(self) -> None:
        with self._cap_lock:
            cap, self._cap = self._cap, None
        if cap:
            cap.release()

    def is_available(self) -> bool:
        with self._cap_lock:
            return self._cap is not None and self._cap.isOpened()

    def capture_frame(self) -> bytes:
        with self._cap_lock:
            if self._cap is None or not self._cap.isOpened():
                raise CaptureError("Vidéo non disponible")

            # Avancer dans la vidéo pour correspondre au fps cible
            for _ in range(self._frame_step - 1):
                self._cap.grab()

            ret, frame = self._cap.read()
            if not ret:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
                if not ret:
                    raise CaptureError("Impossible de relire la vidéo")

            frame_w = self._frame_w
            frame_h = self._frame_h

        # Position GRBL (mm) → coordonnées pixel dans la vidéo plaque
        grbl  = getattr(self.parent, 'grbl', None) if self.parent else None
        x_mm  = float(getattr(grbl, 'x', None) or 0.0)
        y_mm  = float(getattr(grbl, 'y', None) or 0.0)

        # À l'origine CNC (0, 0) : retourner la plaque entière à sa résolution native
        if x_mm == 0.0 and y_mm == 0.0:
            ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
            if not ok:
                raise CaptureError("Encodage JPEG échoué")
            return buf.tobytes()

        cx = int((x_mm - self._x_offset_mm) * self._px_per_mm)
        cy = int((y_mm - self._y_offset_mm) * self._px_per_mm)
        r  = self._crop_radius_px

        # Extraction du carré centré sur le puits courant
        x1 = max(0, cx - r)
        y1 = max(0, cy - r)
        x2 = min(frame_w, cx + r)
        y2 = min(frame_h, cy + r)
        crop = frame[y1:y2, x1:x2]

        # Padding noir si le crop déborde du bord de la vidéo
        if crop.shape[0] != 2 * r or crop.shape[1] != 2 * r:
            padded = np.zeros((2 * r, 2 * r, 3), dtype=np.uint8)
            padded[:crop.shape[0], :crop.shape[1]] = crop
            crop = padded

        ok, buf = cv2.imencode('.jpg', crop, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        if not ok:
            raise CaptureError("Encodage JPEG échoué")
        return buf.tobytes()

    # ------------------------------------------------------------------
    # Privé
    # ------------------------------------------------------------------

    def _find_video(self) -> Path | None:
        """Retourne le premier fichier vidéo trouvé dans video_dir."""
        self._video_dir.mkdir(parents=True, exist_ok=True)
        for ext in ('*.mp4', '*.avi', '*.MP4', '*.AVI'):
            files = sorted(self._video_dir.glob(ext))
            if files:
                return files[0]
        return None

'''
Simulateur GCode pour tester sans CNC physique.

    GRBLController (simulé):
        Reproduit fidèlement l'API de grbl.py
        Simule les mouvements (X, Y) avec délai proportionnel au feed rate
        Le mode absolu est retenu
        Aucune dépendance à pyserial

Created on 07 mai 2026

@author: denis@miraceti.net
'''
import logging
import time
import threading
import math


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GRBLController:
    '''
    Simulateur du contrôleur GRBL 1.1f (L2544 Laser Engraving Machine).
    API 100% identique à grbl.py — interchangeable sans modifier le code appelant.
    Les délais de déplacement sont calculés à partir du feed rate et de la distance.
    '''
    X_MAX = 350
    Y_MAX = 250
    X_MIN = 0
    Y_MIN = 0

    # Facteur de compression du temps simulé (1.0 = temps réel, 0.1 = 10x plus rapide)
    TIME_SCALE = 0.1

    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, timeout=1, send_callback=None, x_max=None, y_max=None):
        logger.info(f"GRBLController SIMULATOR::init begin {port} device port")

        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

        if x_max is not None:
            self.X_MAX = x_max
        if y_max is not None:
            self.Y_MAX = y_max

        self._state = send_callback
        if self._state is None:
            self._state = self._send_msg

        # Position courante simulée
        self.x, self.y = 0.0, 0.0

        # État interne de la machine simulée
        self._machine_state = 'Idle'   # Idle | Run | Alarm
        self._connected = False

    # -------------------------------------------------------------------------
    # Méthodes utilitaires
    # -------------------------------------------------------------------------

    def wait_for(self, delay=1.0):
        # Applique le facteur de compression temporelle
        threading.Event().wait(delay * self.TIME_SCALE)

    def _send_msg(self, **msg):
        # Callback par défaut : simple affichage console
        print(msg)

    # -------------------------------------------------------------------------
    # Simulation de la couche série (pas de port réel)
    # -------------------------------------------------------------------------

    def clear_buffer(self):
        # Rien à vider : pas de port série physique
        logger.debug("SIMULATOR::clear_buffer (no-op)")

    def start_connection(self):
        '''Simule l'ouverture de la connexion série et l'initialisation GRBL.'''
        logger.info(f"SIMULATOR::start_connection on {self.port} @ {self.baudrate} baud")
        self._state(state='serial', msg="Grbl 1.1f ['$' for help]")
        self._connected = True
        self._wake_up()
        self._init_machine()
        logger.info("SIMULATOR::start_connection started")

    def _init_machine(self):
        # Envoie les commandes d'initialisation (simulées)
        self.send("G21")   # Unités en mm
        self.send("G90")   # Mode absolu

    def _clamp(self, x, y):
        self.clear_buffer()
        x = max(self.X_MIN, min(self.X_MAX, x))
        y = max(self.Y_MIN, min(self.Y_MAX, y))
        return x, y

    def _wake_up(self):
        # Simule l'envoi des octets de réveil et la réponse GRBL
        logger.debug("SIMULATOR::_wake_up")
        self.wait_for(1)
        self._state(state='serial', msg="")   # ligne vide typique de GRBL au démarrage
        self.clear_buffer()

    # -------------------------------------------------------------------------
    # Envoi de commandes
    # -------------------------------------------------------------------------

    def send(self, cmd, wait_ok=True, timeout=5):
        try:
            return self._send(cmd, wait_ok, timeout)
        except Exception as e:
            self._state(state='error', msg=f"Error send {cmd} command: {e}")
            self.close()
            self.start_connection()

    def recover(self):
        self._state(state='recover', msg="Erreur, récupération de GRBL...")
        self.wait_for(1)
        self._wake_up()

    def _send(self, cmd, wait_ok=True, timeout=5):
        '''Simule l'envoi d'une commande GCode et retourne "ok".'''
        self._state(state='send', msg=f">>> {cmd}")
        logger.debug(f"SIMULATOR::_send {cmd}")

        # Interprète les commandes de mouvement pour mettre à jour la position interne
        self._interpret_gcode(cmd)

        if not wait_ok:
            return None

        # Simule une réponse "ok" immédiate
        return "ok"

    def _interpret_gcode(self, cmd):
        '''
        Analyse le GCode pour mettre à jour x, y et simuler le délai de déplacement.
        Gère : G0, G1, G53 G1, G92, G21, G90, G91, $X, $H.
        '''
        cmd_upper = cmd.strip().upper()

        # --- Commandes sans mouvement ---
        if cmd_upper in ("G21", "G90", "G91", "$X"):
            return
        if cmd_upper == "$H":
            # Homing : retour à l'origine avec délai simulé
            self._machine_state = 'Run'
            self._state(state='send', msg="SIMULATOR: homing...")
            distance = math.hypot(self.x, self.y)
            self._simulate_move_delay(distance, feed=3000)
            self.x, self.y = 0.0, 0.0
            self._machine_state = 'Idle'
            return

        # --- Extraction des coordonnées X, Y et du feed F ---
        tokens = cmd_upper.replace(',', ' ').split()
        new_x, new_y, feed = self.x, self.y, 1000.0

        for token in tokens:
            if token.startswith('X'):
                try:
                    new_x = float(token[1:])
                except ValueError:
                    pass
            elif token.startswith('Y'):
                try:
                    new_y = float(token[1:])
                except ValueError:
                    pass
            elif token.startswith('F'):
                try:
                    feed = float(token[1:])
                except ValueError:
                    pass

        # --- G92 : redéfinit la position courante sans déplacement ---
        if 'G92' in tokens:
            self.x = new_x
            self.y = new_y
            logger.debug(f"SIMULATOR: G92 position set to ({self.x:.2f}, {self.y:.2f})")
            return

        # --- Mouvement effectif (G0, G1, G53 G1, etc.) ---
        has_move = any(t in tokens for t in ('G0', 'G1', 'G53'))
        if has_move and (new_x != self.x or new_y != self.y):
            distance = math.hypot(new_x - self.x, new_y - self.y)
            self._machine_state = 'Run'
            self._simulate_move_delay(distance, feed)
            self.x = new_x
            self.y = new_y
            self._machine_state = 'Idle'
            logger.debug(f"SIMULATOR: moved to ({self.x:.2f}, {self.y:.2f})")

    def _simulate_move_delay(self, distance_mm, feed):
        '''Simule le temps de déplacement : distance / feed (mm/min) → secondes.'''
        if feed <= 0:
            return
        duration = (distance_mm / feed) * 60.0   # feed est en mm/min
        self.wait_for(duration)

    # -------------------------------------------------------------------------
    # Status machine
    # -------------------------------------------------------------------------

    def get_status(self):
        '''Retourne un status GRBL simulé au format <State|MPos:x,y,z>.'''
        status = f"<{self._machine_state}|MPos:{self.x:.3f},{self.y:.3f},0.000|FS:0,0>"
        logger.debug(f"SIMULATOR::get_status → {status}")
        return status

    def reset_grbl(self):
        self.send("$X")   # Réinitialise les alarmes
        self.wait_idle()
        self.send("$H")   # Homing
        self.wait_idle()

    def _mpos(self, status):
        if "MPos" in status:
            mpos = status.split("MPos:")[1].split("|")[0]
            x, y, *_ = mpos.split(",")
            self._state(state='Mpos', msg=f"pos >>> ({x}, {y})")
            return float(x), float(y)
        return None, None

    def get_mpos(self):
        return self._mpos(self.get_status())

    def wait_idle(self, timeout=20):
        '''Attend que la machine soit à l'état Idle (immédiat en simulation).'''
        start = time.time()
        while True:
            if time.time() - start > timeout:
                raise TimeoutError("Délai d'attente pour Idle dépassé")
            status = self.get_status()
            self.x, self.y = self._mpos(status)
            self._state(xy=True, x=self.x, y=self.y)
            if status and "Idle" in status:
                break
            self.wait_for(0.1)

    # -------------------------------------------------------------------------
    # Commandes de haut niveau (identiques à grbl.py)
    # -------------------------------------------------------------------------

    def send_command(self, cmd):
        self.send(cmd)
        self.wait_idle()

    def move_to(self, x, y, feed=1000):
        x, y = self._clamp(x, y)
        cmd = f"G53 G1 X{x:.2f} Y{y:.2f} F{feed}"
        self.send_command(cmd)

    def move_relative(self, dx=0, dy=0, feed=1000):
        x, y = self.get_mpos()   # Position actuelle
        self.move_to(x + dx, y + dy, feed=feed)

    def move_relative__(self, dx=0, dy=0, feed=1000):
        self.send("G91")   # Mode relatif
        cmd = f"G0 X{dx} Y{dy} F{feed}"
        self.send(cmd)
        self.send("G90")   # Retour en mode absolu
        self.wait_idle()

    def go_origin(self, feed=1000):
        self.move_to(0, 0, feed=feed)
        self.wait_for(2.0)

    def set_position(self, x, y):
        x, y = self._clamp(x, y)
        cmd = f"G92 X{x:.2f} Y{y:.2f}"
        self.send(cmd)
        self.wait_for(2.0)

    def move_up(self, step=10, feed=1000):
        self.move_relative(dy=step, feed=feed)

    def move_down(self, step=10, feed=1000):
        self.move_relative(dy=-step, feed=feed)

    def move_left(self, step=10, feed=1000):
        self.move_relative(dx=-step, feed=feed)

    def move_right(self, step=10, feed=1000):
        self.move_relative(dx=step, feed=feed)

    def close(self):
        # Simule la fermeture du port série
        self._connected = False
        logger.info("SIMULATOR::close — connexion simulée fermée")

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
from gi.repository import Gdk
import threading
import time
import subprocess
import os
import sys
import random
from PIL import Image
import io
import shutil

# Check if screen capture tools are available
capture_tools = ["gnome-screenshot"]
available_tools = [tool for tool in capture_tools if shutil.which(tool)]

if not available_tools:
    print("Attention : Aucun outil de capture d'écran trouvé.")
    print("Pour le mode Ambilight, installez l'outil suivant :")
    print("- gnome-screenshot: sudo apt install gnome-screenshot")
    
BRIGHTNESS_VALUE = 255
KB_PATH = "/sys/class/leds/rgb:kbd_backlight"
BRIGHTNESS_F = f"{KB_PATH}/brightness"
MULTI_IDX_F = f"{KB_PATH}/multi_index"
MULTI_INTENSITY_F = f"{KB_PATH}/multi_intensity"

class KbdRGBController:
    def __init__(self, app_inst):
        self.run = False
        self.thread = None
        self.delay = 0.001
        self.mode = "Cycle fluide"
        self.static_rgb = (255, 0, 0)
        self.app = app_inst
        self.use_sudo = False
        self.sudo_process = None
        self._test_write_permissions()
        
        self.last_ambilight_color = (0, 0, 0)
        self.ambilight_running = False
        self.ambilight_thread = None
        self.ambilight_capture_thread = None
        self.ambilight_capture_lock = threading.Lock()
        self.last_captured_image_data = None
        self.ambilight_target_fps = 30

    def _test_write_permissions(self):
        """Teste si on peut écrire directement ou si sudo est nécessaire"""
        test_file = MULTI_INTENSITY_F
        try:
            with open(test_file, 'w') as f:
                f.write("0 0 0")
            self.use_sudo = False
            print("✓ Écriture directe possible (permissions OK)")
        except PermissionError:
            self.use_sudo = True
            print("⚠ Sudo requis pour l'écriture")
        except Exception as e:
            print(f"Erreur lors du test de permissions: {e}")
            self.use_sudo = True
    
    def _setup_sudo_session(self):
        """Prépare une session sudo persistante pour éviter les multiples prompts"""
        if not self.use_sudo:
            return True
            
        try:
            result = subprocess.run(['sudo', '-n', 'true'], 
                                    capture_output=True, timeout=1)
            if result.returncode == 0:
                print("✓ Session sudo déjà active")
                return True
            else:
                print("Authentification sudo requise...")
                result = subprocess.run(['sudo', 'true'], timeout=30)
                return result.returncode == 0
        except subprocess.TimeoutExpired:
            print("Timeout lors de l'authentification sudo")
            return False
        except Exception as e:
            print(f"Erreur setup sudo: {e}")
            return False

    def w_sysfs(self, f_path, val):
        """Écriture optimisée dans sysfs"""
        if not self.use_sudo:
            try:
                with open(f_path, 'w') as f:
                    f.write(str(val))
                return True
            except Exception as e:
                print(f"Erreur écriture directe {f_path}: {e}")
                return False
        else:
            try:
                cmd = f'echo "{val}" > "{f_path}"'
                result = subprocess.run(['sudo', 'bash', '-c', cmd], 
                                        capture_output=True, timeout=2)
                return result.returncode == 0
            except subprocess.TimeoutExpired:
                print(f"Timeout sudo pour {f_path}")
                return False
            except Exception as e:
                print(f"Erreur sudo pour {f_path}: {e}")
                return False

    def w_sysfs_batch(self, values_dict):
        """Écriture en batch pour plusieurs fichiers (plus efficace)"""
        if not self.use_sudo:
            for f_path, val in values_dict.items():
                try:
                    with open(f_path, 'w') as f:
                        f.write(str(val))
                except Exception as e:
                    print(f"Erreur batch {f_path}: {e}")
                    return False
            return True
        else:
            commands = []
            for f_path, val in values_dict.items():
                commands.append(f'echo "{val}" > "{f_path}"')
            
            full_cmd = ' && '.join(commands)
            try:
                result = subprocess.run(['sudo', 'bash', '-c', full_cmd], 
                                        capture_output=True, timeout=3)
                return result.returncode == 0
            except Exception as e:
                print(f"Erreur batch sudo: {e}")
                return False

    def init_kbd(self):
        print("Initialisation du clavier...")
        
        if self.use_sudo and not self._setup_sudo_session():
            error_msg = "Impossible d'obtenir les privilèges sudo nécessaires"
            GLib.idle_add(lambda: self.app.show_err(error_msg))
            return False
        
        init_values = {
            BRIGHTNESS_F: str(BRIGHTNESS_VALUE),
            MULTI_IDX_F: "0"
        }
        
        success = self.w_sysfs_batch(init_values)
        if success:
            print("✓ Clavier initialisé avec succès")
        else:
            print("✗ Erreur lors de l'initialisation")
        
        time.sleep(0.1)
        return success

    def stop_cycle(self):
        if self.run:
            self.run = False
            self.thread.join()
            print("Cycle arrêté.")
        
        if self.ambilight_running:
            self.ambilight_running = False
            if self.ambilight_capture_thread:
                self.ambilight_capture_thread.join()
            if self.ambilight_thread:
                self.ambilight_thread.join()
            print("Mode Ambilight arrêté.")

    def start_cycle(self):
        if self.run or self.ambilight_running:
            print("Le cycle est déjà en cours.")
            return

        self.run = True
        
        if self.mode == "Ambilight":
            self.ambilight_running = True
            self.ambilight_capture_thread = threading.Thread(target=self._ambilight_capture_loop)
            self.ambilight_capture_thread.daemon = True
            self.ambilight_capture_thread.start()
            
            self.ambilight_thread = threading.Thread(target=self._ambilight_color_loop)
            self.ambilight_thread.daemon = True
            self.ambilight_thread.start()
            print(f"Mode '{self.mode}' démarré.")
        else:
            self.thread = threading.Thread(target=self._run_mode)
            self.thread.daemon = True
            self.thread.start()
            print(f"Mode '{self.mode}' démarré.")

    def _set_col(self, r, g, b):
        r, g, b = max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))
        
        success = self.w_sysfs(MULTI_INTENSITY_F, f"{r} {g} {b}")
        
        if success:
            GLib.idle_add(self.app.upd_col_prev, r, g, b)
        
        return success

    def _set_col_fast(self, r, g, b):
        r, g, b = max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))
        
        if not self.use_sudo:
            try:
                with open(MULTI_INTENSITY_F, 'w') as f:
                    f.write(f"{r} {g} {b}")
                GLib.idle_add(self.app.upd_col_prev, r, g, b)
                return True
            except:
                return False
        else:
            return self._set_col(r, g, b)

    def _run_mode(self):
        try:
            if self.mode == "Cycle fluide":
                self._col_cycle_loop()
            elif self.mode == "Couleur statique":
                self._static_col_loop()
            elif self.mode == "Respiration":
                self._breathing_loop()
            elif self.mode == "Vague arc-en-ciel":
                self._rainbow_wave_loop()
            elif self.mode == "Flash aléatoire":
                self._random_flash_loop()
        except Exception as e:
            print(f"Erreur dans le mode {self.mode}: {e}", file=sys.stderr)
            GLib.idle_add(lambda: self.app.show_err(f"Erreur dans le mode {self.mode}: {e}"))
            self.run = False

    def _col_cycle_loop(self):
        st = 1
        while self.run:
            for g in range(0, 256, st):
                if not self.run: break
                self._set_col_fast(255, g, 0)
                time.sleep(self.delay)
            for r in range(255, -1, -st):
                if not self.run: break
                self._set_col_fast(r, 255, 0)
                time.sleep(self.delay)
            for b in range(0, 256, st):
                if not self.run: break
                self._set_col_fast(0, 255, b)
                time.sleep(self.delay)
            for g in range(255, -1, -st):
                if not self.run: break
                self._set_col_fast(0, g, 255)
                time.sleep(self.delay)
            for r in range(0, 256, st):
                if not self.run: break
                self._set_col_fast(r, 0, 255)
                time.sleep(self.delay)
            for b in range(255, -1, -st):
                if not self.run: break
                self._set_col_fast(255, 0, b)
                time.sleep(self.delay)

    def _static_col_loop(self):
        r, g, b = self.static_rgb
        self._set_col(r, g, b)
        while self.run:
            time.sleep(1)

    def _breathing_loop(self):
        r, g, b = self.static_rgb
        st_val = 5
        while self.run:
            for i in range(0, 256, st_val):
                if not self.run: break
                curr_r = int(r * (i / 255.0))
                curr_g = int(g * (i / 255.0))
                curr_b = int(b * (i / 255.0))
                self._set_col(curr_r, curr_g, curr_b)
                time.sleep(self.delay)
            if self.run:
                self._set_col(r, g, b)
                time.sleep(self.delay * 50)
            for i in range(255, -1, -st_val):
                if not self.run: break
                curr_r = int(r * (i / 255.0))
                curr_g = int(g * (i / 255.0))
                curr_b = int(b * (i / 255.0))
                self._set_col(curr_r, curr_g, curr_b)
                time.sleep(self.delay)
            if self.run:
                self._set_col(0, 0, 0)
                time.sleep(self.delay * 50)

    def _rainbow_wave_loop(self):
        cols = [(255, 0, 0), (255, 127, 0), (255, 255, 0), (0, 255, 0),
                (0, 0, 255), (75, 0, 130), (143, 0, 255)]
        col_idx = 0
        while self.run:
            r, g, b = cols[col_idx]
            self._set_col(r, g, b)
            time.sleep(self.delay)
            col_idx = (col_idx + 1) % len(cols)

    def _random_flash_loop(self):
        while self.run:
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            self._set_col(r, g, b)
            time.sleep(self.delay * 200)

    def _ambilight_capture_loop(self):
        """Thread dédié pour la capture, optimisé pour la vitesse"""
        temp_file = '/tmp/ambilight_temp.jpg'
        
        print("Capture de l'écran entier pour le mode Ambilight...")
        
        while self.ambilight_running:
            try:
                # Capture l'écran entier sans l'option --area pour éviter l'invite
                cmd = ['gnome-screenshot', '--file', temp_file]
                subprocess.run(cmd, check=True, timeout=3)
                
                if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                    with open(temp_file, 'rb') as f:
                        with self.ambilight_capture_lock:
                            self.last_captured_image_data = f.read()
                    os.remove(temp_file)
                else:
                    raise FileNotFoundError("Le fichier de capture est vide ou manquant.")
            except subprocess.CalledProcessError as e:
                print(f"Erreur de capture avec gnome-screenshot: {e}", file=sys.stderr)
            except subprocess.TimeoutExpired:
                print("Timeout lors de la capture d'écran", file=sys.stderr)
            except Exception as e:
                print(f"Erreur inattendue dans la capture: {e}", file=sys.stderr)
            
            time.sleep(1.0 / self.ambilight_target_fps)


    def _ambilight_color_loop(self):
        """Thread pour l'application des couleurs"""
        last_r, last_g, last_b = self.last_ambilight_color
        
        while self.ambilight_running:
            
            new_r, new_g, new_b = last_r, last_g, last_b
            
            with self.ambilight_capture_lock:
                if self.last_captured_image_data:
                    try:
                        img = Image.open(io.BytesIO(self.last_captured_image_data))
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        
                        # Traiter uniquement les 200 pixels du bas
                        height_to_process = 200
                        height_img = img.height
                        
                        if height_img > height_to_process:
                            # Découper la partie basse de l'image
                            img = img.crop((0, height_img - height_to_process, img.width, height_img))
                            
                        pixels = img.load()
                        total_r, total_g, total_b = 0, 0, 0
                        count = img.width * img.height
                        
                        for x in range(img.width):
                            for y in range(img.height):
                                r, g, b = pixels[x, y]
                                total_r += r
                                total_g += g
                                total_b += b
                        
                        new_r = int(total_r / count)
                        new_g = int(total_g / count)
                        new_b = int(total_b / count)
                        
                        self.last_captured_image_data = None
                        
                    except Exception as e:
                        print(f"Erreur traitement image: {e}", file=sys.stderr)

            # Animation de transition fluide
            steps = 5 
            step_r = (new_r - last_r) / steps
            step_g = (new_g - last_g) / steps
            step_b = (new_b - last_b) / steps
            
            for i in range(steps):
                if not self.ambilight_running: break
                
                curr_r = last_r + step_r * i
                curr_g = last_g + step_g * i
                curr_b = last_b + step_b * i
                
                self._set_col_fast(curr_r, curr_g, curr_b)
                time.sleep(1.0 / (self.ambilight_target_fps * steps))
            
            last_r, last_g, last_b = new_r, new_g, new_b
            self.last_ambilight_color = (new_r, new_g, new_b)
            
            time.sleep(1.0 / self.ambilight_target_fps)


class App(Gtk.Window):
    def __init__(self):
        super().__init__(title="Clevo RGB Control")
        self.set_resizable(True)
        self.set_border_width(10)
        self.ctrl = KbdRGBController(self)

        if not all(map(os.path.exists, [BRIGHTNESS_F, MULTI_IDX_F, MULTI_INTENSITY_F])):
            error_msg = f"Erreur : fichiers de contrôle du clavier manquants.\nChemin recherché: {KB_PATH}\nVérifiez que :\n1. Vous avez un clavier Clevo supporté\n2. Les pilotes sont installés\n3. Vous lancez le script avec sudo"
            self.show_err(error_msg)
            return
        
        self.ctrl.init_kbd()
        self.connect("destroy", self.on_close)
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(main_box)
        
        # Grid pour les contrôles de base
        base_grid = Gtk.Grid(column_homogeneous=False, row_spacing=10, column_spacing=10)
        base_grid.set_border_width(10)
        
        self.col_prev_area = Gtk.DrawingArea()
        self.col_prev_area.set_size_request(200, 60)
        self.col_prev_area.connect("draw", self.draw_col_prev)
        self.current_rgb = (255, 0, 0)
        base_grid.attach(self.col_prev_area, 0, 0, 2, 1)

        mode_label = Gtk.Label(label="Sélectionner le mode :")
        base_grid.attach(mode_label, 0, 1, 1, 1)
        self.mode_sel = Gtk.ComboBoxText()
        modes = ["Cycle fluide", "Couleur statique", "Respiration", "Vague arc-en-ciel", "Flash aléatoire", "Ambilight"]
        for mode in modes:
            self.mode_sel.append_text(mode)
        self.mode_sel.set_active(0)
        self.mode_sel.connect("changed", self.on_mode_chg)
        base_grid.attach(self.mode_sel, 1, 1, 1, 1)

        self.start_btn = Gtk.Button(label="Démarrer")
        self.start_btn.connect("clicked", self.toggle_cyc)
        base_grid.attach(self.start_btn, 0, 2, 2, 1)
        
        main_box.pack_start(base_grid, False, False, 0)
        
        # Conteneur pour les sliders qui s'affichent dynamiquement
        self.sliders_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.pack_start(self.sliders_box, False, False, 0)

        self.create_all_control_frames()
        self.apply_css()
        self.on_mode_chg(self.mode_sel)

    def create_all_control_frames(self):
        """Crée tous les cadres de contrôle, mais les cache par défaut."""
        # Frame pour la couleur statique
        self.static_col_frame = Gtk.Frame(label="Couleur statique")
        self.static_col_grid = Gtk.Grid(row_spacing=8, column_spacing=10)
        self.static_col_grid.set_border_width(15)
        self.static_col_frame.add(self.static_col_grid)
        self.sliders_box.pack_start(self.static_col_frame, False, False, 0)
        
        self.r_slider = self.create_color_slider("Rouge :", 0)
        self.g_slider = self.create_color_slider("Vert :", 1)
        self.b_slider = self.create_color_slider("Bleu :", 2)
        self.r_slider.set_value(self.ctrl.static_rgb[0])
        self.g_slider.set_value(self.ctrl.static_rgb[1])
        self.b_slider.set_value(self.ctrl.static_rgb[2])

        # Slider pour cycle fluide (et modes similaires)
        self.cycle_speed_frame = Gtk.Frame(label="Vitesse du cycle")
        self.cycle_speed_frame.set_border_width(5)
        cycle_grid = Gtk.Grid(row_spacing=5, column_spacing=10)
        cycle_grid.set_border_width(10)
        cycle_label = Gtk.Label(label="Vitesse :")
        self.cycle_speed_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
        self.cycle_speed_slider.set_value(50)
        self.cycle_speed_slider.set_hexpand(True)
        self.cycle_speed_slider.connect("value-changed", self.upd_cycle_speed)
        self.cycle_speed_val_label = Gtk.Label(label="50")
        cycle_grid.attach(cycle_label, 0, 0, 1, 1)
        cycle_grid.attach(self.cycle_speed_slider, 1, 0, 1, 1)
        cycle_grid.attach(self.cycle_speed_val_label, 2, 0, 1, 1)
        self.cycle_speed_frame.add(cycle_grid)
        self.sliders_box.pack_start(self.cycle_speed_frame, False, False, 0)
        
        # Slider pour respiration
        self.breathing_speed_frame = Gtk.Frame(label="Vitesse de respiration")
        self.breathing_speed_frame.set_border_width(5)
        breathing_grid = Gtk.Grid(row_spacing=5, column_spacing=10)
        breathing_grid.set_border_width(10)
        breathing_label = Gtk.Label(label="Vitesse :")
        self.breathing_speed_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 50, 1)
        self.breathing_speed_slider.set_value(25)
        self.breathing_speed_slider.set_hexpand(True)
        self.breathing_speed_slider.connect("value-changed", self.upd_breathing_speed)
        self.breathing_speed_val_label = Gtk.Label(label="25")
        breathing_grid.attach(breathing_label, 0, 0, 1, 1)
        breathing_grid.attach(self.breathing_speed_slider, 1, 0, 1, 1)
        breathing_grid.attach(self.breathing_speed_val_label, 2, 0, 1, 1)
        self.breathing_speed_frame.add(breathing_grid)
        self.sliders_box.pack_start(self.breathing_speed_frame, False, False, 0)
        
        # Slider pour Ambilight FPS
        self.ambilight_fps_frame = Gtk.Frame(label="FPS Ambilight")
        self.ambilight_fps_frame.set_border_width(5)
        ambilight_grid = Gtk.Grid(row_spacing=5, column_spacing=10)
        ambilight_grid.set_border_width(10)
        ambilight_label = Gtk.Label(label="FPS :")
        self.ambilight_fps_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 5, 60, 5)
        self.ambilight_fps_slider.set_value(30)
        self.ambilight_fps_slider.set_hexpand(True)
        self.ambilight_fps_slider.connect("value-changed", self.upd_ambilight_fps)
        self.ambilight_fps_val_label = Gtk.Label(label="30")
        ambilight_grid.attach(ambilight_label, 0, 0, 1, 1)
        ambilight_grid.attach(self.ambilight_fps_slider, 1, 0, 1, 1)
        ambilight_grid.attach(self.ambilight_fps_val_label, 2, 0, 1, 1)
        self.ambilight_fps_frame.add(ambilight_grid)
        self.sliders_box.pack_start(self.ambilight_fps_frame, False, False, 0)
        
        # Slider pour flash et vague
        self.flash_freq_frame = Gtk.Frame(label="Fréquence")
        self.flash_freq_frame.set_border_width(5)
        flash_grid = Gtk.Grid(row_spacing=5, column_spacing=10)
        flash_grid.set_border_width(10)
        flash_label = Gtk.Label(label="Fréquence :")
        self.flash_freq_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 50, 1)
        self.flash_freq_slider.set_value(25)
        self.flash_freq_slider.set_hexpand(True)
        self.flash_freq_slider.connect("value-changed", self.upd_flash_freq)
        self.flash_freq_val_label = Gtk.Label(label="25")
        flash_grid.attach(flash_label, 0, 0, 1, 1)
        flash_grid.attach(self.flash_freq_slider, 1, 0, 1, 1)
        flash_grid.attach(self.flash_freq_val_label, 2, 0, 1, 1)
        self.flash_freq_frame.add(flash_grid)
        self.sliders_box.pack_start(self.flash_freq_frame, False, False, 0)
        
    def create_color_slider(self, label_text, row):
        """Crée un slider de couleur plus large avec un meilleur espacement"""
        label = Gtk.Label(label=label_text, halign=Gtk.Align.START)
        label.set_size_request(80, -1)
        
        slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        slider.set_hexpand(True)
        slider.set_size_request(250, -1)
        slider.connect("value-changed", self.upd_static_col)
        
        value_label = Gtk.Label(label=str(int(slider.get_value())))
        value_label.set_size_request(40, -1)
        
        self.static_col_grid.attach(label, 0, row, 1, 1)
        self.static_col_grid.attach(slider, 1, row, 1, 1)
        self.static_col_grid.attach(value_label, 2, row, 1, 1)
        
        slider.value_label = value_label
        return slider

    def upd_cycle_speed(self, scale):
        """Met à jour la vitesse pour les cycles fluides et similaires"""
        speed_val = int(scale.get_value())
        self.cycle_speed_val_label.set_text(str(speed_val))
        
        # Conversion: 1-100 vers delay optimal (beaucoup plus rapide)
        # Ajustement des valeurs pour un délai encore plus court
        max_delay = 0.005
        min_delay = 0.00001
        norm_speed = (speed_val - 1) / 99
        self.ctrl.delay = max_delay - (norm_speed * (max_delay - min_delay))

    def upd_breathing_speed(self, scale):
        """Met à jour la vitesse pour la respiration"""
        speed_val = int(scale.get_value())
        self.breathing_speed_val_label.set_text(str(speed_val))
        
        max_delay = 0.08
        min_delay = 0.005
        norm_speed = (speed_val - 1) / 49
        self.ctrl.delay = max_delay - (norm_speed * (max_delay - min_delay))

    def upd_ambilight_fps(self, scale):
        """Met à jour les FPS pour Ambilight"""
        fps_val = int(scale.get_value())
        self.ambilight_fps_val_label.set_text(str(fps_val))
        self.ctrl.ambilight_target_fps = fps_val

    def upd_flash_freq(self, scale):
        """Met à jour la fréquence pour flash et vague"""
        freq_val = int(scale.get_value())
        self.flash_freq_val_label.set_text(str(freq_val))
        
        max_delay = 0.2
        min_delay = 0.01
        norm_freq = (freq_val - 1) / 49
        self.ctrl.delay = max_delay - (norm_freq * (max_delay - min_delay))

    def apply_css(self):
        style_provider = Gtk.CssProvider()
        css = """
            window {
                background-color: #212529;
            }
            label {
                color: #f8f9fa;
                font-family: 'Inter', sans-serif;
                font-size: 14px;
            }
            #main_grid {
                padding: 20px;
                border-radius: 12px;
                background-color: #2c3034;
            }
            window button {
                background-color: #0d6efd;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                transition: background-color 0.2s ease, box-shadow 0.2s ease;
            }
            window button:hover {
                background-color: #0b5ed7;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            }
            window button:active {
                background-color: #0a58ca;
            }
            window combobox {
                background-color: #343a40;
                color: #f8f9fa;
                border: 1px solid #495057;
                border-radius: 8px;
                padding: 6px;
            }
            window combobox:hover {
                border-color: #6c757d;
            }
            window combobox popover {
                background-color: #343a40;
                border: 1px solid #495057;
            }
            window combobox row {
                background-color: #343a40;
                color: #f8f9fa;
            }
            window combobox row:hover {
                background-color: #495057;
            }
            
            frame {
                background-color: #343a40;
                border: 1px solid #495057;
                border-radius: 12px;
                padding: 15px;
            }
            frame label {
                color: #e9ecef;
                font-weight: bold;
            }
            scale trough {
                background-color: #6c757d;
                border-radius: 4px;
                min-height: 8px;
            }
            scale slider {
                background-color: #e9ecef;
                border-radius: 6px;
                min-width: 16px;
                min-height: 16px;
                transition: background-color 0.2s ease;
            }
            scale slider:hover {
                background-color: #dee2e6;
            }
            scale slider:active {
                background-color: #adb5bd;
            }
            #color_preview {
                border: 2px solid #6c757d;
                border-radius: 8px;
            }
            .dark-dialog {
                background-color: #2c3034;
            }
            .dark-dialog label {
                color: #f8f9fa;
            }
            .dark-dialog button {
                background-color: #dc3545;
                color: #ffffff;
                border: none;
                border-radius: 8px;
            }
            .dark-dialog button:hover {
                background-color: #c82333;
            }
            .dark-dialog button:active {
                background-color: #bd2130;
            }
        """
        style_provider.load_from_data(css.encode('utf-8'))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        self.get_style_context().add_class("window")
        self.col_prev_area.set_name("color_preview")
        
    def draw_col_prev(self, widget, cr):
        r, g, b = self.current_rgb
        r, g, b = r / 255.0, g / 255.0, b / 255.0
        cr.set_source_rgb(r, g, b)
        cr.rectangle(0, 0, widget.get_allocated_width(), widget.get_allocated_height())
        cr.fill()

    def upd_col_prev(self, r, g, b):
        self.current_rgb = (r, g, b)
        self.col_prev_area.queue_draw()

    def toggle_cyc(self, button):
        if self.ctrl.run or self.ctrl.ambilight_running:
            self.ctrl.stop_cycle()
            button.set_label("Démarrer")
        else:
            self.ctrl.start_cycle()
            button.set_label("Arrêter")

    def upd_static_col(self, scale):
        r = int(self.r_slider.get_value())
        g = int(self.g_slider.get_value())
        b = int(self.b_slider.get_value())
        
        self.r_slider.value_label.set_text(str(r))
        self.g_slider.value_label.set_text(str(g))
        self.b_slider.value_label.set_text(str(b))
        
        self.ctrl.static_rgb = (r, g, b)
        self.upd_col_prev(r, g, b)

        if self.ctrl.run and self.ctrl.mode == "Couleur statique":
            self.ctrl._set_col(r, g, b)
        elif self.ctrl.run and self.ctrl.mode == "Respiration":
            self.ctrl.stop_cycle()
            self.ctrl.start_cycle()
            
    def on_mode_chg(self, combobox):
        new_mode = combobox.get_active_text()
        if not new_mode:
            return
            
        print(f"Mode changé pour : {new_mode}")
        
        if self.ctrl.run or self.ctrl.ambilight_running:
            self.ctrl.stop_cycle()
            self.start_btn.set_label("Démarrer")
        
        self.ctrl.mode = new_mode

        # Masquer tous les contrôles d'abord
        self.static_col_frame.set_visible(False)
        self.cycle_speed_frame.set_visible(False)
        self.breathing_speed_frame.set_visible(False)
        self.ambilight_fps_frame.set_visible(False)
        self.flash_freq_frame.set_visible(False)

        # Afficher les contrôles appropriés selon le mode
        if new_mode == "Couleur statique":
            self.static_col_frame.set_visible(True)
            r, g, b = self.ctrl.static_rgb
            self.upd_col_prev(r, g, b)
            
        elif new_mode == "Respiration":
            self.static_col_frame.set_visible(True)
            self.breathing_speed_frame.set_visible(True)
            self.upd_col_prev(self.ctrl.static_rgb[0], self.ctrl.static_rgb[1], self.ctrl.static_rgb[2])
            self.upd_breathing_speed(self.breathing_speed_slider)
            
        elif new_mode == "Ambilight":
            self.ambilight_fps_frame.set_visible(True)
            self.upd_col_prev(128, 128, 128)
            self.upd_ambilight_fps(self.ambilight_fps_slider)
            
        elif new_mode in ["Flash aléatoire", "Vague arc-en-ciel"]:
            self.flash_freq_frame.set_visible(True)
            self.upd_col_prev(128, 128, 128)
            self.upd_flash_freq(self.flash_freq_slider)
            
        else: # Cycle fluide
            self.cycle_speed_frame.set_visible(True)
            self.upd_col_prev(255, 0, 0)
            self.upd_cycle_speed(self.cycle_speed_slider)

    def on_close(self, widget):
        print("Fermeture de l'application...")
        self.ctrl.stop_cycle()
        Gtk.main_quit()
        
    def show_err(self, message):
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Erreur",
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
        
if __name__ == '__main__':
    app = App()
    app.show_all()
    Gtk.main()

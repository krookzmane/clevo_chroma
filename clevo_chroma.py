import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf
import threading
import time
import os
import sys
import random
import colorsys
import math

KB_PATH = "/sys/class/leds/rgb:kbd_backlight/multi_intensity"
UI_UPDATE_RATE = 200
LED_REFRESH_RATE = 0.016

class HighPerfEngine:
    def __init__(self, ui_callback=None):
        self.running = False
        self.fd = None
        self.last_written_bytes = None
        self.ui_callback = ui_callback
        self.current_rgb_for_ui = (0, 0, 0)
        
        self.fluid_lut = []
        self._generate_lut()

        self._init_hardware()
        self._set_high_priority()

    def _generate_lut(self):
        print("⚡ Pré-calcul du cache de couleurs (LUT)...")
        steps = 1000
        for i in range(steps):
            hue = i / steps
            r, g, b = [int(c * 255) for c in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]
            self.fluid_lut.append(f"{r} {g} {b}".encode('ascii'))

    def _init_hardware(self):
        try:
            self.fd = os.open(KB_PATH, os.O_WRONLY | os.O_TRUNC)
        except (PermissionError, FileNotFoundError):
            self.fd = None
            print(f"⚠ ERREUR CRITIQUE: Impossible d'écrire dans {KB_PATH}")
            print("➜ Exécute: sudo chmod 666 /sys/class/leds/rgb:kbd_backlight/multi_intensity")

    def _set_high_priority(self):
        try:
            os.nice(-10) 
            print("🚀 Priorité CPU élevée activée.")
        except PermissionError:
            pass

    def _fast_write(self, data_bytes):
        if data_bytes == self.last_written_bytes:
            return
        
        if self.fd:
            try:
                os.pwrite(self.fd, data_bytes, 0)
                self.last_written_bytes = data_bytes
            except OSError:
                pass

    def loop_fluid_lut(self):
        idx = 0
        length = len(self.fluid_lut)
        lut = self.fluid_lut
        write = self._fast_write
        delay = 0.03
        
        while self.running:
            write(lut[idx])
            idx = (idx + 1) % length
            time.sleep(delay)

            if idx % 10 == 0: 
                parts = lut[idx].split(b' ')
                self.current_rgb_for_ui = (int(parts[0]), int(parts[1]), int(parts[2]))

    def loop_ambilight_native(self):
        screen = Gdk.Screen.get_default()
        root = screen.get_root_window()
        w, h = screen.get_width(), screen.get_height()
        
        h_capture = 100
        y_origin = h - h_capture
        
        prev_r, prev_g, prev_b = 0.0, 0.0, 0.0
        smoothing = 0.2
        write = self._fast_write
        sleep = time.sleep
        get_pixbuf = Gdk.pixbuf_get_from_window
        
        while self.running:
            try:
                pb = get_pixbuf(root, 0, y_origin, w, h_capture)
                if not pb: continue

                tiny_pb = pb.scale_simple(1, 1, GdkPixbuf.InterpType.BILINEAR)
                px = tiny_pb.get_pixels()
                r, g, b = px[0], px[1], px[2]
                
                prev_r += (r - prev_r) * smoothing
                prev_g += (g - prev_g) * smoothing
                prev_b += (b - prev_b) * smoothing
                
                data = f"{int(prev_r)} {int(prev_g)} {int(prev_b)}".encode('ascii')
                write(data)
                
                self.current_rgb_for_ui = (int(prev_r), int(prev_g), int(prev_b))
                
            except Exception:
                pass
            
            sleep(LED_REFRESH_RATE)

    def loop_static(self, rgb_bytes):
        self._fast_write(rgb_bytes)
        parts = rgb_bytes.split(b' ')
        self.current_rgb_for_ui = (int(parts[0]), int(parts[1]), int(parts[2]))
        while self.running:
            time.sleep(1)

    def start(self, mode, r=255, g=0, b=0):
        self.stop()
        self.running = True
        
        if mode == "Fluid Cycle":
            target = self.loop_fluid_lut
            args = ()
        elif mode == "Ambilight":
            target = self.loop_ambilight_native
            args = ()
        elif mode == "Static":
            target = self.loop_static
            args = (f"{r} {g} {b}".encode('ascii'),)
        else:
            return

        self.thread = threading.Thread(target=target, args=args, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join(timeout=0.1)

    def close(self):
        self.stop()
        if self.fd: os.close(self.fd)

class App(Gtk.Window):
    def __init__(self):
        super().__init__(title="RGB MAX")
        self.set_default_size(250, 150)
        self.set_border_width(10)
        self.set_position(Gtk.WindowPosition.CENTER)
        
        self.engine = HighPerfEngine()
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.add(vbox)

        self.area = Gtk.DrawingArea()
        self.area.set_size_request(-1, 40)
        self.area.connect("draw", self.on_draw)
        vbox.pack_start(self.area, False, False, 0)

        self.combo = Gtk.ComboBoxText()
        for m in ["Fluid Cycle", "Ambilight", "Static", "OFF"]:
            self.combo.append_text(m)
        self.combo.set_active(0)
        self.combo.connect("changed", self.on_change)
        vbox.pack_start(self.combo, False, False, 0)

        GLib.timeout_add(UI_UPDATE_RATE, self.update_ui)
        self.connect("destroy", self.on_quit)
        
        self.on_change(self.combo)

    def on_change(self, combo):
        txt = combo.get_active_text()
        if txt == "OFF":
            self.engine.start("Static", 0, 0, 0)
        elif txt == "Static":
            self.engine.start("Static", 255, 0, 0)
        else:
            self.engine.start(txt)

    def update_ui(self):
        if self.engine.running:
            self.area.queue_draw()
        return True

    def on_draw(self, widget, cr):
        r, g, b = self.engine.current_rgb_for_ui
        cr.set_source_rgb(r/255.0, g/255.0, b/255.0)
        cr.rectangle(0, 0, widget.get_allocated_width(), widget.get_allocated_height())
        cr.fill()

    def on_quit(self, *args):
        self.engine.close()
        Gtk.main_quit()

if __name__ == "__main__":
    if not os.access(KB_PATH, os.W_OK):
        print("\033[91m PERMISSION DENIED \033[0m")
        print(f"Run: sudo chmod 666 {KB_PATH}")
    
    win = App()
    win.show_all()
    Gtk.main()

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import subprocess
import os
import random

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
        self.mode = "Fluid Cycle"
        self.static_rgb = (255, 0, 0)
        self.app = app_inst

    def w_sysfs(self, f_path, val):
        try:
            cmd = f"echo '{val}' | tee {f_path}"
            p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, err = p.communicate()
            if p.returncode != 0:
                print(f"Error writing to {f_path}: {err.decode().strip()}", file=os.sys.stderr)
        except Exception as e:
            print(f"Error on {f_path}: {e}", file=os.sys.stderr)

    def init_kbd(self):
        print("Initializing keyboard...")
        self.w_sysfs(BRIGHTNESS_F, str(BRIGHTNESS_VALUE))
        print(f"Brightness set to: {BRIGHTNESS_VALUE}")
        self.w_sysfs(MULTI_IDX_F, "0")
        print("Keyboard mode set to 'fixed color'.")
        time.sleep(0.1)

    def stop_cycle(self):
        self.run = False
        if self.thread and self.thread.is_alive():
            print("Stopping cycle...")
        print("Cycle stopped.")

    def start_cycle(self):
        if self.run:
            print("Cycle already running.")
            return

        self.run = True
        self.thread = threading.Thread(target=self._run_mode)
        self.thread.daemon = True
        self.thread.start()
        print(f"Mode '{self.mode}' started.")

    def _set_col(self, r, g, b):
        self.w_sysfs(MULTI_INTENSITY_F, f"{int(r)} {int(g)} {int(b)}")
        self.app.master.after(0, self.app.upd_col_prev, r, g, b)

    def _run_mode(self):
        if self.mode == "Fluid Cycle":
            self._col_cycle_loop()
        elif self.mode == "Static Color":
            self._static_col_loop()
        elif self.mode == "Breathing":
            self._breathing_loop()
        elif self.mode == "Rainbow Wave":
            self._rainbow_wave_loop()
        elif self.mode == "Random Flash":
            self._random_flash_loop()

    def _col_cycle_loop(self):
        st = 10
        while self.run:
            for g in range(0, 256, st):
                if not self.run: break
                self._set_col(255, g, 0)
                time.sleep(self.delay)
            if self.run: self._set_col(255, 255, 0)

            for r in range(255, -1, -st):
                if not self.run: break
                self._set_col(r, 255, 0)
                time.sleep(self.delay)
            if self.run: self._set_col(0, 255, 0)

            for b in range(0, 256, st):
                if not self.run: break
                self._set_col(0, 255, b)
                time.sleep(self.delay)
            if self.run: self._set_col(0, 255, 255)

            for g in range(255, -1, -st):
                if not self.run: break
                self._set_col(0, g, 255)
                time.sleep(self.delay)
            if self.run: self._set_col(0, 0, 255)

            for r in range(0, 256, st):
                if not self.run: break
                self._set_col(r, 0, 255)
                time.sleep(self.delay)
            if self.run: self._set_col(255, 0, 255)

            for b in range(255, -1, -st):
                if not self.run: break
                self._set_col(255, 0, b)
                time.sleep(self.delay)
            if self.run: self._set_col(255, 0, 0)

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

            if self.run: self._set_col(r, g, b)
            time.sleep(self.delay * 5)

            for i in range(255, -1, -st_val):
                if not self.run: break
                curr_r = int(r * (i / 255.0))
                curr_g = int(g * (i / 255.0))
                curr_b = int(b * (i / 255.0))
                self._set_col(curr_r, curr_g, curr_b)
                time.sleep(self.delay)
            if self.run: self._set_col(0, 0, 0)
            time.sleep(self.delay * 5)

    def _rainbow_wave_loop(self):
        cols = [(255, 0, 0), (255, 127, 0), (255, 255, 0), (0, 255, 0),
                (0, 0, 255), (75, 0, 130), (143, 0, 255)]

        col_idx = 0
        while self.run:
            r, g, b = cols[col_idx]
            self._set_col(r, g, b)
            time.sleep(self.delay * 50)
            col_idx = (col_idx + 1) % len(cols)

    def _random_flash_loop(self):
        while self.run:
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            self._set_col(r, g, b)
            time.sleep(self.delay * 100)

class App:
    def __init__(self, mstr):
        self.master = mstr
        mstr.title("Clevo RGB Control")
        mstr.geometry("500x380")
        mstr.resizable(True, True)

        self.ctrl = KbdRGBController(self)

        if not all(map(os.path.exists, [BRIGHTNESS_F, MULTI_IDX_F, MULTI_INTENSITY_F])):
            self.show_err("Error: Keyboard control files missing or path incorrect.\nEnsure keyboard driver is installed and sysfs files are present.")
            self.master.destroy()
            return

        self.ctrl.init_kbd()

        mf = ttk.Frame(mstr, padding="10")
        mf.pack(fill=tk.BOTH, expand=True)

        self.col_prev_canvas = tk.Canvas(mf, width=150, height=50, bg="black", relief=tk.RIDGE, bd=2)
        self.col_prev_canvas.pack(pady=10)
        self.col_prev_rect = self.col_prev_canvas.create_rectangle(0, 0, 150, 50, fill="black", outline="")

        ttk.Label(mf, text="Select Mode:").pack(pady=(0, 5))
        self.mode_sel = ttk.Combobox(mf,
                                          values=["Fluid Cycle", "Static Color", "Breathing", "Rainbow Wave", "Random Flash"],
                                          state="readonly")
        self.mode_sel.set(self.ctrl.mode)
        self.mode_sel.pack(pady=5)
        self.mode_sel.bind("<<ComboboxSelected>>", self.on_mode_chg)

        self.start_btn = ttk.Button(mf, text="Start", command=self.toggle_cyc)
        self.start_btn.pack(pady=10)

        self.static_col_frame = ttk.LabelFrame(mf, text="Static Color", padding="10")

        ttk.Label(self.static_col_frame, text="Red:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.r_slider = ttk.Scale(self.static_col_frame, from_=0, to_=255, orient=tk.HORIZONTAL, command=self.upd_static_col)
        self.r_slider.set(self.ctrl.static_rgb[0])
        self.r_slider.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.r_lbl = ttk.Label(self.static_col_frame, text=str(self.ctrl.static_rgb[0]))
        self.r_lbl.grid(row=0, column=2, padx=5, pady=2, sticky="w")

        ttk.Label(self.static_col_frame, text="Green:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.g_slider = ttk.Scale(self.static_col_frame, from_=0, to_=255, orient=tk.HORIZONTAL, command=self.upd_static_col)
        self.g_slider.set(self.ctrl.static_rgb[1])
        self.g_slider.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        self.g_lbl = ttk.Label(self.static_col_frame, text=str(self.ctrl.static_rgb[1]))
        self.g_lbl.grid(row=1, column=2, padx=5, pady=2, sticky="w")

        ttk.Label(self.static_col_frame, text="Blue:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.b_slider = ttk.Scale(self.static_col_frame, from_=0, to_=255, orient=tk.HORIZONTAL, command=self.upd_static_col)
        self.b_slider.set(self.ctrl.static_rgb[2])
        self.b_slider.grid(row=2, column=1, padx=5, pady=2, sticky="ew")
        self.b_lbl = ttk.Label(self.static_col_frame, text=str(self.ctrl.static_rgb[2]))
        self.b_lbl.grid(row=2, column=2, padx=5, pady=2, sticky="w")

        self.static_col_frame.columnconfigure(1, weight=1)

        self.speed_lbl_txt = ttk.Label(mf, text="Cycle Speed:")
        self.speed_lbl_txt.pack(pady=(10, 0))

        self.speed_slider = ttk.Scale(mf, from_=1, to_=100, orient=tk.HORIZONTAL, command=self.upd_speed)
        self.speed_slider.set(70)
        self.speed_slider.pack(fill=tk.X, pady=5)

        self.speed_val_lbl = ttk.Label(mf, text=f"Current Speed: {int(self.speed_slider.get())}")
        self.speed_val_lbl.pack()

        mstr.protocol("WM_DELETE_WINDOW", self.on_close)
        self.on_mode_chg(None)

    def upd_col_prev(self, r, g, b):
        hx_col = f"#{r:02x}{g:02x}{b:02x}"
        self.col_prev_canvas.itemconfig(self.col_prev_rect, fill=hx_col)

    def toggle_cyc(self):
        if self.ctrl.run:
            self.ctrl.stop_cycle()
            self.start_btn.config(text="Start")
        else:
            self.ctrl.start_cycle()
            self.start_btn.config(text="Stop")

    def upd_speed(self, val):
        spd_val = float(val)
        if self.ctrl.mode == "Breathing":
            max_int = 0.05
            min_int = 0.005
        elif self.ctrl.mode in ["Random Flash", "Rainbow Wave"]:
            max_int = 0.02
            min_int = 0.001
        else:
            max_int = 0.05
            min_int = 0.0005

        norm_spd = (spd_val - self.speed_slider.cget("from")) / (self.speed_slider.cget("to") - self.speed_slider.cget("from"))
        self.ctrl.delay = max_int - (norm_spd * (max_int - min_int))

        self.speed_val_lbl.config(text=f"Current Speed: {int(spd_val)}")

    def upd_static_col(self, event=None):
        r = int(self.r_slider.get())
        g = int(self.g_slider.get())
        b = int(self.b_slider.get())
        self.ctrl.static_rgb = (r, g, b)
        self.r_lbl.config(text=str(r))
        self.g_lbl.config(text=str(g))
        self.b_lbl.config(text=str(b))

        self.upd_col_prev(r, g, b)

        if self.ctrl.mode == "Static Color" and self.ctrl.run:
            self.ctrl._set_col(r, g, b)
        elif self.ctrl.mode == "Breathing" and self.ctrl.run:
            self.ctrl.stop_cycle()
            self.ctrl.start_cycle()

    def on_mode_chg(self, event):
        new_mode = self.mode_sel.get()
        print(f"Mode changed to: {new_mode}")

        self.ctrl.stop_cycle()
        self.ctrl.mode = new_mode
        self.start_btn.config(text="Start")

        if new_mode == "Static Color" or new_mode == "Breathing":
            self.static_col_frame.pack(pady=10, fill=tk.X)
        else:
            self.static_col_frame.pack_forget()

        self.speed_lbl_txt.pack(pady=(10, 0))
        self.speed_slider.pack(fill=tk.X, pady=5)
        self.speed_val_lbl.pack()

        if new_mode == "Static Color":
            self.speed_slider.config(state=tk.DISABLED)
            self.speed_slider.set(50)
            self.speed_lbl_txt.config(text="Speed (N/A):")
            self.speed_val_lbl.config(text="N/A")
            r, g, b = self.ctrl.static_rgb
            self.upd_col_prev(r, g, b)
        elif new_mode == "Breathing":
            self.speed_slider.config(from_=1, to_=50, state=tk.NORMAL)
            self.speed_slider.set(25)
            self.speed_lbl_txt.config(text="Breathing Speed:")
            r, g, b = self.ctrl.static_rgb
            self.upd_col_prev(r, g, b)
        elif new_mode in ["Random Flash", "Rainbow Wave"]:
            self.speed_slider.config(from_=1, to_=100, state=tk.NORMAL)
            self.speed_slider.set(70)
            self.speed_lbl_txt.config(text="Frequency:")
            self.upd_col_prev(0, 0, 0)
        else:
            self.speed_slider.config(from_=1, to_=100, state=tk.NORMAL)
            self.speed_slider.set(70)
            self.speed_lbl_txt.config(text="Cycle Speed:")
            self.upd_col_prev(255, 0, 0)

        self.upd_speed(self.speed_slider.get())

    def on_close(self):
        print("Closing app...")
        self.ctrl.stop_cycle()
        self.master.destroy()

    def show_err(self, msg):
        messagebox.showerror("Error", msg)

if __name__ == "__main__":
    if not 'SUDO_UID' in os.environ and os.geteuid() != 0:
        print("Run with sudo, please.")
        print("Example: sudo clevo_chroma")
        exit(1)

    r = tk.Tk()
    a = App(r)
    r.mainloop()

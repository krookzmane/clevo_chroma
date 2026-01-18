# CLEVO-CHROMA - Ultra-High Performance Clevo Keyboard Controller

A minimalist and relentlessly optimized RGB controller for **Clevo-based** laptops (Tuxedo, XMG, Sager, System76, etc.) running Linux.

This project was built with a single goal: **absolute performance**. Unlike other solutions that eat up CPU cycles or rely on slow external commands, this script communicates directly with the Linux kernel via low-level system calls.

## ⚡ Features

* **🚀 Extreme Performance:** Near 0% CPU usage thanks to direct file descriptor writing (`os.pwrite`) and Look-Up Tables (LUT).
* **🖥️ Native Ambilight:** Real-time synchronization of the keyboard color with the bottom of your screen. Uses the native GDK API (RAM) instead of slow disk-based screenshots.
* **🌈 Fluid Cycle:** Pre-calculated RGB animation stored in memory to strictly avoid mathematical calculations during runtime.
* **🎨 Static Mode:** Instant and simple static color setting.
* **🔕 Silent Operation:** The GUI is completely decoupled from the RGB engine (no UI lag or freezing).

## 📋 Prerequisites

* A Clevo/Tuxedo laptop with a supported RGB keyboard (the directory `/sys/class/leds/rgb:kbd_backlight` must exist).
* Python 3.
* GTK 3 libraries (usually installed by default on Ubuntu/Fedora/Mint).

### System Dependencies

On Debian, Ubuntu, Mint:

```bash
sudo apt update
sudo apt install python3-gi gir1.2-gtk-3.0

```

On Fedora:

```bash
sudo dnf install python3-gobject gtk3

```

On Arch Linux:

```bash
sudo pacman -S python-gobject gtk3

```

## ⚙️ Installation & Permissions

The script needs to write directly to the keyboard's system file. To avoid running the entire Graphical Interface as `root` (which is dangerous and not recommended), we will grant write permissions to the specific control file.

**Run this command once:**

```bash
sudo chmod 666 /sys/class/leds/rgb:kbd_backlight/multi_intensity

```

*Note: This permission resets when you reboot your PC. To make it permanent, you would need to add a `udev` rule, but the command above is sufficient for immediate use.*

## 🚀 Usage

1. Download the script .
2. Run it simply with Python:

```bash
python3 clevo_chroma.py

```

3. The interface will open. Select a mode from the dropdown menu:
* **Fluid Cycle:** A smooth rainbow loop.
* **Ambilight:** Captures the bottom of your screen to adapt the keyboard color.
* **Static:** Red by default (can be modified in the code).
* **OFF:** Turns off the lights.



## 🧠 Technical Details (Optimizations)

For the curious, here is why this script is faster than others:

1. **Syscall Deduplication:** If the requested color is identical to the previous one, no system call is made to the kernel.
2. **ASCII Pre-encoding:** Colors are not treated as numbers, but as byte strings (`bytes`) ready to be injected into the kernel buffer.
3. **Kernel Direct Write (`pwrite`):** Bypasses the repetitive `open()` and `close()` operations for every frame (which are expensive).
4. **GDK Pixel Sampling:** Ambilight doesn't read every pixel. It uses hardware-optimized scaling to get the average color instantly, avoiding slow Python loops.

## ⚠️ Disclaimer

This software modifies hardware settings via `sysfs`. Although safe and tested, the author cannot be held responsible for any potential damage to your hardware. Ensure your laptop model is compatible with standard Linux Clevo drivers.

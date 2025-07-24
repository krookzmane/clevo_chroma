# Clevo Chroma

Quick and dirty Python script to control RGB backlight on Clevo laptops. Mostly for fun, not robust.
Might set your keyboard on fire. Probably not, but hey, I warned ya.

## Features

* **RGB Color Cycling**: Smooth(ish) color transitions.
* **Static Color**: Pick a single color.
* **Breathing Effect**: Color fades in and out.
* **Rainbow Wave**: A simple rainbow effect.
* **Random Flash**: Just flashes random colors.
* **Speed Control**: Adjust how fast things happen.
* **Color Preview**: See the color before it hits your keyboard.
  
## Requirements
* Linux
* Python 3 (if running from source)
* `tkinter` (usually comes with Python)
* `sudo` access for `/sys/class/leds/rgb:kbd_backlight/*` files. Seriously, you'll need it.
    This script writes directly to kernel files. No warranty, implied or otherwise.

### Driver info (important!)

This assumes you have a Clevo laptop with a working keyboard backlight driver that exposes the RGB controls via `/sys/class/leds/rgb:kbd_backlight/`. If not, this won't work. Check your distro's repos or external modules for `clevo-wmi` or similar.

## Installation / How to Run

You have two options: use the pre-built binary or run from source (if you like messing with Python).

### Option 1: Using the Pre-built Binary

I've bundled this mess with PyInstaller for your convenience.

1.  **Download the latest release:**
    Grab the `clevo_chroma` executable from the [Releases page](https://github.com/krookzmane/clevo_chroma/releases).
2.  **Make it executable:**
    You'll need to run `chmod +x clevo_chroma`.
3.  **Make sure you have the sysfs paths:**
    Just run `ls /sys/class/leds/rgb:kbd_backlight/`. If it complains, you're missing the driver.
4.  **Run it with `sudo`:**
    ```bash
    sudo ./clevo_chroma
    ```
    Yeah, you still need `sudo`. It's talking to hardware, what did you expect?

### Option 2: Running from Source

If you prefer the raw Python experience.

1.  **Clone this repo:**
    ```bash
    git clone [https://github.com/krookzmane/clevo_chroma.git](https://github.com/krookzmane/clevo_chroma.git)
    cd Clevo-RGB-Keyboard-Control
    ```
2.  **Make sure you have the sysfs paths:**
    Just run `ls /sys/class/leds/rgb:kbd_backlight/`. If it complains, you're missing the driver.
3.  **Run it with `sudo`:**
    ```bash
    sudo python3 clevo_chroma_tkinter.py
    ```
    Yeah, you need `sudo`. Deal with it.

## Usage

* Open the app.
* Select a mode from the dropdown.
* Hit "Start".
* Play with sliders. Try not to break anything.

## Known "Features" (Bugs)

* Code might look like a toddler wrote it. It was for speed, not beauty.
* Doesn't save settings. Re-run every time. Live on the edge.

## Contributing

Pull requests are welcome.

## License

MIT. Do whatever you want with it.

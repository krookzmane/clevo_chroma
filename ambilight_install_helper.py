#!/usr/bin/env python3

import os, sys, subprocess, shutil

g = '\033[0;32m'
y = '\033[1;33m'
rd = '\033[0;31m'
n = '\033[0m'

def m(c, e):
    try:
        subprocess.run(c, check=True, text=True, capture_output=True)
        print(f"{g}✓ Success{n}")
    except subprocess.CalledProcessError as err:
        print(f"{rd}✕ Error: {e}{n}")
        print(f"Error output: {err.stderr}")
        sys.exit(1)

def main():
    r = "gnome-screenshot"
    
    print(f"{y}--- Step 1: Dependency Check ---{n}")
    print("Please ensure the following dependencies are installed:")
    print("  - On Arch Linux: git, meson, ninja, gtk3, libhandy")
    print("  - On Debian/Ubuntu: git, meson, ninja-build, libgtk-3-dev, libhandy-1-dev")
    input("Press Enter once the dependencies are ready...")

    print(f"{y}--- Step 2: Uninstall existing version ---{n}")
    if shutil.which("pacman"):
        print("Detecting pacman. Uninstalling gnome-screenshot...")
        m(["sudo", "pacman", "-Rns", "--noconfirm", "gnome-screenshot"], "Failed to uninstall gnome-screenshot via pacman.")
    elif shutil.which("apt"):
        print("Detecting apt. Uninstalling gnome-screenshot...")
        m(["sudo", "apt-get", "remove", "-y", "gnome-screenshot"], "Failed to uninstall gnome-screenshot via apt.")
    else:
        print(f"{y}⚠ Warning: No supported package manager (pacman, apt) found. Please uninstall gnome-screenshot manually if needed.{n}")

    print(f"{y}--- Step 3: Clone and modify code ---{n}")
    if os.path.exists(r):
        print(f"Directory '{r}' exists. Removing...")
        shutil.rmtree(r)
    
    print("Cloning GNOME/gnome-screenshot repo...")
    m(["git", "clone", "https://github.com/GNOME/gnome-screenshot.git"], "Failed to clone repository.")

    try:
        os.chdir(r)
    except FileNotFoundError:
        print(f"{rd}✕ Error: Directory '{r}' not found. Did the cloning fail?{n}")
        sys.exit(1)
    
    f = "src/screenshot-backend-shell.c"
    print(f"Modifying file {f} to disable flash...")
    try:
        with open(f, 'r') as file: content = file.read()
        new_content = content.replace('TRUE, /* flash */', 'FALSE, /* flash */')
        with open(f, 'w') as file: file.write(new_content)
        print(f"{g}✓ Flash successfully disabled.{n}")
    except FileNotFoundError:
        print(f"{rd}✕ Error: File '{f}' not found. Is the source code correct?{n}")
        sys.exit(1)

    s = "src/screenshot-main.c"
    print(f"Modifying file {s} to disable sound...")
    try:
        with open(s, 'r') as file: content = file.read()
        new_content = content.replace('g_settings_set_boolean(settings, "play-shutter-sound", TRUE);', 'g_settings_set_boolean(settings, "play-shutter-sound", FALSE);')
        with open(s, 'w') as file: file.write(new_content)
        print(f"{g}✓ Sound successfully disabled.{n}")
    except FileNotFoundError:
        print(f"{rd}✕ Error: File '{s}' not found. Is the source code correct?{n}")
        sys.exit(1)

    print(f"{y}--- Step 4: Compile and install ---{n}")
    print("Running 'meson setup build'...")
    m(["meson", "setup", "build"], "Meson setup failed.")
    
    print("Compiling project with 'ninja'...")
    m(["ninja", "-C", "build"], "Compilation failed.")

    print("Installing project with 'sudo meson install'...")
    m(["sudo", "meson", "install", "-C", "build"], "Installation failed. Do you have sudo permissions?")

    print(f"{g}--- Congratulations! gnome-screenshot has been installed without flash or sound. ---{n}")
    print("You can now use the modified tool.")

if __name__ == "__main__":
    main()

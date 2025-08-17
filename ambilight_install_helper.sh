#!/bin/bash

g='\033[0;32m'
y='\033[1;33m'
rd='\033[0;31m'
n='\033[0m'

m() {
    local command_to_run=("$@")
    
    if ! "${command_to_run[@]}"; then
        echo -e "${rd}✕ Oh no, something went wrong.${n}"
        exit 1
    fi
}

echo -e "${y}--- Let's get started! ---${n}"
echo "First, please make sure you have all the necessary dependencies installed:"
echo "  - On Arch Linux: git, meson, ninja, gtk3, libhandy"
echo "  - On Debian/Ubuntu: git, meson, ninja-build, libgtk-3-dev, libhandy-1-dev"
read -p "Once you're ready, press Enter to continue..."

echo -e "${y}--- Removing the old version ---${n}"
if command -v pacman &> /dev/null; then
    echo "Looks like you're on Arch Linux! I'm uninstalling gnome-screenshot for you."
    m sudo pacman -Rns --noconfirm gnome-screenshot
elif command -v apt &> /dev/null; then
    echo "Looks like you're on Debian/Ubuntu. I'm removing gnome-screenshot for you."
    m sudo apt-get remove -y gnome-screenshot
else
    echo -e "${y}⚠ Just a heads up: I couldn't find a supported package manager. Please uninstall gnome-screenshot manually if needed.${n}"
fi

echo -e "${y}--- Getting the source code ---${n}"
repo_name="gnome-screenshot"
if [ -d "$repo_name" ]; then
    echo "Found an existing folder, cleaning it up for a fresh start."
    rm -rf "$repo_name"
fi

echo "Cloning the official GNOME/gnome-screenshot repository now..."
m git clone https://github.com/GNOME/gnome-screenshot.git

if ! cd "$repo_name"; then
    echo -e "${rd}✕ Hmm, I couldn't get into the directory. Was the cloning successful?${n}"
    exit 1
fi

echo "Now for the fun part: modifying the code!"
flash_file="src/screenshot-backend-shell.c"
echo "Editing the file to disable that screen flash..."
if sed -i 's/TRUE, \/\* flash \*\//FALSE, \/\* flash \*\//' "$flash_file"; then
    echo -e "${g}✓ The flash is gone!${n}"
else
    echo -e "${rd}✕ Whoops, something went wrong while editing. Are you sure the file is correct?${n}"
    exit 1
fi

sound_file="src/screenshot-main.c"
echo "And now, silencing the shutter sound..."
if sed -i 's/g_settings_set_boolean(settings, "play-shutter-sound", TRUE);/g_settings_set_boolean(settings, "play-shutter-sound", FALSE);/' "$sound_file"; then
    echo -e "${g}✓ It's all quiet now!${n}"
else
    echo -e "${rd}✕ Something went wrong while editing. Double-check the source code!${n}"
    exit 1
fi

echo -e "${y}--- Building and installing ---${n}"
echo "Running meson to set up the build directory..."
m meson setup build

echo "Compiling the project with ninja..."
m ninja -C build

echo "Installing the project with sudo. You may need to enter your password."
m sudo meson install -C build

echo -e "${g}--- Success! The custom gnome-screenshot is ready to go! ---${n}"

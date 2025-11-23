#!/bin/bash

# Get the directory of the currently running .command file
cd "$(dirname "$0")" || exit 1

# Now everything uses the correct working directory
pip3 install -r requirements.txt

# Fix xattr for scripts inside ./scripts
xattr -rc scripts/create_minecraft_directory.sh
xattr -rc scripts/download_vanilla.sh
xattr -rc scripts/fabric.command
xattr -rc scripts/install_fabric.sh

# Run the scripts using the new folder path
./scripts/create_minecraft_directory.sh

python3 python/launcher.py

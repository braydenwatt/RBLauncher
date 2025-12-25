#!/bin/bash

# Define the directory path
APP_SUPPORT_DIR="$HOME/Library/Application Support"
MINECRAFT_DIR="$APP_SUPPORT_DIR/ReallyBadLauncher"

# Create the Minecraft launcher directory if it doesn't exist
if [ ! -d "$MINECRAFT_DIR" ]; then
    echo "Creating Minecraft launcher directory..."
    mkdir -p "$MINECRAFT_DIR"
else
    echo "Minecraft launcher directory already exists."
fi

# Create subdirectories for configuration, mods, and profiles
mkdir -p "$MINECRAFT_DIR/versions"
mkdir -p "$MINECRAFT_DIR/instances"

echo "Custom Minecraft launcher directory structure created successfully!"


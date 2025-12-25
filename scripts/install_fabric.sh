#!/bin/bash

# Fabric installer script with better debugging and Java path support
# Usage: ./install_fabric.sh [minecraft_version] [fabric_version] [java_path]
# If no minecraft_version provided, defaults to latest release

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Output helpers
debug()   { echo -e "${BLUE}[DEBUG]${NC} $1"; }
info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# Parse arguments
MINECRAFT_VERSION=$1
FABRIC_VERSION=$2
JAVA_PATH=$3

# Directories
APP_SUPPORT_DIR="$HOME/Library/Application Support"
MINECRAFT_DIR="$APP_SUPPORT_DIR/ReallyBadLauncher"
VERSIONS_BASE_DIR="$MINECRAFT_DIR/versions"

# Java path detection
if [ -n "$JAVA_PATH" ]; then
    if [ ! -x "$JAVA_PATH" ]; then
        error "Specified Java path is invalid or not executable: $JAVA_PATH"
        exit 1
    fi
    JAVA_CMD="$JAVA_PATH"
    info "Using specified Java: $JAVA_CMD"
else
    debug "No Java path specified, searching..."
    for loc in \
        "/usr/bin/java" \
        "/Library/Internet Plug-Ins/JavaAppletPlugin.plugin/Contents/Home/bin/java" \
        "$(/usr/libexec/java_home 2>/dev/null)/bin/java"; do
        if [ -x "$loc" ]; then
            JAVA_CMD="$loc"
            info "Found Java at: $loc"
            break
        fi
    done
    if [ -z "$JAVA_CMD" ]; then
        error "Java not found. Install Java or specify path as 3rd argument."
        exit 1
    fi
fi

debug "Testing Java version..."
JAVA_VERSION=$("$JAVA_CMD" -version 2>&1 | head -n 1)
info "Java version: $JAVA_VERSION"

# Ensure directories exist
debug "Creating required directories..."
mkdir -p "$VERSIONS_BASE_DIR"

# Get version manifest
MANIFEST_FILE="$MINECRAFT_DIR/version_manifest.json"
info "Downloading Minecraft version manifest..."
if ! curl -fsSL -o "$MANIFEST_FILE" "https://piston-meta.mojang.com/mc/game/version_manifest.json"; then
    error "Failed to download version manifest from Mojang"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Determine Minecraft version
if [ -z "$MINECRAFT_VERSION" ]; then
    debug "Finding latest release from manifest..."
    MINECRAFT_VERSION=$(python3 -c "
import json; print(json.load(open('$MANIFEST_FILE'))['latest']['release'])
" 2>/dev/null)
    if [ -z "$MINECRAFT_VERSION" ]; then
        error "Failed to determine latest Minecraft release"
        exit 1
    fi
    info "Using latest Minecraft release: $MINECRAFT_VERSION"
else
    info "Using specified Minecraft version: $MINECRAFT_VERSION"
fi

if [ -z "$MINECRAFT_VERSION" ]; then
    info "No Minecraft version specified. Will use latest release."
else
    info "Ensuring vanilla Minecraft $MINECRAFT_VERSION is installed..."
    if [ ! -x "$SCRIPT_DIR/download_vanilla.sh" ]; then
        error "download_vanilla.sh not found or not executable in current directory"
        exit 1
    fi
    "$SCRIPT_DIR/download_vanilla.sh" "$MINECRAFT_VERSION" "$JAVA_PATH" "true"
    info "Vanilla Minecraft $MINECRAFT_VERSION installation complete"
fi

if [ -n "$FABRIC_VERSION" ]; then
    info "Using specified Fabric version: $FABRIC_VERSION"
else
    warn "No Fabric version specified. Using latest stable."
fi

# Find version JSON URL
debug "Looking up version URL for $MINECRAFT_VERSION..."
VERSION_URL=$(python3 -c "
import json
for v in json.load(open('$MANIFEST_FILE'))['versions']:
    if v['id'] == '$MINECRAFT_VERSION':
        print(v['url'])
        break
else:
    exit(1)
" 2>/dev/null)

if [ -z "$VERSION_URL" ]; then
    error "Minecraft version $MINECRAFT_VERSION not found"
    exit 1
fi

# Download version JSON
VERSION_DIR="$VERSIONS_BASE_DIR/$MINECRAFT_VERSION"
mkdir -p "$VERSION_DIR"
VERSION_JSON="$VERSION_DIR/${MINECRAFT_VERSION}.json"

info "Downloading version JSON..."
if ! curl -s -f "$VERSION_URL" -o "$VERSION_JSON"; then
    error "Failed to download version JSON"
    exit 1
fi

# Download Minecraft client jar
CLIENT_JAR_URL=$(python3 -c "
import json; print(json.load(open('$VERSION_JSON'))['downloads']['client']['url'])
" 2>/dev/null)

CLIENT_JAR_PATH="$VERSION_DIR/${MINECRAFT_VERSION}.jar"
info "Downloading Minecraft client jar..."
if ! curl -s -f "$CLIENT_JAR_URL" -o "$CLIENT_JAR_PATH"; then
    error "Failed to download client jar"
    exit 1
fi

JAR_SIZE=$(ls -lh "$CLIENT_JAR_PATH" | awk '{print $5}')
info "Client jar downloaded successfully ($JAR_SIZE)"

# Download Fabric installer
FABRIC_INSTALLER_VERSION="1.0.3"
FABRIC_INSTALLER_PATH="$MINECRAFT_DIR/fabric-installer-$FABRIC_INSTALLER_VERSION.jar"
FABRIC_INSTALLER_URL="https://maven.fabricmc.net/net/fabricmc/fabric-installer/$FABRIC_INSTALLER_VERSION/fabric-installer-$FABRIC_INSTALLER_VERSION.jar"

info "Downloading Fabric installer v$FABRIC_INSTALLER_VERSION..."
if ! curl -s -f "$FABRIC_INSTALLER_URL" -o "$FABRIC_INSTALLER_PATH"; then
    error "Failed to download Fabric installer"
    exit 1
fi

INSTALLER_SIZE=$(ls -lh "$FABRIC_INSTALLER_PATH" | awk '{print $5}')
info "Fabric installer downloaded successfully ($INSTALLER_SIZE)"

# Run Fabric installer
info "Running Fabric installer..."
FABRIC_CMD="\"$JAVA_CMD\" -jar \"$FABRIC_INSTALLER_PATH\" client -mcversion \"$MINECRAFT_VERSION\" -dir \"$MINECRAFT_DIR\" -noprofile"
[ -n "$FABRIC_VERSION" ] && FABRIC_CMD="$FABRIC_CMD -loader \"$FABRIC_VERSION\""
debug "Fabric command: $FABRIC_CMD"

if ! eval "$FABRIC_CMD"; then
    error "Fabric installer failed"
    exit 1
fi

# Verify installation
info "Verifying Fabric installation..."
FABRIC_DIR_PATTERN="$VERSIONS_BASE_DIR/fabric-loader-*-$MINECRAFT_VERSION"
FABRIC_INSTALLED=$(find "$VERSIONS_BASE_DIR" -type d -name "fabric-loader-*-$MINECRAFT_VERSION" | head -n 1)

if [ -n "$FABRIC_INSTALLED" ]; then
    info "Fabric installed at: $(basename "$FABRIC_INSTALLED")"
else
    warn "Fabric installation could not be verified"
fi

# Cleanup
rm -f "$MANIFEST_FILE"

# Final info
info "Installation complete"
info "Minecraft version: $MINECRAFT_VERSION"
[ -n "$FABRIC_VERSION" ] && info "Fabric version: $FABRIC_VERSION"
info "Install path: $MINECRAFT_DIR"

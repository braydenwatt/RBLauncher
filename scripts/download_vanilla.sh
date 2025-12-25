#!/bin/bash

# Vanilla Minecraft downloader with better debugging and Java path support
# Usage: ./download_vanilla.sh [minecraft_version] [java_path]
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
JAVA_PATH=$2
INSTALLING_FABRIC=$3

# Directories
APP_SUPPORT_DIR="$HOME/Library/Application Support"
MINECRAFT_DIR="$APP_SUPPORT_DIR/ReallyBadLauncher"
VERSIONS_BASE_DIR="$MINECRAFT_DIR/versions"

# Java path detection (optional for vanilla download, but good for consistency)
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
        warn "Java not found. This is OK for vanilla download, but may be needed later."
    else
        debug "Testing Java version..."
        JAVA_VERSION=$("$JAVA_CMD" -version 2>&1 | head -n 1)
        info "Java version: $JAVA_VERSION"
    fi
fi

# Ensure directories exist
debug "Creating required directories..."
mkdir -p "$VERSIONS_BASE_DIR"

# Get version manifest
MANIFEST_FILE="$MINECRAFT_DIR/version_manifest.json"
info "Downloading Minecraft version manifest..."
if ! curl -s -f https://piston-meta.mojang.com/mc/game/version_manifest.json -o "$MANIFEST_FILE"; then
    error "Failed to download version manifest"
    exit 1
fi

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

debug "Found version JSON URL: $VERSION_URL"

# Create version-specific directory
VERSION_DIR="$VERSIONS_BASE_DIR/$MINECRAFT_VERSION"
debug "Creating version directory: $VERSION_DIR"
mkdir -p "$VERSION_DIR"

# Download version JSON
VERSION_JSON="$VERSION_DIR/${MINECRAFT_VERSION}.json"
info "Downloading version JSON..."
if ! curl -s -f "$VERSION_URL" -o "$VERSION_JSON"; then
    error "Failed to download version JSON"
    exit 1
fi

# Extract client jar URL
debug "Extracting client jar URL from version JSON..."
CLIENT_JAR_URL=$(python3 -c "
import json; print(json.load(open('$VERSION_JSON'))['downloads']['client']['url'])
" 2>/dev/null)

if [ -z "$CLIENT_JAR_URL" ]; then
    error "Client jar URL not found for version $MINECRAFT_VERSION"
    exit 1
fi

debug "Client jar URL: $CLIENT_JAR_URL"

# Download Minecraft client jar
CLIENT_JAR_PATH="$VERSION_DIR/${MINECRAFT_VERSION}.jar"
info "Downloading Minecraft client jar..."
if ! curl -s -f "$CLIENT_JAR_URL" -o "$CLIENT_JAR_PATH"; then
    error "Failed to download client jar"
    exit 1
fi

# Verify download
if [ ! -f "$CLIENT_JAR_PATH" ]; then
    error "Client jar was not downloaded successfully"
    exit 1
fi

JAR_SIZE=$(ls -lh "$CLIENT_JAR_PATH" | awk '{print $5}')
info "Client jar downloaded successfully ($JAR_SIZE)"

# Verify installation
if [ -f "$VERSION_JSON" ] && [ -f "$CLIENT_JAR_PATH" ]; then
    info "Vanilla Minecraft $MINECRAFT_VERSION installed successfully"
    info "Version JSON: $VERSION_JSON"
    info "Client JAR: $CLIENT_JAR_PATH"
else
    error "Installation verification failed"
    exit 1
fi

if [ "$INSTALLING_FABRIC" = "true" ]; then
    info "Installing Fabric Skipping Manifest File"
else
    info "Deleting Manifest File"
    rm -f "$MANIFEST_FILE"
fi

# Final info
info "Installation complete"
info "Minecraft version: $MINECRAFT_VERSION"
info "Install path: $MINECRAFT_DIR"
debug "Ready for Fabric installation or direct play"
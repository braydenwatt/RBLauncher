#!/bin/bash

# Fabric Installer (Offline-ready preparation)
# Usage: ./install_fabric.sh [mc_ver] [fabric_ver] [java_path]

set -e
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'
info() { echo -e "${GREEN}[INFO]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

MC_VERSION=$1
FABRIC_VERSION=$2
JAVA_PATH=$3

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_SUPPORT="$HOME/Library/Application Support/ReallyBadLauncher"

# 1. Install Vanilla Base (Assets, Natives, Vanilla Libs)
info "Ensuring base vanilla files are present..."
"$SCRIPT_DIR/download_vanilla.sh" "$MC_VERSION" "$JAVA_PATH" "true"

# 2. Setup Fabric Directories
FABRIC_DIR="$APP_SUPPORT/versions/fabric-loader-$FABRIC_VERSION-$MC_VERSION"
LIBRARIES_DIR="$APP_SUPPORT/libraries"
mkdir -p "$FABRIC_DIR"
mkdir -p "$LIBRARIES_DIR"

# 3. Download/Run Fabric Installer to generate JSON
INSTALLER_JAR="$APP_SUPPORT/fabric-installer.jar"
curl -fsSL "https://maven.fabricmc.net/net/fabricmc/fabric-installer/1.0.3/fabric-installer-1.0.3.jar" -o "$INSTALLER_JAR"

JAVA_CMD="${JAVA_PATH:-java}"
info "Running Fabric Installer..."
"$JAVA_CMD" -jar "$INSTALLER_JAR" client -mcversion "$MC_VERSION" -loader "$FABRIC_VERSION" -dir "$APP_SUPPORT" -noprofile

# 4. Download Fabric Libraries
# The installer creates a JSON file. We parse it to find libraries to download.
FABRIC_JSON="$FABRIC_DIR/fabric-loader-$FABRIC_VERSION.json"
# Note: Sometimes installer naming varies, check standard path
if [ ! -f "$FABRIC_JSON" ]; then
    # Fallback search
    FABRIC_JSON=$(find "$APP_SUPPORT/versions" -name "fabric-loader-$FABRIC_VERSION-$MC_VERSION.json" | head -1)
fi

info "Downloading Fabric Libraries..."
python3 -c "
import json, os, urllib.request

with open('$FABRIC_JSON') as f: data = json.load(f)
libs = data.get('libraries', [])

base_url = 'https://maven.fabricmc.net/'
mav_url = 'https://repo1.maven.org/maven2/'

for lib in libs:
    name = lib['name']
    parts = name.split(':')
    path = f\"{parts[0].replace('.','/')}/{parts[1]}/{parts[2]}/{parts[1]}-{parts[2]}.jar\"
    local_path = os.path.join('$LIBRARIES_DIR', path)
    
    if not os.path.exists(local_path):
        print(f'Downloading {name}...')
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        url = lib.get('url', base_url) + path
        try:
            urllib.request.urlretrieve(url, local_path)
        except:
            # Try maven central fallback
            try:
                urllib.request.urlretrieve(mav_url + path, local_path)
            except:
                print(f'Failed to download {name}')
"

info "Fabric Installation Complete."
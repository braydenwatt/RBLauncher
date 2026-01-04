#!/bin/bash

# Usage: ./fabric.command [USERNAME] [UUID] [MC_VERSION] [FABRIC_VERSION] [ACCESS_TOKEN] [INSTANCE_DIR] [JAVA_PATH]

set -e

# --- Configuration ---
USERNAME="$1"
UUID="$2"
MC_VERSION="$3"
FABRIC_VERSION="$4"
ACCESS_TOKEN="$5"
INSTANCE_DIR="$6"
JAVA_PATH="$7"

if [ -z "$JAVA_PATH" ]; then
    echo "Error: Missing arguments."
    echo "Usage: $0 [USERNAME] [UUID] [MC_VERSION] [FABRIC_VERSION] [ACCESS_TOKEN] [INSTANCE_DIR] [JAVA_PATH]"
    exit 1
fi

# --- Directories ---
MODRINTH_DIR="$HOME/Library/Application Support/ReallyBadLauncher"
GAME_DIR="$MODRINTH_DIR/instances/$INSTANCE_DIR"
LIBRARIES_DIR="$MODRINTH_DIR/libraries"
ASSETS_DIR="$MODRINTH_DIR/assets"

# Version-specific paths
VER_ID="fabric-loader-${FABRIC_VERSION}-${MC_VERSION}"
VERSION_DIR="$MODRINTH_DIR/versions/$VER_ID"
FABRIC_JSON="$VERSION_DIR/fabric-loader-${FABRIC_VERSION}.json"

# Check if installed
if [ ! -f "$FABRIC_JSON" ]; then
    # Try alternate naming convention
    FABRIC_JSON="$VERSION_DIR/$VER_ID.json"
fi

if [ ! -f "$FABRIC_JSON" ]; then
    echo -e "\033[0;31m[ERROR]\033[0m Fabric JSON not found: $FABRIC_JSON"
    echo "Please run install_fabric.sh first."
    exit 1
fi

# --- Environment Setup (Python) ---
eval $(python3 -c "
import json, os, sys

def get_vanilla_libs(json_path, lib_base):
    libs = []
    try:
        with open(json_path) as f: data = json.load(f)
        for lib in data.get('libraries', []):
            # Vanilla libraries are in downloads -> artifact -> path
            artifact = lib.get('downloads', {}).get('artifact')
            if artifact:
                full = os.path.join(lib_base, artifact['path'])
                if os.path.exists(full): libs.append(full)
    except: pass
    return libs

def get_fabric_libs(data, lib_base):
    libs = []
    for lib in data.get('libraries', []):
        # Fabric libraries are defined by Maven coordinates
        name = lib['name']
        parts = name.split(':')
        path = f'{parts[0].replace(\".\",\"/\")}/{parts[1]}/{parts[2]}/{parts[1]}-{parts[2]}.jar'
        full = os.path.join(lib_base, path)
        if os.path.exists(full): libs.append(full)
    return libs

# 1. Load Fabric JSON
with open('$FABRIC_JSON') as f: fab_data = json.load(f)

# 2. Load Inherited Vanilla JSON
inherit_ver = fab_data.get('inheritsFrom', '$MC_VERSION')
vanilla_json = f'$MODRINTH_DIR/versions/{inherit_ver}/{inherit_ver}.json'
vanilla_jar = f'$MODRINTH_DIR/versions/{inherit_ver}/{inherit_ver}.jar'

# 3. Build Classpath
cp = []
# Add Fabric Libs
cp.extend(get_fabric_libs(fab_data, '$LIBRARIES_DIR'))
# Add Vanilla Libs
cp.extend(get_vanilla_libs(vanilla_json, '$LIBRARIES_DIR'))
# Add Vanilla Client
if os.path.exists(vanilla_jar): cp.append(vanilla_jar)
# Add Fabric Loader (if not already picked up by libraries)
loader_jar = '$LIBRARIES_DIR/net/fabricmc/fabric-loader/$FABRIC_VERSION/fabric-loader-$FABRIC_VERSION.jar'
if os.path.exists(loader_jar) and loader_jar not in cp: cp.append(loader_jar)

# 4. Get Metadata (Robust Main Class Check)
raw_main_class = fab_data.get('mainClass')
if isinstance(raw_main_class, dict):
    main_class = raw_main_class.get('client', 'net.fabricmc.loader.impl.launch.knot.KnotClient')
elif isinstance(raw_main_class, str):
    main_class = raw_main_class
else:
    main_class = 'net.fabricmc.loader.impl.launch.knot.KnotClient'

try:
    with open(vanilla_json) as f: 
        asset_idx = json.load(f).get('assetIndex', {}).get('id', 'legacy')
except: 
    asset_idx = 'legacy'

# 5. Output Shell Variables
print(f'CLASSPATH=\"{\":\".join(cp)}\"')
print(f'MAIN_CLASS=\"{main_class}\"')
print(f'ASSET_INDEX=\"{asset_idx}\"')
")

if [ -z "$CLASSPATH" ]; then
    echo -e "\033[0;31m[ERROR]\033[0m Failed to build classpath. Check library installation."
    exit 1
fi

# --- Java Setup ---
if [ ! -x "$JAVA_PATH" ]; then
    echo -e "\033[0;31m[ERROR]\033[0m Invalid Java Path: $JAVA_PATH"
    exit 1
fi

# Detect Natives (assumed to be in the vanilla version folder from install script)
NATIVES_DIR="$MODRINTH_DIR/versions/$MC_VERSION/natives"
if [ ! -d "$NATIVES_DIR" ]; then
     # Fallback to Fabric folder if natives were moved there
     NATIVES_DIR="$VERSION_DIR/natives"
fi

echo -e "\033[0;32m[INFO]\033[0m Launching Fabric $FABRIC_VERSION on Minecraft $MC_VERSION..."

# --- Launch ---
mkdir -p "$GAME_DIR"

"$JAVA_PATH" \
  -XstartOnFirstThread \
  -Xmx2G \
  -Xms512M \
  -XX:+UseG1GC \
  -Djava.library.path="$NATIVES_DIR" \
  -Djna.tmpdir="$NATIVES_DIR" \
  -Dorg.lwjgl.system.SharedLibraryExtractPath="$NATIVES_DIR" \
  -Dio.netty.native.workdir="$NATIVES_DIR" \
  -Dminecraft.launcher.brand="RBLauncher" \
  -Dminecraft.launcher.version="2.0.4" \
  -cp "$CLASSPATH" \
  "$MAIN_CLASS" \
  -DFabricMcEmu= net.minecraft.client.main.Main \
  --username "$USERNAME" \
  --version "$VER_ID" \
  --gameDir "$GAME_DIR" \
  --assetsDir "$ASSETS_DIR" \
  --assetIndex "$ASSET_INDEX" \
  --uuid "$UUID" \
  --accessToken "$ACCESS_TOKEN" \
  --userType msa \
  --width 854 --height 480 \
  &

echo "$!" > "$GAME_DIR/java.pid"
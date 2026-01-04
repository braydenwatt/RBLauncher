#!/bin/bash
# Offline Vanilla Launcher
# Usage: ./launch_vanilla.command [USER] [UUID] [VER] [TOKEN] [DIR] [JAVA]

set -e
trap 'echo "Error at line $LINENO"' ERR

# Args
USERNAME="$1"
UUID="$2"
MC_VERSION="$3"
ACCESS_TOKEN="$4"
INSTANCE_DIR="$5"
JAVA_PATH="$6"

# Directories
MODRINTH_DIR="$HOME/Library/Application Support/ReallyBadLauncher"
GAME_DIR="$MODRINTH_DIR/instances/$INSTANCE_DIR"
VERSION_DIR="$MODRINTH_DIR/versions/$MC_VERSION"
ASSETS_DIR="$MODRINTH_DIR/assets"
NATIVES_DIR="$VERSION_DIR/natives"
VERSION_JSON="$VERSION_DIR/$MC_VERSION.json"

# Validation
if [ ! -f "$VERSION_JSON" ]; then
    echo "Error: Version $MC_VERSION not installed. Run download_vanilla.sh first."
    exit 1
fi

if [ ! -d "$NATIVES_DIR" ]; then
    echo "Error: Natives not found. Run download_vanilla.sh first."
    exit 1
fi

# Java Setup
if [ -x "$JAVA_PATH" ]; then
    JAVA_CMD="$JAVA_PATH"
else
    JAVA_CMD="java"
fi

# Python Helper (Read-Only)
cat > /tmp/mc_launcher_helper.py << 'EOF'
import json, sys, os
cmd = sys.argv[1]
json_path = sys.argv[2]

with open(json_path) as f: data = json.load(f)

if cmd == 'classpath':
    lib_dir = sys.argv[3]
    cp = []
    for lib in data.get('libraries', []):
        artifact = lib.get('downloads', {}).get('artifact')
        if artifact:
            cp.append(os.path.join(lib_dir, artifact['path']))
    print(':'.join(cp))

elif cmd == 'mainclass':
    print(data.get('mainClass', ''))

elif cmd == 'assetindex':
    print(data.get('assetIndex', {}).get('id', 'legacy'))
EOF

# Build Classpath
CP_LIBS=$(python3 /tmp/mc_launcher_helper.py classpath "$VERSION_JSON" "$MODRINTH_DIR/libraries")
CLASSPATH="$CP_LIBS:$VERSION_DIR/$MC_VERSION.jar"

# Get Metadata
MAIN_CLASS=$(python3 /tmp/mc_launcher_helper.py mainclass "$VERSION_JSON")
ASSET_INDEX=$(python3 /tmp/mc_launcher_helper.py assetindex "$VERSION_JSON")

rm /tmp/mc_launcher_helper.py

# Launch
echo "Launching Minecraft $MC_VERSION..."
mkdir -p "$GAME_DIR"

"$JAVA_CMD" \
    -XstartOnFirstThread \
    -Xmx2G \
    -Djava.library.path="$NATIVES_DIR" \
    -Djna.tmpdir="$NATIVES_DIR" \
    -Dorg.lwjgl.system.SharedLibraryExtractPath="$NATIVES_DIR" \
    -Dio.netty.native.workdir="$NATIVES_DIR" \
    -cp "$CLASSPATH" \
    "$MAIN_CLASS" \
    --username "$USERNAME" \
    --version "$MC_VERSION" \
    --gameDir "$GAME_DIR" \
    --assetsDir "$ASSETS_DIR" \
    --assetIndex "$ASSET_INDEX" \
    --uuid "$UUID" \
    --accessToken "$ACCESS_TOKEN" \
    --userType msa \
    --versionType release &

echo "$!" > "$GAME_DIR/java.pid"
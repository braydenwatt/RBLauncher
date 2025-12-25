#!/bin/bash

INSTANCE_DIR="$1"

MODRINTH_DIR="$HOME/Library/Application Support/ReallyBadLauncher"
GAME_DIR="$MODRINTH_DIR/instances/$INSTANCE_DIR"

kill -9 "$(cat "$GAME_DIR/java.pid")"
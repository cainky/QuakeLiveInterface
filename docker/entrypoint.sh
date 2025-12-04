#!/bin/bash
# Entrypoint for Quake Live Dedicated Server

# Replace Steam ID placeholder in config
STEAM_ID="${STEAM_ID:-76561197984141695}"
sed -i "s/STEAM_ID_PLACEHOLDER/$STEAM_ID/g" /home/steam/.quakelive/27960/baseq3/server.cfg

# Create access.txt for owner permissions
echo "${STEAM_ID}|5" > /home/steam/.quakelive/27960/baseq3/access.txt

# Set map (default to campgrounds)
MAP="${MAP:-campgrounds}"

echo "========================================"
echo "  Quake Live Dedicated Server"
echo "  Steam ID: $STEAM_ID"
echo "  Map: $MAP"
echo "========================================"

# Start the server
cd /home/steam/ql
exec ./run_server_x64_minqlx.sh +exec server.cfg +map "$MAP"

#!/bin/bash
# Quake Live Dedicated Server + minqlx Setup for WSL2
# Run this script inside WSL: bash /mnt/c/Users/kylec/QuakeLiveInterface/tools/setup_wsl_server.sh

set -e

echo "========================================"
echo "  Quake Live Server Setup for WSL2"
echo "========================================"
echo

# Create server directory
QLDIR="$HOME/quakelive"
mkdir -p "$QLDIR"
cd "$QLDIR"

echo "[1/6] Installing dependencies..."
sudo dpkg --add-architecture i386
sudo apt-get update
sudo apt-get install -y lib32gcc-s1 lib32stdc++6 libc6-i386 wget unzip python3 python3-dev git redis-server

echo
echo "[2/6] Installing SteamCMD..."
mkdir -p steamcmd
cd steamcmd
if [ ! -f steamcmd.sh ]; then
    wget -q https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz
    tar -xzf steamcmd_linux.tar.gz
    rm steamcmd_linux.tar.gz
fi

echo
echo "[3/6] Downloading Quake Live Dedicated Server..."
./steamcmd.sh +force_install_dir ../ql +login anonymous +app_update 349090 validate +quit

cd "$QLDIR"

echo
echo "[4/6] Installing minqlx..."
cd ql
if [ ! -f run_server_x64_minqlx.sh ]; then
    # Download minqlx
    wget -q https://github.com/MinoMino/minqlx/releases/download/v0.5.2/minqlx_v0.5.2.tar.gz
    tar -xzf minqlx_v0.5.2.tar.gz
    rm minqlx_v0.5.2.tar.gz
fi

# Clone minqlx-plugins if not present
if [ ! -d minqlx-plugins ]; then
    git clone https://github.com/MinoMino/minqlx-plugins.git
fi

echo
echo "[5/6] Setting up server configuration..."
mkdir -p "$HOME/.quakelive/27960/baseq3"

# Create server.cfg
cat > "$HOME/.quakelive/27960/baseq3/server.cfg" << 'EOF'
// Server Identity
set sv_hostname "AgentTraining"
set sv_tags "ffa,training"
set sv_maxclients 8
set sv_privateClients 0
set g_password ""

// Game Settings
set g_gametype 0  // FFA
set timelimit 0
set fraglimit 0
set g_inactivity 0
set g_allowVote 0

// minqlx settings
set qlx_owner "76561197984141695"
set qlx_plugins "ql_agent_plugin"
set qlx_redisAddress "127.0.0.1"
set qlx_redisPort "6379"
set qlx_redisDatabase "0"

// Agent settings
set qlx_agentSteamId "76561197984141695"
EOF

# Create access.txt (owner permissions)
echo "76561197984141695|5" > "$HOME/.quakelive/27960/baseq3/access.txt"

echo
echo "[6/6] Copying agent plugin..."
PLUGIN_SRC="/mnt/c/Users/kylec/QuakeLiveInterface/minqlx-plugin/ql_agent_plugin.py"
PLUGIN_DST="$QLDIR/ql/minqlx-plugins/ql_agent_plugin.py"
cp "$PLUGIN_SRC" "$PLUGIN_DST"

echo
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo
echo "To start the server, run:"
echo "  cd ~/quakelive/ql"
echo "  ./run_server_x64_minqlx.sh +exec server.cfg +map campgrounds"
echo
echo "Then connect from Quake Live:"
echo "  Open console (~) and type: connect localhost"
echo

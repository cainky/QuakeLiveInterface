#!/bin/bash
# Quake Live Server Start Script
# Applies environment variables and starts the dedicated server

set -e

CONFIG_DIR="/home/steam/.quakelive/27960/baseq3"
CONFIG_FILE="${CONFIG_DIR}/server.cfg"

echo "=== QuakeLive AI Training Server ==="
echo "Configuring server..."

# Apply environment variables to server config
if [ -n "${QLX_REDIS_ADDRESS}" ]; then
    sed -i "s/set qlx_redisAddress.*/set qlx_redisAddress \"${QLX_REDIS_ADDRESS}\"/" ${CONFIG_FILE}
    echo "Redis Address: ${QLX_REDIS_ADDRESS}"
fi

if [ -n "${QLX_REDIS_PORT}" ]; then
    sed -i "s/set qlx_redisPort.*/set qlx_redisPort \"${QLX_REDIS_PORT}\"/" ${CONFIG_FILE}
    echo "Redis Port: ${QLX_REDIS_PORT}"
fi

if [ -n "${QLX_REDIS_DATABASE}" ]; then
    sed -i "s/set qlx_redisDatabase.*/set qlx_redisDatabase \"${QLX_REDIS_DATABASE}\"/" ${CONFIG_FILE}
    echo "Redis Database: ${QLX_REDIS_DATABASE}"
fi

if [ -n "${QLX_AGENT_STEAM_ID}" ]; then
    sed -i "s/set qlx_agentSteamId.*/set qlx_agentSteamId \"${QLX_AGENT_STEAM_ID}\"/" ${CONFIG_FILE}
    echo "Agent Steam ID: ${QLX_AGENT_STEAM_ID}"
fi

# Wait for Redis to be available
echo "Waiting for Redis at ${QLX_REDIS_ADDRESS}:${QLX_REDIS_PORT}..."
max_attempts=30
attempt=0
while ! python3 -c "import redis; r=redis.Redis(host='${QLX_REDIS_ADDRESS}', port=${QLX_REDIS_PORT}); r.ping()" 2>/dev/null; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "ERROR: Could not connect to Redis after ${max_attempts} attempts"
        exit 1
    fi
    echo "  Attempt ${attempt}/${max_attempts}..."
    sleep 1
done
echo "Redis connected!"

# Copy custom plugins if mounted
if [ -d "/home/steam/ql/minqlx-plugins/custom" ]; then
    echo "Loading custom plugins..."
    cp -f /home/steam/ql/minqlx-plugins/custom/*.py /home/steam/ql/minqlx-plugins/ 2>/dev/null || true
fi

echo ""
echo "Starting Quake Live Dedicated Server..."
echo "======================================="

# Start the server
cd /home/steam/ql
exec ./run_server_x64_minqlx.sh +exec server.cfg

#!/bin/bash
set -e

cd /qlds

# Wait for Redis to be available
echo "[start.sh] Waiting for Redis..."
until redis-cli -h ${QLX_REDISADDRESS:-redis} ping 2>/dev/null; do
    sleep 1
done
echo "[start.sh] Redis is ready!"

# Set default map
MAP=${MAP:-toxicity}
GAMETYPE=${GAMETYPE:-duel}

echo "[start.sh] Starting Quake Live server on map: $MAP ($GAMETYPE)"

# Run with minqlx
# +dedicated 1 enables dedicated server mode
# map command format: map <mapname> <factory>
exec stdbuf -oL ./run_server_x64_minqlx.sh \
    +set dedicated 1 \
    +exec server.cfg \
    +set net_port ${NET_PORT:-27960} \
    "+map $MAP $GAMETYPE"

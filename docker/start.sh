#!/bin/bash
set -e

cd /qlds

# Wait for Redis to be available
echo "[start.sh] Waiting for Redis..."
until redis-cli -h ${QLX_REDISADDRESS:-redis} ping 2>/dev/null; do
    sleep 1
done
echo "[start.sh] Redis is ready!"

# Clear any stale Redis keys from previous runs
echo "[start.sh] Clearing stale Redis keys..."
redis-cli -h ${QLX_REDISADDRESS:-redis} DEL ql:agent:last_state ql:agent:frame ql:agent:debug ql:agent:usercmd 2>/dev/null || true

# Set default map
MAP=${MAP:-toxicity}
GAMETYPE=${GAMETYPE:-duel}
AGENT_BOT=${QLX_AGENTBOTNAME:-anarki}
BOT_SKILL=${BOT_SKILL:-5}

echo "[start.sh] Starting Quake Live server on map: $MAP ($GAMETYPE)"
echo "[start.sh] Agent bot: $AGENT_BOT, Skill: $BOT_SKILL"

# Run with minqlx
# +dedicated 1 enables dedicated server mode
# map command format: map <mapname> <factory>
exec stdbuf -oL ./run_server_x64_minqlx.sh \
    +set dedicated 1 \
    +exec server.cfg \
    +set net_port ${NET_PORT:-27960} \
    "+map $MAP $GAMETYPE"

#!/bin/bash
set -e

cd /qlds

# === EXIT DIAGNOSTICS: Capture why the server exits ===
cleanup() {
    EXIT_CODE=$?
    SIGNAL_NUM=$((EXIT_CODE - 128))
    TS=$(date '+%Y-%m-%d %H:%M:%S')
    echo ""
    echo "========================================"
    echo "[start.sh] SERVER EXITED at $TS"
    echo "[start.sh] Exit code: $EXIT_CODE"
    if [ $EXIT_CODE -gt 128 ]; then
        echo "[start.sh] Killed by signal: $SIGNAL_NUM"
        case $SIGNAL_NUM in
            2) echo "[start.sh] Signal: SIGINT (Ctrl+C)" ;;
            9) echo "[start.sh] Signal: SIGKILL (force kill)" ;;
            15) echo "[start.sh] Signal: SIGTERM (graceful shutdown)" ;;
            *) echo "[start.sh] Signal: Unknown ($SIGNAL_NUM)" ;;
        esac
    elif [ $EXIT_CODE -eq 0 ]; then
        echo "[start.sh] Clean exit (exit code 0) - server chose to quit"
    else
        echo "[start.sh] Error exit (exit code $EXIT_CODE)"
    fi
    echo "========================================"
    echo ""
}
trap cleanup EXIT

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

# Run with minqlx (using exec to replace shell - trap will still fire)
# +dedicated 1 enables dedicated server mode
# map command format: map <mapname> <factory>
stdbuf -oL ./run_server_x64_minqlx.sh \
    +set dedicated 1 \
    +exec server.cfg \
    +set net_port ${NET_PORT:-27960} \
    "+map $MAP $GAMETYPE"

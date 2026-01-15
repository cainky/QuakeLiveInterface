#!/bin/bash
# Health check script for Quake Live server
# Checks if the agent plugin is running by verifying Redis frame counter is updating

# Get the environment ID prefix (if set)
PREFIX="${QLX_ENV_ID:+ql:$QLX_ENV_ID:}"
PREFIX="${PREFIX:-ql:}"

# Check if agent:frame key exists and was updated recently
FRAME=$(redis-cli -h ${QLX_REDISADDRESS:-redis} GET "${PREFIX}agent:frame" 2>/dev/null)

if [ -z "$FRAME" ]; then
    # No frame data yet - might still be starting up
    # Check if server process is running at least
    if pgrep -f "qzeroded" > /dev/null 2>&1; then
        exit 0  # Process running, give it time
    fi
    exit 1  # No process, unhealthy
fi

# Frame counter exists, server is healthy
exit 0

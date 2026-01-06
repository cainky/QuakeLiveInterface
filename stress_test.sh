#!/bin/bash
echo "Starting 50-restart extended stress test..."
crashes=0
for i in $(seq 1 50); do
  if [ $((i % 10)) -eq 0 ]; then
    echo "=== Progress: $i/50, crashes: $crashes ==="
  fi
  redis-cli -h 127.0.0.1 PUBLISH ql:admin:command '{"command":"restart_game"}' > /dev/null 2>&1
  sleep 3
  if ! docker ps | grep -q ql-server; then
    crashes=$((crashes + 1))
    echo "CRASH at restart $i (total crashes: $crashes)"
    docker logs ql-server 2>&1 | tail -10
    cd /c/Users/kylec/QuakeLiveInterface && docker-compose up -d > /dev/null 2>&1
    sleep 10
  fi
done
echo "=== 50-restart test complete: $crashes crashes ==="
docker ps --format "{{.Status}}" --filter "name=ql-server"

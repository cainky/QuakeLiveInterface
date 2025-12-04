#!/usr/bin/env python3
"""Quick test to subscribe to game state and print one message."""
import redis
import json

r = redis.Redis('localhost', 6379, decode_responses=True)
ps = r.pubsub()
ps.subscribe('ql:game:state')

print("Waiting for game state message...")
for msg in ps.listen():
    if msg['type'] == 'message':
        data = json.loads(msg['data'])
        print(f"Agent: {data['agent']['name']}")
        print(f"Position: {data['agent']['position']}")
        print(f"Velocity: {data['agent']['velocity']}")
        print(f"Health: {data['agent']['health']}")
        print(f"Armor: {data['agent']['armor']}")
        print(f"View angles: {data['agent']['view_angles']}")
        print(f"Is alive: {data['agent']['is_alive']}")
        print(f"Map: {data['map_name']}")
        print(f"Game type: {data['game_type']}")
        print(f"Game in progress: {data['game_in_progress']}")
        break

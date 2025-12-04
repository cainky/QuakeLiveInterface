#!/usr/bin/env python3
"""
Game State Simulator for QuakeLiveInterface

Simulates a Quake Live server publishing game state to Redis.
This allows testing the visualizer and agents without a real QL server.

Usage:
    poetry run python tools/simulator.py
"""

import redis
import json
import time
import math
import random

# Campgrounds map bounds (approximate)
MAP_BOUNDS = {
    'x': (-1500, 1500),
    'y': (-1500, 1500),
    'z': (0, 500)
}

# Simulated items on the map
ITEMS = [
    {'classname': 'item_health_mega', 'origin': [500, 200, 100]},
    {'classname': 'item_armor_body', 'origin': [-400, -300, 50]},
    {'classname': 'weapon_rocketlauncher', 'origin': [0, 500, 80]},
    {'classname': 'weapon_railgun', 'origin': [-200, -600, 120]},
    {'classname': 'item_health_large', 'origin': [300, -400, 60]},
    {'classname': 'item_armor_combat', 'origin': [-600, 100, 40]},
    {'classname': 'weapon_lightning', 'origin': [700, -200, 90]},
    {'classname': 'ammo_rockets', 'origin': [100, 300, 50]},
]


class AgentSimulator:
    """Simulates an agent moving around the map."""

    def __init__(self, steam_id, name):
        self.steam_id = steam_id
        self.name = name
        self.x = random.uniform(-500, 500)
        self.y = random.uniform(-500, 500)
        self.z = 50
        self.vx = 0
        self.vy = 0
        self.vz = 0
        self.pitch = 0
        self.yaw = random.uniform(0, 360)
        self.health = 100
        self.armor = 0
        self.weapon = 'mg'
        self.ammo = {'mg': 100, 'sg': 0, 'gl': 0, 'rl': 0, 'lg': 0, 'rg': 0, 'pg': 0}

        # Movement state
        self.target_x = self.x
        self.target_y = self.y
        self.pick_new_target()

    def pick_new_target(self):
        """Pick a random point to move toward."""
        self.target_x = random.uniform(MAP_BOUNDS['x'][0] * 0.8, MAP_BOUNDS['x'][1] * 0.8)
        self.target_y = random.uniform(MAP_BOUNDS['y'][0] * 0.8, MAP_BOUNDS['y'][1] * 0.8)

    def update(self, dt):
        """Update agent position and state."""
        # Move toward target
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        dist = math.sqrt(dx*dx + dy*dy)

        if dist < 50:
            self.pick_new_target()
        else:
            speed = 320  # units per second
            self.vx = (dx / dist) * speed
            self.vy = (dy / dist) * speed
            self.x += self.vx * dt
            self.y += self.vy * dt

            # Update yaw to face movement direction
            self.yaw = math.degrees(math.atan2(dy, dx))

        # Random jumps
        if random.random() < 0.02:
            self.vz = 200
        self.z += self.vz * dt
        self.vz -= 800 * dt  # gravity
        if self.z < 50:
            self.z = 50
            self.vz = 0

        # Random health/armor changes (simulating pickups/damage)
        if random.random() < 0.01:
            self.health = min(200, self.health + random.randint(25, 50))
        if random.random() < 0.01:
            self.armor = min(200, self.armor + random.randint(25, 50))
        if random.random() < 0.005:
            self.health = max(1, self.health - random.randint(10, 30))

    def to_dict(self):
        return {
            'steam_id': self.steam_id,
            'name': self.name,
            'team': 'free',
            'position': {'x': self.x, 'y': self.y, 'z': self.z},
            'velocity': {'x': self.vx, 'y': self.vy, 'z': self.vz},
            'view_angles': {'pitch': self.pitch, 'yaw': self.yaw, 'roll': 0},
            'health': self.health,
            'armor': self.armor,
            'weapon': self.weapon,
            'ammo': self.ammo,
            'powerups': [],
            'is_alive': True
        }


def run_simulator():
    """Run the game state simulator."""
    print("=" * 60)
    print("  Quake Live Game State Simulator")
    print("=" * 60)
    print()
    print("Connecting to Redis...")

    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    r.ping()
    print("Connected to Redis!")
    print()
    print("Publishing simulated game state to 'ql:game:state'")
    print("Run the visualizer in another terminal:")
    print("  poetry run python visualizer.py")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 60)

    # Create simulated players
    agent = AgentSimulator('76561197984141695', 'TrainingAgent')
    opponents = [
        AgentSimulator(f'7656119700000000{i}', f'Bot{i}')
        for i in range(3)
    ]

    # Simulation loop
    tick_rate = 60  # Hz
    dt = 1.0 / tick_rate
    frame_count = 0

    try:
        while True:
            start = time.perf_counter()

            # Update all agents
            agent.update(dt)
            for opp in opponents:
                opp.update(dt)

            # Build game state
            game_state = {
                'map_name': 'campgrounds',
                'game_type': 'ffa',
                'game_state': 'IN_PROGRESS',
                'time_remaining': 600,
                'agent': agent.to_dict(),
                'opponents': [opp.to_dict() for opp in opponents],
                'items': ITEMS,
                'frame': frame_count
            }

            # Publish to Redis
            r.publish('ql:game:state', json.dumps(game_state))

            frame_count += 1
            if frame_count % 60 == 0:
                print(f"Frame {frame_count}: Agent at ({agent.x:.0f}, {agent.y:.0f}) "
                      f"HP: {agent.health} Armor: {agent.armor}")

            # Maintain tick rate
            elapsed = time.perf_counter() - start
            sleep_time = dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nSimulator stopped.")


if __name__ == '__main__':
    run_simulator()

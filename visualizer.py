#!/usr/bin/env python3
"""
2D Map Visualizer for QuakeLiveInterface

A real-time top-down visualization of the game state.
Subscribes to the Redis game state channel and renders:
- Agent position (green dot with direction indicator)
- Opponent positions (red dots)
- High-value items (colored by type)

This allows you to "watch" the bot's brain without launching the game client.

Usage:
    python visualizer.py [--host localhost] [--port 6379]

Requirements:
    pip install matplotlib redis
"""

import argparse
import json
import math
import sys
import redis
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.animation import FuncAnimation


# Item colors by classname prefix
ITEM_COLORS = {
    'item_health': '#00FF00',      # Green - health
    'item_armor': '#FFD700',       # Gold - armor
    'weapon_': '#00BFFF',          # Light blue - weapons
    'item_quad': '#FF00FF',        # Magenta - quad
    'item_regen': '#FF69B4',       # Pink - regen
    'ammo_': '#AAAAAA',            # Gray - ammo
}


def get_item_color(item_name):
    """Get color for an item based on its classname."""
    for prefix, color in ITEM_COLORS.items():
        if item_name.startswith(prefix):
            return color
    return '#666666'  # Default gray


class GameVisualizer:
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0,
                 map_size=4000, update_interval=50):
        """
        Initialize the visualizer.

        Args:
            redis_host: Redis server hostname
            redis_port: Redis server port
            redis_db: Redis database number
            map_size: Approximate map size for display scaling
            update_interval: Milliseconds between updates
        """
        self.map_size = map_size
        self.update_interval = update_interval

        # Connect to Redis
        print(f"Connecting to Redis at {redis_host}:{redis_port}...")
        self.redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db,
                                 decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe('ql:game:state')
        print("Subscribed to ql:game:state channel")

        # Current game state
        self.game_state = None

        # Setup matplotlib figure
        self.fig, self.ax = plt.subplots(figsize=(10, 10))
        self.fig.canvas.manager.set_window_title('QuakeLive Visualizer')

        # Initialize plot elements
        self._setup_plot()

    def _setup_plot(self):
        """Initialize the plot with basic styling."""
        self.ax.set_xlim(-self.map_size, self.map_size)
        self.ax.set_ylim(-self.map_size, self.map_size)
        self.ax.set_aspect('equal')
        self.ax.set_facecolor('#1a1a1a')
        self.ax.grid(True, alpha=0.2, color='white')
        self.ax.set_xlabel('X Position', color='white')
        self.ax.set_ylabel('Y Position', color='white')
        self.ax.tick_params(colors='white')
        self.fig.patch.set_facecolor('#2a2a2a')

        # Status text
        self.status_text = self.ax.text(
            0.02, 0.98, '', transform=self.ax.transAxes,
            fontsize=10, verticalalignment='top', color='white',
            fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='#333333', alpha=0.8)
        )

    def _get_latest_state(self):
        """Get the latest game state from Redis, discarding stale messages."""
        latest = None
        while True:
            msg = self.pubsub.get_message(ignore_subscribe_messages=True, timeout=0)
            if msg is None:
                break
            latest = msg['data']

        if latest:
            try:
                self.game_state = json.loads(latest)
            except json.JSONDecodeError:
                pass

    def _draw_player(self, player, color, size=100, draw_direction=False):
        """Draw a player on the map."""
        if not player:
            return []

        pos = player.get('position', {})
        x = pos.get('x', 0)
        y = pos.get('y', 0)

        elements = []

        # Draw player dot
        scatter = self.ax.scatter([x], [y], c=color, s=size, zorder=5,
                                  edgecolors='white', linewidths=1)
        elements.append(scatter)

        # Draw direction indicator for agent
        if draw_direction:
            angles = player.get('view_angles', {})
            yaw = angles.get('yaw', 0)
            # Convert yaw to radians and calculate direction vector
            rad = math.radians(yaw)
            dx = math.cos(rad) * 200
            dy = math.sin(rad) * 200
            arrow = self.ax.arrow(x, y, dx, dy, head_width=50, head_length=30,
                                  fc=color, ec='white', zorder=4)
            elements.append(arrow)

        return elements

    def _draw_item(self, item):
        """Draw an item on the map."""
        pos = item.get('position', {})
        x = pos.get('x', 0)
        y = pos.get('y', 0)
        name = item.get('name', 'unknown')
        available = item.get('is_available', True)

        color = get_item_color(name)
        alpha = 1.0 if available else 0.3
        size = 60 if available else 30

        return self.ax.scatter([x], [y], c=color, s=size, alpha=alpha,
                               marker='s', zorder=3)

    def update(self, frame):
        """Animation update function."""
        # Clear previous frame
        self.ax.clear()
        self._setup_plot()

        # Get latest state
        self._get_latest_state()

        if not self.game_state:
            self.status_text.set_text('Waiting for game state...')
            return

        elements = []

        # Draw items
        for item in self.game_state.get('items', []):
            elements.append(self._draw_item(item))

        # Draw opponents
        for opp in self.game_state.get('opponents', []):
            if opp and opp.get('is_alive', False):
                elements.extend(self._draw_player(opp, '#FF4444', size=120))

        # Draw agent
        agent = self.game_state.get('agent')
        if agent:
            elements.extend(self._draw_player(agent, '#44FF44', size=150,
                                              draw_direction=True))

        # Update status text
        status_lines = []
        if agent:
            status_lines.append(f"Agent: {agent.get('name', 'Unknown')}")
            status_lines.append(f"Health: {agent.get('health', 0)} | Armor: {agent.get('armor', 0)}")
            pos = agent.get('position', {})
            status_lines.append(f"Pos: ({pos.get('x', 0):.0f}, {pos.get('y', 0):.0f}, {pos.get('z', 0):.0f})")
            vel = agent.get('velocity', {})
            speed = math.sqrt(vel.get('x', 0)**2 + vel.get('y', 0)**2)
            status_lines.append(f"Speed: {speed:.0f} ups")

        status_lines.append(f"Game: {'IN PROGRESS' if self.game_state.get('game_in_progress') else 'STOPPED'}")
        status_lines.append(f"Map: {self.game_state.get('map_name', 'Unknown')}")
        status_lines.append(f"Opponents: {len(self.game_state.get('opponents', []))}")
        status_lines.append(f"Items: {len(self.game_state.get('items', []))}")

        self.status_text.set_text('\n'.join(status_lines))

        return elements

    def run(self):
        """Start the visualization."""
        print("Starting visualizer... Press Ctrl+C to exit.")
        print("\nLegend:")
        print("  Green dot + arrow = Agent (you)")
        print("  Red dots = Opponents")
        print("  Blue squares = Weapons")
        print("  Gold squares = Armor")
        print("  Green squares = Health")
        print("  Faded = Item not available (respawning)")

        ani = FuncAnimation(self.fig, self.update, interval=self.update_interval,
                            blit=False, cache_frame_data=False)
        plt.show()


def main():
    parser = argparse.ArgumentParser(description='2D Map Visualizer for QuakeLiveInterface')
    parser.add_argument('--host', default='localhost', help='Redis host')
    parser.add_argument('--port', type=int, default=6379, help='Redis port')
    parser.add_argument('--db', type=int, default=0, help='Redis database')
    parser.add_argument('--map-size', type=int, default=4000,
                        help='Approximate map size for display scaling')
    parser.add_argument('--interval', type=int, default=50,
                        help='Update interval in milliseconds')
    args = parser.parse_args()

    try:
        viz = GameVisualizer(
            redis_host=args.host,
            redis_port=args.port,
            redis_db=args.db,
            map_size=args.map_size,
            update_interval=args.interval
        )
        viz.run()
    except redis.exceptions.ConnectionError as e:
        print(f"Error: Could not connect to Redis at {args.host}:{args.port}")
        print(f"Make sure Redis is running and the server is publishing game state.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)


if __name__ == '__main__':
    main()

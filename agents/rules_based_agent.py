#!/usr/bin/env python3
"""
Rules-Based Agent for QuakeLiveInterface

A simple heuristic-based agent that demonstrates decision-making logic:
- If health < 50: Navigate to nearest health item
- If armor < 30: Navigate to nearest armor item
- Otherwise: Move toward nearest opponent and attack

This provides immediate gratification - run it and watch the bot do something!

Usage:
    python agents/rules_based_agent.py [--episodes 5] [--max-steps 1000]
"""

import argparse
import logging
import math
import sys
import os
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from QuakeLiveInterface.env import QuakeLiveEnv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RulesBasedAgent:
    """
    A simple rules-based agent for QuakeLive.

    Decision hierarchy:
    1. Critical health (< 30): Seek health desperately
    2. Low health (< 50): Seek health
    3. Low armor (< 30): Seek armor
    4. Default: Hunt opponents
    """

    def __init__(self):
        self.current_goal = "hunt"
        self.target_position = None

    def get_action(self, obs, game_state):
        """
        Decide on an action based on the current game state.

        Args:
            obs: Observation vector (not used directly, using game_state instead)
            game_state: The raw GameState object with full info

        Returns:
            MultiDiscrete action: [forward_back, left_right, jump_crouch, attack, pitch, yaw]
        """
        agent = game_state.get_agent()
        if not agent or not agent.is_alive:
            # Dead or no agent - do nothing
            return np.array([1, 1, 1, 0, 5, 5])  # All neutral

        # Decide goal based on health/armor
        if agent.health < 30:
            self.current_goal = "desperate_health"
        elif agent.health < 50:
            self.current_goal = "seek_health"
        elif agent.armor < 30:
            self.current_goal = "seek_armor"
        else:
            self.current_goal = "hunt"

        # Get target position based on goal
        if self.current_goal in ["desperate_health", "seek_health"]:
            self.target_position = self._find_nearest_health(game_state, agent)
        elif self.current_goal == "seek_armor":
            self.target_position = self._find_nearest_armor(game_state, agent)
        else:
            self.target_position = self._find_nearest_opponent(game_state, agent)

        # Navigate to target
        if self.target_position is None:
            # No target - move forward randomly
            return np.array([2, 1, 1, 0, 5, 5])  # Move forward

        return self._navigate_to_target(agent, self.target_position, self.current_goal == "hunt")

    def _find_nearest_health(self, game_state, agent):
        """Find the nearest available health item."""
        return self._find_nearest_item(game_state, agent, ['item_health', 'holdable_medkit'])

    def _find_nearest_armor(self, game_state, agent):
        """Find the nearest available armor item."""
        return self._find_nearest_item(game_state, agent, ['item_armor'])

    def _find_nearest_item(self, game_state, agent, prefixes):
        """Find the nearest available item matching any of the prefixes."""
        agent_pos = np.array([agent.position['x'], agent.position['y'], agent.position['z']])
        nearest_pos = None
        nearest_dist = float('inf')

        for item in game_state.get_items():
            # Handle both dict and Item objects
            if hasattr(item, 'name'):
                name = item.name
                available = item.is_available
                pos = item.position
            else:
                name = item.get('name', '')
                available = item.get('is_available', False)
                pos = item.get('position', {})

            if not available:
                continue

            # Check if item matches any prefix
            if not any(name.startswith(p) for p in prefixes):
                continue

            item_pos = np.array([pos.get('x', 0), pos.get('y', 0), pos.get('z', 0)])
            dist = np.linalg.norm(agent_pos - item_pos)

            if dist < nearest_dist:
                nearest_dist = dist
                nearest_pos = item_pos

        return nearest_pos

    def _find_nearest_opponent(self, game_state, agent):
        """Find the nearest alive opponent."""
        agent_pos = np.array([agent.position['x'], agent.position['y'], agent.position['z']])
        nearest_pos = None
        nearest_dist = float('inf')

        for opp in game_state.get_opponents():
            if not opp.is_alive:
                continue

            opp_pos = np.array([opp.position['x'], opp.position['y'], opp.position['z']])
            dist = np.linalg.norm(agent_pos - opp_pos)

            if dist < nearest_dist:
                nearest_dist = dist
                nearest_pos = opp_pos

        return nearest_pos

    def _navigate_to_target(self, agent, target_pos, should_attack):
        """
        Generate movement actions to navigate toward a target.

        Returns:
            MultiDiscrete action: [forward_back, left_right, jump_crouch, attack, pitch, yaw]
        """
        agent_pos = np.array([agent.position['x'], agent.position['y'], agent.position['z']])

        # Calculate direction to target
        direction = target_pos - agent_pos
        distance = np.linalg.norm(direction[:2])  # XY distance only

        # Calculate desired yaw angle
        desired_yaw = math.degrees(math.atan2(direction[1], direction[0]))
        current_yaw = agent.view_angles['yaw']

        # Calculate yaw difference (normalized to -180 to 180)
        yaw_diff = desired_yaw - current_yaw
        while yaw_diff > 180:
            yaw_diff -= 360
        while yaw_diff < -180:
            yaw_diff += 360

        # Calculate desired pitch (look up/down)
        if distance > 0:
            desired_pitch = math.degrees(math.atan2(direction[2], distance))
        else:
            desired_pitch = 0
        current_pitch = agent.view_angles['pitch']
        pitch_diff = desired_pitch - current_pitch

        # Convert to discrete actions (0-10, where 5 is neutral)
        # Larger differences = faster turning
        yaw_action = int(5 + np.clip(yaw_diff / 10, -5, 5))
        pitch_action = int(5 + np.clip(pitch_diff / 10, -5, 5))

        # Movement: always move forward toward target
        forward_action = 2  # Forward

        # Strafe based on yaw difference (for better navigation)
        if abs(yaw_diff) > 45:
            # Large angle - strafe to help turn
            left_right_action = 2 if yaw_diff > 0 else 0
        else:
            left_right_action = 1  # Neutral

        # Jump occasionally for mobility (and strafe jumping potential)
        jump_action = 2 if distance > 500 and np.random.random() < 0.1 else 1

        # Attack if hunting and close enough
        attack_action = 1 if should_attack and distance < 1500 else 0

        return np.array([forward_action, left_right_action, jump_action,
                        attack_action, pitch_action, yaw_action])


def run_rules_agent(num_episodes=5, max_steps=1000, redis_host='localhost', redis_port=6379):
    """Run the rules-based agent."""
    print("=" * 60)
    print("QuakeLive Rules-Based Agent")
    print("=" * 60)
    print("\nDecision Logic:")
    print("  - Health < 30: Desperately seek health")
    print("  - Health < 50: Navigate to health items")
    print("  - Armor < 30: Navigate to armor items")
    print("  - Otherwise: Hunt nearest opponent")
    print()

    # Initialize environment and agent
    env = QuakeLiveEnv(
        redis_host=redis_host,
        redis_port=redis_port,
        max_episode_steps=max_steps
    )
    agent = RulesBasedAgent()

    print(f"Action space: {env.action_space}")
    print(f"Observation space shape: {env.observation_space.shape}")
    print()

    try:
        for episode in range(1, num_episodes + 1):
            print(f"\n{'='*40}")
            print(f"Episode {episode}/{num_episodes}")
            print(f"{'='*40}")

            obs, info = env.reset()
            terminated = False
            truncated = False
            total_reward = 0
            step_count = 0

            while not (terminated or truncated):
                # Get game state for decision making
                game_state = env.game_state

                # Get action from rules-based agent
                action = agent.get_action(obs, game_state)

                # Step environment
                obs, reward, terminated, truncated, info = env.step(action)
                total_reward += reward
                step_count += 1

                # Print status every 100 steps
                if step_count % 100 == 0:
                    agent_state = game_state.get_agent()
                    if agent_state:
                        print(f"  Step {step_count}: Goal={agent.current_goal}, "
                              f"HP={agent_state.health}, Armor={agent_state.armor}, "
                              f"Reward={total_reward:.2f}")

            # Episode summary
            print(f"\nEpisode {episode} finished:")
            print(f"  Steps: {step_count}")
            print(f"  Total reward: {total_reward:.2f}")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        env.close()
        print("\nEnvironment closed.")


def main():
    parser = argparse.ArgumentParser(description='Rules-Based Agent for QuakeLive')
    parser.add_argument('--episodes', type=int, default=5,
                        help='Number of episodes to run')
    parser.add_argument('--max-steps', type=int, default=1000,
                        help='Maximum steps per episode')
    parser.add_argument('--host', default='localhost',
                        help='Redis host')
    parser.add_argument('--port', type=int, default=6379,
                        help='Redis port')
    args = parser.parse_args()

    run_rules_agent(
        num_episodes=args.episodes,
        max_steps=args.max_steps,
        redis_host=args.host,
        redis_port=args.port
    )


if __name__ == '__main__':
    main()

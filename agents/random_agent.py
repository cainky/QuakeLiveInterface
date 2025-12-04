#!/usr/bin/env python3
"""
Random Agent for QuakeLiveInterface

A simple agent that takes random actions. Useful for:
- Testing the environment setup
- Baseline comparison
- Understanding the action space

Usage:
    python agents/random_agent.py [--episodes 5] [--max-steps 500]
"""

import argparse
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from QuakeLiveInterface.env import QuakeLiveEnv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_random_agent(num_episodes=5, max_steps=500, redis_host='localhost', redis_port=6379):
    """
    Run a random agent in the QuakeLive environment.

    Args:
        num_episodes: Number of episodes to run
        max_steps: Maximum steps per episode
        redis_host: Redis server host
        redis_port: Redis server port
    """
    print("=" * 60)
    print("QuakeLive Random Agent")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Episodes: {num_episodes}")
    print(f"  Max steps per episode: {max_steps}")
    print(f"  Redis: {redis_host}:{redis_port}")
    print()

    # Initialize environment
    print("Initializing environment...")
    env = QuakeLiveEnv(
        redis_host=redis_host,
        redis_port=redis_port,
        max_episode_steps=max_steps
    )

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
                # Random action
                action = env.action_space.sample()

                # Step environment
                obs, reward, terminated, truncated, info = env.step(action)
                total_reward += reward
                step_count += 1

                # Print progress every 100 steps
                if step_count % 100 == 0:
                    print(f"  Step {step_count}: Total reward = {total_reward:.2f}")

            # Episode summary
            print(f"\nEpisode {episode} finished:")
            print(f"  Steps: {step_count}")
            print(f"  Total reward: {total_reward:.2f}")
            print(f"  Terminated: {terminated}, Truncated: {truncated}")

            # Performance summary is logged automatically by the environment

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        env.close()
        print("\nEnvironment closed.")


def main():
    parser = argparse.ArgumentParser(description='Random Agent for QuakeLive')
    parser.add_argument('--episodes', type=int, default=5,
                        help='Number of episodes to run')
    parser.add_argument('--max-steps', type=int, default=500,
                        help='Maximum steps per episode')
    parser.add_argument('--host', default='localhost',
                        help='Redis host')
    parser.add_argument('--port', type=int, default=6379,
                        help='Redis port')
    args = parser.parse_args()

    run_random_agent(
        num_episodes=args.episodes,
        max_steps=args.max_steps,
        redis_host=args.host,
        redis_port=args.port
    )


if __name__ == '__main__':
    main()

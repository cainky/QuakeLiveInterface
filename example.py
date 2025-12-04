#!/usr/bin/env python3
"""
QuakeLiveInterface Example

Demonstrates basic usage of the QuakeLive Gymnasium environment.
Uses button simulation for realistic physics (strafe jumping compatible).

Action Space (MultiDiscrete):
    [0] Forward/Back:  0=back, 1=none, 2=forward
    [1] Left/Right:    0=left, 1=none, 2=right
    [2] Jump/Crouch:   0=crouch, 1=none, 2=jump
    [3] Attack:        0=no, 1=yes
    [4] Look Pitch:    0-10 (discretized view angle)
    [5] Look Yaw:      0-10 (discretized view angle)

For more sophisticated agents, see:
    - agents/random_agent.py     - Random baseline
    - agents/rules_based_agent.py - Simple heuristics

For visualization, run:
    python visualizer.py
"""

import gymnasium as gym
from QuakeLiveInterface.env import QuakeLiveEnv
import logging
import numpy as np

# Configure logging to see the output from the performance tracker
logging.basicConfig(level=logging.INFO)


def run_random_agent():
    """
    Runs a random agent in the QuakeLiveEnv for one episode.
    """
    print("Initializing Quake Live environment...")
    print("This assumes the Quake Live server with minqlx plugin is running")
    print("and Redis is available at localhost:6379.\n")

    # The environment can be configured with different parameters.
    # For example:
    # env = QuakeLiveEnv(
    #     redis_host='127.0.0.1',
    #     max_health=150,
    #     max_armor=150,
    #     num_items=15,
    #     view_sensitivity=3.0  # Degrees per frame at max look input
    # )
    env = QuakeLiveEnv()

    print(f"Action space: {env.action_space}")
    print(f"Observation space: {env.observation_space.shape}")
    print()

    print("Resetting environment for a new episode...")
    obs, info = env.reset()
    terminated = False
    truncated = False
    step_count = 0
    total_reward = 0

    print("Starting episode...\n")
    while not (terminated or truncated):
        # Take a random action
        # Action format: [forward_back, left_right, jump_crouch, attack, look_pitch, look_yaw]
        action = env.action_space.sample()

        # Step the environment
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward

        # Print some info every 50 steps
        if step_count % 50 == 0:
            # Decode action for display
            movement = ['back', 'none', 'forward'][action[0]]
            strafe = ['left', 'none', 'right'][action[1]]
            vertical = ['crouch', 'none', 'jump'][action[2]]
            attack = 'FIRE' if action[3] == 1 else ''

            print(f"Step {step_count:4d}: reward={reward:+.2f} total={total_reward:.2f} "
                  f"| {movement:7s} {strafe:5s} {vertical:6s} {attack}")

        step_count += 1

        if step_count >= 500:
            print("\nReached max steps for the example.")
            break

    print(f"\nEpisode finished after {step_count} steps.")
    print(f"Total reward: {total_reward:.2f}")

    # The performance summary is logged automatically on reset.
    # To show it now, call it manually:
    env.performance_tracker.log_episode(env.episode_num)

    env.close()
    print("Environment closed.")


if __name__ == "__main__":
    run_random_agent()

import gymnasium as gym
from QuakeLiveInterface.env import QuakeLiveEnv
import logging

# Configure logging to see the output from the performance tracker
logging.basicConfig(level=logging.INFO)

def run_random_agent():
    """
    Runs a random agent in the QuakeLiveEnv for one episode.
    """
    print("Initializing Quake Live environment...")
    # This assumes that the Quake Live server with the minqlx plugin is running
    # and that Redis is available at the default host and port.

    # The environment can be configured with different parameters.
    # For example:
    # env = QuakeLiveEnv(
    #     redis_host='127.0.0.1',
    #     max_health=150,
    #     max_armor=150,
    #     num_items=15
    # )
    env = QuakeLiveEnv()

    print("Resetting environment for a new episode...")
    obs, info = env.reset()
    done = False
    step_count = 0

    print("Starting episode...")
    while not done:
        # Take a random action
        action = env.action_space.sample()

        # Step the environment
        obs, reward, done, info = env.step(action)

        # Print some info every 10 steps
        if step_count % 10 == 0:
            print(f"Step: {step_count}, Reward: {reward:.4f}, Done: {done}")
            # You can also render the environment to see some basic stats
            # env.render()

        step_count += 1

        if step_count > 500: # Run for a maximum of 500 steps
            print("Reached max steps for the episode.")
            break

    print("Episode finished.")

    # The performance summary for the episode will be logged automatically
    # when the environment is reset again. To show it now, we can call it manually.
    env.performance_tracker.log_episode(env.episode_num)

    env.close()

if __name__ == "__main__":
    run_random_agent()

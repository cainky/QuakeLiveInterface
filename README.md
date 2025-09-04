# QuakeLiveInterface

QuakeLiveInterface is a Python library designed to provide a comprehensive, object-oriented interface to a Quake Live game server for the purpose of training reinforcement learning agents. It uses [minqlx](https://github.com/MinoMino/minqlx) to interface with the Quake Live server and is designed to be compatible with [Gymnasium](https://gymnasium.farama.org/).

## Features

*   **Gymnasium-Compatible Environment**: A `QuakeLiveEnv` class that provides a standard interface for RL agents (`step`, `reset`). The reset mechanism is robust, waiting for the game to be ready before starting a new episode.
*   **Object-Oriented Game State**: A detailed and structured representation of the game state, including players, items, and weapons. The observation includes the closest opponent's state, providing more relevant information to the agent.
*   **Flexible Reward System**: A customizable reward system that can be configured to encourage different behaviors.
*   **Replay Analysis**: Integration with [UberDemoTools](https://github.com/mightycow/uberdemotools) to record and parse game demos for offline analysis and imitation learning.
*   **Performance Tracking**: A built-in system to track and log key performance metrics like K/D ratio, damage, and accuracy.

## Architecture

The system consists of three main components:
1.  A **Quake Live Dedicated Server** with the `minqlx` modification installed.
2.  A **`minqlx` Python plugin** (`ql_agent_plugin.py`) that runs on the server. This plugin extracts game state, sends it to a Redis server, and listens for commands.
3.  A **Python client library** that provides the `QuakeLiveEnv` for the agent to interact with the game.

## Installation

The project uses Poetry for package management.

```bash
$ poetry install
```

You will also need a running Redis server and, for replay analysis, the [UberDemoTools](https://github.com/mightycow/uberdemotools) command-line tools in your system's PATH.

## Setup

1.  **Set up a Quake Live dedicated server.**
2.  **Install `minqlx` on your server.**
3.  **Install and Configure the `ql_agent_plugin.py` plugin:**
    - Copy the `minqlx-plugin/ql_agent_plugin.py` file to your `minqlx-plugins` directory.
    - Add `ql_agent_plugin` to your `qlx_plugins` cvar in your server configuration.
    - Set the `qlx_agentSteamId` cvar in your server configuration to the SteamID64 of the account that will be used by the AI agent. For example: `set qlx_agentSteamId "your_steam_id_here"`

## Usage

The primary way to use this library is through the `QuakeLiveEnv` class, which is compatible with most reinforcement learning frameworks.

Here is a simple example of how to run a random agent in the environment. See `example.py` for the full script.

```python
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
    env = QuakeLiveEnv()

    print("Resetting environment for a new episode...")
    obs, info = env.reset()
    done = False

    while not done:
        # Take a random action
        action = env.action_space.sample()

        # Step the environment
        obs, reward, done, info = env.step(action)

    print("Episode finished.")

    # The performance summary for the episode will be logged automatically.
    env.close()

if __name__ == "__main__":
    run_random_agent()
```

To run the example:
```bash
$ poetry run python example.py
```

### Environment Configuration

The `QuakeLiveEnv` can be configured upon initialization. Here are the available parameters:

| Parameter      | Type        | Default                  | Description                                                                                             |
|----------------|-------------|--------------------------|---------------------------------------------------------------------------------------------------------|
| `redis_host`   | `str`       | `'localhost'`            | The hostname of the Redis server.                                                                       |
| `redis_port`   | `int`       | `6379`                   | The port of the Redis server.                                                                           |
| `redis_db`     | `int`       | `0`                      | The Redis database to use.                                                                              |
| `max_health`   | `int`       | `200`                    | The maximum health value used for normalization.                                                        |
| `max_armor`    | `int`       | `200`                    | The maximum armor value used for normalization.                                                         |
| `map_dims`     | `tuple`     | `(4000, 4000, 1000)`     | Estimated map dimensions (x, y, z) for position normalization. This should be adjusted for custom maps. |
| `max_velocity` | `int`       | `800`                    | The maximum velocity used for normalization.                                                            |
| `max_ammo`     | `int`       | `200`                    | The maximum ammo for any weapon, used for normalization.                                                |
| `num_items`    | `int`       | `10`                     | The maximum number of items to include in the observation space.                                        |


## Testing

To run tests:

```bash
$ poetry run pytest
```

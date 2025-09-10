# QuakeLiveInterface

QuakeLiveInterface is a Python library designed to provide a comprehensive, object-oriented interface to a Quake Live game server for the purpose of training reinforcement learning agents. It uses [minqlx](https://github.com/MinoMino/minqlx) to interface with the Quake Live server and is designed to be compatible with [Gymnasium](https://gymnasium.farama.org/).

## Features

*   **Gymnasium-Compatible Environment**: A `QuakeLiveEnv` class that provides a standard interface for RL agents (`step`, `reset`).
*   **Flexible Configuration**: The environment and server plugin are highly configurable, allowing for different game modes, maps, and weapon sets.
*   **Object-Oriented Game State**: A detailed and structured representation of the game state, including players, items, and weapons.
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

### 1. Quake Live Server
- Set up a Quake Live dedicated server.
- Install `minqlx` on your server.

### 2. `ql_agent_plugin.py`
- Copy the `minqlx-plugin/ql_agent_plugin.py` file to your `minqlx-plugins` directory.
- Add `ql_agent_plugin` to your `qlx_plugins` cvar in your server configuration.
- Configure the plugin using cvars in your server configuration file (e.g., `server.cfg`).

#### Plugin Configuration (cvars)

| Cvar                | Default       | Description                                                                                                                                      |
|---------------------|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| `qlx_agentSteamId`  | `some_steam_id` | The SteamID64 of the account that will be used by the AI agent. **This must be set.**                                                              |
| `qlx_redisAddress`  | `localhost`   | The hostname of the Redis server.                                                                                                                |
| `qlx_redisPort`     | `6379`        | The port of the Redis server.                                                                                                                    |
| `qlx_redisDatabase` | `0`           | The Redis database to use.                                                                                                                       |
| `qlx_weaponMapJson` | (see default) | A JSON string mapping weapon IDs to names. This allows you to customize the weapon list for different game modes. See example below.                 |

**Example `qlx_weaponMapJson`:**
```
set qlx_weaponMapJson "{\"0\": \"Gauntlet\", \"1\": \"Machinegun\", \"2\": \"Shotgun\"}"
```

## Usage

The primary way to use this library is through the `QuakeLiveEnv` class. See `example.py` for a full example.

### Environment Configuration

The `QuakeLiveEnv` can be configured upon initialization.

| Parameter       | Type        | Default                  | Description                                                                                             |
|-----------------|-------------|--------------------------|---------------------------------------------------------------------------------------------------------|
| `redis_host`    | `str`       | `'localhost'`            | The hostname of the Redis server.                                                                       |
| `redis_port`    | `int`       | `6379`                   | The port of the Redis server.                                                                           |
| `redis_db`      | `int`       | `0`                      | The Redis database to use.                                                                              |
| `max_health`    | `int`       | `200`                    | The maximum health value used for normalization.                                                        |
| `max_armor`     | `int`       | `200`                    | The maximum armor value used for normalization.                                                         |
| `map_dims`      | `tuple`     | `(4000, 4000, 1000)`     | Estimated map dimensions (x, y, z) for position normalization. See "Map Dimensions" section below.      |
| `max_velocity`  | `int`       | `800`                    | The maximum velocity used for normalization.                                                            |
| `max_ammo`      | `int`       | `200`                    | The maximum ammo for any weapon, used for normalization.                                                |
| `num_items`     | `int`       | `10`                     | The maximum number of items to include in the observation space.                                        |
| `weapon_list`   | `list[str]` | (see default list)       | The list of weapon names to include in the observation space. Must match the names in the server's weapon map. |

### Map Dimensions

The `map_dims` parameter is crucial for normalizing player and item positions. If the dimensions are too small, positions will be clipped; if they are too large, the normalized values will be too small.

You can use the provided helper function to estimate map dimensions from a replay file. First, record a demo of a game on the map you want to use. Then, parse it with UberDemoTools to get a JSON file.

```python
from QuakeLiveInterface.env import QuakeLiveEnv

# Estimate map dimensions from a replay file
replay_file = 'path/to/your/replay.json'
map_dims = QuakeLiveEnv.estimate_map_dims(replay_file)

# Use the estimated dimensions to create the environment
env = QuakeLiveEnv(map_dims=map_dims)
```

## Troubleshooting

- **Connection refused to Redis:**
  - Make sure your Redis server is running.
  - Check that the `redis_host` and `redis_port` in your `QuakeLiveEnv` match the Redis server's configuration.
  - Check that the `qlx_redisAddress` and `qlx_redisPort` cvars on your Quake Live server match the Redis server's configuration.

- **Agent does not spawn or take actions:**
  - Verify that `qlx_agentSteamId` is set correctly on the server.
  - Make sure the account with that SteamID is connected to the server.
  - Check the Quake Live server console for any errors from the `ql_agent_plugin`.

- **Incorrect weapon data:**
  - Ensure that the `weapon_list` in your `QuakeLiveEnv` matches the weapon map on the server. If you are using a custom weapon map on the server, you must provide a corresponding `weapon_list` to the environment.

## Testing

To run tests:

```bash
$ poetry run pytest
```

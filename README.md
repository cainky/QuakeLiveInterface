# QuakeLiveInterface

Quake Live Interface is a Python library designed to provide a programmatic interface to a Quake Live game server for the purpose of training an AI agent. This project uses [minqlx](https://github.com/MinoMino/minqlx) to interface with the Quake Live server.

## Architecture

The system consists of three main components:
1.  A **Quake Live Dedicated Server** with the `minqlx` modification installed.
2.  A **`minqlx` Python plugin** (`ql_agent_plugin.py`) that runs on the server. This plugin extracts game state information and sends it to a Redis server. It also listens for commands from the client on a Redis channel.
3.  A **Python client** (`QuakeLiveClient`) that connects to the Redis server to receive game state information and send commands to the agent.

This architecture allows for a clean separation of concerns and a robust way to control and monitor the game state for an AI agent.

## Installation

The project uses Poetry for package management.

```bash
$ poetry install
```

You will also need a running Redis server.

## Setup

1.  **Set up a Quake Live dedicated server.** Follow the official instructions to get a server running.
2.  **Install `minqlx` on your server.** Follow the instructions on the [minqlx GitHub page](https://github.com/MinoMino/minqlx).
3.  **Install the `ql_agent_plugin.py` plugin.**
    - Copy the `minqlx-plugin/ql_agent_plugin.py` file to your `minqlx-plugins` directory on the server.
    - Add `ql_agent_plugin` to your `qlx_plugins` cvar in your server configuration.
    - Set the `AGENT_STEAM_ID` in `ql_agent_plugin.py` to the SteamID64 of the account that will be used by the AI agent.

## Usage

To create a connection to the Quake Live server and control the agent:

```python
from QuakeLiveInterface.client import QuakeLiveClient
import time

# Initialize the client
client = QuakeLiveClient()

# Main loop
while True:
    # Update the game state from Redis
    if client.update_game_state():
        game_state = client.get_game_state()

        # Print some info
        print(f"Health: {game_state.get_player_health()}, Armor: {game_state.get_player_armor()}")
        print(f"Position: {game_state.get_player_position()}")

        # Example: make the agent jump
        client.move(0, 0, 1)

    time.sleep(0.1)
```

## Testing

To run tests:

```bash
$ poetry run pytest
```

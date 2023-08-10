# QuakeLiveInterface

Quake Live Interface is a Python library designed to provide a programmatic interface to a Quake Live game server. The library's main components are:

- `ServerConnection`: A class that manages the TCP/IP connection to the Quake Live server. It sends commands to the server and receives data packets from the server.

- `GameState`: A class that parses the data packets from the server into a more accessible format. The game state includes information about the player's position, the positions of other entities, and other game state information.

- `QuakeLiveClient`: A class that encapsulates the connection to the server and the interpretation of game state data. It provides an intuitive interface for users to interact with the game.

## Installation

The project uses Poetry for package management.

```bash
$ poetry install
```

### Usage

To create a connection to a Quake Live server:

```python

from QuakeLiveInterface.connection import ServerConnection

connection = ServerConnection(server_ip, server_port)
connection.connect()
```

To send a command to the server:

```python

connection.send_command("some_command")
```

To create a Quake Live client and interpret game state data:

```python

from QuakeLiveInterface.client import QuakeLiveClient

client = QuakeLiveClient(server_ip, server_port)
client.connect()
game_state = client.get_game_state()
```

### Testing

To run tests:

```bash
$ poetry run pytest
```

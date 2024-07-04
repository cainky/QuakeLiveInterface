# QuakeLiveInterface

This project provides an interface for Quake Live servers running minqlx. It allows external clients to control players and receive game state information.

## Installation

The project uses Poetry for package management.

1. Install the packages using [Poetry](https://python-poetry.org/)
```bash
$ poetry install
```

2. Ensure you have a Quake Live server running with minqlx installed.

3. Copy the `quake_ai_interface` folder into your `minqlx-plugins` directory.

4. Add `quake_ai_interface` to your `qlx_plugins` cvar in your server config. For example:

   ```
   set qlx_plugins "plugin1, plugin2, quake_ai_interface"
   ```

5. (Optional) Set the port for the AI interface by adding the following to your server config:

   ```
   set qlx_aiInterfacePort "27960"
   ```

   If not set, the default port is 27960.

6. Restart your Quake Live server.

## Architecture

The Quake AI Interface consists of three main components:

1. MinQLX Plugin: This runs on the Quake Live server and handles the low-level interaction with the game.

2. Python API: This provides a high-level interface for controlling players and receiving game state information.

3. AI Bot: This is where the decision-making logic resides. It uses the Python API to interact with the game.

## Usage

The client can interact with the game through the Python API. This API provides methods that correspond to the various commands available in the game.

1. `move_player(player_id: int, direction: Direction, amount: float) -> str`
   - Moves the player in the specified direction.
   - Direction: An enum value from the Direction class (FORWARD, BACKWARD, LEFT, RIGHT)
   - Amount: Float value representing the movement amount

2. `aim_player(player_id: int, pitch: float, yaw: float) -> str`
   - Aims the player's view.
   - Pitch and Yaw: Float values representing the aim angles

3. `switch_weapon(player_id: int, weapon: WeaponType) -> str`
   - Switches the player's weapon.
   - Weapon: An enum value from the WeaponType class (GAUNTLET, MACHINEGUN, SHOTGUN, etc.)

4. `fire_weapon(player_id: int) -> str`
   - Makes the player fire their current weapon.

5. `jump_player(player_id: int) -> str`
   - Makes the player jump.

6. `get_game_state() -> GameState`
   - Returns the current state of the game, including player positions, health, weapons, etc.

The server will respond with a string indicating the result of the command. This could be a success message or an error message if the command was invalid or couldn't be executed.

### Testing

To run tests:

```bash
$ poetry run pytest
```

## Contributing

Contributions to this project are welcome. Please submit pull requests with any improvements or bug fixes. When contributing, please:

1. Add unit tests for any new features or bug fixes.
2. Update the documentation if you're changing the API or adding new features.
3. Follow the existing code style and conventions.

## License
This project is licensed under the [GNU General Public License Version 3 (GPLv3)](./LICENSE)

1. You are free to use, modify, and distribute this software.
2. If you distribute this software or any derivative works, you must:
   - Make the source code available.
   - License it under the same GPLv3 terms.
   - Preserve the original copyright notices.
3. There is no warranty for this program, and the authors are not liable for any damages from its use.

This license ensures that the software remains free and open source, promoting collaboration and shared improvements.
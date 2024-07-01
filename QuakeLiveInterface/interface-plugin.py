import minqlx
import json
import threading
import socket
from typing import List, Callable, Any, Tuple
from utils import CommandType, Direction, WeaponId, DEFAULT_PORT, STATE_REQUEST, COMMAND_PREFIX

from loguru import logger

logger.add(
    "quakelive_interface.log",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} [{level}] - {message}",
)

class Player:
    def __init__(self, id: int, name: str, team: str, position: Tuple[float, float, float, float, float, float],
                 health: int, armor: int, weapons: List[int]):
        self.id = id
        self.name = name
        self.team = team
        self.position = position
        self.health = health
        self.armor = armor
        self.weapons = weapons

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "team": self.team,
            "position": self.position,
            "health": self.health,
            "armor": self.armor,
            "weapons": self.weapons
        }

class Command:
    def __init__(self, type: CommandType, handler: Callable[..., Any], arg_count: int):
        self.type = type
        self.handler = handler
        self.arg_count = arg_count # expected number of args

class StateExposer(minqlx.Plugin):
    def __init__(self):
        super().__init__()
        self.set_cvar_once("qlx_stateExposerPort", str(DEFAULT_PORT))
        self.state_lock = threading.Lock()
        self.current_state = {}
        self.players = {}
        self.add_hook("frame", self.handle_frame)
        self.server_thread = threading.Thread(target=self.run_server)
        self.server_thread.start()
        self.add_hook("player_disconnect", self.handle_player_disconnect)
        self.add_hook("map", self.handle_map)

        self.commands = {
            CommandType.MOVE: Command(CommandType.MOVE, self.move_player, 3),
            CommandType.AIM: Command(CommandType.AIM, self.aim_player, 3),
            CommandType.WEAPON: Command(CommandType.WEAPON, self.switch_weapon, 2),
            CommandType.FIRE: Command(CommandType.FIRE, self.fire_weapon, 1),
            CommandType.JUMP: Command(CommandType.JUMP, self.player_jump, 1),
            CommandType.SAY: Command(CommandType.SAY, self.player_say, 2),
        }

    def handle_frame(self):
        with self.state_lock:
            self.players = {
                p.id: Player(
                    p.id, p.name, p.team, p.position,
                    p.health, p.armor, p.weapons()
                ) for p in self.players()
            }
            self.current_state = {
                "players": [player.to_dict() for player in self.players.values()],
                "items": [
                    {
                        "type": item.type,
                        "position": item.position
                    } for item in self.items()
                ]
            }

    def run_server(self):
        port = int(self.get_cvar("qlx_stateExposerPort"))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', port))
            s.listen()
            while True:
                conn, addr = s.accept()
                with conn:
                    while True:
                        data = conn.recv(1024)
                        if not data:
                            break
                        if data == STATE_REQUEST:
                            with self.state_lock:
                                conn.sendall(json.dumps(self.current_state).encode())
                        elif data.startswith(COMMAND_PREFIX):
                            command = data.decode().split(":", 1)[1]
                            result = self.execute_command(command)
                            conn.sendall(json.dumps({"result": result}).encode())

    def execute_command(self, command_string: str) -> str:
        try:
            parts = command_string.split()
            action = CommandType[parts[0].upper()]
            args = parts[1:]

            if action in self.commands:
                command = self.commands[action]
                if len(args) != command.arg_count:
                    return f"Error: {action.name} command requires {command.arg_count} argument(s)"
                return command.handler(*args)
            else:
                # For any other commands, pass them directly to the console
                self.console_command(command_string)
                return f"Executed console command: {command_string}"

        except KeyError:
            return f"Error: Unknown command {parts[0]}"
        except Exception as e:
            self.msg(f"Error executing command: {command_string}. Error: {str(e)}")
            return f"Error: {str(e)}"

    def move_player(self, player_id: str, direction: str, amount: str) -> str:
        try:
            player = self.players[int(player_id)]
        except KeyError:
            return f"Error: Player with id {player_id} not found"

        amount = int(amount)
        try:
            direction = Direction(direction.lower())
        except ValueError:
            return f"Invalid direction: {direction}"

        x, y, z, pitch, yaw, roll = player.position
        if direction == Direction.FORWARD:
            y += amount
        elif direction == Direction.BACKWARD:
            y -= amount
        elif direction == Direction.LEFT:
            x -= amount
        elif direction == Direction.RIGHT:
            x += amount

        player.position = (x, y, z, pitch, yaw, roll)
        self.force_player_pos(player.id, player.position)
        return f"Moved player {player.name} {direction.value} by {amount}"

    def aim_player(self, player_id: str, pitch: str, yaw: str) -> str:
        try:
            player = self.players[int(player_id)]
        except KeyError:
            return f"Error: Player with id {player_id} not found"

        pitch, yaw = float(pitch), float(yaw)
        x, y, z, _, _, roll = player.position
        player.position = (x, y, z, pitch, yaw, roll)
        self.force_player_pos(player.id, player.position)
        return f"Aimed player {player.name} with pitch {pitch} and yaw {yaw}"

    def switch_weapon(self, player_id: str, weapon_id: str) -> str:
        try:
            player = self.players[int(player_id)]
        except KeyError:
            return f"Error: Player with id {player_id} not found"

        try:
            weapon = WeaponId(int(weapon_id))
        except ValueError:
            return f"Invalid weapon ID: {weapon_id}"

        self.console_command(f"tell {player.id} weapon {weapon.value}")
        return f"Switched player {player.name} to weapon {weapon.name}"

    def fire_weapon(self, player_id: str) -> str:
        try:
            player = self.players[int(player_id)]
        except KeyError:
            return f"Error: Player with id {player_id} not found"

        self.console_command(f"tell {player.id} +attack;wait 10;-attack")
        return f"Fired weapon for player {player.name}"

    def player_jump(self, player_id: str) -> str:
        try:
            player = self.players[int(player_id)]
        except KeyError:
            return f"Error: Player with id {player_id} not found"

        self.console_command(f"tell {player.id} +moveup;wait 10;-moveup")
        return f"Player {player.name} jumped"

    def player_say(self, player_id: str, message: str) -> str:
        try:
            player = self.players[int(player_id)]
        except KeyError:
            return f"Error: Player with id {player_id} not found"

        self.console_command(f"tell {player.id} say {message}")
        return f"Player {player.name} said: {message}"

    def force_player_pos(self, player_id: int, position: Tuple[float, float, float, float, float, float]):
        self.console_command(f"position {player_id} {' '.join(map(str, position))}")

    def handle_player_disconnect(self, player):
        # Remove the player from our local players dict when they disconnect
        if player.id in self.players:
            del self.players[player.id]

    def handle_map(self, mapname, factory):
        # Reset the players dict when a new map loads
        self.players = {}
            
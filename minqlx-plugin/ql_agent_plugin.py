import minqlx
import redis
import json
import threading
import time

# Default weapon map, used as a fallback
DEFAULT_WEAPON_MAP = {
    "0": "Gauntlet", "1": "Machinegun", "2": "Shotgun", "3": "Grenade Launcher",
    "4": "Rocket Launcher", "5": "Lightning Gun", "6": "Railgun", "7": "Plasma Gun",
    "8": "BFG", "9": "Grappling Hook"
}


class ql_agent_plugin(minqlx.Plugin):
    def __init__(self):
        super().__init__()

        # Configuration
        self.agent_steam_id = self.get_cvar("qlx_agentSteamId", "some_steam_id")
        self.redis_host = self.get_cvar("qlx_redisAddress", "localhost")
        self.redis_port = int(self.get_cvar("qlx_redisPort", 6379))
        self.redis_db = int(self.get_cvar("qlx_redisDatabase", 0))
        self.redis_conn = redis.Redis(host=self.redis_host, port=self.redis_port, db=self.redis_db, decode_responses=True)
        self._load_weapon_map()

        # Redis channels
        self.command_channel = 'ql:agent:command'
        self.admin_command_channel = 'ql:admin:command'
        self.game_state_channel = 'ql:game:state'

        # Track current input state for the agent (button simulation)
        # These persist across frames until changed
        self.agent_inputs = {
            'forward': False,
            'back': False,
            'left': False,
            'right': False,
            'jump': False,
            'crouch': False,
            'attack': False,
        }
        # View angle deltas to apply each frame
        self.agent_view_delta = {'pitch': 0.0, 'yaw': 0.0}

        self.add_hook("server_frame", self.handle_server_frame)

        self.agent_command_thread = threading.Thread(target=self.listen_for_agent_commands)
        self.agent_command_thread.daemon = True
        self.agent_command_thread.start()

        self.admin_command_thread = threading.Thread(target=self.listen_for_admin_commands)
        self.admin_command_thread.daemon = True
        self.admin_command_thread.start()

    def listen_for_agent_commands(self):
        pubsub = self.redis_conn.pubsub()
        pubsub.subscribe(self.command_channel)
        for message in pubsub.listen():
            if message['type'] == 'message':
                self.handle_agent_command(message['data'])

    def listen_for_admin_commands(self):
        pubsub = self.redis_conn.pubsub()
        pubsub.subscribe(self.admin_command_channel)
        for message in pubsub.listen():
            if message['type'] == 'message':
                self.handle_admin_command(message['data'])

    def handle_agent_command(self, command_data):
        """
        Handles agent commands using button simulation for realistic physics.
        Movement commands set button states that are applied each server frame.
        """
        try:
            data = json.loads(command_data)
            command = data.get('command')

            if command == 'input':
                # New unified input command - sets all button states at once
                # Expected format: {"command": "input", "forward": 1, "back": 0, "left": 0, "right": 1, ...}
                self.agent_inputs['forward'] = bool(data.get('forward', 0))
                self.agent_inputs['back'] = bool(data.get('back', 0))
                self.agent_inputs['left'] = bool(data.get('left', 0))
                self.agent_inputs['right'] = bool(data.get('right', 0))
                self.agent_inputs['jump'] = bool(data.get('jump', 0))
                self.agent_inputs['crouch'] = bool(data.get('crouch', 0))
                self.agent_inputs['attack'] = bool(data.get('attack', 0))
                # View deltas are applied incrementally each frame
                self.agent_view_delta['pitch'] = float(data.get('pitch_delta', 0.0))
                self.agent_view_delta['yaw'] = float(data.get('yaw_delta', 0.0))

            elif command == 'look':
                # Set view angle deltas (degrees per frame)
                self.agent_view_delta['pitch'] = float(data.get('pitch', 0.0))
                self.agent_view_delta['yaw'] = float(data.get('yaw', 0.0))

            elif command == 'weapon_select':
                agent_player = self.get_agent_player()
                if agent_player:
                    weapon = data.get('weapon')
                    if weapon:
                        minqlx.command(f"cmd {agent_player.id} weapon {weapon}")

            elif command == 'say':
                minqlx.command(f"say {data.get('message', '')}")

        except Exception as e:
            minqlx.log_error(f"Error handling agent command: {e}")

    def handle_admin_command(self, command_data):
        try:
            data = json.loads(command_data)
            command = data.get('command')

            if command == 'restart_game':
                minqlx.log_info("Restarting game via admin command.")
                minqlx.command("restart")
            elif command == 'start_demo_record':
                filename = data.get('filename', 'agent_demo')
                minqlx.log_info(f"Starting demo recording: {filename}")
                minqlx.command(f"record {filename}")
            elif command == 'stop_demo_record':
                minqlx.log_info("Stopping demo recording.")
                minqlx.command("stoprecord")

        except Exception as e:
            minqlx.log_error(f"Error handling admin command: {e}")

    def get_agent_player(self):
        """Finds the player object for the agent."""
        for player in self.players():
            if player.steam_id == self.agent_steam_id:
                return player
        return None

    def _load_weapon_map(self):
        """Loads the weapon map from a cvar or uses the default."""
        weapon_map_json = self.get_cvar("qlx_weaponMapJson")
        if weapon_map_json:
            try:
                self.weapon_map = json.loads(weapon_map_json)
                minqlx.log_info("Loaded custom weapon map from cvar.")
            except json.JSONDecodeError:
                minqlx.log_error("Invalid JSON in qlx_weaponMapJson cvar. Falling back to default weapon map.")
                self.weapon_map = DEFAULT_WEAPON_MAP
        else:
            minqlx.log_info("Using default weapon map.")
            self.weapon_map = DEFAULT_WEAPON_MAP

    def _serialize_player(self, player):
        """Serializes a player object into a dictionary."""
        if not player:
            return None

        weapons = player.weapons()
        weapon_data = []
        for w_num in weapons:
            weapon_name = self.weapon_map.get(str(w_num), "Unknown")
            weapon_data.append({"name": weapon_name, "ammo": player.get_weapon_ammo(w_num)})

        current_weapon_num = player.weapon
        selected_weapon_data = {
            "name": self.weapon_map.get(str(current_weapon_num), "Unknown"),
            "ammo": player.get_weapon_ammo(current_weapon_num)
        } if current_weapon_num else None

        return {
            'steam_id': player.steam_id,
            'name': player.name,
            'health': player.health,
            'armor': player.armor,
            'position': {'x': player.position[0], 'y': player.position[1], 'z': player.position[2]},
            'velocity': {'x': player.velocity[0], 'y': player.velocity[1], 'z': player.velocity[2]},
            'view_angles': {'pitch': player.view_angles[0], 'yaw': player.view_angles[1], 'roll': player.view_angles[2]},
            'is_alive': player.is_alive,
            'weapons': weapon_data,
            'selected_weapon': selected_weapon_data,
        }

    def _serialize_item(self, item):
        """Serializes an item object into a dictionary."""
        # Based on the minqlx source code, the item object is a gentity_t.
        # The 'inuse' attribute indicates if the item is currently spawned.
        # The 'spawnTime' attribute indicates when the item will respawn.
        return {
            'name': item.classname,
            'position': {'x': item.s.origin[0], 'y': item.s.origin[1], 'z': item.s.origin[2]},
            'is_available': item.inuse,
            'spawn_time': item.spawnTime
        }

    def _apply_agent_inputs(self, agent_player):
        """
        Applies the current input state to the agent using user_cmd injection.
        This simulates actual button presses for realistic physics (strafe jumping, etc).
        """
        if not agent_player or not agent_player.is_alive:
            return

        try:
            # Build the user_cmd for this frame
            # In Quake, movement is controlled via forwardmove, rightmove, upmove
            # Each ranges from -127 to 127
            forwardmove = 0
            rightmove = 0
            upmove = 0

            if self.agent_inputs['forward']:
                forwardmove = 127
            elif self.agent_inputs['back']:
                forwardmove = -127

            if self.agent_inputs['right']:
                rightmove = 127
            elif self.agent_inputs['left']:
                rightmove = -127

            if self.agent_inputs['jump']:
                upmove = 127
            elif self.agent_inputs['crouch']:
                upmove = -127

            # Apply movement via user_cmd
            # Note: This uses minqlx's player.user_cmd interface
            agent_player.user_cmd.forwardmove = forwardmove
            agent_player.user_cmd.rightmove = rightmove
            agent_player.user_cmd.upmove = upmove

            # Apply attack button
            if self.agent_inputs['attack']:
                agent_player.user_cmd.buttons |= 1  # +attack is bit 0
            else:
                agent_player.user_cmd.buttons &= ~1

            # Apply view angle changes (incremental)
            if self.agent_view_delta['pitch'] != 0 or self.agent_view_delta['yaw'] != 0:
                current_angles = agent_player.view_angles
                new_pitch = current_angles[0] + self.agent_view_delta['pitch']
                new_yaw = current_angles[1] + self.agent_view_delta['yaw']
                # Clamp pitch to valid range
                new_pitch = max(-89.0, min(89.0, new_pitch))
                # Wrap yaw to [-180, 180]
                while new_yaw > 180:
                    new_yaw -= 360
                while new_yaw < -180:
                    new_yaw += 360
                agent_player.set_view_angles((new_pitch, new_yaw, current_angles[2]))

        except Exception as e:
            minqlx.log_error(f"Error applying agent inputs: {e}")

    def handle_server_frame(self):
        """Called every server frame to apply inputs and publish the game state."""
        try:
            agent_player = self.get_agent_player()
            if not agent_player:
                return

            # Apply the agent's button inputs for this frame (physics simulation)
            self._apply_agent_inputs(agent_player)

            # Collect and publish game state
            opponents = [self._serialize_player(p) for p in self.players() if p.steam_id != self.agent_steam_id]
            items = [self._serialize_item(item) for item in minqlx.items()]

            game_state = {
                'agent': self._serialize_player(agent_player),
                'opponents': opponents,
                'items': items,
                'game_in_progress': self.game.state == "in_progress",
                'game_type': self.game.type_short,
                'map_name': self.game.map,  # Include map name for dynamic config
            }
            self.redis_conn.publish(self.game_state_channel, json.dumps(game_state))
        except Exception as e:
            minqlx.log_error(f"Error in handle_server_frame: {e}")

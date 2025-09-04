import minqlx
import redis
import json
import threading
import time

# See https://www.quakelive.com/forum/showthread.php?612-Useful-Commands-and-Cvars
WEAPON_MAP = {
    0: "Gauntlet",
    1: "Machinegun",
    2: "Shotgun",
    3: "Grenade Launcher",
    4: "Rocket Launcher",
    5: "Lightning Gun",
    6: "Railgun",
    7: "Plasma Gun",
    8: "BFG",
    9: "Grappling Hook",
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

        # Redis channels
        self.command_channel = 'ql:agent:command'
        self.admin_command_channel = 'ql:admin:command'
        self.game_state_channel = 'ql:game:state'

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
        try:
            data = json.loads(command_data)
            command = data.get('command')
            agent_player = self.get_agent_player()
            if not agent_player:
                return

            if command == 'move':
                agent_player.set_velocity((data['forward'], data['right'], data['up']))
            elif command == 'look':
                agent_player.set_view_angles((data['pitch'], data['yaw'], data['roll']))
            elif command == 'attack':
                minqlx.command(f"cmd {agent_player.id} +attack; wait; -attack")
            elif command == 'use':
                agent_player.use(data['item'])
            elif command == 'weapon_select':
                agent_player.weapon(data['weapon'])
            elif command == 'say':
                minqlx.command(f"say {data['message']}")

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

    def _serialize_player(self, player):
        """Serializes a player object into a dictionary."""
        if not player:
            return None

        weapons = player.weapons()
        weapon_data = []
        for w_num in weapons:
            weapon_name = WEAPON_MAP.get(w_num, "Unknown")
            weapon_data.append({"name": weapon_name, "ammo": player.get_weapon_ammo(w_num)})

        current_weapon_num = player.weapon
        selected_weapon_data = {
            "name": WEAPON_MAP.get(current_weapon_num, "Unknown"),
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

    def handle_server_frame(self):
        """Called every server frame to publish the game state."""
        try:
            agent_player = self.get_agent_player()
            if not agent_player:
                return

            opponents = [self._serialize_player(p) for p in self.players() if p.steam_id != self.agent_steam_id]

            # minqlx.items() returns all item entities in the game.
            items = [self._serialize_item(item) for item in minqlx.items()]

            game_state = {
                'agent': self._serialize_player(agent_player),
                'opponents': opponents,
                'items': items,
                'game_in_progress': self.game.state == "in_progress",
                'game_type': self.game.type_short,
            }
            self.redis_conn.publish(self.game_state_channel, json.dumps(game_state))
        except Exception as e:
            # Using minqlx.log_error to log the exception to the Quake Live console.
            minqlx.log_error(f"Error in handle_server_frame: {e}")

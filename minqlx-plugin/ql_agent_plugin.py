import minqlx
import redis
import json
import threading
import time

# This is the address of the agent that is being trained.
# For the purpose of this project, we assume there is only one agent playing at a time.
# In a real scenario, this would need to be more dynamic.
AGENT_STEAM_ID = "some_steam_id"

class ql_agent_plugin(minqlx.Plugin):
    def __init__(self):
        super().__init__()
        self.redis_host = self.get_cvar("qlx_redisAddress", "localhost")
        self.redis_port = int(self.get_cvar("qlx_redisPort", 6379))
        self.redis_db = int(self.get_cvar("qlx_redisDatabase", 0))
        self.redis_conn = redis.Redis(host=self.redis_host, port=self.redis_port, db=self.redis_db, decode_responses=True)

        self.command_channel = 'ql:agent:command'
        self.game_state_channel = 'ql:game:state'

        self.add_hook("game_frame", self.handle_game_frame)

        # Start a thread to listen for commands from the agent
        self.command_thread = threading.Thread(target=self.listen_for_commands)
        self.command_thread.daemon = True
        self.command_thread.start()

    def listen_for_commands(self):
        pubsub = self.redis_conn.pubsub()
        pubsub.subscribe(self.command_channel)
        for message in pubsub.listen():
            if message['type'] == 'message':
                self.handle_command(message['data'])

    def handle_command(self, command_data):
        try:
            data = json.loads(command_data)
            command = data.get('command')
            player = self.player(AGENT_STEAM_ID)
            if not player:
                return

            if command == 'move':
                player.set_velocity((data['forward'], data['right'], data['up']))
            elif command == 'look':
                player.set_view_angles((data['pitch'], data['yaw'], data['roll']))
            elif command == 'attack':
                minqlx.console_command("cmd " + player.id + " +attack")
            elif command == 'use':
                player.use(data['item'])
            elif command == 'weapon_select':
                player.weapon(data['weapon'])
            elif command == 'say':
                minqlx.console_command(f"say {data['message']}")

        except Exception as e:
            minqlx.log_error(f"Error handling command: {e}")

    def handle_game_frame(self):
        # This is called every game frame. We can use it to publish the game state.
        # This might be too frequent and could be optimized.
        try:
            player = self.player(AGENT_STEAM_ID)
            if not player:
                return

            opponents = []
            for p in self.players():
                if p.steam_id != AGENT_STEAM_ID:
                    opponents.append({
                        'player_id': p.steam_id,
                        'name': p.name,
                        'health': p.health,
                        'armor': p.armor,
                        'position': {'x': p.position[0], 'y': p.position[1], 'z': p.position[2]},
                        'velocity': {'x': p.velocity[0], 'y': p.velocity[1], 'z': p.velocity[2]},
                        'is_alive': p.is_alive,
                    })

            game_state = {
                'player_id': player.steam_id,
                'health': player.health,
                'armor': player.armor,
                'position': {'x': player.position[0], 'y': player.position[1], 'z': player.position[2]},
                'velocity': {'x': player.velocity[0], 'y': player.velocity[1], 'z': player.velocity[2]},
                'ammo': player.weapons, # this might need more detail
                'is_alive': player.is_alive,
                'opponents': opponents,
                'game_in_progress': self.game.state == "in_progress",
                'game_type': self.game.type,
            }
            self.redis_conn.publish(self.game_state_channel, json.dumps(game_state))
        except Exception as e:
            minqlx.log_error(f"Error in handle_game_frame: {e}")

import json
import logging
from QuakeLiveInterface.connection import RedisConnection
from QuakeLiveInterface.state import GameState

logger = logging.getLogger(__name__)


class QuakeLiveClient:
    """
    The main client for interacting with the Quake Live server via minqlx and Redis.
    """

    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0):
        self.connection = RedisConnection(redis_host, redis_port, redis_db)
        self.game_state = GameState()
        self.command_channel = 'ql:agent:command'
        self.admin_command_channel = 'ql:admin:command'
        self.game_state_channel = 'ql:game:state'
        self.game_state_pubsub = self.connection.subscribe(self.game_state_channel)

    def update_game_state(self):
        """
        Checks for a new game state message from Redis and updates the local game state.
        """
        message = self.connection.get_message(self.game_state_pubsub)
        if message:
            self.game_state.update_from_redis(message)
            return True
        return False

    def send_command(self, channel, command, args=None):
        """
        Sends a command to the minqlx plugin via Redis on a specific channel.
        Args:
            channel: The Redis channel to publish to.
            command: The command to send.
            args: A dictionary of arguments for the command.
        """
        payload = {'command': command}
        if args:
            payload.update(args)
        self.connection.publish(channel, json.dumps(payload))

    def send_agent_command(self, command, args=None):
        """Sends a command for the agent to execute."""
        self.send_command(self.command_channel, command, args)

    def send_admin_command(self, command, args=None):
        """Sends an administrative command to the server."""
        self.send_command(self.admin_command_channel, command, args)

    # Movement commands:
    def move(self, forward, right, up):
        self.send_agent_command('move', {'forward': forward, 'right': right, 'up': up})

    def look(self, pitch, yaw, roll):
        self.send_agent_command('look', {'pitch': pitch, 'yaw': yaw, 'roll': roll})

    # Combat commands:
    def attack(self):
        self.send_agent_command('attack')

    def use_item(self, item_name):
        self.send_agent_command('use', {'item': item_name})

    def select_weapon(self, weapon_name):
        self.send_agent_command('weapon_select', {'weapon': weapon_name})

    # Communication commands:
    def say(self, message):
        self.send_agent_command('say', {'message': message})

    # Demo recording commands
    def start_demo_recording(self, filename):
        """Starts recording a demo on the server."""
        self.send_admin_command('start_demo_record', {'filename': filename})

    def stop_demo_recording(self):
        """Stops recording a demo on the server."""
        self.send_admin_command('stop_demo_record')

    # Other getters
    def get_game_state(self):
        return self.game_state

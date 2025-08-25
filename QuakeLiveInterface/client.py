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

    def send_command(self, command, args=None):
        """
        Sends a command to the minqlx plugin via Redis.
        Args:
            command: The command to send.
            args: A dictionary of arguments for the command.
        """
        payload = {'command': command}
        if args:
            payload.update(args)
        self.connection.publish(self.command_channel, json.dumps(payload))

    # Movement commands:
    def move(self, forward, right, up):
        self.send_command('move', {'forward': forward, 'right': right, 'up': up})

    def look(self, pitch, yaw, roll):
        self.send_command('look', {'pitch': pitch, 'yaw': yaw, 'roll': roll})

    # Combat commands:
    def attack(self):
        self.send_command('attack')

    def use_item(self, item_name):
        self.send_command('use', {'item': item_name})

    def select_weapon(self, weapon_name):
        self.send_command('weapon_select', {'weapon': weapon_name})

    # Communication commands:
    def say(self, message):
        self.send_command('say', {'message': message})

    # Other getters
    def get_game_state(self):
        return self.game_state

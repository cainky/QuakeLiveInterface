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
        Gets the latest game state from Redis and updates the local game state.
        Uses GET on ql:agent:last_state for reliable polling instead of pubsub.
        """
        # Poll the stored state instead of using pubsub (more reliable)
        state_data = self.connection.get('ql:agent:last_state')
        if state_data:
            self.game_state.update_from_redis(state_data)
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

    # Unified input command - sets all button states at once for physics simulation
    def send_input(self, forward=False, back=False, left=False, right=False,
                   jump=False, crouch=False, attack=False, pitch_delta=0.0, yaw_delta=0.0):
        """
        Sends a unified input command with all button states and view deltas.

        This simulates actual button presses for realistic Quake physics,
        allowing the agent to learn strafe jumping and other advanced movement.

        Args:
            forward: Hold +forward button
            back: Hold +back button
            left: Hold +moveleft button
            right: Hold +moveright button
            jump: Hold +jump button
            crouch: Hold +crouch button
            attack: Hold +attack button
            pitch_delta: View pitch change in degrees per frame
            yaw_delta: View yaw change in degrees per frame
        """
        self.send_agent_command('input', {
            'forward': int(forward),
            'back': int(back),
            'left': int(left),
            'right': int(right),
            'jump': int(jump),
            'crouch': int(crouch),
            'attack': int(attack),
            'pitch_delta': pitch_delta,
            'yaw_delta': yaw_delta,
        })

    def look(self, pitch_delta, yaw_delta):
        """Sets view angle deltas (degrees per frame)."""
        self.send_agent_command('look', {'pitch': pitch_delta, 'yaw': yaw_delta})

    def select_weapon(self, weapon_name):
        """Selects a weapon by name."""
        self.send_agent_command('weapon_select', {'weapon': weapon_name})

    def say(self, message):
        """Sends a chat message."""
        self.send_agent_command('say', {'message': message})

    # Demo recording commands
    def start_demo_recording(self, filename):
        """Starts recording a demo on the server."""
        self.send_admin_command('start_demo_record', {'filename': filename})

    def stop_demo_recording(self):
        """Stops recording a demo on the server."""
        self.send_admin_command('stop_demo_record')

    def kick_all_bots(self):
        """Kicks all bots from the server."""
        self.send_admin_command('kickbots')

    # Other getters
    def get_game_state(self):
        return self.game_state

    def close(self):
        """
        Closes the connection to the Redis server.
        """
        logger.info("Closing QuakeLiveClient connection.")
        self.connection.close()

import json
import logging
from QuakeLiveInterface.connection import RedisConnection
from QuakeLiveInterface.state import GameState

logger = logging.getLogger(__name__)


class QuakeLiveClient:
    """
    The main client for interacting with the Quake Live server via minqlx and Redis.

    Args:
        redis_host: Redis server hostname
        redis_port: Redis server port
        redis_db: Redis database number
        env_id: Environment ID for namespacing (0, 1, 2, ... for parallel envs)
                When None, uses legacy 'ql:' prefix for backwards compatibility
    """

    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0, env_id=None):
        self.connection = RedisConnection(redis_host, redis_port, redis_db)
        self.game_state = GameState()
        self.env_id = env_id

        # Build namespaced channel/key names
        prefix = f'ql:{env_id}:' if env_id is not None else 'ql:'
        self.prefix = prefix
        self.command_channel = f'{prefix}agent:command'
        self.admin_command_channel = f'{prefix}admin:command'
        self.game_state_channel = f'{prefix}game:state'
        self.last_state_key = f'{prefix}agent:last_state'
        self.game_state_pubsub = self.connection.subscribe(self.game_state_channel)

        # Frame synchronization - ensure we only process each server frame once
        self._last_frame_id = -1
        self._last_state_time_ms = 0

    def update_game_state(self, timeout_ms=250, require_new_frame=True):
        """
        Gets the latest game state from Redis and updates the local game state.
        Uses GET on ql:agent:last_state for reliable polling instead of pubsub.

        Args:
            timeout_ms: Maximum time to wait for a new frame (default 250ms)
            require_new_frame: If True, wait until state_frame_id changes

        Returns:
            True if state was updated, False on timeout
        """
        import time
        start_time = time.time()
        timeout_sec = timeout_ms / 1000.0

        while True:
            state_data = self.connection.get(self.last_state_key)
            if state_data:
                # Parse to check frame_id before full update
                import json
                try:
                    raw_state = json.loads(state_data)
                    frame_id = raw_state.get('state_frame_id', 0)

                    # If we require a new frame, check if this is different
                    if require_new_frame and frame_id == self._last_frame_id:
                        # Same frame, keep waiting (unless timeout)
                        if time.time() - start_time > timeout_sec:
                            logger.warning(f"Frame sync timeout: stuck on frame {frame_id}")
                            return False
                        time.sleep(0.005)  # 5ms poll interval
                        continue

                    # New frame (or we don't require new frame)
                    self._last_frame_id = frame_id
                    self._last_state_time_ms = raw_state.get('server_time_ms', 0)
                    self.game_state.update_from_redis(state_data)
                    return True

                except json.JSONDecodeError:
                    logger.error("Failed to parse game state JSON")
                    return False

            # No state data yet
            if time.time() - start_time > timeout_sec:
                return False
            time.sleep(0.005)

    def get_frame_timing(self):
        """Returns (last_frame_id, last_state_time_ms) for debugging."""
        return self._last_frame_id, self._last_state_time_ms

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
        # Close pubsub first
        if hasattr(self, 'game_state_pubsub') and self.game_state_pubsub is not None:
            try:
                self.game_state_pubsub.close()
            except Exception:
                pass
            self.game_state_pubsub = None
        self.connection.close()

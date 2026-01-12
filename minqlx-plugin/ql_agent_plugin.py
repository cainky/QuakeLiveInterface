import minqlx
import redis
import json
import threading
import time
import os
import sys
import math
import traceback


def create_robust_redis_connection(host, port, db, max_retries=10, initial_delay=0.5, max_delay=5.0):
    """
    Create a Redis connection with retry logic and proper timeouts.
    This is critical for reliability during Docker restarts and network issues.
    """
    retry_delay = initial_delay
    last_error = None

    for attempt in range(max_retries):
        try:
            conn = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True,
                socket_connect_timeout=2.0,  # Don't hang forever on connect
                socket_timeout=0.5,  # Short timeout for game loop
                retry_on_timeout=True,
                health_check_interval=30,
            )
            # Verify connection works
            conn.ping()
            return conn
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            last_error = e
            if attempt < max_retries - 1:
                minqlx.console_print(
                    f"[ql_agent] Redis connection attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {retry_delay:.1f}s..."
                )
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_delay)  # Exponential backoff
            else:
                minqlx.console_print(
                    f"[ql_agent] FATAL: Could not connect to Redis after {max_retries} attempts"
                )
                raise

    raise redis.exceptions.ConnectionError(f"Failed to connect after {max_retries} attempts: {last_error}")


class RobustPubSubListener:
    """
    A robust pub/sub listener that automatically reconnects on failure.
    This prevents the common issue where disconnects require Docker restarts.
    """

    def __init__(self, redis_conn, channel, handler, name="pubsub"):
        self.redis_conn = redis_conn
        self.channel = channel
        self.handler = handler
        self.name = name
        self._running = True
        self._pubsub = None
        self._lock = threading.Lock()
        self._consecutive_errors = 0
        self._max_consecutive_errors = 20
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 30.0

    def _create_pubsub(self):
        """Create a new pubsub subscription."""
        with self._lock:
            if self._pubsub:
                try:
                    self._pubsub.close()
                except Exception:
                    pass

            self._pubsub = self.redis_conn.pubsub()
            self._pubsub.subscribe(self.channel)
            minqlx.console_print(f"[ql_agent] {self.name}: Subscribed to {self.channel}")

    def run(self):
        """Main loop that listens for messages with automatic reconnection."""
        minqlx.console_print(f"[ql_agent] {self.name}: Starting listener loop")
        reconnect_delay = self._reconnect_delay

        while self._running:
            try:
                # Create/reconnect subscription if needed
                if self._pubsub is None:
                    self._create_pubsub()
                    reconnect_delay = self._reconnect_delay  # Reset delay on success

                # Get message with timeout (don't block forever)
                message = self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )

                if message and message['type'] == 'message':
                    self._consecutive_errors = 0  # Reset on success
                    try:
                        self.handler(message['data'])
                    except Exception as e:
                        minqlx.console_print(f"[ql_agent] {self.name}: Handler error: {e}")

            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError,
                    ConnectionResetError, BrokenPipeError, OSError) as e:
                self._consecutive_errors += 1
                self._pubsub = None  # Force reconnection

                if self._consecutive_errors <= 3:
                    minqlx.console_print(f"[ql_agent] {self.name}: Connection lost: {e}. Reconnecting...")
                elif self._consecutive_errors % 10 == 0:
                    minqlx.console_print(
                        f"[ql_agent] {self.name}: Still trying to reconnect "
                        f"({self._consecutive_errors} attempts)..."
                    )

                if self._consecutive_errors >= self._max_consecutive_errors:
                    # Back off significantly to avoid log spam
                    reconnect_delay = min(reconnect_delay * 2, self._max_reconnect_delay)

                time.sleep(reconnect_delay)

            except Exception as e:
                self._consecutive_errors += 1
                minqlx.console_print(f"[ql_agent] {self.name}: Unexpected error: {e}")
                time.sleep(1.0)

    def stop(self):
        """Stop the listener."""
        self._running = False
        with self._lock:
            if self._pubsub:
                try:
                    self._pubsub.close()
                except Exception:
                    pass


# Default weapon map, used as a fallback
DEFAULT_WEAPON_MAP = {
    "0": "Gauntlet", "1": "Machinegun", "2": "Shotgun", "3": "Grenade Launcher",
    "4": "Rocket Launcher", "5": "Lightning Gun", "6": "Railgun", "7": "Plasma Gun",
    "8": "BFG", "9": "Grappling Hook"
}
# Static item spawn positions per map (items spawn at fixed locations)
# Respawn times: Mega=35s, RA/YA=25s, Weapons=5s
MAP_ITEMS = {
    'toxicity': [
        {'name': 'item_armor_body', 'position': {'x': 384, 'y': 576, 'z': 40}, 'respawn': 25},
        {'name': 'item_health_mega', 'position': {'x': -448, 'y': 64, 'z': -88}, 'respawn': 35},
        {'name': 'weapon_rocketlauncher', 'position': {'x': -64, 'y': 832, 'z': 8}, 'respawn': 5},
        {'name': 'weapon_railgun', 'position': {'x': 576, 'y': -192, 'z': -88}, 'respawn': 5},
        {'name': 'weapon_lightning', 'position': {'x': -512, 'y': 704, 'z': 8}, 'respawn': 5},
    ],
    'campgrounds': [
        {'name': 'item_armor_body', 'position': {'x': 512, 'y': -192, 'z': 96}, 'respawn': 25},
        {'name': 'item_health_mega', 'position': {'x': -832, 'y': 320, 'z': -56}, 'respawn': 35},
        {'name': 'weapon_rocketlauncher', 'position': {'x': -64, 'y': -64, 'z': 96}, 'respawn': 5},
        {'name': 'weapon_railgun', 'position': {'x': -512, 'y': -448, 'z': -56}, 'respawn': 5},
    ],
    'bloodrun': [
        {'name': 'item_armor_body', 'position': {'x': 64, 'y': 1152, 'z': 184}, 'respawn': 25},
        {'name': 'item_health_mega', 'position': {'x': -448, 'y': 1536, 'z': 56}, 'respawn': 35},
        {'name': 'weapon_rocketlauncher', 'position': {'x': 448, 'y': 1024, 'z': 56}, 'respawn': 5},
    ],
    'aerowalk': [
        {'name': 'item_armor_body', 'position': {'x': -384, 'y': 1088, 'z': 192}, 'respawn': 25},
        {'name': 'item_health_mega', 'position': {'x': 192, 'y': 1344, 'z': 32}, 'respawn': 35},
        {'name': 'weapon_rocketlauncher', 'position': {'x': -64, 'y': 576, 'z': 192}, 'respawn': 5},
    ],
}


class ql_agent_plugin(minqlx.Plugin):
    def __init__(self):
        super().__init__()

        # ===========================================
        # FEATURE FLAGS for isolation testing
        # Set these env vars to "0" to disable features
        # ===========================================
        self.ENABLE_AGENT = os.environ.get("QL_AGENT_ENABLE", "1") == "1"
        self.ENABLE_STATE_LOOP = os.environ.get("QL_AGENT_ENABLE_STATE_LOOP", "1") == "1"
        self.ENABLE_SET_USERCMD = os.environ.get("QL_AGENT_ENABLE_SET_USERCMD", "1") == "1"
        self.ENABLE_EVENTS = os.environ.get("QL_AGENT_ENABLE_EVENTS", "1") == "1"
        self.ENABLE_ADMIN_COMMANDS = os.environ.get("QL_AGENT_ENABLE_ADMIN", "1") == "1"
        self.ENABLE_AGENT_COMMANDS = os.environ.get("QL_AGENT_ENABLE_COMMANDS", "1") == "1"

        minqlx.console_print(f"[ql_agent] Feature flags: ENABLE_AGENT={self.ENABLE_AGENT}, STATE_LOOP={self.ENABLE_STATE_LOOP}, SET_USERCMD={self.ENABLE_SET_USERCMD}, EVENTS={self.ENABLE_EVENTS}")

        # If master switch is off, don't initialize anything
        if not self.ENABLE_AGENT:
            minqlx.console_print("[ql_agent] MASTER SWITCH OFF - plugin disabled")
            return

        # Configuration - try cvar first, then env var, then default
        self.agent_steam_id = self.get_cvar("qlx_agentSteamId", str) or os.environ.get("QLX_AGENTSTEAMID", "76561197984141695")
        # Optional: control a bot by name instead of a human by steam ID
        self.agent_bot_name = self.get_cvar("qlx_agentBotName", str) or os.environ.get("QLX_AGENTBOTNAME", "")
        bot_skill_raw = self.get_cvar("qlx_agentBotSkill", str) or os.environ.get("QLX_AGENTBOTSKILL", "5")
        try:
            self.agent_bot_skill = int(bot_skill_raw)
        except (TypeError, ValueError):
            self.agent_bot_skill = 5
        self.redis_host = self.get_cvar("qlx_redisAddress", str) or os.environ.get("QLX_REDISADDRESS", "localhost")
        self.redis_port = int(self.get_cvar("qlx_redisPort", str) or os.environ.get("QLX_REDISPORT", "6379"))
        self.redis_db = int(self.get_cvar("qlx_redisDatabase", str) or os.environ.get("QLX_REDISDATABASE", "0"))

        # Environment ID for namespacing parallel instances
        # When set, all Redis keys/channels use prefix "ql:{env_id}:" instead of "ql:"
        env_id_str = os.environ.get("QLX_ENV_ID", "")
        self.env_id = int(env_id_str) if env_id_str else None
        self.prefix = f'ql:{self.env_id}:' if self.env_id is not None else 'ql:'

        minqlx.console_print(f"[ql_agent] Connecting to Redis at {self.redis_host}:{self.redis_port}")
        if self.env_id is not None:
            minqlx.console_print(f"[ql_agent] Using namespaced prefix: {self.prefix}")

        # Use robust connection with retry logic and proper timeouts
        self.redis_conn = create_robust_redis_connection(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db
        )
        self._redis_lock = threading.Lock()  # Thread safety for Redis operations
        minqlx.console_print(f"[ql_agent] Redis connection established (robust mode)")
        self._load_weapon_map()

        # Redis channels (namespaced)
        self.command_channel = f'{self.prefix}agent:command'
        self.admin_command_channel = f'{self.prefix}admin:command'
        self.game_state_channel = f'{self.prefix}game:state'
        self.events_channel = f'{self.prefix}game:events'

        # Track damage for delta calculation
        self.last_damage_dealt = {}  # steam_id -> total damage dealt
        self.last_damage_taken = {}  # steam_id -> total damage taken

        # Register event hooks for kills and deaths
        self.add_hook("kill", self.handle_kill)
        self.add_hook("death", self.handle_death)
        # Register hooks for game transitions to pause state loop
        self.add_hook("new_game", self.handle_new_game)
        self.add_hook("map", self.handle_map_change)
        # Use frame hook for state publishing (runs in main server thread - safe!)
        if self.ENABLE_STATE_LOOP:
            self.add_hook("frame", self.handle_game_frame)
            minqlx.console_print("[ql_agent] Frame hook registered for state publishing")
        # Register after_frame hook for agent input control
        # This runs AFTER G_RunFrame (including bot AI), allowing us to override
        # any view angles the bot AI may have set
        self.add_hook("after_frame", self.handle_after_frame)
        minqlx.console_print("[ql_agent] After-frame hook registered for agent input override")
        # CRITICAL: Start DISABLED - only enable after confirming game is ready
        # This prevents crashes during initial server startup
        self._safe_to_run = False  # Flag to pause state loop during transitions
        self._game_restarting = False  # Flag to block commands during restart
        self._startup_check_count = 0  # Counter for startup safety checks
        self._bot_spawn_next_t = 0.0

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
        # ABSOLUTE desired view angles - we track these ourselves to avoid bot AI interference
        # These are updated by adding deltas, NOT by reading from game state
        self.agent_view_angles = {'pitch': 0.0, 'yaw': 0.0}
        self.agent_view_initialized = False  # Set to True once we read initial angles

        # Use timer-based polling since minqlx doesn't have a frame hook
        self._running = True
        self._frame_count = 0

        # Only start threads if their features are enabled
        # Use robust pubsub listeners with automatic reconnection
        if self.ENABLE_AGENT_COMMANDS:
            self._agent_listener = RobustPubSubListener(
                self.redis_conn,
                self.command_channel,
                self.handle_agent_command,
                name="agent-cmd"
            )
            self.agent_command_thread = threading.Thread(
                target=self._agent_listener.run,
                daemon=True,
                name="ql-agent-cmd-listener"
            )
            self.agent_command_thread.start()
            minqlx.console_print("[ql_agent] Agent command listener started (robust mode)")
        else:
            self._agent_listener = None
            minqlx.console_print("[ql_agent] Agent command listener DISABLED")

        if self.ENABLE_ADMIN_COMMANDS:
            self._admin_listener = RobustPubSubListener(
                self.redis_conn,
                self.admin_command_channel,
                self.handle_admin_command,
                name="admin-cmd"
            )
            self.admin_command_thread = threading.Thread(
                target=self._admin_listener.run,
                daemon=True,
                name="ql-admin-cmd-listener"
            )
            self.admin_command_thread.start()
            minqlx.console_print("[ql_agent] Admin command listener started (robust mode)")
        else:
            self._admin_listener = None
            minqlx.console_print("[ql_agent] Admin command listener DISABLED")

        # Game state publishing now uses frame hook (NOT background thread)
        # The frame hook runs in the main server thread so it's safe
        if self.ENABLE_STATE_LOOP:
            minqlx.console_print("[ql_agent] State publishing via frame hook (safe mode)")
        else:
            minqlx.console_print("[ql_agent] State publishing DISABLED")

        minqlx.console_print("[ql_agent] Plugin initialization complete")

    def _safe_redis_op(self, operation, *args, **kwargs):
        """
        Thread-safe Redis operation wrapper with automatic retry.
        Prevents race conditions when multiple threads access Redis.
        """
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                with self._redis_lock:
                    return operation(*args, **kwargs)
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError,
                    ConnectionResetError, BrokenPipeError, OSError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # Brief backoff
                    continue
                # Log but don't crash
                return None
            except Exception as e:
                # Non-connection errors - log and return
                return None

        return None

    def _publish_event(self, event_type, data):
        """Publish an event to the events channel."""
        if not self.ENABLE_EVENTS:
            return
        try:
            game_time_ms = minqlx.get_game_time() if hasattr(minqlx, 'get_game_time') else 0
            event = {
                'type': event_type,
                'game_time_ms': game_time_ms,
                'server_time_ms': int(time.time() * 1000),
                **data
            }
            self._safe_redis_op(self.redis_conn.publish, self.events_channel, json.dumps(event))
        except Exception as e:
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:event_error', str(e))

    def handle_kill(self, victim, killer, data):
        """Hook for kill events - publishes ALL kill events for diagnostics."""
        try:
            # Get actual agent player (may be a bot if agent_bot_name is set)
            agent_player = self.get_agent_player()
            agent_id = agent_player.steam_id if agent_player else None

            # DIAGNOSTIC: Publish ALL kills, not just agent-involved ones
            # This helps us understand if kills are happening at all
            killer_id = killer.steam_id if killer else None
            killer_name = killer.clean_name if killer else 'world'
            victim_id = victim.steam_id if victim else None
            victim_name = victim.clean_name if victim else 'unknown'

            # Determine relationship to agent
            agent_is_killer = agent_id and killer_id == agent_id
            agent_is_victim = agent_id and victim_id == agent_id

            self._publish_event('KILL', {
                'killer_id': killer_id,
                'killer_name': killer_name,
                'victim_id': victim_id,
                'victim_name': victim_name,
                'weapon': data.get('WEAPON', '') if data else '',
                'mod': data.get('MOD', '') if data else '',
                'agent_is_killer': agent_is_killer,
                'agent_is_victim': agent_is_victim,
            })

            # Log to Redis for easy debugging (thread-safe)
            self._safe_redis_op(self.redis_conn.lpush, f'{self.prefix}kills_log', json.dumps({
                'frame': self._frame_count,
                'killer': killer_name,
                'killer_id': killer_id,
                'victim': victim_name,
                'victim_id': victim_id,
                'agent_is_killer': agent_is_killer,
            }))
            # Keep only last 50 kills
            self._safe_redis_op(self.redis_conn.ltrim, f'{self.prefix}kills_log', 0, 49)

            # Legacy events for backwards compatibility
            if agent_is_killer:
                self._publish_event('frag', {
                    'agent_role': 'killer',
                    'victim_steam_id': victim_id,
                    'victim_name': victim_name,
                    'weapon': data.get('WEAPON', '') if data else '',
                })
            elif agent_is_victim:
                self._publish_event('death', {
                    'agent_role': 'victim',
                    'killer_steam_id': killer_id,
                    'killer_name': killer_name,
                    'weapon': data.get('WEAPON', '') if data else '',
                })
        except Exception as e:
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:kill_hook_error', str(e))

    def handle_death(self, victim, killer, data):
        """Hook for death events (same as kill but from victim perspective)."""
        # Debug: Log ALL deaths to see if this fires when kill hook doesn't
        try:
            victim_name = victim.clean_name if victim else 'unknown'
            killer_name = killer.clean_name if killer else 'world'
            self._safe_redis_op(self.redis_conn.lpush, f'{self.prefix}deaths_log', json.dumps({
                'frame': self._frame_count,
                'victim': victim_name,
                'killer': killer_name,
                'hook': 'death',  # Mark which hook this came from
            }))
            self._safe_redis_op(self.redis_conn.ltrim, f'{self.prefix}deaths_log', 0, 49)
        except Exception as e:
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:death_hook_error', str(e))

    def handle_new_game(self, restart=False):
        """Hook for new game events - pause state loop during transition."""
        minqlx.console_print("[ql_agent] New game starting, pausing state loop...")
        self._safe_to_run = False
        self._startup_check_count = 0  # Reset startup safety counter
        self._game_restarting = False  # Allow commands - the frame hook will verify game readiness

    def handle_map_change(self, mapname, factory=None):
        """Hook for map change events - pause state loop during transition."""
        minqlx.console_print(f"[ql_agent] Map changing to {mapname}, pausing state loop...")
        self._safe_to_run = False
        self._startup_check_count = 0  # Reset startup safety counter
        self._game_restarting = True  # Block commands during map change
        # Clear the restarting flag after a delay - the frame hook will verify game readiness
        @minqlx.delay(2.0)
        def clear_restart_flag():
            self._game_restarting = False
        clear_restart_flag()

    def handle_after_frame(self):
        """Called after G_RunFrame completes.

        This is the key hook for agent control. By applying our inputs AFTER
        the bot AI has run, we ensure our desired view angles and movements
        override whatever the bot AI tried to set.

        STATE PUBLISHING: We publish state HERE (after applying inputs) so
        that the published state reflects OUR view angles, not the bot AI's.
        """
        try:
            # Safety check: don't access players during map change/shutdown
            game = self.game
            if game is None or game.state not in ('in_progress', 'warmup', 'countdown'):
                return

            if self._frame_count % 60 == 0:
                self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:after_frame_called', f'frame={self._frame_count}')

            agent_player = self.get_agent_player()
            if agent_player and agent_player.is_alive:
                # Apply our inputs FIRST (overrides bot AI)
                self._apply_agent_inputs(agent_player)
                # Track damage events
                self._check_damage_events(agent_player)

            # Publish state AFTER applying inputs so it reflects our angles
            if self._safe_to_run:
                self._publish_agent_state()

        except Exception as e:
            # Don't spam errors every frame, just log to Redis
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:after_frame_error', str(e))

    def _publish_agent_state(self):
        """Publish game state to Redis. Called from after_frame hook."""
        try:
            game = self.game
            if game is None:
                return

            agent_player = self.get_agent_player()
            if not agent_player:
                return

            agent_data = self._serialize_player(agent_player)
            agent_id = agent_player.steam_id

            # Serialize opponents with in_fov calculation
            opponents = []
            for p in self.players():
                if p.steam_id != agent_id:
                    opp_data = self._serialize_player(p)
                    if opp_data:
                        if agent_data and 'position' in agent_data and 'position' in opp_data:
                            opp_data['in_fov'] = self._is_in_fov(
                                agent_data['position'],
                                agent_data['view_angles']['yaw'],
                                opp_data['position']
                            )
                        else:
                            opp_data['in_fov'] = False
                        opponents.append(opp_data)

            items = self.get_items()
            server_time_ms = int(time.time() * 1000)
            game_time_ms = minqlx.get_game_time() if hasattr(minqlx, 'get_game_time') else 0

            # Get agent's score stats (kills/deaths) from minqlx stats object
            agent_kills = 0
            agent_deaths = 0
            try:
                stats = agent_player.stats
                if stats:
                    # minqlx stats has kills and deaths attributes
                    agent_kills = getattr(stats, 'kills', 0)
                    agent_deaths = getattr(stats, 'deaths', 0)
                    # Debug: log available stats attributes (once per 300 frames)
                    if self._frame_count % 300 == 0:
                        attrs = [a for a in dir(stats) if not a.startswith('_')]
                        self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:stats_debug',
                            f'kills={agent_kills} deaths={agent_deaths} attrs={attrs}')
            except Exception as e:
                self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:stats_error', str(e))

            game_state = {
                'agent': agent_data,
                'opponents': opponents,
                'items': items,
                'game_in_progress': game.state in ("in_progress", "warmup", "countdown"),
                'game_state_raw': game.state,
                'game_type': game.type_short if hasattr(game, 'type_short') else None,
                'map_name': game.map if hasattr(game, 'map') else None,
                'server_time_ms': server_time_ms,
                'game_time_ms': game_time_ms,
                'state_frame_id': self._frame_count,  # For debugging sync issues
                'agent_kills': agent_kills,  # Cumulative frags this match
                'agent_deaths': agent_deaths,  # Cumulative deaths this match
            }
            self._safe_redis_op(self.redis_conn.publish, self.game_state_channel, json.dumps(game_state))
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:last_state', json.dumps(game_state))
        except Exception as e:
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:publish_error', str(e))

    def _check_damage_events(self, agent_player):
        """Check for damage changes and publish damage events."""
        try:
            stats = agent_player.stats
            if not stats:
                return

            steam_id = agent_player.steam_id

            # Get current damage values
            current_dealt = stats.damage_dealt
            current_taken = stats.damage_taken

            # Get previous values
            prev_dealt = self.last_damage_dealt.get(steam_id, 0)
            prev_taken = self.last_damage_taken.get(steam_id, 0)

            # Calculate deltas
            damage_dealt_delta = current_dealt - prev_dealt
            damage_taken_delta = current_taken - prev_taken

            # Publish damage events if there's a change
            if damage_dealt_delta > 0:
                self._publish_event('damage_dealt', {
                    'value': damage_dealt_delta,
                    'total': current_dealt,
                })

            if damage_taken_delta > 0:
                self._publish_event('damage_taken', {
                    'value': damage_taken_delta,
                    'total': current_taken,
                })

            # Update tracked values
            self.last_damage_dealt[steam_id] = current_dealt
            self.last_damage_taken[steam_id] = current_taken

        except Exception as e:
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:damage_check_error', str(e))

    # NOTE: Old listener methods removed - now using RobustPubSubListener class
    # which handles reconnection automatically

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

            elif command == 'set_view_angles':
                # Direct test command: call minqlx.set_view_angles
                # This bypasses the normal input->usercmd path for testing
                # Must run on main thread via delay
                pitch = float(data.get('pitch', 0.0))
                yaw = float(data.get('yaw', 0.0))
                roll = float(data.get('roll', 0.0))
                # Update our tracked angles so usercmd doesn't fight us
                self.agent_view_angles['pitch'] = pitch
                self.agent_view_angles['yaw'] = yaw
                self.agent_view_initialized = True

                @minqlx.delay(0)
                def do_set_view_angles():
                    agent_player = self.get_agent_player()
                    if agent_player and hasattr(minqlx, 'set_view_angles'):
                        # Read angles BEFORE setting
                        state_before = agent_player.state
                        angles_before = state_before.view_angles if state_before else None

                        result = minqlx.set_view_angles(agent_player.id, pitch, yaw, roll)

                        # Read angles IMMEDIATELY AFTER setting (same frame)
                        state_after = agent_player.state
                        angles_after = state_after.view_angles if state_after else None

                        self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:set_view_angles_result', json.dumps({
                            'client_id': agent_player.id,
                            'pitch': pitch,
                            'yaw': yaw,
                            'roll': roll,
                            'result': result,
                            'before': list(angles_before) if angles_before else None,
                            'after': list(angles_after) if angles_after else None,
                        }))
                do_set_view_angles()

        except Exception as e:
            print(f"Error handling agent command: {e}")

    def handle_admin_command(self, command_data):
        """Queue admin command for main thread execution."""
        try:
            data = json.loads(command_data)
            command = data.get('command')

            # Block commands during game restart to prevent crashes
            if self._game_restarting and command != 'restart_game':
                minqlx.console_print(f"[ql_agent] Ignoring command '{command}' - game is restarting")
                return

            # Schedule command execution on main thread using minqlx.delay
            # This is critical - console_command must run on main game thread
            @minqlx.delay(0)
            def execute_command():
                self._execute_admin_command(command, data)
            execute_command()

        except Exception as e:
            print(f"Error handling admin command: {e}")

    def _execute_admin_command(self, command, data):
        """Execute admin command on main thread."""
        try:
            if command == 'restart_game':
                minqlx.console_print("[ql_agent] Restarting game via admin command.")
                self._game_restarting = True  # Block further commands
                self._safe_to_run = False     # Pause state loop
                self._reset_agent_tracking()
                minqlx.console_command("map_restart")
            elif command == 'start_demo_record':
                filename = data.get('filename', 'agent_demo')
                minqlx.console_print(f"[ql_agent] Starting demo recording: {filename}")
                minqlx.console_command(f"record {filename}")
            elif command == 'stop_demo_record':
                minqlx.console_print("[ql_agent] Stopping demo recording.")
                minqlx.console_command("stoprecord")
            elif command == 'kickbots':
                minqlx.console_print("[ql_agent] Kicking all bots")
                # Kick each bot individually (kick allbots doesn't work)
                # Add delay between kicks to prevent command overflow
                import time as time_module
                bots_kicked = 0
                for player in list(self.players()):
                    # Bots have steam_ids starting with 90071996842377
                    if player.steam_id > 90071996842377000 and player.steam_id < 90071996842378000:
                        try:
                            player.kick()
                            bots_kicked += 1
                            minqlx.console_print(f"[ql_agent] Kicked bot: {player.clean_name}")
                            time_module.sleep(0.5)  # Delay to prevent command buffer overflow
                        except Exception as e:
                            minqlx.console_print(f"[ql_agent] Failed to kick {player.clean_name}: {e}")
                minqlx.console_print(f"[ql_agent] Kicked {bots_kicked} bots")
            elif command == 'addbot':
                bot_name = data.get('name', 'crash')
                bot_skill = data.get('skill', 5)
                minqlx.console_print(f"[ql_agent] Adding bot: {bot_name} skill {bot_skill}")
                self._reset_agent_tracking()  # Reset view tracking for new bot
                minqlx.console_command(f"addbot {bot_name} {bot_skill}")
            elif command == 'console':
                # Execute arbitrary console command
                cmd = data.get('cmd', '')
                if cmd:
                    print(f"Executing console command: {cmd}")
                    minqlx.console_command(cmd)

        except Exception as e:
            print(f"Error executing admin command: {e}")

    def _reset_agent_tracking(self):
        """Reset the tracked view angles and inputs when agent respawns."""
        self.agent_view_angles = {'pitch': 0.0, 'yaw': 0.0}
        self.agent_view_initialized = False
        self.agent_inputs = {
            'forward': False,
            'back': False,
            'left': False,
            'right': False,
            'jump': False,
            'crouch': False,
            'attack': False,
        }
        self.agent_view_delta = {'pitch': 0.0, 'yaw': 0.0}
        print("[ql_agent] Agent tracking reset")

    def get_agent_player(self):
        """Finds the player object for the agent.

        If agent_bot_name is set, matches by player name (for controlling bots).
        Otherwise matches by steam_id (for controlling humans).
        """
        # If controlling a bot by name
        if self.agent_bot_name:
            for player in self.players():
                if player.clean_name.lower() == self.agent_bot_name.lower():
                    return player
            return None

        # Otherwise match by steam ID (original behavior)
        agent_id = int(self.agent_steam_id)
        for player in self.players():
            if player.steam_id == agent_id:
                return player
        return None

    def _load_weapon_map(self):
        """Loads the weapon map from a cvar or uses the default."""
        weapon_map_json = self.get_cvar("qlx_weaponMapJson")
        if weapon_map_json:
            try:
                self.weapon_map = json.loads(weapon_map_json)
                print("Loaded custom weapon map from cvar.")
            except json.JSONDecodeError:
                print("Invalid JSON in qlx_weaponMapJson cvar. Falling back to default weapon map.")
                self.weapon_map = DEFAULT_WEAPON_MAP
        else:
            print("Using default weapon map.")
            self.weapon_map = DEFAULT_WEAPON_MAP

    def _is_in_fov(self, agent_pos, agent_yaw, target_pos, fov_degrees=90):
        """
        Check if target is within agent's field of view (horizontal only).
        This is an FOV check, NOT a line-of-sight raycast.

        Args:
            agent_pos: Dict with x, y, z
            agent_yaw: Agent's yaw angle in degrees
            target_pos: Dict with x, y, z
            fov_degrees: Total FOV width (default 90)

        Returns:
            bool: True if target is within FOV cone
        """
        try:
            dx = target_pos['x'] - agent_pos['x']
            dy = target_pos['y'] - agent_pos['y']

            # Calculate angle to target
            angle_to_target = math.degrees(math.atan2(dy, dx))

            # Calculate difference and normalize to [-180, 180]
            yaw_diff = angle_to_target - agent_yaw
            while yaw_diff > 180:
                yaw_diff -= 360
            while yaw_diff < -180:
                yaw_diff += 360

            return abs(yaw_diff) < (fov_degrees / 2)
        except Exception:
            return False

    def _serialize_player(self, player):
        """Serializes a player object into a dictionary using available minqlx attributes."""
        if not player:
            return None

        try:
            # Get player state - contains position, velocity, etc.
            state = player.state
            pos = state.position if state else None
            vel = state.velocity if state else None

            # View angles might be on player directly or on state with different names
            angles = None
            if hasattr(player, 'view_angles'):
                angles = player.view_angles
            elif state and hasattr(state, 'view_angles'):
                angles = state.view_angles
            elif state and hasattr(state, 'viewangles'):
                angles = state.viewangles

            return {
                'steam_id': player.steam_id,
                'name': player.clean_name,
                'health': player.health,
                'armor': player.armor,
                'position': {'x': pos.x, 'y': pos.y, 'z': pos.z} if pos else {'x': 0, 'y': 0, 'z': 0},
                'velocity': {'x': vel.x, 'y': vel.y, 'z': vel.z} if vel else {'x': 0, 'y': 0, 'z': 0},
                'view_angles': {'pitch': angles[0], 'yaw': angles[1], 'roll': angles[2]} if angles else {'pitch': 0, 'yaw': 0, 'roll': 0},
                'is_alive': player.is_alive,
                'team': str(player.team),
            }
        except Exception as e:
            # Fallback with minimal data
            return {
                'steam_id': player.steam_id,
                'name': player.clean_name,
                'health': getattr(player, 'health', 0),
                'armor': getattr(player, 'armor', 0),
                'position': {'x': 0, 'y': 0, 'z': 0},
                'velocity': {'x': 0, 'y': 0, 'z': 0},
                'view_angles': {'pitch': 0, 'yaw': 0, 'roll': 0},
                'is_alive': getattr(player, 'is_alive', False),
                'error': str(e),
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

    def get_items(self):
        """
        Scans raw game entities using our custom get_entity_info() function.
        Falls back to static map data if get_entity_info is not available.
        """
        items = []

        # Get current game time for calculating time_to_spawn_ms
        game_time = minqlx.get_game_time() if hasattr(minqlx, 'get_game_time') else 0

        # Try our custom get_entity_info() first (added in our minqlx fork)
        if hasattr(minqlx, 'get_entity_info'):
            try:
                for i in range(1024):
                    ent = minqlx.get_entity_info(i)
                    if not ent:
                        continue

                    classname = ent.get('classname', '')
                    if not classname:
                        continue

                    if not (classname.startswith('item_') or
                            classname.startswith('weapon_') or
                            classname.startswith('ammo_')):
                        continue

                    in_use = ent.get('in_use', False)
                    next_think = ent.get('next_think', 0)
                    is_available = in_use and next_think == 0

                    # Calculate time_to_spawn_ms (0 if available, positive if respawning)
                    if is_available:
                        time_to_spawn_ms = 0
                    elif next_think > 0 and game_time > 0:
                        time_to_spawn_ms = max(0, next_think - game_time)
                    else:
                        time_to_spawn_ms = 0  # Unknown state

                    items.append({
                        'name': classname,
                        'position': ent.get('position', {'x': 0, 'y': 0, 'z': 0}),
                        'is_available': is_available,
                        'time_to_spawn_ms': time_to_spawn_ms,
                    })

                if items:
                    return items
            except Exception:
                pass

        # Fallback to static map data
        map_name = self.game.map.lower() if self.game else None
        if not map_name or map_name not in MAP_ITEMS:
            return []

        return [
            {
                'name': item['name'],
                'position': item['position'],
                'is_available': True,
                'time_to_spawn_ms': 0
            }
            for item in MAP_ITEMS[map_name]
        ]
    
    def get_items_OLD(self):
        """OLD: Entity-based item scanning (doesn't work on most minqlx builds)."""
        items = []
        try:
            if hasattr(minqlx, 'Entity'):
                # Iterate through entity IDs (QL typically has max 1024 entities)
                for i in range(1024):
                    try:
                        ent = minqlx.Entity(i)
                        if ent is None or not ent.is_used:
                            continue

                        classname = ent.classname if hasattr(ent, 'classname') else None
                        if not classname:
                            continue

                        # Filter for items: health, armor, weapons, ammo, powerups
                        if (classname.startswith("item_") or
                            classname.startswith("weapon_") or
                            classname.startswith("ammo_") or
                            classname.startswith("holdable_")):

                            # Get position - try different attribute names
                            pos = {'x': 0, 'y': 0, 'z': 0}
                            if hasattr(ent, 'origin'):
                                origin = ent.origin
                                pos = {'x': origin[0], 'y': origin[1], 'z': origin[2]}
                            elif hasattr(ent, 's') and hasattr(ent.s, 'origin'):
                                origin = ent.s.origin
                                pos = {'x': origin[0], 'y': origin[1], 'z': origin[2]}

                            # Determine availability
                            is_available = True
                            if hasattr(ent, 'is_suspended'):
                                is_available = not ent.is_suspended
                            elif hasattr(ent, 'inuse'):
                                is_available = ent.inuse

                            # Get spawn time if available
                            spawn_time = 0
                            if hasattr(ent, 'spawnTime'):
                                spawn_time = ent.spawnTime
                            elif hasattr(ent, 'nextthink'):
                                spawn_time = ent.nextthink

                            items.append({
                                'name': classname,
                                'position': pos,
                                'is_available': is_available,
                                'spawn_time': spawn_time
                            })
                    except (ValueError, RuntimeError):
                        # Entity doesn't exist or is invalid
                        continue

        except Exception as e:
            # Log error but don't crash - return empty list
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:item_error', str(e))

        return items

    def _state_loop(self):
        """Background thread that publishes game state at ~60Hz."""
        minqlx.console_print("[ql_agent] State loop starting...")

        while self._running:
            try:
                # Sleep longer if we know we're in an unsafe state
                if not self._safe_to_run:
                    time.sleep(0.5)
                    continue

                # CRITICAL: Check C-level safety flag before accessing ANY game state
                # This prevents crashes during map restart/shutdown
                if hasattr(minqlx, 'is_game_safe') and not minqlx.is_game_safe():
                    time.sleep(0.1)
                    continue

                # Safety: Skip if game is not in a safe state
                # Wrap ALL game state access in try/except
                try:
                    game = self.game
                    if game is None:
                        time.sleep(0.1)
                        continue
                    # Check if game module is loaded
                    game_state = game.state
                    # Allow warmup and in_progress states
                    if game_state not in ('in_progress', 'warmup', 'countdown'):
                        time.sleep(0.1)
                        continue
                    # Double-check we have players before proceeding
                    player_list = list(self.players())
                    if not player_list:
                        time.sleep(0.1)
                        continue
                except:
                    # Any exception during game state check = skip this frame
                    time.sleep(0.1)
                    continue

                self._frame_count += 1
                # Write frame count to Redis for debugging
                if self._frame_count % 100 == 0:
                    self._safe_redis_op(self.redis_conn.set, f"{self.prefix}agent:frame", self._frame_count)
                self.handle_server_frame()
                time.sleep(1/60)  # ~60Hz
            except Exception as e:
                self._safe_redis_op(self.redis_conn.set, f"{self.prefix}agent:error", str(e))
                time.sleep(0.1)

    def _apply_agent_inputs(self, agent_player):
        """
        Applies the current input state to the agent using set_usercmd.
        This sets the usercmd directly for full control over bot input.
        """
        if not self.ENABLE_SET_USERCMD:
            return
        if not agent_player or not agent_player.is_alive:
            return
        # CRITICAL: Double-check game safety before any C calls
        if hasattr(minqlx, 'is_game_safe') and not minqlx.is_game_safe():
            return

        try:
            client_id = agent_player.id

            # Calculate movement values (-127 to 127)
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

            # Calculate button state
            buttons = 0
            if self.agent_inputs['attack']:
                buttons |= 1  # BUTTON_ATTACK

            # Initialize our tracked view angles from game state on first run
            # After that, we ONLY use our tracked values to avoid bot AI interference
            if not self.agent_view_initialized:
                # Check game safety before accessing player state
                if hasattr(minqlx, 'is_game_safe') and not minqlx.is_game_safe():
                    return
                try:
                    state = agent_player.state
                    if state and hasattr(state, 'view_angles') and state.view_angles:
                        self.agent_view_angles['pitch'] = state.view_angles[0]
                        self.agent_view_angles['yaw'] = state.view_angles[1]
                        self.agent_view_initialized = True
                except Exception:
                    pass

            # Apply view deltas to OUR tracked angles (not game state)
            # Note: delta is applied ONCE when received, not every frame
            # The deltas are consumed (set to 0) after applying
            if self.agent_view_delta['pitch'] != 0.0 or self.agent_view_delta['yaw'] != 0.0:
                self.agent_view_angles['pitch'] += self.agent_view_delta['pitch']
                self.agent_view_angles['yaw'] += self.agent_view_delta['yaw']

                # Debug: log delta application
                self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:delta_applied', json.dumps({
                    'frame': self._frame_count,
                    'delta_pitch': self.agent_view_delta['pitch'],
                    'delta_yaw': self.agent_view_delta['yaw'],
                    'new_pitch': self.agent_view_angles['pitch'],
                    'new_yaw': self.agent_view_angles['yaw']
                }))

                # Clear deltas after applying (one-shot application)
                self.agent_view_delta['pitch'] = 0.0
                self.agent_view_delta['yaw'] = 0.0

            # Clamp pitch to valid range
            self.agent_view_angles['pitch'] = max(-89.0, min(89.0, self.agent_view_angles['pitch']))

            # Wrap yaw to [-180, 180]
            while self.agent_view_angles['yaw'] > 180:
                self.agent_view_angles['yaw'] -= 360
            while self.agent_view_angles['yaw'] < -180:
                self.agent_view_angles['yaw'] += 360

            new_pitch = self.agent_view_angles['pitch']
            new_yaw = self.agent_view_angles['yaw']

            # Use set_usercmd for direct control (if available)
            # Final safety check right before the call
            if hasattr(minqlx, 'is_game_safe') and not minqlx.is_game_safe():
                return
            if hasattr(minqlx, 'set_usercmd'):
                # Read angles BEFORE set_usercmd
                state_before = agent_player.state
                yaw_before = state_before.view_angles[1] if state_before and state_before.view_angles else None

                result = minqlx.set_usercmd(
                    client_id,
                    forwardmove, rightmove, upmove,
                    new_pitch, new_yaw,
                    buttons
                )

                # Read angles IMMEDIATELY AFTER set_usercmd
                state_after = agent_player.state
                yaw_after = state_after.view_angles[1] if state_after and state_after.view_angles else None

                # Log usercmd every 10 frames (~6Hz) for debugging visibility
                if self._frame_count % 10 == 0:
                    self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:usercmd', json.dumps({
                        'client_id': client_id,
                        'forward': forwardmove,
                        'right': rightmove,
                        'up': upmove,
                        'pitch': new_pitch,
                        'yaw': new_yaw,
                        'buttons': buttons,
                        'result': result,
                        'tracked_pitch': self.agent_view_angles['pitch'],
                        'tracked_yaw': self.agent_view_angles['yaw'],
                        'delta_pitch': self.agent_view_delta['pitch'],
                        'delta_yaw': self.agent_view_delta['yaw'],
                        'ps_yaw_before': yaw_before,
                        'ps_yaw_after': yaw_after
                    }))
            else:
                # Fallback to old method if set_usercmd not available
                if hasattr(minqlx, 'apply_movement'):
                    minqlx.apply_movement(client_id, forwardmove/127.0, rightmove/127.0, 320.0)
                if hasattr(minqlx, 'set_buttons'):
                    minqlx.set_buttons(client_id, buttons)
                if hasattr(minqlx, 'set_view_angles'):
                    minqlx.set_view_angles(client_id, new_pitch, new_yaw, 0.0)

        except Exception as e:
            # Log error to Redis for debugging
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:input_error', f"{e}")
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:input_traceback', traceback.format_exc())

    def _publish_state_if_possible(self):
        """Publish game state to Redis without applying inputs. Used during startup."""
        try:
            game = self.game
            if game is None:
                return

            agent_player = self.get_agent_player()
            agent_data = self._serialize_player(agent_player) if agent_player else None

            # Get actual agent steam_id (not configured one, which might be for human)
            agent_steam_id = agent_player.steam_id if agent_player else int(self.agent_steam_id)

            opponents = []
            for p in self.players():
                if p.steam_id != agent_steam_id:
                    opp_data = self._serialize_player(p)
                    if opp_data:
                        opp_data['in_fov'] = False  # Don't calculate FOV during startup
                        opponents.append(opp_data)

            items = self.get_items()
            server_time_ms = int(time.time() * 1000)
            game_time_ms = minqlx.get_game_time() if hasattr(minqlx, 'get_game_time') else 0

            game_state = {
                'agent': agent_data,
                'opponents': opponents,
                'items': items,
                'game_in_progress': game.state in ("in_progress", "warmup", "countdown"),
                'game_state_raw': game.state,
                'game_type': game.type_short if hasattr(game, 'type_short') else None,
                'map_name': game.map if hasattr(game, 'map') else None,
                'server_time_ms': server_time_ms,
                'game_time_ms': game_time_ms,
                'safe_to_run': self._safe_to_run,
                'startup_check_count': self._startup_check_count,
                'state_frame_id': self._frame_count,
            }
            self._safe_redis_op(self.redis_conn.publish, self.game_state_channel, json.dumps(game_state))
            # Always store last state for polling
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:last_state', json.dumps(game_state))
        except Exception as e:
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:publish_error', str(e))

    def handle_game_frame(self):
        """Called by the frame hook (main server thread). Safe to access game state."""
        try:
            # Always increment frame counter for debugging visibility
            self._frame_count += 1
            if self._frame_count % 100 == 0:
                self._safe_redis_op(self.redis_conn.set, f"{self.prefix}agent:frame", self._frame_count)

            # STARTUP SAFETY CHECK: Don't enable until game is confirmed ready
            # Must pass multiple consecutive checks before we start operating
            if not self._safe_to_run:
                # Try to verify game is ready
                try:
                    game = self.game
                    if game is None:
                        self._startup_check_count = 0
                        # Still try to publish state for debugging
                        self._publish_state_if_possible()
                        return
                    game_state = game.state
                    if game_state not in ('in_progress', 'warmup', 'countdown'):
                        self._startup_check_count = 0
                        self._publish_state_if_possible()
                        return
                    # Additional check: make sure we can actually list players
                    players = list(self.players())
                    if not players:
                        self._startup_check_count = 0
                        self._publish_state_if_possible()
                        return
                    # C-level safety check if available
                    if hasattr(minqlx, 'is_game_safe') and not minqlx.is_game_safe():
                        self._startup_check_count = 0
                        self._publish_state_if_possible()
                        return
                    # Passed all checks - increment counter
                    self._startup_check_count += 1
                    # Require 60 consecutive successful checks (~1 second at 60fps)
                    # before enabling operations
                    if self._startup_check_count >= 60:
                        minqlx.console_print("[ql_agent] Game ready - enabling state publishing")
                        self._safe_to_run = True
                        self._maybe_spawn_agent_bot()
                except Exception:
                    self._startup_check_count = 0
                # Publish state even when not fully ready (for env visibility)
                self._publish_state_if_possible()
                return

            # Double-check game state is still valid
            game = self.game
            if game is None:
                return
            game_state = game.state
            if game_state not in ('in_progress', 'warmup', 'countdown'):
                return

            self._maybe_spawn_agent_bot()

            # Call the actual handler (just debug logging now - state publishing moved to after_frame)
            self.handle_server_frame()
        except Exception as e:
            self._safe_redis_op(self.redis_conn.set, f"{self.prefix}agent:frame_error", str(e))

    def _maybe_spawn_agent_bot(self):
        if not self.agent_bot_name:
            return
        if self._game_restarting:
            return
        if self.get_agent_player() is not None:
            return
        now = time.time()
        if now < self._bot_spawn_next_t:
            return
        self._bot_spawn_next_t = now + 5.0
        bot_name = self.agent_bot_name
        bot_skill = self.agent_bot_skill
        minqlx.console_print(f"[ql_agent] Auto-adding agent bot: {bot_name} skill {bot_skill}")
        minqlx.console_command(f"addbot {bot_name} {bot_skill}")

    def handle_server_frame(self):
        """Called by frame handler. Only handles startup safety and debug logging.

        NOTE: Input application and state publishing are now done in handle_after_frame
        to ensure our view angles are set AFTER bot AI runs and the published state
        reflects our angles, not the bot AI's.
        """
        try:
            # Store debug info in Redis every 100 frames
            if self._frame_count % 100 == 0:
                players = list(self.players())
                agent_player_debug = self.get_agent_player()
                items_debug = self.get_items()
                debug = {
                    'frame': self._frame_count,
                    'looking_for': self.agent_steam_id,
                    'looking_for_int': int(self.agent_steam_id),
                    'players': [(p.steam_id, p.clean_name) for p in players],
                    'agent_found': agent_player_debug is not None,
                    'agent_name': agent_player_debug.clean_name if agent_player_debug else None,
                    'item_count': len(items_debug),
                    'has_get_entity_info': hasattr(minqlx, 'get_entity_info'),
                    'has_set_usercmd': hasattr(minqlx, 'set_usercmd'),
                    'has_apply_movement': hasattr(minqlx, 'apply_movement'),
                    'has_set_view_angles': hasattr(minqlx, 'set_view_angles'),
                    'has_set_buttons': hasattr(minqlx, 'set_buttons'),
                    'agent_inputs': self.agent_inputs,
                    'agent_view_delta': self.agent_view_delta
                }
                self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:debug', json.dumps(debug))

            # Note: Actual input application and state publishing moved to after_frame hook
        except Exception as e:
            # Store errors to Redis since console_print doesn't work from threads
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:error', f"Frame {self._frame_count}: {e}")
            self._safe_redis_op(self.redis_conn.set, f'{self.prefix}agent:traceback', traceback.format_exc())

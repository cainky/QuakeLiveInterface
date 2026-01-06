import minqlx
import redis
import json
import threading
import time
import os
import sys
import math

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
        self.redis_host = self.get_cvar("qlx_redisAddress", str) or os.environ.get("QLX_REDISADDRESS", "localhost")
        self.redis_port = int(self.get_cvar("qlx_redisPort", str) or os.environ.get("QLX_REDISPORT", "6379"))
        self.redis_db = int(self.get_cvar("qlx_redisDatabase", str) or os.environ.get("QLX_REDISDATABASE", "0"))

        minqlx.console_print(f"[ql_agent] Connecting to Redis at {self.redis_host}:{self.redis_port}")
        self.redis_conn = redis.Redis(host=self.redis_host, port=self.redis_port, db=self.redis_db, decode_responses=True)
        minqlx.console_print(f"[ql_agent] Redis connection established: {self.redis_conn.ping()}")
        self._load_weapon_map()

        # Redis channels
        self.command_channel = 'ql:agent:command'
        self.admin_command_channel = 'ql:admin:command'
        self.game_state_channel = 'ql:game:state'
        self.events_channel = 'ql:game:events'

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
        if self.ENABLE_AGENT_COMMANDS:
            self.agent_command_thread = threading.Thread(target=self.listen_for_agent_commands)
            self.agent_command_thread.daemon = True
            self.agent_command_thread.start()
            minqlx.console_print("[ql_agent] Agent command listener started")
        else:
            minqlx.console_print("[ql_agent] Agent command listener DISABLED")

        if self.ENABLE_ADMIN_COMMANDS:
            self.admin_command_thread = threading.Thread(target=self.listen_for_admin_commands)
            self.admin_command_thread.daemon = True
            self.admin_command_thread.start()
            minqlx.console_print("[ql_agent] Admin command listener started")
        else:
            minqlx.console_print("[ql_agent] Admin command listener DISABLED")

        # Game state publishing now uses frame hook (NOT background thread)
        # The frame hook runs in the main server thread so it's safe
        if self.ENABLE_STATE_LOOP:
            minqlx.console_print("[ql_agent] State publishing via frame hook (safe mode)")
        else:
            minqlx.console_print("[ql_agent] State publishing DISABLED")

        minqlx.console_print("[ql_agent] Plugin initialization complete")

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
            self.redis_conn.publish(self.events_channel, json.dumps(event))
        except Exception as e:
            self.redis_conn.set('ql:agent:event_error', str(e))

    def handle_kill(self, victim, killer, data):
        """Hook for kill events - publishes frag events."""
        try:
            # Get actual agent player (may be a bot if agent_bot_name is set)
            agent_player = self.get_agent_player()
            if not agent_player:
                return  # No agent found, nothing to track
            agent_id = agent_player.steam_id

            # Check if agent is involved
            if killer and killer.steam_id == agent_id:
                # Agent killed someone
                self._publish_event('frag', {
                    'agent_role': 'killer',
                    'victim_steam_id': victim.steam_id if victim else None,
                    'victim_name': victim.clean_name if victim else None,
                    'weapon': data.get('WEAPON', '') if data else '',
                })
            elif victim and victim.steam_id == agent_id:
                # Agent was killed
                self._publish_event('death', {
                    'agent_role': 'victim',
                    'killer_steam_id': killer.steam_id if killer else None,
                    'killer_name': killer.clean_name if killer else None,
                    'weapon': data.get('WEAPON', '') if data else '',
                })
        except Exception as e:
            self.redis_conn.set('ql:agent:kill_hook_error', str(e))

    def handle_death(self, victim, killer, data):
        """Hook for death events (same as kill but from victim perspective)."""
        # Most logic is handled in handle_kill, this is just for completeness
        pass

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
        """
        try:
            # Safety check: don't access players during map change/shutdown
            game = self.game
            if game is None or game.state not in ('in_progress', 'warmup', 'countdown'):
                return

            self._frame_count += 1
            if self._frame_count % 60 == 0:
                self.redis_conn.set('ql:agent:after_frame_called', f'frame={self._frame_count}')

            agent_player = self.get_agent_player()
            if agent_player and agent_player.is_alive:
                self._apply_agent_inputs(agent_player)
        except Exception as e:
            # Don't spam errors every frame, just log to Redis
            self.redis_conn.set('ql:agent:after_frame_error', str(e))

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
            self.redis_conn.set('ql:agent:damage_check_error', str(e))

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
                bots_kicked = 0
                for player in list(self.players()):
                    # Bots have steam_ids starting with 90071996842377
                    if player.steam_id > 90071996842377000 and player.steam_id < 90071996842378000:
                        try:
                            player.kick()
                            bots_kicked += 1
                            minqlx.console_print(f"[ql_agent] Kicked bot: {player.clean_name}")
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
            self.redis_conn.set('ql:agent:item_error', str(e))

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
                    self.redis_conn.set("ql:agent:frame", self._frame_count)
                self.handle_server_frame()
                time.sleep(1/60)  # ~60Hz
            except Exception as e:
                self.redis_conn.set("ql:agent:error", str(e))
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
                self.redis_conn.set('ql:agent:delta_applied', json.dumps({
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
                result = minqlx.set_usercmd(
                    client_id,
                    forwardmove, rightmove, upmove,
                    new_pitch, new_yaw,
                    buttons
                )
                # Log usercmd every 10 frames (~6Hz) for debugging visibility
                if self._frame_count % 10 == 0:
                    self.redis_conn.set('ql:agent:usercmd', json.dumps({
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
                        'delta_yaw': self.agent_view_delta['yaw']
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
            import traceback
            self.redis_conn.set('ql:agent:input_error', f"{e}")
            self.redis_conn.set('ql:agent:input_traceback', traceback.format_exc())

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
            }
            self.redis_conn.publish(self.game_state_channel, json.dumps(game_state))
            # Always store last state for polling
            self.redis_conn.set('ql:agent:last_state', json.dumps(game_state))
        except Exception as e:
            self.redis_conn.set('ql:agent:publish_error', str(e))

    def handle_game_frame(self):
        """Called by the frame hook (main server thread). Safe to access game state."""
        try:
            # Always increment frame counter for debugging visibility
            self._frame_count += 1
            if self._frame_count % 100 == 0:
                self.redis_conn.set("ql:agent:frame", self._frame_count)

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

            # Call the actual handler (includes input application and state publishing)
            self.handle_server_frame()
        except Exception as e:
            try:
                self.redis_conn.set("ql:agent:frame_error", str(e))
            except:
                pass

    def handle_server_frame(self):
        """Called by frame handler to apply inputs and publish the game state."""
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
                self.redis_conn.set('ql:agent:debug', json.dumps(debug))

            agent_player = self.get_agent_player()
            if not agent_player:
                return

            # Apply agent inputs - this calls set_usercmd() to cache the command
            # The C code will apply it after G_RunFrame to override bot AI
            if agent_player.is_alive:
                self._apply_agent_inputs(agent_player)

            # Track damage deltas and publish damage events
            self._check_damage_events(agent_player)

            # Collect and publish game state
            # Use actual agent's steam_id for filtering (not configured human ID)
            agent_id = agent_player.steam_id
            agent_data = self._serialize_player(agent_player)

            # Serialize opponents with in_fov calculation
            opponents = []
            for p in self.players():
                if p.steam_id != agent_id:
                    opp_data = self._serialize_player(p)
                    if opp_data and agent_data:
                        # Calculate if opponent is in agent's FOV
                        opp_data['in_fov'] = self._is_in_fov(
                            agent_data['position'],
                            agent_data['view_angles']['yaw'],
                            opp_data['position']
                        )
                    else:
                        opp_data['in_fov'] = False
                    opponents.append(opp_data)

            items = self.get_items()  # Scan gentities for items

            # Get timing information
            server_time_ms = int(time.time() * 1000)  # Wall clock time in ms
            game_time_ms = minqlx.get_game_time() if hasattr(minqlx, 'get_game_time') else 0

            game_state = {
                'agent': agent_data,
                'opponents': opponents,
                'items': items,
                'game_in_progress': self.game.state in ("in_progress", "warmup", "countdown"),
                'game_state_raw': self.game.state,
                'game_type': self.game.type_short,
                'map_name': self.game.map,
                'server_time_ms': server_time_ms,
                'game_time_ms': game_time_ms,
            }
            num_recipients = self.redis_conn.publish(self.game_state_channel, json.dumps(game_state))

            # Track successful publishes
            if self._frame_count % 100 == 0:
                self.redis_conn.set('ql:agent:last_publish', self._frame_count)
                self.redis_conn.set('ql:agent:recipients', num_recipients)
                # Also store last game state for debugging
                self.redis_conn.set('ql:agent:last_state', json.dumps(game_state))
        except Exception as e:
            # Store errors to Redis since console_print doesn't work from threads
            self.redis_conn.set('ql:agent:error', f"Frame {self._frame_count}: {e}")
            import traceback
            self.redis_conn.set('ql:agent:traceback', traceback.format_exc())

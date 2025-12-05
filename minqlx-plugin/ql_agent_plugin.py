import minqlx
import redis
import json
import threading
import time
import os
import sys

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

        # Configuration - try cvar first, then env var, then default
        self.agent_steam_id = self.get_cvar("qlx_agentSteamId", str) or os.environ.get("QLX_AGENTSTEAMID", "76561197984141695")
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

        # Use timer-based polling since minqlx doesn't have a frame hook
        self._running = True
        self._frame_count = 0

        self.agent_command_thread = threading.Thread(target=self.listen_for_agent_commands)
        self.agent_command_thread.daemon = True
        self.agent_command_thread.start()

        self.admin_command_thread = threading.Thread(target=self.listen_for_admin_commands)
        self.admin_command_thread.daemon = True
        self.admin_command_thread.start()

        # Game state publishing thread (runs at ~60Hz)
        self.state_thread = threading.Thread(target=self._state_loop)
        self.state_thread.daemon = True
        self.state_thread.start()

        minqlx.console_print("[ql_agent] Plugin initialized - state publishing thread started")

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
        try:
            data = json.loads(command_data)
            command = data.get('command')

            if command == 'restart_game':
                print("Restarting game via admin command.")
                minqlx.command("restart")
            elif command == 'start_demo_record':
                filename = data.get('filename', 'agent_demo')
                print(f"Starting demo recording: {filename}")
                minqlx.command(f"record {filename}")
            elif command == 'stop_demo_record':
                print("Stopping demo recording.")
                minqlx.command("stoprecord")

        except Exception as e:
            print(f"Error handling admin command: {e}")

    def get_agent_player(self):
        """Finds the player object for the agent."""
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

                    items.append({
                        'name': classname,
                        'position': ent.get('position', {'x': 0, 'y': 0, 'z': 0}),
                        'is_available': is_available,
                        'next_think': next_think,
                        'in_use': in_use
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
                'spawn_time': 0
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
            print(f"Error applying agent inputs: {e}")

    def handle_server_frame(self):
        """Called by state loop to apply inputs and publish the game state."""
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
                    'has_get_entity_info': hasattr(minqlx, 'get_entity_info')
                }
                self.redis_conn.set('ql:agent:debug', json.dumps(debug))

            agent_player = self.get_agent_player()
            if not agent_player:
                return

            # NOTE: user_cmd injection not available in this minqlx version
            # self._apply_agent_inputs(agent_player)

            # Collect and publish game state
            agent_id = int(self.agent_steam_id)
            opponents = [self._serialize_player(p) for p in self.players() if p.steam_id != agent_id]
            items = self.get_items()  # Scan gentities for items

            game_state = {
                'agent': self._serialize_player(agent_player),
                'opponents': opponents,
                'items': items,
                'game_in_progress': self.game.state == "in_progress",
                'game_type': self.game.type_short,
                'map_name': self.game.map,
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

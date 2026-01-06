import gymnasium as gym
from gymnasium import spaces
import numpy as np
import time
import logging
import os
from QuakeLiveInterface.client import QuakeLiveClient
from QuakeLiveInterface.state import GameState
from QuakeLiveInterface.rewards import RewardSystem
from QuakeLiveInterface.metrics import PerformanceTracker
from QuakeLiveInterface.utils import estimate_map_dims_from_replay

logger = logging.getLogger(__name__)

# Default weapon list for Quake Live
DEFAULT_WEAPON_LIST = [
    "Gauntlet", "Machinegun", "Shotgun", "Grenade Launcher",
    "Rocket Launcher", "Lightning Gun", "Railgun", "Plasma Gun",
    "BFG", "Grappling Hook"
]

# View sensitivity: degrees per frame at max input
# At 40 Hz: 3°/step = 120°/sec max turn rate (reasonable for Quake, less jitter)
VIEW_SENSITIVITY = 3.0


class QuakeLiveEnv(gym.Env):
    """
    A Gymnasium environment for Quake Live.

    Action Space (MultiDiscrete):
        [0] Forward/Back:  0=back, 1=none, 2=forward
        [1] Left/Right:    0=left, 1=none, 2=right
        [2] Jump/Crouch:   0=crouch, 1=none, 2=jump
        [3] Attack:        0=no, 1=yes
        [4] Look Pitch:    0-10 discretized (-1 to +1, mapped to degrees)
        [5] Look Yaw:      0-10 discretized (-1 to +1, mapped to degrees)

    This uses button simulation for realistic Quake physics,
    allowing the agent to learn strafe jumping and advanced movement.
    """
    metadata = {'render.modes': ['human']}

    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0,
                 max_health=200, max_armor=200, map_dims=(4000, 4000, 1000),
                 max_velocity=800, max_ammo=200, num_items=10, num_opponents=3,
                 max_episode_steps=1000, demo_dir=None, weapon_list=None,
                 view_sensitivity=VIEW_SENSITIVITY, obs_mode='oracle',
                 agent_bot_name=None, agent_bot_skill=5):
        """
        Args:
            obs_mode: Observation mode for opponent visibility.
                'oracle' - Always include all opponent features (full information)
                'human' - Mask opponent features when not in agent's FOV (partial observability)
            agent_bot_name: If set, the agent is a bot that will be re-added after reset.
            agent_bot_skill: Skill level for the agent bot (1-5).
        """
        super(QuakeLiveEnv, self).__init__()

        if obs_mode not in ('oracle', 'human'):
            raise ValueError(f"obs_mode must be 'oracle' or 'human', got '{obs_mode}'")

        self.client = QuakeLiveClient(redis_host, redis_port, redis_db)
        self.game_state = GameState()
        self.reward_system = RewardSystem()
        self.performance_tracker = PerformanceTracker()
        self.episode_num = 0
        self.step_count = 0
        self.max_episode_steps = max_episode_steps
        self.demo_dir = demo_dir
        self.view_sensitivity = view_sensitivity
        self.obs_mode = obs_mode
        self.agent_bot_name = agent_bot_name
        self.agent_bot_skill = agent_bot_skill


        # MultiDiscrete action space for universal RL compatibility
        # [forward/back, left/right, jump/crouch, attack, look_pitch, look_yaw]
        self.action_space = spaces.MultiDiscrete([3, 3, 3, 2, 11, 11])

        # Constants for normalization
        self.MAX_HEALTH = max_health
        self.MAX_ARMOR = max_armor
        self.MAP_DIMS = np.array(map_dims)
        self.MAX_VELOCITY = max_velocity
        self.WEAPON_LIST = weapon_list if weapon_list is not None else DEFAULT_WEAPON_LIST
        self.WEAPON_MAP = {name: i for i, name in enumerate(self.WEAPON_LIST)}
        self.NUM_WEAPONS = len(self.WEAPON_LIST)
        self.MAX_AMMO = max_ammo
        self.NUM_ITEMS = num_items
        self.NUM_OPPONENTS = num_opponents

        # Define observation space size dynamically
        self.agent_feature_size = 11
        self.weapon_feature_size = 2 * self.NUM_WEAPONS
        self.opponent_feature_size = 11 * self.NUM_OPPONENTS
        self.item_feature_size = 5 * self.NUM_ITEMS # x, y, z, is_available, spawn_time
        obs_size = self.agent_feature_size + self.weapon_feature_size + self.opponent_feature_size + self.item_feature_size
        self.observation_space = spaces.Box(low=-1.0, high=1.0, shape=(obs_size,), dtype=np.float32)

        self.last_action = None
        self._consecutive_bad_states = 0  # Track consecutive "terminated" conditions
        self._BAD_STATE_THRESHOLD = 3     # Require N bad states before terminating

        # Decision tick timing for monitoring
        self._last_step_time = None
        self._step_dt_sum = 0.0
        self._step_dt_count = 0

    def step(self, action):
        """
        Run one timestep of the environment's dynamics.
        """
        # Track decision tick timing
        step_start = time.time()
        if self._last_step_time is not None:
            dt = step_start - self._last_step_time
            self._step_dt_sum += dt
            self._step_dt_count += 1
        self._last_step_time = step_start

        self.last_action = action
        self._apply_action(action)
        self.step_count += 1

        # Wait for the next game state update (blocks until new frame_id)
        if not self.client.update_game_state():
            # Handle case where no update is received (timeout)
            obs = self._get_observation()
            return obs, 0, False, False, {'frame_sync_timeout': True}

        new_game_state = self.client.get_game_state()

        # Calculate reward
        reward = self.reward_system.calculate_reward(new_game_state, self.last_action)
        self.game_state = new_game_state

        # Check if the episode is terminated or truncated
        # Use consecutive bad state counter to avoid terminating on transient glitches
        agent = self.game_state.get_agent()
        bad_state = not self.game_state.game_in_progress or not agent or not agent.is_alive

        if bad_state:
            self._consecutive_bad_states += 1
        else:
            self._consecutive_bad_states = 0

        # Only terminate after N consecutive bad states (avoids transient countdown/respawn)
        terminated = self._consecutive_bad_states >= self._BAD_STATE_THRESHOLD
        truncated = self.step_count >= self.max_episode_steps

        # Get the observation
        obs = self._get_observation()

        # Log performance metrics
        self.performance_tracker.log_step(self.game_state, action)

        # Build info dict with episode metrics on termination/truncation
        # Use 'terminal_info' key to avoid VecMonitor overwriting 'episode'
        info = {}
        if terminated or truncated:
            tracker = self.performance_tracker
            # Calculate decision tick rate
            avg_dt_ms = (self._step_dt_sum / self._step_dt_count * 1000) if self._step_dt_count > 0 else 0
            decision_hz = 1000 / avg_dt_ms if avg_dt_ms > 0 else 0

            info['terminal_info'] = {
                'damage_dealt': tracker.damage_dealt,
                'damage_taken': tracker.damage_taken,
                'frags': tracker.kills,
                'deaths': tracker.deaths,
                'frag_diff': tracker.kills - tracker.deaths,
                'shots_fired': tracker.shots_fired,
                'hits': tracker.successful_hits,
                'accuracy': (tracker.successful_hits / tracker.shots_fired * 100) if tracker.shots_fired > 0 else 0,
                'health_pickups': tracker.items_collected.get('Health', 0),
                'armor_pickups': tracker.items_collected.get('Armor', 0),
                'distance_traveled': tracker.total_distance_traveled,
                'avg_step_dt_ms': avg_dt_ms,
                'decision_hz': decision_hz,
            }
            # Quick validation print
            logger.info(f"Episode {self.episode_num} end: frags={tracker.kills} deaths={tracker.deaths} "
                       f"dmg_dealt={tracker.damage_dealt} dmg_taken={tracker.damage_taken} "
                       f"accuracy={info['terminal_info']['accuracy']:.1f}% hz={decision_hz:.1f}")

        return obs, reward, terminated, truncated, info

    def reset(self, seed=None, options=None, reset_timeout=15.0):
        """
        Resets the state of the environment and returns an initial observation.
        """
        super().reset(seed=seed)

        # Stop recording the previous demo
        if self.episode_num > 0 and self.demo_dir:
            self.client.stop_demo_recording()

        # Log performance for the completed episode
        if self.episode_num > 0:
            self.performance_tracker.log_episode(self.episode_num)

        self.episode_num += 1
        self.step_count = 0

        # Start recording a new demo
        if self.demo_dir:
            if not os.path.exists(self.demo_dir):
                os.makedirs(self.demo_dir)
            demo_filename = f"ep_{self.episode_num}_{int(time.time())}"
            self.client.start_demo_recording(demo_filename)

        # Reset trackers and systems
        self.reward_system.reset()
        self.performance_tracker.reset()
        self.game_state = GameState()  # Reset game state
        self._consecutive_bad_states = 0  # Reset termination counter
        self._last_step_time = None  # Reset timing stats
        self._step_dt_sum = 0.0
        self._step_dt_count = 0

        import time as time_module

        # First, check current roster before doing anything disruptive
        self.client.update_game_state()
        current_state = self.client.get_game_state()
        num_opponents = len(current_state.get_opponents()) if current_state else 0
        agent = current_state.get_agent() if current_state else None

        # Log roster for debugging
        if agent:
            logger.info(f"Episode {self.episode_num}: Roster check - Agent={agent.name}, Opponents={num_opponents}")
        else:
            logger.info(f"Episode {self.episode_num}: No agent found, Opponents={num_opponents}")

        # Only fix roster if it's actually wrong
        roster_correct = agent is not None and num_opponents == 1
        if self.agent_bot_name and not roster_correct:
            logger.info(f"Episode {self.episode_num}: Roster incorrect, fixing (once)...")

            # Kick ALL bots first
            self.client.send_admin_command('kickbots')
            time_module.sleep(2.0)

            # Add agent bot
            logger.info(f"Episode {self.episode_num}: Adding agent bot: {self.agent_bot_name}")
            self.client.send_admin_command('addbot', {
                'name': self.agent_bot_name,
                'skill': self.agent_bot_skill
            })
            time_module.sleep(2.0)

            # Add opponent bot (different from agent)
            opponent_name = 'crash' if self.agent_bot_name.lower() != 'crash' else 'doom'
            logger.info(f"Episode {self.episode_num}: Adding opponent bot: {opponent_name}")
            self.client.send_admin_command('addbot', {
                'name': opponent_name,
                'skill': self.agent_bot_skill
            })
            time_module.sleep(3.0)
        else:
            # Roster is fine - just restart the match (fast, no kicks)
            logger.info(f"Episode {self.episode_num}: Roster OK, restarting match.")
            self.client.send_admin_command('restart_game')
            time_module.sleep(1.5)  # Shorter wait since no bot changes

        # Wait for STABLE game state (N consecutive good ticks)
        # This prevents returning during transient countdown/respawn states
        STABLE_TICKS_REQUIRED = 5
        stable_tick_count = 0
        last_game_time = None

        start_time = time.time()
        while time.time() - start_time < reset_timeout:
            if self.client.update_game_state():
                self.game_state = self.client.get_game_state()
                agent = self.game_state.get_agent()
                opponents = self.game_state.get_opponents()
                game_time = getattr(self.game_state, 'game_time_ms', 0)

                # Check all stability conditions
                is_stable = (
                    self.game_state.game_in_progress and
                    agent is not None and
                    agent.is_alive and
                    len(opponents) >= 1 and
                    (last_game_time is None or game_time >= last_game_time)
                )

                if is_stable:
                    stable_tick_count += 1
                    if stable_tick_count >= STABLE_TICKS_REQUIRED:
                        logger.info(f"Game reset successful after {stable_tick_count} stable ticks. Agent is alive.")
                        obs = self._get_observation()
                        return obs, {}
                else:
                    stable_tick_count = 0  # Reset counter on any instability

                last_game_time = game_time

            time.sleep(0.1)  # ~10Hz check rate

        logger.warning(f"Reset timeout ({reset_timeout}s) reached. Environment may not be ready.")
        obs = self._get_observation()
        return obs, {}

    def render(self, mode='human'):
        """
        Renders the environment.
        """
        if mode == 'human':
            agent_state = self.game_state.get_agent()
            if agent_state:
                print(f"Health: {agent_state.health}, Armor: {agent_state.armor}")
                print(f"Position: {agent_state.position}")
            else:
                print("No agent state available.")

    def close(self):
        """
        Cleans up the environment's resources.
        """
        self.client.close()

    def _get_observation(self):
        """
        Converts the current game state into a normalized observation vector.
        """
        obs = np.zeros(self.observation_space.shape, dtype=np.float32)

        # If game state is not ready, return zero vector
        if not self.game_state or not self.game_state.get_agent():
            return obs

        agent = self.game_state.get_agent()

        # Agent features
        agent_feats = self._get_player_features(agent)

        # Weapon features
        weapon_feats = self._get_weapon_features(agent)

        # Opponent features: find the N closest opponents
        opponents = [opp for opp in self.game_state.get_opponents() if opp.is_alive]
        opponent_feats = np.zeros(self.opponent_feature_size)
        if opponents:
            agent_pos = np.array(list(agent.position.values()))

            # Calculate distances to all living opponents
            for opp in opponents:
                opp_pos = np.array(list(opp.position.values()))
                opp.distance = np.sum(np.square(agent_pos - opp_pos))

            # Sort opponents by distance
            opponents.sort(key=lambda o: o.distance)

            # Get features for the N closest opponents
            for i, opp in enumerate(opponents[:self.NUM_OPPONENTS]):
                start_idx = i * 11
                end_idx = start_idx + 11
                # In 'human' mode, only include opponents that are in FOV
                if self.obs_mode == 'human' and not getattr(opp, 'in_fov', True):
                    # Opponent not in FOV - leave as zeros (masked)
                    continue
                opponent_feats[start_idx:end_idx] = self._get_player_features(opp)


        # Item features
        item_feats = self._get_item_features(self.game_state.get_items())

        # Concatenate all features into the observation vector
        offset = 0
        obs[offset:offset+self.agent_feature_size] = agent_feats
        offset += self.agent_feature_size
        obs[offset:offset+self.weapon_feature_size] = weapon_feats
        offset += self.weapon_feature_size
        obs[offset:offset+self.opponent_feature_size] = opponent_feats
        offset += self.opponent_feature_size
        obs[offset:offset+self.item_feature_size] = item_feats

        return obs

    def _normalize_pos(self, pos):
        return np.array([pos['x'], pos['y'], pos['z']]) / self.MAP_DIMS * 2 - 1

    def _normalize_vel(self, vel):
        return np.array([vel['x'], vel['y'], vel['z']]) / self.MAX_VELOCITY

    def _get_player_features(self, player):
        """Extracts and normalizes features for a single player."""
        if not player:
            return np.zeros(11)

        pos = self._normalize_pos(player.position)
        vel = self._normalize_vel(player.velocity)
        health = player.health / self.MAX_HEALTH
        armor = player.armor / self.MAX_ARMOR
        is_alive = 1 if player.is_alive else 0

        # Normalize view angles. Pitch: [-90, 90] -> [-1, 1]. Yaw: [-180, 180] -> [-1, 1].
        pitch = player.view_angles['pitch'] / 90.0
        yaw = player.view_angles['yaw'] / 180.0

        return np.array([*pos, *vel, pitch, yaw, health, armor, is_alive])

    def _get_weapon_features(self, agent):
        """Extracts and normalizes weapon features for the agent."""
        features = np.zeros(2 * self.NUM_WEAPONS)
        if not agent:
            return features

        # One-hot encode selected weapon
        if agent.selected_weapon:
            weapon_idx = self.WEAPON_MAP.get(agent.selected_weapon.name, -1)
            if weapon_idx != -1:
                features[weapon_idx] = 1

        # Ammo for each weapon
        for weapon in agent.weapons:
            weapon_idx = self.WEAPON_MAP.get(weapon.name, -1)
            if weapon_idx != -1:
                features[self.NUM_WEAPONS + weapon_idx] = weapon.ammo / self.MAX_AMMO

        return features

    def _get_item_features(self, items):
        """Extracts and normalizes features for items."""
        features = np.zeros(5 * self.NUM_ITEMS)
        for i, item in enumerate(items):
            if i >= self.NUM_ITEMS:
                break
            # Handle both Item objects and dicts for backwards compatibility
            if hasattr(item, 'position'):
                pos = self._normalize_pos(item.position)
                is_available = 1 if item.is_available else 0
                time_to_spawn = getattr(item, 'time_to_spawn_ms', 0) / 30000.0
            else:
                pos = self._normalize_pos(item['position'])
                is_available = 1 if item['is_available'] else 0
                time_to_spawn = item.get('time_to_spawn_ms', item.get('spawn_time', 0)) / 30000.0
            features[i*5 : i*5 + 5] = [*pos, is_available, time_to_spawn]
        return features

    @staticmethod
    def estimate_map_dims(replay_file_path):
        """
        A helper function to estimate map dimensions from a replay file.
        This is a convenience wrapper around the utility function.
        """
        return estimate_map_dims_from_replay(replay_file_path)

    def _apply_action(self, action):
        """
        Applies a MultiDiscrete action to the game using button simulation.

        Action format: [forward_back, left_right, jump_crouch, attack, look_pitch, look_yaw]
        - forward_back: 0=back, 1=none, 2=forward
        - left_right:   0=left, 1=none, 2=right
        - jump_crouch:  0=crouch, 1=none, 2=jump
        - attack:       0=no, 1=yes
        - look_pitch:   0-10 (maps to -sensitivity to +sensitivity degrees)
        - look_yaw:     0-10 (maps to -sensitivity to +sensitivity degrees)
        """
        # Decode movement buttons
        forward = (action[0] == 2)
        back = (action[0] == 0)
        right = (action[1] == 2)
        left = (action[1] == 0)
        jump = (action[2] == 2)
        crouch = (action[2] == 0)
        attack = (action[3] == 1)

        # Decode look inputs: 0-10 -> -1 to +1 -> degrees
        pitch_normalized = (action[4] - 5) / 5.0  # -1 to +1
        yaw_normalized = (action[5] - 5) / 5.0    # -1 to +1
        pitch_delta = pitch_normalized * self.view_sensitivity
        yaw_delta = yaw_normalized * self.view_sensitivity

        # Send unified input command
        self.client.send_input(
            forward=forward,
            back=back,
            left=left,
            right=right,
            jump=jump,
            crouch=crouch,
            attack=attack,
            pitch_delta=pitch_delta,
            yaw_delta=yaw_delta
        )

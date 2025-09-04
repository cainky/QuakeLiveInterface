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

logger = logging.getLogger(__name__)

class QuakeLiveEnv(gym.Env):
    """
    A Gymnasium environment for Quake Live.
    """
    metadata = {'render.modes': ['human']}

    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0,
                 max_health=200, max_armor=200, map_dims=(4000, 4000, 1000),
                 max_velocity=800, max_ammo=200, num_items=10, num_opponents=3,
                 max_episode_steps=1000, demo_dir=None):
        super(QuakeLiveEnv, self).__init__()

        self.client = QuakeLiveClient(redis_host, redis_port, redis_db)
        self.game_state = GameState()
        self.reward_system = RewardSystem()
        self.performance_tracker = PerformanceTracker()
        self.episode_num = 0
        self.step_count = 0
        self.max_episode_steps = max_episode_steps
        self.demo_dir = demo_dir

        # Define action and observation space
        self.action_space = spaces.Dict({
            "move_forward_back": spaces.Discrete(3),  # 0: back, 1: none, 2: forward
            "move_right_left": spaces.Discrete(3),  # 0: left, 1: none, 2: right
            "move_up_down": spaces.Discrete(3),  # 0: down (crouch), 1: none, 2: up (jump)
            "attack": spaces.Discrete(2), # 0: no, 1: yes
            "look_pitch": spaces.Box(low=-1.0, high=1.0, shape=(1,)),
            "look_yaw": spaces.Box(low=-1.0, high=1.0, shape=(1,)),
        })

        # Constants for normalization
        self.MAX_HEALTH = max_health
        self.MAX_ARMOR = max_armor
        self.MAP_DIMS = np.array(map_dims)
        self.MAX_VELOCITY = max_velocity
        self.WEAPON_LIST = [
            "Gauntlet", "Machinegun", "Shotgun", "Grenade Launcher",
            "Rocket Launcher", "Lightning Gun", "Railgun", "Plasma Gun",
            "BFG", "Grappling Hook"
        ]
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

    def step(self, action):
        """
        Run one timestep of the environment's dynamics.
        """
        self.last_action = action
        self._apply_action(action)
        self.step_count += 1

        # Wait for the next game state update
        if not self.client.update_game_state():
            # Handle case where no update is received
            # For now, we'll just return the current state with no reward
            obs = self._get_observation()
            return obs, 0, False, False, {}

        new_game_state = self.client.get_game_state()

        # Calculate reward
        reward = self.reward_system.calculate_reward(new_game_state, self.last_action)
        self.game_state = new_game_state

        # Check if the episode is terminated or truncated
        terminated = bool(not self.game_state.game_in_progress or not (self.game_state.get_agent() and self.game_state.get_agent().is_alive))
        truncated = self.step_count >= self.max_episode_steps

        # Get the observation
        obs = self._get_observation()

        # Log performance metrics
        self.performance_tracker.log_step(self.game_state, action)

        return obs, reward, terminated, truncated, {}

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
        self.game_state = GameState() # Reset game state

        # Send a command to restart the game
        logger.info(f"Episode {self.episode_num}: Sending command to restart game.")
        self.client.send_admin_command('restart_game')

        # Wait for the game to restart and for the agent to be alive
        start_time = time.time()
        while time.time() - start_time < reset_timeout:
            if self.client.update_game_state():
                self.game_state = self.client.get_game_state()
                agent = self.game_state.get_agent()
                if self.game_state.game_in_progress and agent and agent.is_alive:
                    logger.info("Game reset successful. Agent is alive.")
                    obs = self._get_observation()
                    return obs, {}
            time.sleep(0.1) # Avoid busy-waiting

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
            pos = self._normalize_pos(item['position'])
            is_available = 1 if item['is_available'] else 0
            spawn_time = item['spawn_time'] / 30000.0 # Normalize by 30 seconds
            features[i*5 : i*5 + 5] = [*pos, is_available, spawn_time]
        return features

    def _apply_action(self, action):
        """
        Applies an action to the game.
        """
        # Movement
        f = action["move_forward_back"] - 1
        r = action["move_right_left"] - 1
        u = action["move_up_down"] - 1
        self.client.move(f, r, u)

        # Looking
        pitch = action["look_pitch"][0]
        yaw = action["look_yaw"][0]
        self.client.look(pitch, yaw, 0) # Roll is not used

        # Attack
        if action["attack"] == 1:
            self.client.attack()

import gymnasium as gym
from gymnasium import spaces
import numpy as np
from QuakeLiveInterface.client import QuakeLiveClient
from QuakeLiveInterface.state import GameState
from QuakeLiveInterface.rewards import RewardSystem
from QuakeLiveInterface.metrics import PerformanceTracker

class QuakeLiveEnv(gym.Env):
    """
    A Gymnasium environment for Quake Live.
    """
    metadata = {'render.modes': ['human']}

    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0):
        super(QuakeLiveEnv, self).__init__()

        self.client = QuakeLiveClient(redis_host, redis_port, redis_db)
        self.game_state = GameState()
        self.reward_system = RewardSystem()
        self.performance_tracker = PerformanceTracker()
        self.episode_num = 0

        # Define action and observation space
        # These will be refined in the next step.
        # For now, a placeholder multi-discrete action space
        self.action_space = spaces.Dict({
            "move_forward_back": spaces.Discrete(3),  # 0: back, 1: none, 2: forward
            "move_right_left": spaces.Discrete(3),  # 0: left, 1: none, 2: right
            "move_up_down": spaces.Discrete(3),  # 0: down (crouch), 1: none, 2: up (jump)
            "attack": spaces.Discrete(2), # 0: no, 1: yes
            "look_pitch": spaces.Box(low=-1.0, high=1.0, shape=(1,)),
            "look_yaw": spaces.Box(low=-1.0, high=1.0, shape=(1,)),
        })

        # The observation space will be a flattened vector of normalized game state features.
        # Let's define the size based on the features we will include.
        # Agent state: 11
        # Weapon state: 20
        # Opponent state: 11
        # Item states: 40
        # Total size = 11 + 20 + 11 + 40 = 82
        self.observation_space = spaces.Box(low=-1.0, high=1.0, shape=(82,), dtype=np.float32)

        self.last_action = None

        # Constants for normalization
        self.MAX_HEALTH = 200
        self.MAX_ARMOR = 200
        self.MAP_DIMS = np.array([4000, 4000, 1000]) # Estimated map dimensions
        self.MAX_VELOCITY = 800 # units per second
        self.NUM_WEAPONS = 10 # Number of weapons for one-hot encoding
        self.MAX_AMMO = 200
        self.NUM_ITEMS = 10 # Max number of items to track

    def step(self, action):
        """
        Run one timestep of the environment's dynamics.
        """
        self.last_action = action
        self._apply_action(action)

        # Wait for the next game state update
        if not self.client.update_game_state():
            # Handle case where no update is received
            # For now, we'll just return the current state with no reward
            obs = self._get_observation()
            return obs, 0, False, {}

        new_game_state = self.client.get_game_state()

        # Calculate reward
        reward = self.reward_system.calculate_reward(new_game_state, self.last_action)
        self.game_state = new_game_state

        # Check if the episode is done
        done = not self.game_state.game_in_progress or not (self.game_state.get_agent() and self.game_state.get_agent().is_alive)

        # Get the observation
        obs = self._get_observation()

        # Log performance metrics
        self.performance_tracker.log_step(self.game_state, action)

        return obs, reward, done, {}

    def reset(self, seed=None, options=None):
        """
        Resets the state of the environment and returns an initial observation.
        """
        super().reset(seed=seed)

        # Log performance for the completed episode
        if self.episode_num > 0:
            self.performance_tracker.log_episode(self.episode_num)

        self.episode_num += 1

        # Reset trackers and systems
        self.reward_system.reset()
        self.performance_tracker.reset()

        # Send a command to restart the game
        self.client.send_admin_command('restart_game')

        # Wait for the game to restart and get the initial state
        # This needs a more robust implementation to ensure the game is ready
        self.client.update_game_state()
        self.game_state = self.client.get_game_state()

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
        # The Redis connection is managed by the client, which doesn't have a close method yet.
        # We can add one if needed.
        pass

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

        # Opponent features (we'll just take the first opponent for simplicity)
        opponents = self.game_state.get_opponents()
        opponent_feats = self._get_player_features(opponents[0]) if opponents else np.zeros(11)

        # Item features
        item_feats = self._get_item_features(self.game_state.get_items())

        # Concatenate all features into the observation vector
        # The slicing needs to match the size defined in __init__
        obs[0:11] = agent_feats
        obs[11:31] = weapon_feats
        obs[31:42] = opponent_feats
        obs[42:82] = item_feats

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

        # Assuming view angles are not available in player object yet, placeholder
        # In a real implementation, this would come from the game state.
        pitch = 0.0
        yaw = 0.0

        return np.array([*pos, *vel, pitch, yaw, health, armor, is_alive])

    def _get_weapon_features(self, agent):
        """Extracts and normalizes weapon features for the agent."""
        features = np.zeros(20)
        if not agent or not agent.selected_weapon:
            return features

        # One-hot encode selected weapon
        # This requires a mapping from weapon name to index
        weapon_map = {name: i for i, name in enumerate(self.game_state.get_agent().weapons)}
        weapon_idx = weapon_map.get(agent.selected_weapon.name, -1)
        if weapon_idx != -1 and weapon_idx < self.NUM_WEAPONS:
            features[weapon_idx] = 1

        # Ammo for each weapon
        for i, weapon in enumerate(agent.weapons):
            if i < self.NUM_WEAPONS:
                features[self.NUM_WEAPONS + i] = weapon.ammo / self.MAX_AMMO

        return features

    def _get_item_features(self, items):
        """Extracts and normalizes features for items."""
        features = np.zeros(4 * self.NUM_ITEMS)
        for i, item in enumerate(items):
            if i >= self.NUM_ITEMS:
                break
            pos = self._normalize_pos(item.position)
            is_available = 1 if item.is_available else 0
            features[i*4 : i*4 + 4] = [*pos, is_available]
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

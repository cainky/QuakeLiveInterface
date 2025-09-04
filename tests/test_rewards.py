import pytest
from QuakeLiveInterface.rewards import RewardSystem
import numpy as np

# Mock classes to simulate the game state
class MockWeapon:
    def __init__(self, name, ammo):
        self.name = name
        self.ammo = ammo

class MockPlayer:
    def __init__(self, health=100, armor=100, is_alive=True, position={'x': 0, 'y': 0, 'z': 0}, steam_id="agent_id", weapons=None):
        self.health = health
        self.armor = armor
        self.is_alive = is_alive
        self.position = position
        self.steam_id = steam_id
        self.weapons = weapons if weapons is not None else []

class MockGameState:
    def __init__(self, agent, opponents):
        self._agent = agent
        self._opponents = opponents

    def get_agent(self):
        return self._agent

    def get_opponents(self):
        return self._opponents

@pytest.fixture
def reward_system():
    """Returns a RewardSystem instance with default weights."""
    return RewardSystem()

def test_reset(reward_system):
    """Tests if the reward system resets its state."""
    agent1 = MockPlayer()
    state1 = MockGameState(agent=agent1, opponents=[])
    reward_system.previous_state = state1
    reward_system.reset()
    assert reward_system.previous_state is None

def test_calculate_reward_initial_step(reward_system):
    """Tests that the reward is 0 on the first step."""
    state = MockGameState(agent=MockPlayer(), opponents=[])
    reward = reward_system.calculate_reward(state, {})
    assert reward == 0

def test_calculate_item_reward(reward_system):
    """Tests the item pickup reward component."""
    agent1 = MockPlayer(health=80, armor=40, weapons=[MockWeapon("Machinegun", 50)])
    agent2 = MockPlayer(health=100, armor=50, weapons=[MockWeapon("Machinegun", 100), MockWeapon("Shotgun", 10)])
    state1 = MockGameState(agent=agent1, opponents=[])
    state2 = MockGameState(agent=agent2, opponents=[])

    reward_system.calculate_reward(state1, {}) # Initialize previous_state

    reward_system.reward_weights = {
        'item_control': 1.0, 'damage_and_kills': 0.0,
        'map_control': 0.0, 'health_penalty': 0.0
    }
    reward = reward_system.calculate_reward(state2, {})

    # Expected item reward = (100-80) health + (50-40) armor + 50 new weapon + 50 ammo = 130
    assert reward == 130

def test_calculate_damage_reward(reward_system):
    """Tests the damage and kills reward component."""
    agent = MockPlayer()
    opponent1_s1 = MockPlayer(health=100, is_alive=True, steam_id="opp1")
    opponent1_s2 = MockPlayer(health=20, is_alive=True, steam_id="opp1") # 80 damage
    opponent2_s1 = MockPlayer(health=50, is_alive=True, steam_id="opp2")
    opponent2_s2 = MockPlayer(health=0, is_alive=False, steam_id="opp2") # 50 damage + 1 kill (100 bonus)

    state1 = MockGameState(agent=agent, opponents=[opponent1_s1, opponent2_s1])
    state2 = MockGameState(agent=agent, opponents=[opponent1_s2, opponent2_s2])

    reward_system.calculate_reward(state1, {}) # Initialize previous_state
    reward_system.reward_weights = {
        'item_control': 0.0, 'damage_and_kills': 1.0,
        'map_control': 0.0, 'health_penalty': 0.0
    }
    reward = reward_system.calculate_reward(state2, {})

    # Expected damage reward = 80 (damage) + 50 (damage) + 100 (kill bonus) = 230
    assert reward == 230

def test_calculate_map_control_reward(reward_system):
    """Tests the map control reward component."""
    # Using the first strategic point from the default list as the target
    strategic_pos = reward_system.strategic_points[0]['pos']

    agent1 = MockPlayer(position={'x': strategic_pos[0] + 1000, 'y': strategic_pos[1], 'z': strategic_pos[2]})
    agent2 = MockPlayer(position={'x': strategic_pos[0], 'y': strategic_pos[1], 'z': strategic_pos[2]}) # at strategic point
    state1 = MockGameState(agent=agent1, opponents=[])
    state2 = MockGameState(agent=agent2, opponents=[])

    reward_system.calculate_reward(state1, {}) # Initialize previous_state
    reward_system.reward_weights = {
        'item_control': 0.0, 'damage_and_kills': 0.0,
        'map_control': 1.0, 'health_penalty': 0.0
    }
    reward = reward_system.calculate_reward(state2, {})

    # Expected map control reward = 1000 / (dist + 1)
    # dist for agent2 is 0, so reward is 1000 / 1 = 1000
    assert reward == 1000.0

def test_calculate_health_penalty(reward_system):
    """Tests the health penalty component."""
    agent1 = MockPlayer(health=100, armor=50)
    agent2 = MockPlayer(health=70, armor=20) # -30 health, -30 armor
    state1 = MockGameState(agent=agent1, opponents=[])
    state2 = MockGameState(agent=agent2, opponents=[])

    reward_system.calculate_reward(state1, {}) # Initialize previous_state
    reward_system.reward_weights = {
        'item_control': 0.0, 'damage_and_kills': 0.0,
        'map_control': 0.0, 'health_penalty': 1.0 # use 1.0 to get raw penalty
    }
    reward = reward_system.calculate_reward(state2, {})

    # Expected penalty = -((100-70) + (50-20)) = -60
    assert reward == -60

def test_calculate_total_reward_with_weights(reward_system):
    """Tests the final weighted reward calculation."""
    # Agent state
    agent1 = MockPlayer(health=100, armor=50, position={'x': 1000, 'y': 1000, 'z': 100}, weapons=[])
    agent2 = MockPlayer(health=80, armor=40, position={'x': 0, 'y': 0, 'z': 100}, weapons=[]) # Took damage, moved to RL

    # Opponent state
    opp1_s1 = MockPlayer(health=100, is_alive=True, steam_id="opp1")
    opp1_s2 = MockPlayer(health=50, is_alive=True, steam_id="opp1") # Dealt 50 damage

    state1 = MockGameState(agent=agent1, opponents=[opp1_s1])
    state2 = MockGameState(agent=agent2, opponents=[opp1_s2])

    reward_system.calculate_reward(state1, {}) # Initialize

    # Default weights:
    # 'item_control': 0.4
    # 'damage_and_kills': 0.35
    # 'map_control': 0.25
    # 'health_penalty': -0.1

    # item_reward: 0 (no pickups)
    # damage_reward: 50
    # map_control_reward: 1000 / (0 + 1) = 1000 (at RL)
    # health_penalty: -((100-80) + (50-40)) = -30

    expected_reward = (0 * 0.4) + (50 * 0.35) + (1000 * 0.25) + (-30 * -0.1)
    # expected_reward = 0 + 17.5 + 250 + 3.0 = 270.5

    reward = reward_system.calculate_reward(state2, {})

    assert reward == pytest.approx(270.5)

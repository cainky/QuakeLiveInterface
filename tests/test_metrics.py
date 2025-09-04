import pytest
from unittest.mock import Mock
import numpy as np
from QuakeLiveInterface.metrics import PerformanceTracker

# Mock classes to simulate the game state
class MockPlayer:
    def __init__(self, health=100, armor=100, is_alive=True, position={'x': 0, 'y': 0, 'z': 0}, steam_id="agent_id"):
        self.health = health
        self.armor = armor
        self.is_alive = is_alive
        self.position = position
        self.steam_id = steam_id

class MockGameState:
    def __init__(self, agent, opponents):
        self._agent = agent
        self._opponents = opponents

    def get_agent(self):
        return self._agent

    def get_opponents(self):
        return self._opponents

@pytest.fixture
def tracker():
    """Returns a PerformanceTracker instance."""
    return PerformanceTracker()

def test_reset(tracker):
    """Tests if the tracker resets its metrics correctly."""
    tracker.damage_dealt = 10
    tracker.kills = 1
    tracker.reset()
    assert tracker.damage_dealt == 0
    assert tracker.kills == 0

def test_log_step_damage_taken(tracker):
    """Tests logging damage taken."""
    agent1 = MockPlayer(health=100, armor=50)
    agent2 = MockPlayer(health=80, armor=40)
    state1 = MockGameState(agent=agent1, opponents=[])
    state2 = MockGameState(agent=agent2, opponents=[])

    tracker.log_step(state1, {})
    tracker.log_step(state2, {})

    assert tracker.damage_taken == 30 # 20 health + 10 armor

def test_log_step_damage_dealt_and_kills(tracker):
    """Tests logging damage dealt and kills."""
    agent = MockPlayer()
    opponent1_s1 = MockPlayer(health=100, steam_id="opp1")
    opponent1_s2 = MockPlayer(health=50, steam_id="opp1")
    opponent2_s1 = MockPlayer(health=100, is_alive=True, steam_id="opp2")
    opponent2_s2 = MockPlayer(health=0, is_alive=False, steam_id="opp2")

    state1 = MockGameState(agent=agent, opponents=[opponent1_s1, opponent2_s1])
    state2 = MockGameState(agent=agent, opponents=[opponent1_s2, opponent2_s2])

    tracker.log_step(state1, {})
    tracker.log_step(state2, {})

    assert tracker.damage_dealt == 150 # 50 + 100
    assert tracker.kills == 1
    assert tracker.successful_hits == 2

def test_log_step_death(tracker):
    """Tests logging agent death."""
    agent1 = MockPlayer(is_alive=True)
    agent2 = MockPlayer(is_alive=False)
    state1 = MockGameState(agent=agent1, opponents=[])
    state2 = MockGameState(agent=agent2, opponents=[])

    tracker.log_step(state1, {})
    tracker.log_step(state2, {})

    assert tracker.deaths == 1

def test_log_step_item_collection(tracker):
    """Tests logging item collection."""
    agent1 = MockPlayer(health=50, armor=25)
    agent2 = MockPlayer(health=100, armor=75)
    state1 = MockGameState(agent=agent1, opponents=[])
    state2 = MockGameState(agent=agent2, opponents=[])

    tracker.log_step(state1, {})
    tracker.log_step(state2, {})

    assert tracker.items_collected.get("Health") == 1
    assert tracker.items_collected.get("Armor") == 1

def test_log_step_shots_fired(tracker):
    """Tests logging shots fired."""
    agent = MockPlayer()
    state1 = MockGameState(agent=agent, opponents=[])
    state2 = MockGameState(agent=agent, opponents=[])

    tracker.log_step(state1, {'attack': 1})
    tracker.log_step(state2, {'attack': 0})
    tracker.log_step(state2, {'attack': 1})

    assert tracker.shots_fired == 2

def test_log_step_movement(tracker):
    """Tests logging movement."""
    agent1 = MockPlayer(position={'x': 0, 'y': 0, 'z': 0})
    agent2 = MockPlayer(position={'x': 3, 'y': 4, 'z': 0}) # distance of 5
    state1 = MockGameState(agent=agent1, opponents=[])
    state2 = MockGameState(agent=agent2, opponents=[])

    tracker.log_step(state1, {})
    tracker.log_step(state2, {})

    assert tracker.total_distance_traveled == 5.0

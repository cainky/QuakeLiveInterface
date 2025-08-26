import pytest
import json
from QuakeLiveInterface.state import GameState, Player, Weapon, Item

@pytest.fixture
def sample_redis_data():
    """Provides a sample JSON payload similar to what's received from Redis."""
    return json.dumps({
        "agent": {
            "steam_id": "76561197960265728",
            "name": "Agent",
            "health": 100,
            "armor": 50,
            "position": {"x": 10, "y": 20, "z": 30},
            "velocity": {"x": 1, "y": 2, "z": 3},
            "is_alive": True,
            "weapons": [{"name": "Gauntlet", "ammo": 0}, {"name": "Machinegun", "ammo": 100}],
            "selected_weapon": {"name": "Machinegun", "ammo": 100}
        },
        "opponents": [
            {
                "steam_id": "76561197960265729",
                "name": "Opponent1",
                "health": 80,
                "armor": 25,
                "position": {"x": 100, "y": 200, "z": 300},
                "velocity": {"x": 4, "y": 5, "z": 6},
                "is_alive": True,
                "weapons": [{"name": "Gauntlet", "ammo": 0}],
                "selected_weapon": {"name": "Gauntlet", "ammo": 0}
            }
        ],
        "items": [
            {
                "name": "Mega Health",
                "position": {"x": 50, "y": 50, "z": 50},
                "is_available": True,
                "spawn_time": -1
            }
        ],
        "game_in_progress": True,
        "game_type": "duel"
    })

def test_game_state_update(sample_redis_data):
    """Tests that the GameState object is correctly updated from Redis data."""
    gs = GameState()
    gs.update_from_redis(sample_redis_data)

    # Test agent state
    agent = gs.get_agent()
    assert isinstance(agent, Player)
    assert agent.name == "Agent"
    assert agent.health == 100
    assert len(agent.weapons) == 2
    assert agent.selected_weapon.name == "Machinegun"

    # Test opponent state
    opponents = gs.get_opponents()
    assert len(opponents) == 1
    assert isinstance(opponents[0], Player)
    assert opponents[0].name == "Opponent1"

    # Test item state
    items = gs.get_items()
    assert len(items) == 1
    assert isinstance(items[0], Item)
    assert items[0].name == "Mega Health"
    assert items[0].is_available

    # Test game state
    assert gs.game_in_progress
    assert gs.game_type == "duel"

def test_empty_game_state():
    """Tests the GameState with empty or missing data."""
    gs = GameState()
    gs.update_from_redis(json.dumps({}))

    assert gs.get_agent() is None
    assert len(gs.get_opponents()) == 0
    assert len(gs.get_items()) == 0
    assert not gs.game_in_progress
    assert gs.game_type is None

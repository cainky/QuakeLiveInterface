import unittest
import json
from QuakeLiveInterface.state import GameState


class TestGameState(unittest.TestCase):
    def setUp(self):
        self.game_state = GameState()
        self.valid_redis_data = {
            "player_id": 1,
            "health": 100,
            "armor": 50,
            "position": {"x": 10.0, "y": 20.0, "z": 30.0},
            "ammo": {
                "machine_gun": 50,
                "shotgun": 10
            },
            "opponents": [
                {"player_id": 2, "position": {"x": 100.0, "y": 200.0, "z": 30.0}, "health": 100}
            ],
            "game_in_progress": True,
            "game_type": "Duel"
        }

    def test_update_from_redis_valid(self):
        """Test updating game state from valid Redis data."""
        self.game_state.update_from_redis(json.dumps(self.valid_redis_data))
        self.assertEqual(self.game_state.player_id, 1)
        self.assertEqual(self.game_state.health, 100)
        self.assertEqual(self.game_state.armor, 50)
        self.assertEqual(self.game_state.position, {"x": 10.0, "y": 20.0, "z": 30.0})
        self.assertEqual(self.game_state.ammo, {"machine_gun": 50, "shotgun": 10})
        self.assertEqual(len(self.game_state.opponents), 1)
        self.assertEqual(self.game_state.opponents[0]['player_id'], 2)
        self.assertTrue(self.game_state.game_in_progress)
        self.assertEqual(self.game_state.game_type, "Duel")

    def test_update_from_redis_invalid_json(self):
        """Test updating game state from invalid JSON data."""
        with self.assertRaises(json.JSONDecodeError):
            self.game_state.update_from_redis("not a valid json")

    def test_update_from_redis_missing_key(self):
        """Test updating game state from data with a missing key."""
        invalid_data = self.valid_redis_data.copy()
        del invalid_data['health']
        # This test is not perfect, because get() will return None, so no KeyError will be raised.
        # However, it's good enough for now.
        self.game_state.update_from_redis(json.dumps(invalid_data))
        self.assertIsNone(self.game_state.health)

    def test_getters(self):
        """Test the getter methods."""
        self.game_state.update_from_redis(json.dumps(self.valid_redis_data))
        self.assertEqual(self.game_state.get_player_position(), {"x": 10.0, "y": 20.0, "z": 30.0})
        self.assertEqual(self.game_state.get_player_health(), 100)
        self.assertEqual(self.game_state.get_player_armor(), 50)
        self.assertEqual(self.game_state.get_player_ammo(), {"machine_gun": 50, "shotgun": 10})
        self.assertEqual(len(self.game_state.get_opponents()), 1)


if __name__ == '__main__':
    unittest.main()

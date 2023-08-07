import unittest
from QuakeLiveInterface.state import GameState

class GameStateTest(unittest.TestCase):
    def setUp(self):
        self.game_state = GameState()

    def test_get_player_position(self):
        player_id = 1
        position = self.game_state.get_player_position(player_id)
        # Assert that the position is None since no game state has been updated yet
        self.assertIsNone(position)

    # Add more test cases for other methods...

if __name__ == "__main__":
    unittest.main()

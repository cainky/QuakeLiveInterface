import unittest
from unittest.mock import patch, MagicMock
from QuakeLiveInterface.client import QuakeLiveClient
import json


class TestQuakeLiveClient(unittest.TestCase):
    @patch('QuakeLiveInterface.client.RedisConnection')
    @patch('QuakeLiveInterface.client.GameState')
    def setUp(self, mock_game_state, mock_redis_connection):
        self.mock_redis_connection_instance = MagicMock()
        mock_redis_connection.return_value = self.mock_redis_connection_instance
        self.mock_game_state_instance = MagicMock()
        mock_game_state.return_value = self.mock_game_state_instance
        self.client = QuakeLiveClient()

    def test_init(self):
        """Test client initialization."""
        self.mock_redis_connection_instance.subscribe.assert_called_once_with('ql:game:state')
        self.assertIsNotNone(self.client)

    def test_update_game_state_with_message(self):
        """Test updating game state when a message is received."""
        redis_message = '{"health": 100}'
        self.mock_redis_connection_instance.get_message.return_value = redis_message
        result = self.client.update_game_state()
        self.mock_redis_connection_instance.get_message.assert_called_once()
        self.mock_game_state_instance.update_from_redis.assert_called_once_with(redis_message)
        self.assertTrue(result)

    def test_update_game_state_no_message(self):
        """Test updating game state when no message is received."""
        self.mock_redis_connection_instance.get_message.return_value = None
        result = self.client.update_game_state()
        self.mock_redis_connection_instance.get_message.assert_called_once()
        self.mock_game_state_instance.update_from_redis.assert_not_called()
        self.assertFalse(result)

    def test_send_command(self):
        """Test sending a command."""
        command = 'move'
        args = {'forward': 1, 'right': 0, 'up': 0}
        expected_payload = {'command': command}
        expected_payload.update(args)
        self.client.send_command(command, args)
        self.mock_redis_connection_instance.publish.assert_called_once_with(
            'ql:agent:command', json.dumps(expected_payload)
        )

    def test_move_command(self):
        """Test the move command."""
        with patch.object(self.client, 'send_command') as mock_send_command:
            self.client.move(1, 0, 1)
            mock_send_command.assert_called_once_with('move', {'forward': 1, 'right': 0, 'up': 1})

    def test_get_game_state(self):
        """Test getting the game state."""
        state = self.client.get_game_state()
        self.assertEqual(state, self.mock_game_state_instance)


if __name__ == '__main__':
    unittest.main()

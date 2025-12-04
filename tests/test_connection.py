import unittest
from unittest.mock import patch, MagicMock
from QuakeLiveInterface.connection import RedisConnection
import redis


class TestRedisConnection(unittest.TestCase):
    @patch('redis.Redis')
    def test_init_success(self, mock_redis):
        """Test successful Redis connection initialization."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        conn = RedisConnection()
        # Check that Redis was called with expected parameters (including timeouts)
        mock_redis.assert_called_once_with(
            host='localhost', port=6379, db=0, decode_responses=True,
            socket_connect_timeout=5.0, socket_timeout=5.0
        )
        mock_redis_instance.ping.assert_called_once()
        self.assertIsNotNone(conn)

    @patch('redis.Redis')
    def test_init_failure(self, mock_redis):
        """Test Redis connection initialization failure."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.side_effect = redis.exceptions.ConnectionError
        mock_redis.return_value = mock_redis_instance
        with self.assertRaises(redis.exceptions.ConnectionError):
            RedisConnection()

    @patch('redis.Redis')
    def test_publish(self, mock_redis):
        """Test publishing a message."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        conn = RedisConnection()
        conn.publish('test_channel', 'test_message')
        mock_redis_instance.publish.assert_called_once_with('test_channel', 'test_message')

    @patch('redis.Redis')
    def test_subscribe(self, mock_redis):
        """Test subscribing to a channel."""
        mock_redis_instance = MagicMock()
        mock_pubsub = MagicMock()
        mock_redis_instance.pubsub.return_value = mock_pubsub
        mock_redis.return_value = mock_redis_instance
        conn = RedisConnection()
        pubsub = conn.subscribe('test_channel')
        mock_redis_instance.pubsub.assert_called_once()
        mock_pubsub.subscribe.assert_called_once_with('test_channel')
        self.assertEqual(pubsub, mock_pubsub)

    @patch('redis.Redis')
    def test_get_message(self, mock_redis):
        """Test getting a message from a subscribed channel.
        The new implementation drains the queue and returns only the latest message.
        """
        mock_redis_instance = MagicMock()
        mock_pubsub = MagicMock()
        # First call returns a message, subsequent calls return None (queue drained)
        mock_pubsub.get_message.side_effect = [
            {'channel': 'test_channel', 'data': 'test_data'},
            None  # Queue is empty after first message
        ]
        mock_redis.return_value = mock_redis_instance
        conn = RedisConnection()
        message = conn.get_message(mock_pubsub)
        self.assertEqual(message, 'test_data')

    @patch('redis.Redis')
    def test_get_message_returns_latest(self, mock_redis):
        """Test that get_message returns the latest message when multiple are queued."""
        mock_redis_instance = MagicMock()
        mock_pubsub = MagicMock()
        # Multiple messages in queue - should return the last one
        mock_pubsub.get_message.side_effect = [
            {'channel': 'test_channel', 'data': 'old_message'},
            {'channel': 'test_channel', 'data': 'newer_message'},
            {'channel': 'test_channel', 'data': 'latest_message'},
            None  # Queue is now empty
        ]
        mock_redis.return_value = mock_redis_instance
        conn = RedisConnection()
        message = conn.get_message(mock_pubsub)
        self.assertEqual(message, 'latest_message')

    @patch('redis.Redis')
    def test_get_message_no_message(self, mock_redis):
        """Test getting no message from a subscribed channel."""
        mock_redis_instance = MagicMock()
        mock_pubsub = MagicMock()
        mock_pubsub.get_message.return_value = None
        mock_redis.return_value = mock_redis_instance
        conn = RedisConnection()
        message = conn.get_message(mock_pubsub)
        self.assertIsNone(message)


if __name__ == '__main__':
    unittest.main()

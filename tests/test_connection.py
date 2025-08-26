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
        mock_redis.assert_called_once_with(host='localhost', port=6379, db=0, decode_responses=True)
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
        """Test getting a message from a subscribed channel."""
        mock_redis_instance = MagicMock()
        mock_pubsub = MagicMock()
        mock_pubsub.get_message.return_value = {'channel': b'test_channel', 'data': b'test_data'}
        mock_redis.return_value = mock_redis_instance
        conn = RedisConnection()
        message = conn.get_message(mock_pubsub)
        mock_pubsub.get_message.assert_called_once_with(ignore_subscribe_messages=True, timeout=1.0)
        self.assertEqual(message, b'test_data')

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

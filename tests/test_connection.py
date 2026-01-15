import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from QuakeLiveInterface.connection import RedisConnection, RobustPubSub
import redis


class TestRedisConnection(unittest.TestCase):
    @patch('QuakeLiveInterface.connection.redis.ConnectionPool')
    @patch('QuakeLiveInterface.connection.redis.Redis')
    def test_init_success(self, mock_redis_class, mock_pool_class):
        """Test successful Redis connection initialization."""
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool
        mock_redis_instance = MagicMock()
        mock_redis_class.return_value = mock_redis_instance

        conn = RedisConnection()

        # Verify connection pool was created with expected parameters
        mock_pool_class.assert_called_once()
        call_kwargs = mock_pool_class.call_args[1]
        self.assertEqual(call_kwargs['host'], 'localhost')
        self.assertEqual(call_kwargs['port'], 6379)
        self.assertEqual(call_kwargs['db'], 0)
        self.assertTrue(call_kwargs['decode_responses'])

        # Verify Redis client was created with the pool
        mock_redis_class.assert_called_with(connection_pool=mock_pool)

        # Verify ping was called to test connection
        mock_redis_instance.ping.assert_called()
        self.assertIsNotNone(conn)

        conn.close()

    @patch('QuakeLiveInterface.connection.redis.ConnectionPool')
    @patch('QuakeLiveInterface.connection.redis.Redis')
    def test_init_failure(self, mock_redis_class, mock_pool_class):
        """Test Redis connection initialization failure."""
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.side_effect = redis.exceptions.ConnectionError
        mock_redis_class.return_value = mock_redis_instance

        with self.assertRaises(redis.exceptions.ConnectionError):
            RedisConnection(max_retries=1, initial_retry_delay=0.01)

    @patch('QuakeLiveInterface.connection.redis.ConnectionPool')
    @patch('QuakeLiveInterface.connection.redis.Redis')
    def test_publish(self, mock_redis_class, mock_pool_class):
        """Test publishing a message."""
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool
        mock_redis_instance = MagicMock()
        mock_redis_class.return_value = mock_redis_instance

        conn = RedisConnection()
        result = conn.publish('test_channel', 'test_message')

        mock_redis_instance.publish.assert_called_with('test_channel', 'test_message')
        self.assertTrue(result)

        conn.close()

    @patch('QuakeLiveInterface.connection.redis.ConnectionPool')
    @patch('QuakeLiveInterface.connection.redis.Redis')
    def test_subscribe(self, mock_redis_class, mock_pool_class):
        """Test subscribing to a channel."""
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool
        mock_redis_instance = MagicMock()
        mock_pubsub = MagicMock()
        mock_redis_instance.pubsub.return_value = mock_pubsub
        mock_redis_class.return_value = mock_redis_instance

        conn = RedisConnection()
        pubsub = conn.subscribe('test_channel')

        # Should return a RobustPubSub object, not the raw pubsub
        self.assertIsInstance(pubsub, RobustPubSub)
        mock_redis_instance.pubsub.assert_called_once()
        mock_pubsub.subscribe.assert_called_once_with('test_channel')

        conn.close()

    @patch('QuakeLiveInterface.connection.redis.ConnectionPool')
    @patch('QuakeLiveInterface.connection.redis.Redis')
    def test_get_message(self, mock_redis_class, mock_pool_class):
        """Test getting a message from a subscribed channel."""
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool
        mock_redis_instance = MagicMock()
        mock_pubsub = MagicMock()
        # First call returns a message, second returns None (queue drained)
        mock_pubsub.get_message.side_effect = [
            {'type': 'message', 'channel': 'test_channel', 'data': 'test_data'},
            None
        ]
        mock_redis_instance.pubsub.return_value = mock_pubsub
        mock_redis_class.return_value = mock_redis_instance

        conn = RedisConnection()
        robust_pubsub = conn.subscribe('test_channel')
        message = conn.get_message(robust_pubsub)

        self.assertEqual(message, 'test_data')

        conn.close()

    @patch('QuakeLiveInterface.connection.redis.ConnectionPool')
    @patch('QuakeLiveInterface.connection.redis.Redis')
    def test_get_message_returns_latest(self, mock_redis_class, mock_pool_class):
        """Test that get_message returns the latest message when multiple are queued."""
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool
        mock_redis_instance = MagicMock()
        mock_pubsub = MagicMock()
        # Multiple messages in queue - should return the last one
        mock_pubsub.get_message.side_effect = [
            {'type': 'message', 'channel': 'test_channel', 'data': 'old_message'},
            {'type': 'message', 'channel': 'test_channel', 'data': 'newer_message'},
            {'type': 'message', 'channel': 'test_channel', 'data': 'latest_message'},
            None
        ]
        mock_redis_instance.pubsub.return_value = mock_pubsub
        mock_redis_class.return_value = mock_redis_instance

        conn = RedisConnection()
        robust_pubsub = conn.subscribe('test_channel')
        message = conn.get_message(robust_pubsub)

        self.assertEqual(message, 'latest_message')

        conn.close()

    @patch('QuakeLiveInterface.connection.redis.ConnectionPool')
    @patch('QuakeLiveInterface.connection.redis.Redis')
    def test_get_message_no_message(self, mock_redis_class, mock_pool_class):
        """Test getting no message from a subscribed channel."""
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool
        mock_redis_instance = MagicMock()
        mock_pubsub = MagicMock()
        mock_pubsub.get_message.return_value = None
        mock_redis_instance.pubsub.return_value = mock_pubsub
        mock_redis_class.return_value = mock_redis_instance

        conn = RedisConnection()
        robust_pubsub = conn.subscribe('test_channel')
        message = conn.get_message(robust_pubsub)

        self.assertIsNone(message)

        conn.close()


if __name__ == '__main__':
    unittest.main()

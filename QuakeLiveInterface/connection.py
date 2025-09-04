import redis
import logging

logger = logging.getLogger(__name__)


class RedisConnection:
    """
    A class to manage the connection to a Redis server.
    This is used to communicate with the minqlx plugin.
    """

    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        """
        Initializes the Redis connection.
        Args:
            host: The Redis server host.
            port: The Redis server port.
            db: The Redis database to use.
        """
        try:
            self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            self.redis.ping()
            logger.info(f"Successfully connected to Redis at {host}:{port}")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Could not connect to Redis at {host}:{port}: {e}")
            raise

    def publish(self, channel: str, message: str):
        """
        Publishes a message to a Redis channel.
        Args:
            channel: The channel to publish to.
            message: The message to publish.
        """
        try:
            self.redis.publish(channel, message)
            logger.debug(f"Published message to {channel}: {message}")
        except redis.exceptions.RedisError as e:
            logger.error(f"Error publishing to {channel}: {e}")
            raise

    def subscribe(self, channel: str):
        """
        Subscribes to a Redis channel.
        Returns a pubsub object that can be used to listen for messages.
        """
        try:
            pubsub = self.redis.pubsub()
            pubsub.subscribe(channel)
            logger.info(f"Subscribed to Redis channel: {channel}")
            return pubsub
        except redis.exceptions.RedisError as e:
            logger.error(f"Error subscribing to {channel}: {e}")
            raise

    def get_message(self, pubsub, timeout: float = 1.0):
        """
        Gets a message from a subscribed channel.
        Args:
            pubsub: The pubsub object returned by subscribe().
            timeout: The time to wait for a message.
        Returns:
            The message, or None if no message is received within the timeout.
        """
        try:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout)
            if message:
                logger.debug(f"Received message from channel {message['channel']}: {message['data']}")
                return message['data']
            return None
        except redis.exceptions.RedisError as e:
            logger.error(f"Error getting message: {e}")
            raise

    def close(self):
        """
        Closes the Redis connection.
        """
        try:
            self.redis.close()
            logger.info("Redis connection closed.")
        except redis.exceptions.RedisError as e:
            logger.error(f"Error closing Redis connection: {e}")
            raise

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
        Gets the latest message from a subscribed channel, discarding stale ones.

        This drains the message queue and returns only the newest message,
        ensuring the client always reacts to the current game state rather
        than processing outdated frames.

        Args:
            pubsub: The pubsub object returned by subscribe().
            timeout: The time to wait for the first message if queue is empty.
        Returns:
            The most recent message, or None if no message is received within the timeout.
        """
        try:
            latest_message = None
            messages_discarded = 0

            # First, try to get a message with timeout (blocks if queue empty)
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout)
            if message:
                latest_message = message['data']

                # Drain any remaining messages in the queue (non-blocking)
                while True:
                    message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0)
                    if message is None:
                        break
                    latest_message = message['data']
                    messages_discarded += 1

                if messages_discarded > 0:
                    logger.debug(f"Discarded {messages_discarded} stale messages, using latest")

            if latest_message:
                logger.debug(f"Returning latest message from queue")
                return latest_message
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

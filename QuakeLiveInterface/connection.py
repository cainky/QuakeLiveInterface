import redis
import logging
import time

logger = logging.getLogger(__name__)


class RedisConnection:
    """
    A class to manage the connection to a Redis server.
    This is used to communicate with the minqlx plugin.

    Features automatic reconnection on connection loss.
    """

    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0,
                 max_retries: int = 5, retry_delay: float = 1.0):
        """
        Initializes the Redis connection.
        Args:
            host: The Redis server host.
            port: The Redis server port.
            db: The Redis database to use.
            max_retries: Maximum reconnection attempts.
            retry_delay: Delay between reconnection attempts in seconds.
        """
        self.host = host
        self.port = port
        self.db = db
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.redis = None
        self._connect()

    def _connect(self):
        """Establish connection to Redis with retry logic."""
        for attempt in range(self.max_retries):
            try:
                self.redis = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    decode_responses=True,
                    socket_connect_timeout=5.0,
                    socket_timeout=5.0
                )
                self.redis.ping()
                logger.info(f"Successfully connected to Redis at {self.host}:{self.port}")
                return
            except redis.exceptions.ConnectionError as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Connection attempt {attempt + 1}/{self.max_retries} failed: {e}")
                    logger.info(f"Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Could not connect to Redis at {self.host}:{self.port} after {self.max_retries} attempts")
                    raise

    def reconnect(self):
        """Force a reconnection to Redis."""
        logger.info("Attempting to reconnect to Redis...")
        try:
            if self.redis:
                self.redis.close()
        except Exception:
            pass
        self._connect()

    def _ensure_connected(self):
        """Check connection and reconnect if necessary."""
        try:
            self.redis.ping()
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            logger.warning("Redis connection lost. Attempting reconnect...")
            self.reconnect()

    def publish(self, channel: str, message: str):
        """
        Publishes a message to a Redis channel.
        Automatically reconnects on connection failure.

        Args:
            channel: The channel to publish to.
            message: The message to publish.
        """
        try:
            self._ensure_connected()
            self.redis.publish(channel, message)
            logger.debug(f"Published message to {channel}: {message}")
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            logger.warning(f"Publish failed, attempting reconnect: {e}")
            self.reconnect()
            # Retry once after reconnect
            self.redis.publish(channel, message)
            logger.debug(f"Published message after reconnect to {channel}")
        except redis.exceptions.RedisError as e:
            logger.error(f"Error publishing to {channel}: {e}")
            raise

    def subscribe(self, channel: str):
        """
        Subscribes to a Redis channel.
        Returns a pubsub object that can be used to listen for messages.
        Automatically reconnects on connection failure.
        """
        try:
            self._ensure_connected()
            pubsub = self.redis.pubsub()
            pubsub.subscribe(channel)
            logger.info(f"Subscribed to Redis channel: {channel}")
            return pubsub
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            logger.warning(f"Subscribe failed, attempting reconnect: {e}")
            self.reconnect()
            pubsub = self.redis.pubsub()
            pubsub.subscribe(channel)
            logger.info(f"Subscribed after reconnect to: {channel}")
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

    def get(self, key: str):
        """
        Gets a value from Redis by key.

        Args:
            key: The key to retrieve.
        Returns:
            The value, or None if key doesn't exist.
        """
        try:
            self._ensure_connected()
            return self.redis.get(key)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            logger.warning(f"Get failed, attempting reconnect: {e}")
            self.reconnect()
            return self.redis.get(key)
        except redis.exceptions.RedisError as e:
            logger.error(f"Error getting key {key}: {e}")
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

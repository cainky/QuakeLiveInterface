import redis
import logging
import time
import threading
from typing import Optional, Callable
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class RedisConnection:
    """
    A robust Redis connection manager with:
    - Connection pooling for efficient resource usage
    - Exponential backoff for reconnection attempts
    - Shorter timeouts optimized for game loop (60Hz)
    - Background health monitoring
    - Auto-recovering pubsub subscriptions
    """

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        db: int = 0,
        max_retries: int = 10,
        initial_retry_delay: float = 0.1,
        max_retry_delay: float = 5.0,
        socket_timeout: float = 0.5,
        socket_connect_timeout: float = 2.0,
        health_check_interval: float = 5.0,
        max_connections: int = 10,
    ):
        """
        Initialize the Redis connection with robust settings.

        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number
            max_retries: Maximum reconnection attempts before giving up
            initial_retry_delay: Initial delay between retries (seconds)
            max_retry_delay: Maximum delay between retries (exponential backoff cap)
            socket_timeout: Timeout for socket operations (keep short for game loop!)
            socket_connect_timeout: Timeout for establishing connection
            health_check_interval: How often to check connection health (seconds)
            max_connections: Maximum connections in pool
        """
        self.host = host
        self.port = port
        self.db = db
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.health_check_interval = health_check_interval

        # Connection pool for efficient resource usage
        self._pool = redis.ConnectionPool(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
            socket_connect_timeout=socket_connect_timeout,
            socket_timeout=socket_timeout,
            max_connections=max_connections,
            health_check_interval=30,  # Redis-py's built-in health check
        )

        self.redis: Optional[redis.Redis] = None
        self._lock = threading.RLock()
        self._healthy = False
        self._last_error: Optional[str] = None
        self._consecutive_failures = 0
        self._max_consecutive_failures = 5  # Circuit breaker threshold

        # Active pubsub subscriptions for auto-recovery
        self._pubsub_subscriptions: dict[str, 'RobustPubSub'] = {}

        # Health monitor thread
        self._health_monitor_running = False
        self._health_monitor_thread: Optional[threading.Thread] = None

        self._connect()
        self._start_health_monitor()

    def _connect(self):
        """Establish connection to Redis with exponential backoff."""
        retry_delay = self.initial_retry_delay

        for attempt in range(self.max_retries):
            try:
                self.redis = redis.Redis(connection_pool=self._pool)
                self.redis.ping()
                self._healthy = True
                self._consecutive_failures = 0
                self._last_error = None
                logger.info(f"Connected to Redis at {self.host}:{self.port}")
                return
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
                self._last_error = str(e)
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Connection attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {retry_delay:.2f}s..."
                    )
                    time.sleep(retry_delay)
                    # Exponential backoff with cap
                    retry_delay = min(retry_delay * 2, self.max_retry_delay)
                else:
                    logger.error(
                        f"Could not connect to Redis at {self.host}:{self.port} "
                        f"after {self.max_retries} attempts: {e}"
                    )
                    self._healthy = False
                    raise

    def _start_health_monitor(self):
        """Start background thread that monitors connection health."""
        if self._health_monitor_running:
            return

        self._health_monitor_running = True
        self._health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            daemon=True,
            name="redis-health-monitor"
        )
        self._health_monitor_thread.start()
        logger.debug("Redis health monitor started")

    def _health_monitor_loop(self):
        """Background loop that checks connection health and reconnects if needed."""
        while self._health_monitor_running:
            try:
                time.sleep(self.health_check_interval)

                if not self._health_monitor_running:
                    break

                with self._lock:
                    if self.redis is None:
                        self._attempt_reconnect()
                        continue

                    try:
                        self.redis.ping()
                        if not self._healthy:
                            logger.info("Redis connection restored")
                        self._healthy = True
                        self._consecutive_failures = 0
                    except Exception as e:
                        self._healthy = False
                        self._last_error = str(e)
                        logger.warning(f"Health check failed: {e}")
                        self._attempt_reconnect()

            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    def _attempt_reconnect(self):
        """Attempt to reconnect with circuit breaker pattern."""
        self._consecutive_failures += 1

        if self._consecutive_failures > self._max_consecutive_failures:
            # Circuit breaker: Don't spam reconnection attempts
            logger.warning(
                f"Circuit breaker open: {self._consecutive_failures} consecutive failures. "
                f"Waiting before retry..."
            )
            time.sleep(self.max_retry_delay)
            self._consecutive_failures = 0  # Reset and try again

        try:
            # Reset the connection pool to clear any stale connections
            self._pool.disconnect()
            self._connect()

            # Reconnect any active pubsub subscriptions
            for channel, pubsub in list(self._pubsub_subscriptions.items()):
                try:
                    pubsub._reconnect()
                    logger.info(f"Resubscribed to channel: {channel}")
                except Exception as e:
                    logger.error(f"Failed to resubscribe to {channel}: {e}")

        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            self._healthy = False

    def reconnect(self):
        """Force a reconnection to Redis."""
        logger.info("Manual reconnection requested")
        with self._lock:
            try:
                if self.redis:
                    self.redis.close()
            except Exception:
                pass

            self._pool.disconnect()
            self._connect()

    @property
    def is_healthy(self) -> bool:
        """Check if the connection is healthy."""
        return self._healthy

    @property
    def last_error(self) -> Optional[str]:
        """Get the last error message."""
        return self._last_error

    def _ensure_connected(self) -> bool:
        """
        Quick health check - doesn't ping every time (expensive).
        Returns True if likely connected, False otherwise.
        """
        if not self._healthy or self.redis is None:
            try:
                self._attempt_reconnect()
            except Exception:
                return False
        return self._healthy

    def publish(self, channel: str, message: str) -> bool:
        """
        Publish a message to a Redis channel.
        Returns True on success, False on failure.

        Args:
            channel: The channel to publish to
            message: The message to publish

        Returns:
            bool: True if publish succeeded, False otherwise
        """
        if not self._ensure_connected():
            logger.warning(f"Cannot publish to {channel}: not connected")
            return False

        try:
            self.redis.publish(channel, message)
            logger.debug(f"Published to {channel}")
            return True
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError,
                ConnectionResetError, BrokenPipeError, OSError) as e:
            self._healthy = False
            self._last_error = str(e)
            logger.warning(f"Publish failed: {e}")

            # Try once more after reconnect
            try:
                self._attempt_reconnect()
                if self._healthy:
                    self.redis.publish(channel, message)
                    logger.debug(f"Published after reconnect to {channel}")
                    return True
            except Exception as retry_e:
                logger.error(f"Publish retry failed: {retry_e}")

            return False
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error publishing to {channel}: {e}")
            return False

    def subscribe(self, channel: str) -> 'RobustPubSub':
        """
        Subscribe to a Redis channel with auto-reconnection support.

        Returns a RobustPubSub object that automatically handles reconnection.
        """
        if not self._ensure_connected():
            raise redis.exceptions.ConnectionError("Not connected to Redis")

        pubsub = RobustPubSub(self, channel)
        self._pubsub_subscriptions[channel] = pubsub
        return pubsub

    def unsubscribe(self, channel: str):
        """Unsubscribe from a channel and remove from tracking."""
        if channel in self._pubsub_subscriptions:
            try:
                self._pubsub_subscriptions[channel].close()
            except Exception:
                pass
            del self._pubsub_subscriptions[channel]

    def get_message(self, pubsub: 'RobustPubSub', timeout: float = 0.1) -> Optional[str]:
        """
        Get the latest message from a subscription, discarding stale ones.

        Args:
            pubsub: The RobustPubSub object from subscribe()
            timeout: Time to wait for a message if queue is empty

        Returns:
            The most recent message data, or None if no message available
        """
        return pubsub.get_latest_message(timeout)

    def get(self, key: str) -> Optional[str]:
        """
        Get a value from Redis by key.

        Returns None if key doesn't exist or on connection failure.
        """
        if not self._ensure_connected():
            return None

        try:
            return self.redis.get(key)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError,
                ConnectionResetError, BrokenPipeError, OSError) as e:
            self._healthy = False
            self._last_error = str(e)
            logger.warning(f"Get failed: {e}")

            try:
                self._attempt_reconnect()
                if self._healthy:
                    return self.redis.get(key)
            except Exception:
                pass
            return None
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error getting {key}: {e}")
            return None

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """
        Set a value in Redis.

        Args:
            key: The key to set
            value: The value to store
            ex: Optional expiration time in seconds

        Returns:
            bool: True if set succeeded, False otherwise
        """
        if not self._ensure_connected():
            return False

        try:
            self.redis.set(key, value, ex=ex)
            return True
        except Exception as e:
            logger.warning(f"Set failed for {key}: {e}")
            return False

    def close(self, timeout: float = 2.0):
        """
        Close the Redis connection and stop health monitoring.

        Args:
            timeout: Maximum time to wait for threads to stop (seconds)
        """
        logger.info("Closing Redis connection...")

        # Signal health monitor to stop
        self._health_monitor_running = False

        # Wait for health monitor thread to finish
        if self._health_monitor_thread and self._health_monitor_thread.is_alive():
            logger.debug("Waiting for health monitor thread to stop...")
            self._health_monitor_thread.join(timeout=timeout)
            if self._health_monitor_thread.is_alive():
                logger.warning("Health monitor thread did not stop in time")

        # Close all pubsub subscriptions
        for channel, pubsub in list(self._pubsub_subscriptions.items()):
            try:
                logger.debug(f"Closing pubsub subscription: {channel}")
                pubsub.close()
            except Exception as e:
                logger.warning(f"Error closing pubsub {channel}: {e}")
        self._pubsub_subscriptions.clear()

        # Close connection pool
        try:
            self._pool.disconnect()
            logger.debug("Connection pool disconnected")
        except Exception as e:
            logger.warning(f"Error disconnecting pool: {e}")

        self._healthy = False
        logger.info("Redis connection closed")

    def __enter__(self):
        """Context manager entry - returns self."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup on exit."""
        self.close()
        return False  # Don't suppress exceptions


class RobustPubSub:
    """
    A robust pub/sub wrapper with automatic reconnection and message recovery.
    """

    def __init__(self, connection: RedisConnection, channel: str):
        self._connection = connection
        self._channel = channel
        self._pubsub: Optional[redis.client.PubSub] = None
        self._lock = threading.Lock()
        self._closed = False
        self._subscribe()

    def _subscribe(self):
        """Create pubsub and subscribe to channel."""
        with self._lock:
            if self._closed:
                return

            try:
                if self._pubsub:
                    try:
                        self._pubsub.close()
                    except Exception:
                        pass

                self._pubsub = self._connection.redis.pubsub()
                self._pubsub.subscribe(self._channel)
                logger.info(f"Subscribed to channel: {self._channel}")
            except Exception as e:
                logger.error(f"Failed to subscribe to {self._channel}: {e}")
                raise

    def _reconnect(self):
        """Reconnect the pubsub subscription."""
        self._subscribe()

    def get_latest_message(self, timeout: float = 0.1) -> Optional[str]:
        """
        Get the latest message, discarding any stale messages in the queue.

        Args:
            timeout: Time to wait for first message if queue is empty

        Returns:
            The most recent message data, or None if timeout/error
        """
        if self._closed:
            return None

        try:
            with self._lock:
                if self._pubsub is None:
                    return None

                latest_message = None
                messages_discarded = 0

                # Get first message with timeout
                message = self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=timeout
                )

                if message and message.get('type') == 'message':
                    latest_message = message['data']

                    # Drain queue (non-blocking)
                    while True:
                        msg = self._pubsub.get_message(
                            ignore_subscribe_messages=True,
                            timeout=0
                        )
                        if msg is None:
                            break
                        if msg.get('type') == 'message':
                            latest_message = msg['data']
                            messages_discarded += 1

                    if messages_discarded > 0:
                        logger.debug(f"Discarded {messages_discarded} stale messages")

                return latest_message

        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError,
                ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.warning(f"PubSub connection error: {e}")
            self._connection._healthy = False

            # Don't try to reconnect here - let the health monitor handle it
            return None
        except Exception as e:
            logger.error(f"PubSub error: {e}")
            return None

    def listen(self, timeout: float = 1.0):
        """
        Generator that yields messages with automatic reconnection.

        This is a robust replacement for pubsub.listen() that handles
        disconnections gracefully.

        Args:
            timeout: How long to wait for each message

        Yields:
            Message data strings
        """
        consecutive_errors = 0
        max_consecutive_errors = 10

        while not self._closed:
            try:
                message = self.get_latest_message(timeout)
                if message:
                    consecutive_errors = 0
                    yield message
                else:
                    # No message - check if we need to reconnect
                    if not self._connection.is_healthy:
                        time.sleep(0.5)  # Wait before retry

            except Exception as e:
                consecutive_errors += 1
                logger.warning(f"Listen error ({consecutive_errors}): {e}")

                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many consecutive errors in listen()")
                    time.sleep(2.0)  # Longer wait before continuing
                    consecutive_errors = 0
                else:
                    time.sleep(0.1)

    def close(self):
        """Close the pubsub subscription."""
        self._closed = True
        with self._lock:
            if self._pubsub:
                try:
                    self._pubsub.unsubscribe(self._channel)
                    self._pubsub.close()
                except Exception:
                    pass
                self._pubsub = None


# Backwards compatibility: expose original interface
def create_connection(
    host: str = 'localhost',
    port: int = 6379,
    db: int = 0,
    **kwargs
) -> RedisConnection:
    """Create a robust Redis connection with sensible defaults."""
    return RedisConnection(host=host, port=port, db=db, **kwargs)

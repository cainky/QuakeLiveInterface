import socket
import time

from loguru import logger

logger.add(
    "quakelive_interface.log",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} [{level}] - {message}",
)


class ServerConnection:
    def __init__(self, host: str, port: int, sock=None):
        logger.info(f"Initializing connection to {host}:{port}")
        self.host = host
        self.port = port
        self.socket = sock or socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def listen(self, buffer_size=4096):
        """Listens for incoming data from the server."""
        try:
            data, _ = self.socket.recvfrom(buffer_size)
            return data
        except socket.error as e:
            logger.error(f"Error while listening: {e}")
            return None

    def set_timeout(self, timeout):
        self.socket.settimeout(timeout)

    def send_command(self, command: str):
        try:
            self.socket.sendto(command.encode(), (self.host, self.port))
            logger.info(f"Sent command: {command}")
        except socket.error as e:
            logger.error(f"Error sending command: {command}. Error: {e}")

    def reconnect(self, retries=3):
        for i in range(retries):
            try:
                self.socket.close()
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                return
            except socket.error as e:
                logger.error(f"Failed to reconnect, attempt {i+1}/{retries}: {e}")
                time.sleep(2)  # Wait before retrying

import logging
import socket
import time

logging.basicConfig(filename='quakelive_interface.log', level=logging.DEBUG, 
                    format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

class ServerConnection:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

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

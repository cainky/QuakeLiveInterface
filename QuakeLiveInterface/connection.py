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
        except Exception as e:
            logger.error(f"Error while listening: {e}")
            return None

    def set_timeout(self, timeout):
        self.socket.settimeout(timeout)
    
    def send_command(self, command: str):
        try:
            self.socket.sendto(command.encode(), (self.host, self.port))
            logger.info(f"Sent command: {command}")
        except Exception as e:
            logger.error(f"Error sending command: {command}. Error: {e}")
    
    def reconnect(self, retries=3):
        for i in range(retries):
            try:
                self.socket.close()
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                return
            except Exception as e:
                logger.error(f"Failed to reconnect, attempt {i+1}/{retries}: {e}")
                time.sleep(2)  # Wait before retrying


class CommandIssuer:
    def __init__(self, connection: ServerConnection):
        self.connection = connection
        self.command_queue = []
    
    def queue_command(self, command):
        self.command_queue.append(command)
    
    def issue_next_command(self):
        if self.command_queue:
            next_command = self.command_queue.pop(0)
            self.connection.send_command(next_command)

if __name__ == "__main__":
    # For basic testing purposes
    conn = ServerConnection('localhost', 27960)  # Example host and port
    issuer = CommandIssuer(conn)
    
    issuer.queue_command("sample_command")
    issuer.issue_next_command()

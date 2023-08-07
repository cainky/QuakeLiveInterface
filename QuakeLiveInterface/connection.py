# file: QuakeLiveInterface/connection.py

import socket

BUFFER_SIZE = 4096

class ServerConnection:
    def __init__(self, ip_address: str, port: int, rcon_password: str):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_address = (ip_address, port)
        self.rcon_password = rcon_password

    def connect(self):
        self.socket.connect(self.server_address)

    def disconnect(self):
        self.socket.close()

    def send_rcon_command(self, command: str):
        # the format for rcon commands is "rcon [password] [command]"
        rcon_command = f"rcon {self.rcon_password} {command}"
        data = rcon_command.encode()

        # Quake Live uses UDP, so we use sendto instead of send
        self.socket.sendto(data, self.server_address)

    def receive_response(self) -> str:
        # you might need to adjust the buffer size
        data = self.socket.recv(BUFFER_SIZE)
        return data.decode()

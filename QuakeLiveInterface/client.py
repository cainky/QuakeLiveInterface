import time
from QuakeLiveInterface.connection import ServerConnection
from QuakeLiveInterface.state import GameState

class QuakeLiveClient:
    def __init__(self, ip_address, port, rcon_password):
        self.connection = ServerConnection(ip_address, port, rcon_password)
        self.game_state = GameState()
    
    def send_command(self, command):
        self.connection.send_command(command)
        time.sleep(0.5)  # Giving some time for the server to process the command.
        self.update_game_state()

    def connect(self):
        self.connection.connect()

    def disconnect(self):
        self.connection.disconnect()

    def update_game_state(self):
        # get the latest data packet from the server
        data_packet = self.connection.receive_response()
        # update the game state
        self.game_state.update(data_packet)

    def get_player_position(self, player_id):
        return self.game_state.get_player_position(player_id)

    def get_item_location(self, item_id):
        return self.game_state.get_item_location(item_id)

    def send_command(self, command):
        self.connection.send_rcon_command(command)

from QuakeLiveInterface.connection import ServerConnection
from QuakeLiveInterface.state import GameState

class QuakeLiveClient:
    def __init__(self, ip_address, port):
        self.connection = ServerConnection(ip_address, port)
        self.game_state = GameState()

    def update_game_state(self):
        try:
            data_packet = self.connection.listen()
            if data_packet:
                self.game_state.update(data_packet)
        except Exception as e:
            raise RuntimeError("Error while updating game state") from e

    def get_player_position(self, player_id):
        try:
            return self.game_state.get_player_position(player_id)
        except Exception as e:
            raise RuntimeError("Error while retrieving player position") from e

    def get_item_location(self, item_id):
        try:
            return self.game_state.get_item_location(item_id)
        except Exception as e:
            raise RuntimeError("Error while retrieving item location") from e

    def send_command(self, command):
        try:
            self.connection.send_command(command)
        except Exception as e:
            raise RuntimeError("Error while sending command") from e

    # Movement commands:
    def move_forward(self):
        self.send_command("+forward")

    def move_backward(self):
        self.send_command("-forward")

    def move_left(self):
        self.send_command("+moveleft")

    def move_right(self):
        self.send_command("+moveright")

    def jump(self):
        self.send_command("+jump")

    def crouch(self):
        self.send_command("+crouch")

    # Combat commands:
    def shoot(self):
        self.send_command("+attack")

    def stop_shoot(self):
        self.send_command("-attack")

    def use_item(self):
        self.send_command("+useitem")

    def reload_weapon(self):
        self.send_command("+reload")

    def next_weapon(self):
        self.send_command("weapnext")

    def prev_weapon(self):
        self.send_command("weapprev")

    # Communication commands:
    def say(self, message):
        self.send_command(f"say {message}")

    def say_team(self, message):
        self.send_command(f"say_team {message}")

    def voice_chat(self, voice_command):
        self.send_command(f"voice_chat {voice_command}")

    # Miscellaneous:
    def toggle_console(self):
        self.send_command("toggleconsole")

    def screenshot(self):
        self.send_command("screenshot")

    def record_demo(self, demo_name):
        self.send_command(f"record {demo_name}")

    def stop_demo(self):
        self.send_command("stoprecord")

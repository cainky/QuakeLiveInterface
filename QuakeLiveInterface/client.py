import math
from QuakeLiveInterface.connection import ServerConnection
from QuakeLiveInterface.state import GameState
from QuakeLiveInterface.constants import WEAPONS

class QuakeLiveClient:
    def __init__(self, ip_address: str, port: int):
        self.connection = ServerConnection(ip_address, port)
        self.game_state = GameState()

    def update_game_state(self):
        try:
            data_packet = self.connection.listen()
            if data_packet:
                self.game_state.update(data_packet)
        except Exception as e:
            raise RuntimeError("Error while updating game state") from e
    
    def calculate_distance(self, pos1, pos2):
        return math.sqrt(sum((p1 - p2) ** 2 for p1, p2 in zip(pos1, pos2)))


    def get_item_location(self, item_id):
        try:
            return self.game_state.get_item_location(item_id)
        except Exception as e:
            raise RuntimeError("Error while retrieving item location") from e

    def send_command(self, command: str):
        try:
            self.connection.send_command(command)
        except Exception as e:
            raise RuntimeError("Error while sending command") from e

    def switch_weapon(self, weapon_id: int):
        if weapon_id in WEAPONS:
            self.send_command(WEAPONS[weapon_id])

    # Movement commands:
    def aim(self, pitch, yaw):
        self.send_command(f"+mlook;cl_pitchspeed {pitch};cl_yawspeed {yaw}")

    def move_forward(self):
        self.send_command("+forward")

    def move_backward(self):
        self.send_command("+back")

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
    def say(self, message: str):
        self.send_command(f"say {message}")

    def say_team(self, message: str):
        self.send_command(f"say_team {message}")

    # Miscellaneous:
    def toggle_console(self):
        self.send_command("toggleconsole")

    def screenshot(self):
        self.send_command("screenshot")

    def record_demo(self, demo_name):
        self.send_command(f"record {demo_name}")

    def stop_demo(self):
        self.send_command("stoprecord")

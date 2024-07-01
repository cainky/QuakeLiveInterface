import unittest
from unittest.mock import MagicMock
from QuakeLiveInterface.client import QuakeLiveClient


class QuakeLiveClientTest(unittest.TestCase):
    def setUp(self):
        self.client = QuakeLiveClient("127.0.0.1", 1234)
        if self.client.connection.socket:
            self.client.connection.socket.close()
        self.client.connection.socket = MagicMock()

    def send_command_test_helper(self, method, expected_command):
        method()
        self.assertEqual(
            self.client.connection.socket.sendto.call_args[0][0].decode(),
            expected_command,
        )

    def test_commands(self):
        commands = [
            (self.client.crouch, "+crouch"),
            (self.client.jump, "+jump"),
            (self.client.move_backward, "-forward"),
            (self.client.move_forward, "+forward"),
            (self.client.move_left, "+moveleft"),
            (self.client.move_right, "+moveright"),
            (self.client.next_weapon, "weapnext"),
            (self.client.prev_weapon, "weapprev"),
            (self.client.reload_weapon, "+reload"),
            (self.client.screenshot, "screenshot"),
            (self.client.shoot, "+attack"),
            (self.client.stop_demo, "stoprecord"),
            (self.client.stop_shoot, "-attack"),
            (self.client.toggle_console, "toggleconsole"),
            (self.client.use_item, "+useitem"),
        ]

        for method, command in commands:
            with self.subTest(method=method):
                self.send_command_test_helper(method, command)

    def test_record_demo(self):
        demo_name = "test_demo"
        self.send_command_test_helper(
            lambda: self.client.record_demo(demo_name), f"record {demo_name}"
        )

    def test_say(self):
        message = "Hello, world!"
        self.send_command_test_helper(
            lambda: self.client.say(message), f"say {message}"
        )

    def test_say_team(self):
        message = "Hello, team!"
        self.send_command_test_helper(
            lambda: self.client.say_team(message), f"say_team {message}"
        )

    def test_voice_chat(self):
        voice_command = "test_command"
        self.send_command_test_helper(
            lambda: self.client.voice_chat(voice_command), f"voice_chat {voice_command}"
        )


if __name__ == "__main__":
    unittest.main()

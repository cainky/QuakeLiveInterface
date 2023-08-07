import unittest
from unittest.mock import MagicMock
from QuakeLiveInterface.client import QuakeLiveClient

class QuakeLiveClientTest(unittest.TestCase):
    def setUp(self):
        self.client = QuakeLiveClient("127.0.0.1", 1234)
        self.client.connection.socket.sendto = MagicMock()

    def test_crouch(self):
        self.client.crouch()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "+crouch")

    def test_jump(self):
        self.client.jump()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "+jump")

    def test_move_backward(self):
        self.client.move_backward()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "-forward")

    def test_move_forward(self):
        self.client.move_forward()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "+forward")

    def test_move_left(self):
        self.client.move_left()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "+moveleft")

    def test_move_right(self):
        self.client.move_right()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "+moveright")

    def test_next_weapon(self):
        self.client.next_weapon()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "weapnext")

    def test_prev_weapon(self):
        self.client.prev_weapon()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "weapprev")

    def test_record_demo(self):
        demo_name = "test_demo"
        self.client.record_demo(demo_name)
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), f"record {demo_name}")

    def test_reload_weapon(self):
        self.client.reload_weapon()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "+reload")

    def test_say(self):
        message = "Hello, world!"
        self.client.say(message)
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), f"say {message}")

    def test_say_team(self):
        message = "Hello, team!"
        self.client.say_team(message)
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), f"say_team {message}")

    def test_screenshot(self):
        self.client.screenshot()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "screenshot")

    def test_shoot(self):
        self.client.shoot()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "+attack")

    def test_stop_demo(self):
        self.client.stop_demo()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "stoprecord")

    def test_stop_shoot(self):
        self.client.stop_shoot()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "-attack")

    def test_toggle_console(self):
        self.client.toggle_console()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "toggleconsole")

    def test_use_item(self):
        self.client.use_item()
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), "+useitem")

    def test_voice_chat(self):
        voice_command = "test_command"
        self.client.voice_chat(voice_command)
        self.assertEqual(self.client.connection.socket.sendto.call_args[0][0].decode(), f"voice_chat {voice_command}")

if __name__ == "__main__":
    unittest.main()

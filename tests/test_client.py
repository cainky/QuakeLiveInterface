import unittest
from QuakeLiveInterface.client import QuakeLiveClient

class QuakeLiveClientTest(unittest.TestCase):
    def setUp(self):
        self.client = QuakeLiveClient("localhost", 27960)  # Example IP address and port

    def test_move_forward(self):
        self.client.move_forward()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "+forward")

    def test_move_backward(self):
        self.client.move_backward()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "-forward")

    def test_move_left(self):
        self.client.move_left()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "+moveleft")

    def test_move_right(self):
        self.client.move_right()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "+moveright")

    def test_jump(self):
        self.client.jump()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "+jump")

    def test_crouch(self):
        self.client.crouch()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "+crouch")

    def test_shoot(self):
        self.client.shoot()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "+attack")

    def test_stop_shoot(self):
        self.client.stop_shoot()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "-attack")

    def test_use_item(self):
        self.client.use_item()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "+useitem")

    def test_reload_weapon(self):
        self.client.reload_weapon()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "+reload")

    def test_next_weapon(self):
        self.client.next_weapon()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "weapnext")

    def test_prev_weapon(self):
        self.client.prev_weapon()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "weapprev")

    def test_say(self):
        message = "Hello, world!"
        self.client.say(message)
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, f"say {message}")

    def test_say_team(self):
        message = "Hello, team!"
        self.client.say_team(message)
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, f"say_team {message}")

    def test_voice_chat(self):
        voice_command = "attack"
        self.client.voice_chat(voice_command)
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, f"voice_chat {voice_command}")

    def test_toggle_console(self):
        self.client.toggle_console()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "toggleconsole")

    def test_screenshot(self):
        self.client.screenshot()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "screenshot")

    def test_record_demo(self):
        demo_name = "demo1"
        self.client.record_demo(demo_name)
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, f"record {demo_name}")

    def test_stop_demo(self):
        self.client.stop_demo()
        # Assert that the expected command was sent to the server
        self.assertEqual(self.client.connection.command_sent, "stoprecord")

if __name__ == "__main__":
    unittest.main()

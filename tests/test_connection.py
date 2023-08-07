import unittest
from QuakeLiveInterface.connection import ServerConnection

class ServerConnectionTest(unittest.TestCase):
    def setUp(self):
        self.connection = ServerConnection("localhost", 27960)  # Example IP address and port

    def test_send_command(self):
        command = "+forward"
        self.connection.send_command(command)
        # Assert that the expected command was sent to the server
        self.assertEqual(self.connection.command_sent, command)

    def test_listen(self):
        data_packet = b"sample_data"
        self.connection.socket.recvfrom = lambda buffer_size: (data_packet, None)
        result = self.connection.listen()
        # Assert that the expected data packet was received
        self.assertEqual(result, data_packet)

    def test_listen_error(self):
        error_message = "Sample error"
        self.connection.socket.recvfrom = lambda buffer_size: (None, error_message)
        result = self.connection.listen()
        # Assert that the expected error message was logged
        self.assertIn(error_message, self.connection.logger.error_log)

    def test_reconnect(self):
        self.connection.socket.close = lambda: None
        self.connection.socket = None
        self.connection.reconnect()
        # Assert that the socket was recreated
        self.assertIsNotNone(self.connection.socket)

if __name__ == "__main__":
    unittest.main()

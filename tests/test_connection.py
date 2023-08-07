import unittest
from unittest.mock import MagicMock
from QuakeLiveInterface.connection import ServerConnection

class ServerConnectionTest(unittest.TestCase):
    def setUp(self):
        self.connection = ServerConnection("127.0.0.1", 1234)
        self.connection.socket = MagicMock()

    def test_listen(self):
        data_packet = b"test data"
        self.connection.socket.recvfrom = MagicMock(return_value=(data_packet, None))
        result = self.connection.listen()
        self.assertEqual(result, data_packet)

    def test_listen_error(self):
        error_message = "test error"
        self.connection.socket.recvfrom = MagicMock(return_value=(None, error_message))
        result = self.connection.listen()
        self.assertIsNone(result)

    def test_reconnect(self):
        self.connection.socket.close = MagicMock()
        self.connection.reconnect()
        # Add assertions to verify that the socket is closed and a new socket is created
        self.assertTrue(self.connection.socket.close.called)
        self.assertTrue(self.connection.socket.socket.called)

if __name__ == "__main__":
    unittest.main()

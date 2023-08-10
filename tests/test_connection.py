import unittest
from unittest.mock import MagicMock, patch
import socket
from QuakeLiveInterface.connection import ServerConnection


class ServerConnectionTest(unittest.TestCase):
    def setUp(self):
        self.ip = "127.0.0.1"
        self.port = 1234
        self.mock_socket = MagicMock()
        self.connection = ServerConnection(self.ip, self.port, sock=self.mock_socket)

    def tearDown(self):
        if self.connection.socket:
            self.connection.socket.close()

    def test_initialization(self):
        """Test proper initialization of the ServerConnection class."""
        self.assertEqual(self.connection.host, self.ip)
        self.assertEqual(self.connection.port, self.port)
        self.assertIsInstance(self.connection.socket, MagicMock)

    def test_listen_success(self):
        """Test listening for data successfully."""
        data_packet = b"test data"
        self.connection.socket.recvfrom = MagicMock(return_value=(data_packet, None))
        result = self.connection.listen()
        self.assertEqual(result, data_packet)

    def test_listen_error(self):
        """Test listening for data when an error occurs."""
        self.connection.socket.recvfrom.side_effect = socket.error("test error")
        result = self.connection.listen()
        self.assertIsNone(result)

    def test_set_timeout(self):
        """Test setting socket timeout."""
        timeout_value = 5
        self.connection.set_timeout(timeout_value)
        self.connection.socket.settimeout.assert_called_once_with(timeout_value)

    def test_send_command_success(self):
        """Test sending a command successfully."""
        command = "test_command"
        self.connection.send_command(command)
        self.connection.socket.sendto.assert_called_once_with(
            command.encode(), (self.ip, self.port)
        )

    def test_send_command_error(self):
        """Test sending a command when an error occurs."""
        command = "test_command"
        self.connection.socket.sendto.side_effect = socket.error("test error")
        with self.assertLogs(level="ERROR") as log:
            self.connection.send_command(command)
            self.assertIn("Error sending command", log.output[0])

    def test_reconnect_success(self):
        """Test successful reconnection."""
        new_mock_socket = MagicMock()
        with patch("socket.socket", return_value=new_mock_socket):
            self.connection.reconnect()
            self.mock_socket.close.assert_called_once()

    def test_reconnect_failure(self):
        """Test failing to reconnect after max retries."""
        with patch.object(
            socket, "socket", side_effect=socket.error("test error"), autospec=True
        ):
            with self.assertLogs(level="ERROR") as log:
                self.connection.reconnect()
                self.assertIn("Failed to reconnect, attempt 3/3", log.output[2])


if __name__ == "__main__":
    unittest.main()

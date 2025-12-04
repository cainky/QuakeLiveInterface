import pytest
from unittest.mock import MagicMock
from QuakeLiveInterface.client import QuakeLiveClient

@pytest.fixture
def mock_redis_connection(mocker):
    """Mocks the RedisConnection class."""
    mock = MagicMock()
    mocker.patch('QuakeLiveInterface.client.RedisConnection', return_value=mock)
    return mock

def test_send_agent_command(mock_redis_connection):
    """Tests that agent commands are sent to the correct channel."""
    client = QuakeLiveClient()
    client.send_agent_command('attack')

    mock_redis_connection.publish.assert_called_with('ql:agent:command', '{"command": "attack"}')

def test_send_admin_command(mock_redis_connection):
    """Tests that admin commands are sent to the correct channel."""
    client = QuakeLiveClient()
    client.send_admin_command('restart_game')

    mock_redis_connection.publish.assert_called_with('ql:admin:command', '{"command": "restart_game"}')

def test_send_input_command(mock_redis_connection):
    """Tests the unified input command with button simulation."""
    client = QuakeLiveClient()
    client.send_input(forward=True, right=True, attack=True, yaw_delta=2.5)

    # Verify the input command was sent with correct parameters
    mock_redis_connection.publish.assert_called()
    call_args = mock_redis_connection.publish.call_args
    assert call_args[0][0] == 'ql:agent:command'
    import json
    payload = json.loads(call_args[0][1])
    assert payload['command'] == 'input'
    assert payload['forward'] == 1
    assert payload['right'] == 1
    assert payload['attack'] == 1
    assert payload['yaw_delta'] == 2.5
    assert payload['back'] == 0
    assert payload['left'] == 0

def test_start_demo_recording(mock_redis_connection):
    """Tests starting a demo recording."""
    client = QuakeLiveClient()
    client.start_demo_recording('my_demo')

    mock_redis_connection.publish.assert_called_with(
        'ql:admin:command',
        '{"command": "start_demo_record", "filename": "my_demo"}'
    )

def test_stop_demo_recording(mock_redis_connection):
    """Tests stopping a demo recording."""
    client = QuakeLiveClient()
    client.stop_demo_recording()

    mock_redis_connection.publish.assert_called_with(
        'ql:admin:command',
        '{"command": "stop_demo_record"}'
    )

def test_update_game_state(mock_redis_connection):
    """Tests updating the game state."""
    client = QuakeLiveClient()

    # Mock the get_message to return a sample state
    mock_redis_connection.get_message.return_value = '{"game_in_progress": true}'

    updated = client.update_game_state()

    assert updated
    assert client.get_game_state().game_in_progress

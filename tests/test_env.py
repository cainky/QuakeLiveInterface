import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from QuakeLiveInterface.env import QuakeLiveEnv
from QuakeLiveInterface.state import GameState
from gymnasium.utils.env_checker import check_env

@pytest.fixture
def mock_client(mocker):
    """Mocks the QuakeLiveClient."""
    mock = MagicMock()
    mock.update_game_state.return_value = True
    mock.get_game_state.return_value = GameState()
    mocker.patch('QuakeLiveInterface.env.QuakeLiveClient', return_value=mock)
    return mock

def test_env_init(mock_client):
    """Tests that the environment initializes correctly."""
    env = QuakeLiveEnv()
    assert env.client is not None
    assert env.action_space is not None
    assert env.observation_space is not None
    assert env.client == mock_client

def test_env_reset(mock_client):
    """Tests the reset method of the environment."""
    env = QuakeLiveEnv()
    obs, info = env.reset()
    mock_client.send_admin_command.assert_called_with('restart_game')
    assert isinstance(obs, np.ndarray)
    assert obs.shape == env.observation_space.shape

def test_env_step(mock_client):
    """Tests the step method of the environment."""
    env = QuakeLiveEnv()
    env.reset()

    # Use a deterministic MultiDiscrete action
    # [forward_back, left_right, jump_crouch, attack, look_pitch, look_yaw]
    # forward=2, none=1, none=1, attack=1, pitch=5 (center), yaw=5 (center)
    action = np.array([2, 1, 1, 1, 5, 5])

    obs, reward, terminated, truncated, info = env.step(action)

    # Verify send_input was called (unified input command)
    mock_client.send_input.assert_called()

    assert isinstance(obs, np.ndarray)
    assert isinstance(reward, (int, float))
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert isinstance(info, dict)

@pytest.mark.filterwarnings("ignore:.*np.bool8.*:DeprecationWarning")
def test_gym_env_checker():
    """
    Uses the official Gymnasium environment checker to validate the environment.
    """
    with patch('QuakeLiveInterface.env.QuakeLiveClient') as MockClient, \
         patch('QuakeLiveInterface.env.GameState') as MockGameState:

        mock_client_instance = MockClient.return_value
        mock_client_instance.update_game_state.return_value = True

        mock_game_state_instance = MockGameState.return_value
        mock_client_instance.get_game_state.return_value = mock_game_state_instance

        mock_agent = MagicMock()
        mock_agent.is_alive = True
        mock_agent.health = 100
        mock_agent.armor = 100
        mock_agent.position = {'x':0,'y':0,'z':0}
        mock_agent.velocity = {'x':0,'y':0,'z':0}
        mock_agent.view_angles = {'pitch': 0, 'yaw': 0, 'roll': 0}
        mock_agent.weapons = []
        mock_agent.selected_weapon = None

        # Also mock the opponent to have the same structure
        mock_opponent = MagicMock()
        mock_opponent.is_alive = True
        mock_opponent.health = 100
        mock_opponent.armor = 100
        mock_opponent.position = {'x':0,'y':0,'z':0}
        mock_opponent.velocity = {'x':0,'y':0,'z':0}
        mock_opponent.view_angles = {'pitch': 0, 'yaw': 0, 'roll': 0}

        mock_game_state_instance.get_agent.return_value = mock_agent
        mock_game_state_instance.get_opponents.return_value = [mock_opponent]
        mock_game_state_instance.get_items.return_value = []
        mock_game_state_instance.game_in_progress = True

        env = QuakeLiveEnv()

        # This will raise an exception if the environment is not compliant
        check_env(env)

def test_get_item_features(mock_client):
    """Tests the _get_item_features method."""
    env = QuakeLiveEnv()

    # Create a mock item
    mock_item = {
        'name': 'item_health_large',
        'position': {'x': 100, 'y': 200, 'z': 50},
        'is_available': True,
        'spawn_time': 15000
    }

    # Create another mock item
    mock_item2 = {
        'name': 'item_armor_shard',
        'position': {'x': -100, 'y': -200, 'z': -50},
        'is_available': False,
        'spawn_time': 0
    }

    items = [mock_item, mock_item2]
    features = env._get_item_features(items)

    assert features.shape == (5 * env.NUM_ITEMS,)

    # Check features for the first item
    assert features[0] == 100 / env.MAP_DIMS[0] * 2 - 1
    assert features[1] == 200 / env.MAP_DIMS[1] * 2 - 1
    assert features[2] == 50 / env.MAP_DIMS[2] * 2 - 1
    assert features[3] == 1
    assert features[4] == 15000 / 30000.0

    # Check features for the second item
    assert features[5] == -100 / env.MAP_DIMS[0] * 2 - 1
    assert features[6] == -200 / env.MAP_DIMS[1] * 2 - 1
    assert features[7] == -50 / env.MAP_DIMS[2] * 2 - 1
    assert features[8] == 0
    assert features[9] == 0 / 30000.0

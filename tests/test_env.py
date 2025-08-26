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

    # Use a deterministic action to ensure attack is called
    action = {
        "move_forward_back": 1,
        "move_right_left": 1,
        "move_up_down": 1,
        "attack": 1,
        "look_pitch": np.array([0.0]),
        "look_yaw": np.array([0.0]),
    }

    obs, reward, done, info = env.step(action)

    mock_client.move.assert_called()
    mock_client.look.assert_called()
    mock_client.attack.assert_called()

    assert isinstance(obs, np.ndarray)
    assert isinstance(reward, (int, float))
    assert isinstance(done, bool)
    assert isinstance(info, dict)

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
        mock_agent.weapons = []
        mock_agent.selected_weapon = None

        # Also mock the opponent to have the same structure
        mock_opponent = MagicMock()
        mock_opponent.is_alive = True
        mock_opponent.health = 100
        mock_opponent.armor = 100
        mock_opponent.position = {'x':0,'y':0,'z':0}
        mock_opponent.velocity = {'x':0,'y':0,'z':0}

        mock_game_state_instance.get_agent.return_value = mock_agent
        mock_game_state_instance.get_opponents.return_value = [mock_opponent]
        mock_game_state_instance.get_items.return_value = []
        mock_game_state_instance.game_in_progress = True

        env = QuakeLiveEnv()

        # This will raise an exception if the environment is not compliant
        check_env(env)

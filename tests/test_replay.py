import pytest
import subprocess
import json
from unittest.mock import mock_open
from QuakeLiveInterface.replay import ReplayAnalyzer

DEMO_FILE = 'test.dm_91'
JSON_FILE = DEMO_FILE + '.json'

@pytest.fixture
def analyzer():
    """Returns a ReplayAnalyzer instance."""
    return ReplayAnalyzer()

def test_parse_demo_file_not_found(analyzer, mocker):
    """Tests that parse_demo returns None if the demo file doesn't exist."""
    mocker.patch('os.path.exists', return_value=False)
    result = analyzer.parse_demo(DEMO_FILE)
    assert result is None

def test_parse_demo_udt_not_found(analyzer, mocker):
    """Tests that parse_demo returns None if the udt executable is not found."""
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('subprocess.run', side_effect=FileNotFoundError)
    result = analyzer.parse_demo(DEMO_FILE)
    assert result is None

def test_parse_demo_subprocess_error(analyzer, mocker):
    """Tests that parse_demo returns None if udt fails."""
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'cmd'))
    result = analyzer.parse_demo(DEMO_FILE)
    assert result is None

def test_parse_demo_success(analyzer, mocker):
    """Tests the successful parsing of a demo file."""
    # Mock os.path.exists to simulate file presence
    mocker.patch('os.path.exists', side_effect=[True, True])

    # Mock subprocess.run to simulate successful execution
    mock_run = mocker.patch('subprocess.run', return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout='', stderr=''))

    # Mock open to simulate reading the JSON file
    mock_json_data = '{"key": "value"}'
    mocker.patch('builtins.open', mock_open(read_data=mock_json_data))

    # Mock os.remove to check if cleanup happens
    mock_remove = mocker.patch('os.remove')

    result = analyzer.parse_demo(DEMO_FILE)

    # Assertions
    mock_run.assert_called_once_with(['udt_json', '-j', DEMO_FILE], check=True, capture_output=True, text=True)
    assert result == {"key": "value"}
    mock_remove.assert_called_once_with(JSON_FILE)

def test_parse_demo_json_decode_error(analyzer, mocker):
    """Tests that parse_demo returns None if the JSON output is malformed."""
    mocker.patch('os.path.exists', side_effect=[True, True])
    mocker.patch('subprocess.run', return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout='', stderr=''))

    # Simulate malformed JSON
    mocker.patch('builtins.open', mock_open(read_data='not a valid json'))

    result = analyzer.parse_demo(DEMO_FILE)
    assert result is None

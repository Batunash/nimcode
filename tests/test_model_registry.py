import os
import json
import time
import pytest
from unittest.mock import patch, mock_open, MagicMock

import nimcode.model_registry as mr

@pytest.fixture(autouse=True)
def reset_registry_state():
    """Reset the module-level state before each test."""
    mr._CACHE_LOADED = False
    mr._UPDATE_THREAD_STARTED = False
    mr._DYNAMIC_CACHE = {}
    yield

def test_get_context_window_hardcoded():
    # Known model in hardcoded dictionary
    assert mr.get_context_window("meta/llama-3.1-8b-instruct") == 128000
    
def test_get_context_window_unknown():
    # Completely unknown model
    assert mr.get_context_window("unknown/model-123") == mr.DEFAULT_CONTEXT_WINDOW

@patch("os.path.exists")
@patch("os.path.getmtime")
@patch("builtins.open", new_callable=mock_open, read_data='{"provider/test-model": 64000, "test-model": 64000}')
def test_get_context_window_from_cache(mock_file, mock_getmtime, mock_exists):
    mock_exists.return_value = True
    mock_getmtime.return_value = time.time()  # Very recent cache
    
    # Force reload
    mr._load_or_update_cache()
    
    assert mr.get_context_window("provider/test-model") == 64000
    assert mr.get_context_window("other_provider/test-model") == 64000
    assert mr._UPDATE_THREAD_STARTED is False  # Cache is fresh, no thread spawned

@patch("os.path.exists")
@patch("threading.Thread")
def test_get_context_window_spawns_thread_if_no_cache(mock_thread, mock_exists):
    mock_exists.return_value = False
    
    # Should spawn thread to fetch cache
    mr.get_context_window("some-model")
    
    assert mr._UPDATE_THREAD_STARTED is True
    mock_thread.assert_called_once()
    mock_thread.return_value.start.assert_called_once()

@patch("os.path.exists")
@patch("os.path.getmtime")
@patch("threading.Thread")
@patch("builtins.open", new_callable=mock_open, read_data='{"old-model": 1000}')
def test_get_context_window_spawns_thread_if_old_cache(mock_file, mock_thread, mock_getmtime, mock_exists):
    mock_exists.return_value = True
    mock_getmtime.return_value = time.time() - (8 * 24 * 3600)  # 8 days old
    
    mr.get_context_window("old-model")
    
    assert mr._UPDATE_THREAD_STARTED is True
    mock_thread.assert_called_once()
    mock_thread.return_value.start.assert_called_once()

@patch("urllib.request.urlopen")
def test_fetch_and_cache_models(mock_urlopen, tmp_path):
    mock_response = MagicMock()
    mock_response.read.return_value = b'''
    {
        "provider/model-A": {"max_tokens": 1234},
        "provider/model-B": {"max_tokens": 5678, "other": "ignored"},
        "provider/model-C": {"ignored": 10}
    }
    '''
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response
    
    with patch("nimcode.model_registry._CACHE_FILE", str(tmp_path / "cache.json")):
        mr._fetch_and_cache_models()
        
        assert "provider/model-A" in mr._DYNAMIC_CACHE
        assert mr._DYNAMIC_CACHE["provider/model-A"] == 1234
        assert mr._DYNAMIC_CACHE["model-A"] == 1234
        assert "provider/model-C" not in mr._DYNAMIC_CACHE
        
        # Verify file is written
        with open(str(tmp_path / "cache.json"), "r") as f:
            data = json.load(f)
            assert data["provider/model-A"] == 1234
            assert data["model-A"] == 1234

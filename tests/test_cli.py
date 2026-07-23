import pytest
import os
import sys
from unittest.mock import patch
from nimcode.cli import main

def test_cli_missing_api_key():
    with patch.dict(os.environ, clear=True):
        with patch.object(sys, 'argv', ["nimcode"]):
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 1

def test_cli_with_api_key_env_var():
    with patch.dict(os.environ, {"NIM_API_KEY": "test_env_key"}):
        with patch.object(sys, 'argv', ["nimcode", "Do a task"]):
            with patch("nimcode.cli.Agent.run") as mock_run:
                # We also need to patch start_repl just in case
                with patch("nimcode.cli.Agent.start_repl"):
                    main()
                    mock_run.assert_called_once_with("Do a task")

def test_cli_with_api_key_flag():
    with patch.dict(os.environ, clear=True):
        with patch.object(sys, 'argv', ["nimcode", "Do a task", "--api-key", "test_flag_key", "--permission-mode", "bypass"]):
            with patch("nimcode.cli.Agent.run") as mock_run:
                with patch("nimcode.cli.Agent.start_repl"):
                    main()
                    mock_run.assert_called_once_with("Do a task")

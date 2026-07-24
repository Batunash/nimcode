import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from nimcode.cli import main, run_login, run_doctor, install_hook

def test_run_login():
    with patch("getpass.getpass", return_value="my_key"):
        with patch("nimcode.config.save_global_setting") as mock_save:
            with patch("nimcode.cli.console.print") as mock_print:
                run_login()
                mock_save.assert_called_with("api_key", "my_key")
                
def test_run_login_empty():
    with patch("getpass.getpass", return_value="   "):
        with patch("nimcode.cli.console.print") as mock_print:
            run_login()
            mock_print.assert_any_call("[red]API Key cannot be empty.[/red]")

def test_run_doctor():
    real_env_get = os.environ.get
    with patch("os.environ.get", side_effect=lambda k, d=None: "key" if k == "NIM_API_KEY" else real_env_get(k, d)):
        with patch("os.path.exists", return_value=True):
            with patch("nimcode.cli.console.print") as mock_print:
                run_doctor()
                mock_print.assert_any_call("[green][OK][/green] .nimcode directory found in current project.")

def test_run_doctor_missing():
    real_env_get = os.environ.get
    with patch("os.environ.get", side_effect=lambda k, d=None: None if k == "NIM_API_KEY" else real_env_get(k, d)):
        with patch("os.path.exists", return_value=False):
            with patch("nimcode.cli.console.print") as mock_print:
                run_doctor()
                mock_print.assert_any_call("[yellow][!][/yellow] No .nimcode directory found. Standard settings apply.")

def test_install_hook(tmp_path):
    cwd = str(tmp_path)
    # Missing .git
    with patch("os.path.exists", return_value=False):
        with patch("nimcode.cli.console.print") as mock_print:
            install_hook()
            mock_print.assert_any_call("[red][X][/red] Not a git repository.")
            
def test_install_hook_success(tmp_path):
    cwd = str(tmp_path)
    git_dir = os.path.join(cwd, ".git")
    os.makedirs(os.path.join(git_dir, "hooks"))
    
    real_join = os.path.join
    with patch("os.path.exists", return_value=True):
        with patch("nimcode.cli.os.path.join", side_effect=lambda *args: real_join(cwd, *args)):
            with patch("nimcode.cli.console.print"):
                install_hook()
                hook = real_join(cwd, ".git", "hooks", "prepare-commit-msg")
                assert os.path.exists(hook)

def test_main_doctor():
    with patch("sys.argv", ["nimcode", "doctor"]):
        with patch("nimcode.cli.run_doctor") as mock_doc:
            main()
            mock_doc.assert_called_once()

def test_main_install_hook():
    with patch("sys.argv", ["nimcode", "install-hook"]):
        with patch("nimcode.cli.install_hook") as mock_hook:
            main()
            mock_hook.assert_called_once()

def test_main_login():
    with patch("sys.argv", ["nimcode", "/login"]):
        with patch("nimcode.cli.run_login") as mock_log:
            with patch("sys.exit"):
                main()
                mock_log.assert_called_once()

def test_main_no_key():
    with patch("sys.argv", ["nimcode", "my prompt"]):
        with patch("nimcode.cli.load_settings", return_value={}):
            real_env_get = os.environ.get
            with patch("os.environ.get", side_effect=lambda k, d=None: None if k == "NIM_API_KEY" else real_env_get(k, d)):
                with patch("nimcode.cli.run_login"):
                    with patch("sys.stdin.isatty", return_value=True):
                        with patch("builtins.input", side_effect=EOFError):
                            with pytest.raises(SystemExit):
                                main()

def test_main_with_key():
    with patch("sys.argv", ["nimcode", "prompt task", "--api-key", "key"]):
        with patch("nimcode.cli.load_settings", return_value={}):
            with patch("nimcode.agent.Agent") as mock_agent_class:
                mock_agent = MagicMock()
                mock_agent_class.return_value = mock_agent
                with patch("nimcode.cli.asyncio.run") as mock_run:
                    with patch("sys.stdin.isatty", return_value=True):
                        with patch("rich.prompt.Prompt.ask", return_value="1"):
                            with patch("nimcode.nim_client.NimClient") as mock_client:
                                mock_client.return_value.get_available_models.return_value = []
                                main()
                                assert mock_run.called

def test_main_piped_input():
    with patch("sys.argv", ["nimcode"]):
        with patch("nimcode.cli.load_settings", return_value={"api_key": "k"}):
            with patch("nimcode.agent.Agent") as mock_agent_class:
                with patch("sys.stdin.isatty", return_value=False):
                    with patch("sys.stdin.read", return_value="piped"):
                        with patch("nimcode.cli.asyncio.run") as mock_run:
                            with patch("rich.prompt.Prompt.ask", return_value="1"):
                                with patch("nimcode.nim_client.NimClient") as mock_client:
                                    mock_client.return_value.get_available_models.return_value = []
                                    main()
                                    assert mock_run.called

def test_main_repl():
    with patch("sys.argv", ["nimcode"]):
        with patch("nimcode.cli.load_settings", return_value={"api_key": "k"}):
            with patch("nimcode.agent.Agent") as mock_agent_class:
                with patch("sys.stdin.isatty", return_value=True):
                    with patch("nimcode.cli.asyncio.run") as mock_run:
                        with patch("rich.prompt.Prompt.ask", return_value="1"):
                            with patch("nimcode.nim_client.NimClient") as mock_client:
                                mock_client.return_value.get_available_models.return_value = []
                                main()
                                assert mock_run.called

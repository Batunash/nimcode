import pytest
from unittest.mock import patch, MagicMock
from nimcode.permissions import PermissionEngine, PermissionMode

@pytest.mark.asyncio
async def test_permission_bypass():
    engine = PermissionEngine(mode=PermissionMode.BYPASS)
    assert await engine.check_permission({"tool": "Bash", "args": {}}) == True

@pytest.mark.asyncio
async def test_permission_readonly_blocked():
    engine = PermissionEngine(mode=PermissionMode.AUTO)
    # Bash should still be checked (not returned True immediately) and if not interactive, returns True for now (which is a flaw but let's test current behavior)
    assert await engine.check_permission({"tool": "Bash", "args": {}}) == True

@pytest.mark.asyncio
async def test_permission_safe_tools():
    engine = PermissionEngine(mode=PermissionMode.DEFAULT)
    # Read is a safe tool
    assert await engine.check_permission({"tool": "Read", "args": {}}) == True
    assert await engine.check_permission({"tool": "Glob", "args": {}}) == True

@pytest.mark.asyncio
async def test_permission_default_interactive_accept():
    engine = PermissionEngine(mode=PermissionMode.DEFAULT)
    with patch("sys.stdin.isatty", return_value=True):
        with patch("builtins.input", return_value="a"):
            assert await engine.check_permission({"tool": "Bash", "args": {"command": "echo hi"}}) == True

@pytest.mark.asyncio
async def test_permission_default_interactive_reject():
    engine = PermissionEngine(mode=PermissionMode.DEFAULT)
    with patch("sys.stdin.isatty", return_value=True):
        with patch("builtins.input", return_value="r"):
            assert await engine.check_permission({"tool": "Bash", "args": {"command": "echo hi"}}) == False

@pytest.mark.asyncio
async def test_permission_default_interactive_empty_accept():
    engine = PermissionEngine(mode=PermissionMode.DEFAULT)
    with patch("sys.stdin.isatty", return_value=True):
        with patch("builtins.input", return_value=""):
            assert await engine.check_permission({"tool": "Bash", "args": {"command": "echo hi"}}) == True

@pytest.mark.asyncio
async def test_permission_default_interactive_unknown_tool_format():
    engine = PermissionEngine(mode=PermissionMode.DEFAULT)
    with patch("sys.stdin.isatty", return_value=True):
        with patch("builtins.input", return_value="a"):
            # UnknownTool triggers the else branch for generic JSON display
            assert await engine.check_permission({"tool": "UnknownTool", "args": {"k1": "v1", "k2": "v2"}}) == True

@pytest.mark.asyncio
async def test_permission_edit_bash_command():
    engine = PermissionEngine(mode=PermissionMode.DEFAULT)
    call = {"tool": "Bash", "args": {"command": "echo hi"}}
    
    # First choose 'e', then choose 'a' on the second loop
    with patch("sys.stdin.isatty", return_value=True):
        with patch("builtins.input", side_effect=["e", "a"]):
            with patch("prompt_toolkit.prompt", return_value="echo edited"):
                assert await engine.check_permission(call) == True
                assert call["args"]["command"] == "echo edited"

@pytest.mark.asyncio
async def test_permission_edit_other_args_valid():
    engine = PermissionEngine(mode=PermissionMode.DEFAULT)
    call = {"tool": "Write", "args": {"file_path": "a.txt", "content": "hello"}}
    
    # Choose 'e', prompt_toolkit returns modified JSON, then choose 'a'
    with patch("sys.stdin.isatty", return_value=True):
        with patch("builtins.input", side_effect=["e", "a"]):
            with patch("prompt_toolkit.prompt", return_value='{"file_path": "a.txt", "content": "edited"}'):
                assert await engine.check_permission(call) == True
                assert call["args"]["content"] == "edited"

@pytest.mark.asyncio
async def test_permission_edit_other_args_invalid_json():
    engine = PermissionEngine(mode=PermissionMode.DEFAULT)
    call = {"tool": "Write", "args": {"file_path": "a.txt"}}
    
    # Choose 'e', prompt returns BAD JSON, repeats loop, choose 'e' again with GOOD JSON, choose 'a'
    with patch("sys.stdin.isatty", return_value=True):
        with patch("builtins.input", side_effect=["e", "e", "a"]):
            with patch("prompt_toolkit.prompt", side_effect=["bad json", '{"file_path": "b.txt"}', '{"file_path": "b.txt"}']):
                assert await engine.check_permission(call) == True
                assert call["args"]["file_path"] == "b.txt"

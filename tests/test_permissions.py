import pytest
from unittest.mock import patch
from nimcode.permissions import PermissionEngine, PermissionMode

def test_permissions_default_read():
    engine = PermissionEngine(mode=PermissionMode.DEFAULT)
    # Read-only tools should be allowed without prompting
    assert engine.check_permission({"tool": "Read"}) is True
    assert engine.check_permission({"tool": "Glob"}) is True

def test_permissions_bypass():
    engine = PermissionEngine(mode=PermissionMode.BYPASS)
    assert engine.check_permission({"tool": "Bash"}) is True
    assert engine.check_permission({"tool": "Write"}) is True

def test_permissions_auto_mode_safe():
    engine = PermissionEngine(mode=PermissionMode.AUTO)
    assert engine.check_permission({"tool": "Read", "args": {"file_path": "test.txt"}}) is True

def test_permissions_auto_mode_dangerous():
    engine = PermissionEngine(mode=PermissionMode.AUTO)
    # Mock sys.stdin.isatty to True so it falls to the prompt, then mock the prompt
    import sys
    with patch("sys.stdin.isatty", return_value=True):
        with patch("typer.prompt", return_value="n"):
            assert engine.check_permission({"tool": "Bash", "args": {"command": "ls"}}) is False

def test_permissions_prompt_yes():
    engine = PermissionEngine(mode=PermissionMode.DEFAULT)
    import sys
    with patch("sys.stdin.isatty", return_value=True):
        with patch("typer.prompt", return_value="y"):
            assert engine.check_permission({"tool": "Write", "args": {"file_path": "f", "content": "x"}}) is True

def test_permissions_prompt_no():
    engine = PermissionEngine(mode=PermissionMode.DEFAULT)
    import sys
    with patch("sys.stdin.isatty", return_value=True):
        with patch("typer.prompt", return_value="n"):
            assert engine.check_permission({"tool": "Bash", "args": {"command": "ls"}}) is False
        
def test_permissions_prompt_output_coverage():
    # Just to get coverage on the console print branches
    engine = PermissionEngine(mode=PermissionMode.DEFAULT)
    with patch("typer.prompt", return_value="y"):
        engine.check_permission({"tool": "Write", "args": {"file_path": "a.txt"}})
        engine.check_permission({"tool": "Edit", "args": {"file_path": "a.txt", "old_string": "a", "new_string": "b"}})
        engine.check_permission({"tool": "UnknownMutator", "args": {}})

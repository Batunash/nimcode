import pytest
import os
from unittest.mock import patch, MagicMock
from nimcode.tools import ToolRegistry

def test_mock_data_hunter():
    """Test if Mock Data Hunter catches lazy patterns."""
    content_with_lorem = "const x = 'lorem ipsum';"
    content_with_dummy = "function mockUser() { return true; }"
    
    with pytest.raises(Exception) as exc1:
        ToolRegistry._check_lazy_code(content_with_lorem, "test.js")
    assert "Mock data detected" in str(exc1.value)
    
    with pytest.raises(Exception) as exc2:
        ToolRegistry._check_lazy_code(content_with_dummy, "test.js")
    assert "Mock data detected" in str(exc2.value)
    
    # Should not raise for valid code
    ToolRegistry._check_lazy_code("const x = 'real data';", "test.js")

@patch("subprocess.run")
def test_syntax_checker_success(mock_run):
    """Test syntax checker when syntax is correct."""
    mock_run.return_value = MagicMock(returncode=0)
    
    # Should not raise any exception
    ToolRegistry._check_syntax("test.js", "/path/to/test.js", [])
    mock_run.assert_called_once()

@patch("subprocess.run")
@patch("os.remove")
@patch("os.path.exists")
def test_syntax_checker_failure_new_file(mock_exists, mock_remove, mock_run):
    """Test syntax checker when syntax is wrong for a newly created file."""
    import subprocess
    mock_run.side_effect = subprocess.CalledProcessError(1, "node --check", stderr="SyntaxError: Unexpected token")
    mock_exists.return_value = True
    
    with pytest.raises(Exception) as exc:
        ToolRegistry._check_syntax("test.js", "/path/to/test.js", [])
        
    assert "Syntax Error detected" in str(exc.value)
    mock_remove.assert_called_once_with("/path/to/test.js")

@patch("os.path.exists")
@patch("os.listdir")
def test_architecture_validator(mock_listdir, mock_exists, tmp_path):
    """Test Architecture Validator on TaskUpdate."""
    # Mocking that no package.json or requirements.txt exists
    mock_exists.return_value = False
    
    with pytest.raises(Exception) as exc:
        with patch("os.getcwd", return_value=str(tmp_path)):
            ToolRegistry._execute_task_update("backend-1", "completed")
            
    assert "Architecture Validator failed" in str(exc.value)

@patch("os.path.exists")
@patch("os.listdir")
@patch("builtins.open")
def test_coverage_enforcer(mock_open, mock_listdir, mock_exists, tmp_path):
    """Test Coverage Enforcer on TaskUpdate."""
    # Mock files exist
    mock_exists.return_value = True
    mock_listdir.return_value = ["test.log"]
    
    # Mock file content with coverage below 70%
    mock_open.return_value.__enter__.return_value.read.return_value = "PASS test\nLines : 50.5%"
    
    with pytest.raises(Exception) as exc:
        with patch("os.getcwd", return_value=str(tmp_path)):
            # Mock architecture validator pass by mocking package.json exists
            original_exists = os.path.exists
            def side_effect(path):
                if "package.json" in path: return True
                return original_exists(path)
            
            with patch("os.path.exists", side_effect=side_effect):
                ToolRegistry._execute_task_update("backend-1", "completed")
            
    assert "Test Coverage Enforcer blocked completion" in str(exc.value)

@patch("os.path.exists")
@patch("builtins.open")
def test_missing_dependency_blocker(mock_open, mock_exists):
    mock_exists.return_value = True
    # mock package.json content
    mock_open.return_value.__enter__.return_value.read.return_value = '{"dependencies": {"express": "4.17.1"}}'
    
    # Should not raise for express
    ToolRegistry._check_dependency_hallucination('import express from "express";', "test.js", "/cwd")
    
    # Should raise for axios because it's not in package.json
    with pytest.raises(Exception) as exc:
        ToolRegistry._check_dependency_hallucination('import axios from "axios";', "test.js", "/cwd")
    assert "Missing Dependency Blocker" in str(exc.value)

@patch("os.path.exists")
@patch("builtins.open")
def test_api_hallucination(mock_open, mock_exists):
    mock_exists.return_value = True
    # mock api checks log
    mock_open.return_value.__enter__.return_value.read.return_value = "http://api.github.com"
    
    # Should not raise for github api
    ToolRegistry._check_api_hallucination('fetch("http://api.github.com/users")', "/cwd")
    
    # Should raise for fake api
    with pytest.raises(Exception) as exc:
        ToolRegistry._check_api_hallucination('fetch("http://fake.api/data")', "/cwd")
    assert "Network Check Enforcer" in str(exc.value)

def test_bash_command_blacklist():
    with pytest.raises(Exception) as exc:
        ToolRegistry._execute_bash("rm -rf /", "/cwd")
    assert "Security Blocker" in str(exc.value)
    
    with pytest.raises(Exception) as exc:
        ToolRegistry._execute_bash("sudo apt-get update", "/cwd")
    assert "Security Blocker" in str(exc.value)
    
    with pytest.raises(Exception) as exc:
        ToolRegistry._execute_bash("cd ../..", "/cwd")
    assert "Security Blocker" in str(exc.value)

def test_plan_quality_validator():
    """Test Plan Quality Validator in TaskCreate."""
    with pytest.raises(Exception) as exc1:
        ToolRegistry._execute_task_create("task-1", "Subject", "Very short description.")

@patch("os.path.exists")
@patch("builtins.open")
def test_missing_dependency_blocker(mock_open, mock_exists):
    mock_exists.return_value = True
    # mock package.json content
    mock_open.return_value.__enter__.return_value.read.return_value = '{"dependencies": {"express": "4.17.1"}}'
    
    # Should not raise for express
    ToolRegistry._check_dependency_hallucination('import express from "express";', "test.js", "/cwd")
    
    # Should raise for axios because it's not in package.json
    with pytest.raises(Exception) as exc:
        ToolRegistry._check_dependency_hallucination('import axios from "axios";', "test.js", "/cwd")
    assert "Missing Dependency Blocker" in str(exc.value)

@patch("os.path.exists")
@patch("builtins.open")
def test_api_hallucination(mock_open, mock_exists):
    mock_exists.return_value = True
    # mock api checks log
    mock_open.return_value.__enter__.return_value.read.return_value = "http://api.github.com"
    
    # Should not raise for github api
    ToolRegistry._check_api_hallucination('fetch("http://api.github.com/users")', "/cwd")
    
    # Should raise for fake api
    with pytest.raises(Exception) as exc:
        ToolRegistry._check_api_hallucination('fetch("http://fake.api/data")', "/cwd")
    assert "Network Check Enforcer" in str(exc.value)

def test_bash_command_blacklist():
    with pytest.raises(Exception) as exc:
        ToolRegistry._execute_bash("rm -rf /", "/cwd")
    assert "Security Blocker" in str(exc.value)
    
    with pytest.raises(Exception) as exc:
        ToolRegistry._execute_bash("sudo apt-get update", "/cwd")
    assert "Security Blocker" in str(exc.value)
    
    with pytest.raises(Exception) as exc:
        ToolRegistry._execute_bash("cd ../..", "/cwd")
    assert "Security Blocker" in str(exc.value)

def test_plan_quality_validator():
    """Test Plan Quality Validator in TaskCreate."""
    with pytest.raises(Exception) as exc1:
        ToolRegistry._execute_task_create("task-1", "Subject", "Very short description.")
    assert "too short" in str(exc1.value)
    
    with pytest.raises(Exception) as exc2:
        ToolRegistry._execute_task_create("task-1", "Subject", "This is a very long description that is over 150 characters but does not have the required sections Foo, Bar, and Baz. It is just filler text to pass the length check.")
    assert "missing required markdown sections" in str(exc2.value)
    
    with pytest.raises(Exception) as exc3:
        ToolRegistry._execute_task_create("task-1", "Subject", "This is a very long description that is over 150 characters indeed, let me add some more words here so it safely passes the length check. Target Files: none. Implementation Details: code it. Checklist: done.")
    assert "lacks quality. It MUST contain 'Acceptance Criteria'" in str(exc3.value)

import pytest
import os
import tempfile
from nimcode.tools import ToolRegistry, ToolError

def test_get_tool_schema():
    assert ToolRegistry.get_tool_schema("Bash")["required"] == ["command"]
    assert ToolRegistry.get_tool_schema("UnknownTool") is None

def test_validate_tool_call_invalid():
    with pytest.raises(ValueError, match="Tool call must be a dictionary"):
        ToolRegistry.validate_tool_call("not a dict")
        
    with pytest.raises(ValueError, match="Missing 'tool' key"):
        ToolRegistry.validate_tool_call({})
        
    with pytest.raises(ValueError, match="'args' must be a dictionary"):
        ToolRegistry.validate_tool_call({"tool": "Read", "args": "not a dict"})
        
    with pytest.raises(ValueError, match="Unknown tool"):
        ToolRegistry.validate_tool_call({"tool": "UnknownTool"})
        
    with pytest.raises(ValueError, match="missing required argument"):
        ToolRegistry.validate_tool_call({"tool": "Read", "args": {}})

def test_validate_tool_call_valid():
    # Should not raise
    ToolRegistry.validate_tool_call({"tool": "Read", "args": {"file_path": "a.txt"}})

def test_execute_bash():
    result = ToolRegistry.execute({"tool": "Bash", "args": {"command": "echo hello"}})
    assert "hello" in result

def test_execute_read_write(tmp_path):
    cwd = str(tmp_path)
    # Write
    res_w = ToolRegistry.execute({"tool": "Write", "args": {"file_path": "test.txt", "content": "Hello World"}}, cwd)
    assert "Successfully" in res_w
    
    # Read
    res_r = ToolRegistry.execute({"tool": "Read", "args": {"file_path": "test.txt"}}, cwd)
    assert res_r == "Hello World"

def test_execute_edit_success(tmp_path):
    cwd = str(tmp_path)
    file_path = os.path.join(cwd, "test.txt")
    with open(file_path, "w") as f:
        f.write("A B C")
        
    res = ToolRegistry.execute({
        "tool": "Edit", 
        "args": {"file_path": "test.txt", "old_string": "B", "new_string": "X"}
    }, cwd)
    
    assert "Successfully" in res
    with open(file_path, "r") as f:
        assert f.read() == "A X C"

def test_execute_edit_not_found(tmp_path):
    cwd = str(tmp_path)
    file_path = os.path.join(cwd, "test.txt")
    with open(file_path, "w") as f:
        f.write("A B C")
        
    res = ToolRegistry.execute({
        "tool": "Edit", 
        "args": {"file_path": "test.txt", "old_string": "D", "new_string": "X"}
    }, cwd)
    assert "ToolError" in res
    assert "not found" in res

def test_execute_edit_ambiguous(tmp_path):
    cwd = str(tmp_path)
    file_path = os.path.join(cwd, "test.txt")
    with open(file_path, "w") as f:
        f.write("A B B C")
        
    res = ToolRegistry.execute({
        "tool": "Edit", 
        "args": {"file_path": "test.txt", "old_string": "B", "new_string": "X"}
    }, cwd)
    assert "ToolError" in res
    assert "unique" in res

def test_execute_glob(tmp_path):
    cwd = str(tmp_path)
    os.makedirs(os.path.join(cwd, "sub"))
    with open(os.path.join(cwd, "sub", "file1.txt"), "w") as f: f.write("")
    
    res = ToolRegistry.execute({"tool": "Glob", "args": {"pattern": "sub/*.txt"}}, cwd)
    assert "file1.txt" in res

def test_execute_grep(tmp_path):
    cwd = str(tmp_path)
    os.makedirs(os.path.join(cwd, "sub"))
    with open(os.path.join(cwd, "sub", "file1.txt"), "w") as f: f.write("FindMe here")
    
    res = ToolRegistry.execute({"tool": "Grep", "args": {"query": "FindMe", "directory": "sub"}}, cwd)
    assert "file1.txt" in res
    assert "FindMe here" in res

def test_execute_read_not_found(tmp_path):
    cwd = str(tmp_path)
    res = ToolRegistry.execute({"tool": "Read", "args": {"file_path": "missing.txt"}}, cwd)
    assert "ToolError" in res

def test_execute_read_directory(tmp_path):
    cwd = str(tmp_path)
    os.makedirs(os.path.join(cwd, "mydir"))
    res = ToolRegistry.execute({"tool": "Read", "args": {"file_path": "mydir"}}, cwd)
    assert "ToolError" in res

def test_execute_edit_file_not_found(tmp_path):
    cwd = str(tmp_path)
    res = ToolRegistry.execute({"tool": "Edit", "args": {"file_path": "missing.txt", "old_string": "a", "new_string": "b"}}, cwd)
    assert "ToolError" in res

def test_execute_unknown_tool_but_bypassed_validation():
    # Bypass validation just to test the fallback block
    with pytest.raises(Exception):
        ToolRegistry.execute({"tool": "NonExistent", "args": {}})

def test_bash_timeout():
    import subprocess
    from unittest.mock import patch
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="sleep", timeout=120)):
        res = ToolRegistry.execute({"tool": "Bash", "args": {"command": "sleep 121"}})
        assert "timed out" in res

def test_bash_general_exception():
    from unittest.mock import patch
    with patch("subprocess.run", side_effect=RuntimeError("Oops")):
        res = ToolRegistry.execute({"tool": "Bash", "args": {"command": "ls"}})
        assert "Error running bash" in res

def test_bash_truncation():
    from unittest.mock import patch, MagicMock
    mock_res = MagicMock()
    mock_res.stdout = "a" * 11000
    mock_res.stderr = ""
    with patch("subprocess.run", return_value=mock_res):
        res = ToolRegistry.execute({"tool": "Bash", "args": {"command": "ls"}})
        assert "TRUNCATED" in res
        assert len(res) < 11000

def test_execute_general_exception():
    from unittest.mock import patch
    with patch("nimcode.tools.ToolRegistry._execute_read", side_effect=ValueError("Bad read")):
        res = ToolRegistry.execute({"tool": "Read", "args": {"file_path": "a.txt"}})
        assert "Error executing Read: Bad read" in res

def test_execute_unimplemented_tool():
    # Force a tool to pass validation but fail execution
    from unittest.mock import patch
    with patch("nimcode.tools.ToolRegistry.validate_tool_call"):
        res = ToolRegistry.execute({"tool": "FakeTool", "args": {}})
        assert "is registered but execution is not implemented" in res

def test_grep_directory_not_found(tmp_path):
    cwd = str(tmp_path)
    res = ToolRegistry.execute({"tool": "Grep", "args": {"query": "a", "directory": "missing"}}, cwd)
    assert "ToolError" in res

def test_glob_no_results(tmp_path):
    cwd = str(tmp_path)
    res = ToolRegistry.execute({"tool": "Glob", "args": {"pattern": "*.missing"}}, cwd)
    assert "No files found" in res

def test_grep_regex_error(tmp_path):
    cwd = str(tmp_path)
    os.makedirs(os.path.join(cwd, "sub2"))
    res = ToolRegistry.execute({"tool": "Grep", "args": {"query": "[invalid regex", "directory": "sub2"}}, cwd)
    assert "Invalid regex query" in res

def test_grep_read_error(tmp_path):
    cwd = str(tmp_path)
    os.makedirs(os.path.join(cwd, "sub3"))
    with open(os.path.join(cwd, "sub3", "file1.txt"), "w") as f:
        f.write("FindMe here")
    from unittest.mock import patch
    with patch("builtins.open", side_effect=PermissionError("No access")):
        res = ToolRegistry.execute({"tool": "Grep", "args": {"query": "FindMe", "directory": "sub3"}}, cwd)
        assert "No matches found" in res

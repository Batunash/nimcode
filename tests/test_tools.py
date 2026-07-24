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

def test_execute_replace_success(tmp_path):
    cwd = str(tmp_path)
    file_path = os.path.join(cwd, "test.txt")
    with open(file_path, "w") as f:
        f.write("A B C\n1 2 3")
        
    res = ToolRegistry.execute({
        "tool": "Replace", 
        "args": {
            "file_path": "test.txt", 
            "replacements": [
                {"old_string": "B", "new_string": "X"},
                {"old_string": "2", "new_string": "Y"}
            ]
        }
    }, cwd)
    
    assert "Successfully applied 2 replacements" in res
    with open(file_path, "r") as f:
        assert f.read() == "A X C\n1 Y 3"

def test_execute_replace_not_found(tmp_path):
    cwd = str(tmp_path)
    file_path = os.path.join(cwd, "test.txt")
    with open(file_path, "w") as f:
        f.write("A B C")
        
    res = ToolRegistry.execute({
        "tool": "Replace", 
        "args": {
            "file_path": "test.txt", 
            "replacements": [{"old_string": "D", "new_string": "X"}]
        }
    }, cwd)
    assert "ToolError" in res
    assert "Target string not found" in res

def test_execute_replace_ambiguous(tmp_path):
    cwd = str(tmp_path)
    file_path = os.path.join(cwd, "test.txt")
    with open(file_path, "w") as f:
        f.write("A B B C")
        
    res = ToolRegistry.execute({
        "tool": "Replace", 
        "args": {
            "file_path": "test.txt",
            "replacements": [{"old_string": "B", "new_string": "X"}]
        }
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

def test_execute_replace_file_not_found(tmp_path):
    cwd = str(tmp_path)
    res = ToolRegistry.execute({"tool": "Replace", "args": {"file_path": "missing.txt", "replacements": [{"old_string": "a", "new_string": "b"}]}}, cwd)
    assert "Error" in res or "ToolError" in res

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



def test_execute_undo(tmp_path):
    cwd = str(tmp_path)
    file_path = os.path.join(cwd, "test.txt")
    with open(file_path, "w") as f:
        f.write("A B C")
        
    # First, apply a replace
    ToolRegistry.execute({
        "tool": "Replace", 
        "args": {
            "file_path": "test.txt", 
            "replacements": [{"old_string": "B", "new_string": "X"}]
        }
    }, cwd)
    
    with open(file_path, "r") as f:
        assert f.read() == "A X C"
        
    # Now undo
    res = ToolRegistry._execute_undo(cwd)
    assert "Successfully reverted" in res
    
    # Check if reverted
    with open(file_path, "r") as f:
        assert f.read() == "A B C"

def test_execute_start_terminal():
    from unittest.mock import patch, MagicMock
    from nimcode.tools import ToolRegistry
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.stdout.readline.return_value = ''
        mock_popen.return_value = mock_proc
        res = ToolRegistry.execute({"tool": "StartTerminal", "args": {"command": "cmd", "term_id": "t1"}})
        assert "Started terminal 't1'" in res

def test_execute_terminal_input():
    from unittest.mock import MagicMock
    from nimcode.tools import ToolRegistry
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_queue = MagicMock()
    mock_queue.empty.side_effect = [False, True]
    mock_queue.get_nowait.return_value = "hello"
    ToolRegistry._ACTIVE_TERMINALS["t1"] = {"proc": mock_proc, "queue": mock_queue}
    res = ToolRegistry.execute({"tool": "TerminalInput", "args": {"term_id": "t1", "text": "ls"}})
    assert "Input sent. Output:" in res
    
    # Test unknown terminal
    res2 = ToolRegistry.execute({"tool": "TerminalInput", "args": {"term_id": "t2", "text": "ls"}})
    assert "not found" in res2

def test_execute_browse_web():
    from unittest.mock import patch, MagicMock, AsyncMock
    from nimcode.tools import ToolRegistry
    import sys
    
    pw_mock = MagicMock()
    pw_sync_mock = MagicMock()
    
    class FakeBrowser:
        def new_page(self):
            page = MagicMock()
            page.screenshot.return_value = b"fake_image"
            page.evaluate.return_value = "Fake Text"
            return page
        def close(self): pass
            
    class FakePlaywrightContextManager:
        def __enter__(self):
            p = MagicMock()
            p.chromium.launch.return_value = FakeBrowser()
            return p
        def __exit__(self, *args): pass
        
    pw_sync_mock.sync_playwright.return_value = FakePlaywrightContextManager()
    sys.modules['playwright'] = pw_mock
    sys.modules['playwright.sync_api'] = pw_sync_mock
    
    with patch("nimcode.nim_client.NimClient.chat_vision", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = "Fake Vision Result"
        with patch("os.environ.get", return_value="fake_key"):
            res = ToolRegistry.execute({"tool": "BrowseWeb", "args": {"url": "http://example.com", "goal": "Extract text"}})
            assert "Visual Analysis" in res

def test_execute_read_architecture(tmp_path):
    cwd = str(tmp_path)
    from nimcode.tools import ToolRegistry
    res = ToolRegistry.execute({"tool": "ReadArchitecture", "args": {"directory": "."}}, cwd)
    assert isinstance(res, str)

def test_execute_symbol_search(tmp_path):
    cwd = str(tmp_path)
    file_path = os.path.join(cwd, "test.py")
    with open(file_path, "w") as f:
        f.write("def search_me():\n    pass\n")
    from nimcode.tools import ToolRegistry
    res = ToolRegistry.execute({"tool": "SymbolSearch", "args": {"symbol_name": "search_me", "directory": "."}}, cwd)
    assert "search_me" in res
    
    res2 = ToolRegistry.execute({"tool": "SymbolSearch", "args": {"symbol_name": "not_found", "directory": "."}}, cwd)
    assert "No definition found" in res2

def test_execute_semantic_search():
    from nimcode.tools import ToolRegistry
    from unittest.mock import patch, MagicMock
    
    with patch("nimcode.rag.LightweightRAG") as MockRag:
        mock_instance = MagicMock()
        mock_instance.search.return_value = [("fake_path.py", 5.0, "snippet")]
        MockRag.return_value = mock_instance
        
        # Reset any existing indexer to force instantiation
        ToolRegistry._RAG_INDEXER = None
        
        res = ToolRegistry.execute({"tool": "SemanticSearch", "args": {"query": "hello"}})
        assert "fake_path.py" in res
        assert "snippet" in res

def test_execute_ask_question():
    from unittest.mock import patch
    import sys
    from nimcode.tools import ToolRegistry
    
    # Interactive with options
    with patch("sys.stdin.isatty", return_value=True):
        with patch("rich.prompt.Prompt.ask", return_value="1"):
            res = ToolRegistry.execute({"tool": "AskQuestion", "args": {"question": "Q?", "options": ["A", "B"]}})
            assert "A" in res
            
    # Interactive no options
    with patch("sys.stdin.isatty", return_value=True):
        with patch("rich.prompt.Prompt.ask", return_value="My answer"):
            res = ToolRegistry.execute({"tool": "AskQuestion", "args": {"question": "Q?"}})
            assert "My answer" in res
            
    # Non-interactive
    with patch("sys.stdin.isatty", return_value=False):
        res = ToolRegistry.execute({"tool": "AskQuestion", "args": {"question": "Q?"}})
        assert "non-interactive" in res

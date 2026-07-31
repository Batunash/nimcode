import pytest
from nimcode.tools import ToolRegistry

def test_ast_blocker_rejects_pass():
    content = "def test():\n    pass\n"
    
    # execute returns a string that starts with 'ToolError:' if a ToolError is raised internally
    out = ToolRegistry.execute({
        "tool": "Write",
        "args": {
            "file_path": "dummy.py",
            "content": content
        }
    }, cwd=".")
    
    assert "ToolError" in out
    assert "Validation Error" in out
    assert "Lazy code detected" in out

def test_ast_blocker_rejects_todo():
    content = "// TODO: implement feature"
    
    out = ToolRegistry.execute({
        "tool": "Write",
        "args": {
            "file_path": "dummy.js",
            "content": content
        }
    }, cwd=".")
    
    assert "ToolError" in out
    assert "Lazy code detected" in out

def test_ast_blocker_allows_valid_code():
    content = "def test():\n    print('Hello World')\n"
    
    # We mock os.path.join to prevent it from actually trying to write if we don't want it to,
    # or we can let it write to a temp directory.
    # Actually, the file size check or open check might fail if dummy is not a real path,
    # but the lazy check happens *before* the file is written. 
    # If the file doesn't exist, the write proceeds. To avoid side-effects, let's just 
    # call _check_lazy_code directly.

    try:
        ToolRegistry._check_lazy_code(content, "dummy.py")
        assert True
    except Exception:
        pytest.fail("_check_lazy_code raised an exception on valid code")

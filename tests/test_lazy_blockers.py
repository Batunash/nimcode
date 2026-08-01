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

def test_ast_deletion_blocker():
    old_content = '''
def func1(): pass
def func2(): pass
def func3(): pass
    '''
    new_content = '''
def func1(): pass
    '''
    # We deleted 2 functions out of 3, this should trigger the AST deletion blocker
    try:
        ToolRegistry._check_ast_deletion(old_content, new_content, "dummy.py")
        pytest.fail("Failed to block massive code deletion")
    except Exception as e:
        assert "Validation Error: Massive code deletion detected" in str(e)

def test_strict_markdown_validator():
    # Too short
    out = ToolRegistry.execute({"tool": "TaskCreate", "args": {"task_id": "1", "subject": "S", "description": "Short"}}, cwd=".")
    assert "Validation Error: Task description is too short" in out
    
    # Missing sections
    long_desc = "x" * 200
    out = ToolRegistry.execute({"tool": "TaskCreate", "args": {"task_id": "1", "subject": "S", "description": long_desc}}, cwd=".")
    assert "missing required markdown sections" in out
    
    # Valid
    valid_desc = "x" * 150 + "Target Files\nImplementation Details\nChecklist\nAcceptance Criteria\nTests"
    # Execute will try to create the task, which might succeed or say already exists, but won't raise ToolError
    out = ToolRegistry.execute({"tool": "TaskCreate", "args": {"task_id": "test_valid", "subject": "S", "description": valid_desc}}, cwd=".")
    assert "Validation Error" not in out

def test_ast_blocker_rejects_ellipsis():
    content = "def test():\n    ...\n"
    try:
        ToolRegistry._check_lazy_code(content, "dummy.py")
        pytest.fail("Failed to block Ellipsis")
    except Exception as e:
        assert "Lazy code detected" in str(e)

def test_regex_blocker_rejects_rest_of_code():
    content = "def test():\n    print('test')\n# rest of the code remains unchanged\n"
    try:
        ToolRegistry._check_lazy_code(content, "dummy.py")
        pytest.fail("Failed to block 'rest of the code'")
    except Exception as e:
        assert "Lazy code detected" in str(e)

def test_regex_blocker_rejects_ellipsis_comment():
    content = "def test():\n    print('test')\n# ...\n"
    try:
        ToolRegistry._check_lazy_code(content, "dummy.py")
        pytest.fail("Failed to block '# ...'")
    except Exception as e:
        assert "Lazy code detected" in str(e)
        
def test_regex_blocker_rejects_logic_goes_here():
    content = "def test():\n    # logic goes here\n"
    try:
        ToolRegistry._check_lazy_code(content, "dummy.py")
        pytest.fail("Failed to block 'logic goes here'")
    except Exception as e:
        assert "Lazy code detected" in str(e)

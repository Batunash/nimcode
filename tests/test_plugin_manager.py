import pytest
import os
import tempfile
from unittest.mock import MagicMock
from nimcode.plugin_manager import PluginManager

@pytest.fixture
def temp_plugins_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d

def test_load_and_execute_plugin(temp_plugins_dir):
    plugin_code = """
def register_commands():
    return {"hello": lambda args, agent: f"Hello {args} from plugin"}
"""
    with open(os.path.join(temp_plugins_dir, "my_plugin.py"), "w") as f:
        f.write(plugin_code)
        
    manager = PluginManager(plugins_dir=temp_plugins_dir)
    manager.load_plugins()
    
    assert "hello" in manager.commands
    
    result = manager.execute_command("hello", "World", None)
    assert result == "Hello World from plugin"

def test_execute_unknown_plugin(temp_plugins_dir):
    manager = PluginManager(plugins_dir=temp_plugins_dir)
    result = manager.execute_command("unknown", "", None)
    assert "Unknown command" in result

def test_plugin_load_error(temp_plugins_dir):
    # Syntax error plugin
    with open(os.path.join(temp_plugins_dir, "bad_plugin.py"), "w") as f:
        f.write("def bad syntax((")
        
    manager = PluginManager(plugins_dir=temp_plugins_dir)
    manager.load_plugins() # Should not raise
    assert len(manager.commands) == 0

def test_plugin_execute_error(temp_plugins_dir):
    plugin_code = """
def register_commands():
    return {"fail": lambda args, agent: 1/0}
"""
    with open(os.path.join(temp_plugins_dir, "fail_plugin.py"), "w") as f:
        f.write(plugin_code)
        
    manager = PluginManager(plugins_dir=temp_plugins_dir)
    manager.load_plugins()
    result = manager.execute_command("fail", "", None)
    assert "Plugin Error" in result

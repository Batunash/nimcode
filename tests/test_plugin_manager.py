import os
from nimcode.plugin_manager import PluginManager

def test_plugin_manager_loads_plugin(tmp_path):
    plugins_dir = os.path.join(tmp_path, "plugins")
    os.makedirs(plugins_dir)
    
    plugin_content = """
def handle_test(args, agent):
    return f"Test: {args}"

def register_commands():
    return {"testcmd": handle_test}
"""
    with open(os.path.join(plugins_dir, "test_plugin.py"), "w") as f:
        f.write(plugin_content)
        
    pm = PluginManager(plugins_dir=plugins_dir)
    cmds = pm.get_command_names()
    assert "testcmd" in cmds
    
    result = pm.execute_command("testcmd", "hello world", None)
    assert result == "Test: hello world"
    
def test_plugin_manager_invalid_plugin(tmp_path):
    plugins_dir = os.path.join(tmp_path, "plugins")
    os.makedirs(plugins_dir)
    
    plugin_content = "def invalid_syntax("
    with open(os.path.join(plugins_dir, "bad_plugin.py"), "w") as f:
        f.write(plugin_content)
        
    pm = PluginManager(plugins_dir=plugins_dir)
    cmds = pm.get_command_names()
    assert len(cmds) == 0

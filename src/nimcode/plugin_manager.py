import os
import importlib.util
import logging
from typing import Dict, Any, Callable

logger = logging.getLogger(__name__)

class PluginManager:
    def __init__(self, plugins_dir: str = ".nimcode/plugins"):
        self.plugins_dir = os.path.abspath(plugins_dir)
        self.commands: Dict[str, Callable] = {}
        self.load_plugins()

    def load_plugins(self):
        """Scans the plugins directory and loads all python files as plugins."""
        if not os.path.exists(self.plugins_dir):
            return

        for filename in os.listdir(self.plugins_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                plugin_path = os.path.join(self.plugins_dir, filename)
                module_name = filename[:-3]
                
                try:
                    spec = importlib.util.spec_from_file_location(module_name, plugin_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        # Register commands from the plugin
                        if hasattr(module, "register_commands"):
                            plugin_commands = module.register_commands()
                            for cmd_name, cmd_func in plugin_commands.items():
                                self.commands[cmd_name] = cmd_func
                                logger.info(f"Registered plugin command: {cmd_name}")
                except Exception as e:
                    logger.error(f"Failed to load plugin {filename}: {e}")

    def execute_command(self, command_name: str, args: str, agent: Any) -> str:
        """Executes a registered plugin command."""
        if command_name in self.commands:
            try:
                # The command function should take (args, agent) and return a string
                result = self.commands[command_name](args, agent)
                return str(result) if result else ""
            except Exception as e:
                logger.error(f"Error executing plugin command {command_name}: {e}")
                return f"Plugin Error: {e}"
        return f"Unknown command: {command_name}"

    def get_command_names(self) -> list:
        """Returns a list of registered command names."""
        return list(self.commands.keys())

import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def load_settings() -> Dict[str, Any]:
    """Loads configuration from ~/.nimcode/settings.json and .nimcode/settings.json"""
    settings = {
        "model": "meta/llama-3.1-70b-instruct",
        "mcp_servers": {}
    }
    
    # Global settings
    global_path = os.path.expanduser("~/.nimcode/settings.json")
    if os.path.exists(global_path):
        try:
            with open(global_path, "r", encoding="utf-8") as f:
                global_settings = json.load(f)
                settings.update(global_settings)
        except Exception as e:
            logger.error(f"Failed to load global settings: {e}")
            
    # Scrub legacy api_key if found to ensure it uses keyring
    if "api_key" in settings:
        import keyring
        try:
            if not keyring.get_password("nimcode", "api_key"):
                keyring.set_password("nimcode", "api_key", settings["api_key"])
            
            # Remove from file
            del settings["api_key"]
            with open(global_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
        except Exception:
            pass

    # Local settings
    local_path = os.path.join(os.getcwd(), ".nimcode", "settings.json")
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                local_settings = json.load(f)
                settings.update(local_settings)
        except Exception as e:
            logger.error(f"Failed to load local settings: {e}")

    return settings

def save_global_setting(key: str, value: Any) -> None:
    """Saves a setting to ~/.nimcode/settings.json"""
    global_dir = os.path.expanduser("~/.nimcode")
    os.makedirs(global_dir, exist_ok=True)
    global_path = os.path.join(global_dir, "settings.json")
    
    settings = {}
    if os.path.exists(global_path):
        try:
            with open(global_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            pass
            
    settings[key] = value
    
    with open(global_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def load_settings() -> Dict[str, Any]:
    """Loads configuration from ~/.nimcode/settings.json and .nimcode/settings.json"""
    settings = {
        "model": "deepseek-ai/deepseek-v4-pro",
        "api_base_url": "https://integrate.api.nvidia.com/v1",
        "mcp_servers": {},
        # Timeouts (0 = disabled/infinite)
        "timeout_command": 1200,    # Timeout for bash commands (seconds)
        "timeout_llm": 120,         # Timeout for LLM API calls (seconds)
        "timeout_format": 10,       # Timeout for formatting/linting tools (seconds)
        "timeout_browser": 15000,   # Timeout for browser actions (milliseconds)
        "timeout_updater": 3,       # Timeout for update checks (seconds)
        # Agent behavior
        "max_turns": 200,           # Max agent turns per session (0 = unlimited)
        "max_tokens": 120000,       # Token budget before auto-compact kicks in
        "max_retries": 15,          # Max LLM API retry attempts on transient errors
        "retry_base_delay": 2.0,    # Base delay for exponential backoff (seconds)
        "retry_max_delay": 60.0,    # Max delay cap for exponential backoff (seconds)
        # Security
        "allow_bash_non_interactive": False,  # Allow Bash in non-interactive (CI) mode
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

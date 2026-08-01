import logging
import os
import json
import urllib.request
import threading
import time

logger = logging.getLogger(__name__)

# Known NVIDIA NIM models and their context window sizes (in tokens)
# This acts as a fallback + enrichment layer when API is unavailable
MODEL_CONTEXT_WINDOWS = {
    # Llama 3.1 family
    "meta/llama-3.1-8b-instruct": 128000,
    "meta/llama-3.3-70b-instruct": 128000,
    "meta/llama-3.1-405b-instruct": 128000,
    # Llama 3.2 family
    "meta/llama-3.2-1b-instruct": 128000,
    "meta/llama-3.2-3b-instruct": 128000,
    "meta/llama-3.2-11b-vision-instruct": 128000,
    "meta/llama-3.2-90b-vision-instruct": 128000,
    # Llama 3.3 family
    "meta/llama-3.3-70b-instruct": 128000,
    # Nemotron
    "nvidia/nemotron-4-340b-instruct": 4096,
    "nvidia/llama-3.1-nemotron-70b-instruct": 128000,
    # Mistral
    "mistralai/mixtral-8x22b-instruct-v0.1": 65536,
    "mistralai/mistral-large-2-instruct": 128000,
    # DeepSeek
    "deepseek-ai/deepseek-r1": 128000,
    "deepseek-ai/deepseek-v4-pro": 128000,
    # Qwen
    "qwen/qwen2.5-72b-instruct": 128000,
    "qwen/qwq-32b": 128000,
}

# Default context window for unknown models
DEFAULT_CONTEXT_WINDOW = 8192

# Hardcoded fallback model list (used when API is unreachable)
FALLBACK_MODELS = [
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-8b-instruct",
    "meta/llama-3.1-405b-instruct",
    "meta/llama-3.3-70b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "deepseek-ai/deepseek-r1",
    "mistralai/mixtral-8x22b-instruct-v0.1",
    "qwen/qwen2.5-72b-instruct",
]

_CACHE_FILE = os.path.expanduser("~/.nimcode/model_contexts.json")
_CACHE_MAX_AGE_DAYS = 7
_DYNAMIC_CACHE = {}
_CACHE_LOADED = False
_UPDATE_THREAD_STARTED = False

def _fetch_and_cache_models():
    """Background task to fetch latest model info from LiteLLM."""
    url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 Nimcode/1.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            processed = {}
            for k, v in data.items():
                if isinstance(v, dict) and "max_tokens" in v and isinstance(v["max_tokens"], int):
                    processed[k] = v["max_tokens"]
                    basename = k.split("/")[-1]
                    if basename not in processed or processed[basename] < v["max_tokens"]:
                        processed[basename] = v["max_tokens"]
            
            os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(processed, f, indent=4)
                
            global _DYNAMIC_CACHE
            _DYNAMIC_CACHE.update(processed)
            logger.debug(f"Successfully cached {len(processed)} models from LiteLLM.")
    except Exception as e:
        logger.debug(f"Failed to fetch model contexts: {e}")

def _load_or_update_cache():
    """Loads cache from disk, spawns background update if old/missing."""
    global _CACHE_LOADED, _DYNAMIC_CACHE, _UPDATE_THREAD_STARTED
    if _CACHE_LOADED:
        return

    _CACHE_LOADED = True
    needs_update = True
    
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                _DYNAMIC_CACHE = json.load(f)
            
            # Check age
            mtime = os.path.getmtime(_CACHE_FILE)
            age_days = (time.time() - mtime) / (24 * 3600)
            if age_days < _CACHE_MAX_AGE_DAYS:
                needs_update = False
        except Exception as e:
            logger.debug(f"Error reading cache file: {e}")

    if needs_update and not _UPDATE_THREAD_STARTED:
        _UPDATE_THREAD_STARTED = True
        t = threading.Thread(target=_fetch_and_cache_models, daemon=True)
        t.start()

def get_context_window(model_id: str) -> int:
    """Returns the context window size for a given model ID."""
    _load_or_update_cache()
    
    # 1. Check hardcoded exact match
    if model_id in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[model_id]
        
    # 2. Check dynamic cache exact match
    if model_id in _DYNAMIC_CACHE:
        return _DYNAMIC_CACHE[model_id]
        
    # 3. Check dynamic cache basename match
    basename = model_id.split("/")[-1]
    if basename in _DYNAMIC_CACHE:
        return _DYNAMIC_CACHE[basename]
        
    return DEFAULT_CONTEXT_WINDOW

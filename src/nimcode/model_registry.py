"""
Model registry with context window sizes and metadata.
Used for auto-compact thresholds and dynamic model listing.
"""
import logging

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


def get_context_window(model_id: str) -> int:
    """Returns the context window size for a given model ID."""
    return MODEL_CONTEXT_WINDOWS.get(model_id, DEFAULT_CONTEXT_WINDOW)

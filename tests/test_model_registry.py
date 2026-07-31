"""Tests for the model_registry module."""
import pytest
from nimcode.model_registry import (
    MODEL_CONTEXT_WINDOWS,
    FALLBACK_MODELS,
    DEFAULT_CONTEXT_WINDOW,
    get_context_window,
)


def test_get_context_window_known_model():
    """Known models should return their specific context window size."""
    assert get_context_window("meta/llama-3.3-70b-instruct") == 128000
    assert get_context_window("nvidia/nemotron-4-340b-instruct") == 4096
    assert get_context_window("mistralai/mixtral-8x22b-instruct-v0.1") == 65536


def test_get_context_window_unknown_model():
    """Unknown models should return the default context window."""
    assert get_context_window("some/unknown-model") == DEFAULT_CONTEXT_WINDOW
    assert get_context_window("") == DEFAULT_CONTEXT_WINDOW


def test_fallback_models_not_empty():
    """Fallback model list should have entries."""
    assert len(FALLBACK_MODELS) > 0


def test_fallback_models_all_in_context_windows():
    """All fallback models should have a known context window entry."""
    for model in FALLBACK_MODELS:
        assert model in MODEL_CONTEXT_WINDOWS, f"Fallback model {model} missing from context windows"


def test_context_windows_positive():
    """All context window values should be positive integers."""
    for model, ctx in MODEL_CONTEXT_WINDOWS.items():
        assert isinstance(ctx, int) and ctx > 0, f"Invalid context window for {model}: {ctx}"

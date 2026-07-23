import pytest
import os
from nimcode.memory import MemoryManager

def test_count_tokens():
    assert MemoryManager.count_tokens("") == 0
    assert MemoryManager.count_tokens("1234") == 2
    assert MemoryManager.count_tokens("12345") == 2

def test_count_messages_tokens():
    messages = [
        {"role": "system", "content": "1234"},
        {"role": "user", "content": "12345678"}
    ]
    # 4 chars -> 2 tokens, 8 chars -> 3 tokens => 5 total
    assert MemoryManager.count_messages_tokens(messages) == 5


def test_compact_context_empty():
    manager = MemoryManager(max_tokens=-1)
    # This should trigger `if not messages: return messages` inside compact_context
    assert manager.compact_context([]) == []

def test_compact_context_no_change():
    manager = MemoryManager(max_tokens=100)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"}
    ]
    compacted = manager.compact_context(messages)
    assert len(compacted) == 2
    assert compacted == messages

def test_compact_context_drops_oldest():
    # max_tokens = 4 means around 12-15 chars max
    manager = MemoryManager(max_tokens=4) 
    messages = [
        {"role": "system", "content": "s"},          # 1 token
        {"role": "user", "content": "12345678"},     # 3 tokens
        {"role": "user", "content": "new"},          # 1 token
    ]
    # Total tokens = 5 > max(4). 
    # System takes 1. We start from end. "new" takes 1. Total 2.
    # Next is "12345678" takes 3. 2+3 = 5 > 4. So we drop it.
    compacted = manager.compact_context(messages)
    assert len(compacted) == 2
    assert compacted[0]["content"] == "s"
    assert compacted[1]["content"] == "new"

def test_compact_context_truncates_if_single_message_too_large():
    manager = MemoryManager(max_tokens=3)
    messages = [
        {"role": "system", "content": "s"},          # 1 token
        {"role": "user", "content": "1234567890"},   # 3 tokens
    ]
    # Total = 4 > max(3). 
    # System takes 1. Remaining allowed = 2 tokens (8 chars).
    # Since it's the only message kept, we truncate it.
    compacted = manager.compact_context(messages)
    assert len(compacted) == 2
    assert compacted[0]["content"] == "s"
    assert "TRUNCATED" in compacted[1]["content"]
    # 8 chars kept
    assert compacted[1]["content"].startswith("12345678")

def test_compact_context_empty():
    manager = MemoryManager(max_tokens=100)
    assert manager.compact_context([]) == []

def test_log_to_nimcode_md(tmp_path):
    cwd = str(tmp_path)
    MemoryManager.log_to_nimcode_md(1, "hello", "world", cwd)
    file_path = os.path.join(cwd, "NIMCODE.md")
    assert os.path.exists(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "## Turn 1" in content
    assert "**User**: hello" in content
    assert "**Agent**: world" in content

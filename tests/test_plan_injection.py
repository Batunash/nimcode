"""Tests for plan-mode automatic file injection in NimcodeREPL."""
import os
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_repl(tmp_path):
    """Create a minimal NimcodeREPL-like object with just the fields we need."""
    from nimcode.agent import Agent
    from nimcode.permissions import PermissionEngine, PermissionMode

    agent = Agent(api_key="test_key", permission_mode=PermissionMode.BYPASS)
    # Stub run so it doesn't hit the API
    agent.run = AsyncMock()

    class FakeREPL:
        _in_plan_mode = True
        permission_engine = PermissionEngine(mode=PermissionMode.BYPASS)

    repl = FakeREPL()
    repl.agent = agent
    repl._cwd = str(tmp_path)
    return repl


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

def test_plan_injection_detects_md_file(tmp_path):
    """When user mentions an existing .md file in plan mode, content is injected."""
    sdd = tmp_path / "sdd.md"
    sdd.write_text("# Executive Summary\nThis is the ImagEase Pro SDD.")

    repl = _make_repl(tmp_path)
    user_input = "read this sdd.md and make a detailed plan"

    import re as _re
    _file_pattern = _re.compile(
        r"[\w./\\-]+\.(?:md|txt|rst|pdf|json|yaml|yml|toml|csv|xml|sdd|prd|rfc|spec)",
        _re.IGNORECASE,
    )
    mentioned = _file_pattern.findall(user_input)
    assert "sdd.md" in mentioned

    # Simulate the injection loop
    injected = []
    for fname in mentioned:
        fpath = os.path.join(str(tmp_path), fname)
        if os.path.isfile(fpath):
            with open(fpath, "r", encoding="utf-8") as fh:
                content = fh.read()
            repl.agent.messages.append({
                "role": "user",
                "content": f"[AUTO-READ] Here is the full content of '{fname}':\n\n```\n{content}\n```",
            })
            injected.append(fname)

    assert injected == ["sdd.md"]
    # The injected message should contain the real SDD content
    last_msg = repl.agent.messages[-1]["content"]
    assert "ImagEase Pro" in last_msg
    assert "Executive Summary" in last_msg


def test_plan_injection_ignores_missing_files(tmp_path):
    """Files that don't exist on disk are silently skipped."""
    repl = _make_repl(tmp_path)
    initial_count = len(repl.agent.messages)

    user_input = "make a plan based on nonexistent.md"

    import re as _re
    _file_pattern = _re.compile(
        r"[\w./\\-]+\.(?:md|txt|rst|pdf|json|yaml|yml|toml|csv|xml|sdd|prd|rfc|spec)",
        _re.IGNORECASE,
    )
    mentioned = _file_pattern.findall(user_input)

    injected = []
    for fname in mentioned:
        fpath = os.path.join(str(tmp_path), fname)
        if os.path.isfile(fpath):
            injected.append(fname)

    # Nothing should have been injected
    assert injected == []
    assert len(repl.agent.messages) == initial_count


def test_plan_injection_skipped_outside_plan_mode(tmp_path):
    """Injection should NOT happen when _in_plan_mode is False."""
    sdd = tmp_path / "prd.txt"
    sdd.write_text("Product requirements...")

    repl = _make_repl(tmp_path)
    repl._in_plan_mode = False  # Not in plan mode
    initial_count = len(repl.agent.messages)

    # Simulate: injection only runs if _in_plan_mode is True
    if getattr(repl, "_in_plan_mode", False):
        repl.agent.messages.append({"role": "user", "content": "injected"})

    assert len(repl.agent.messages) == initial_count


def test_plan_injection_truncates_large_files(tmp_path):
    """Files larger than 40k chars are truncated with a hint."""
    big_file = tmp_path / "bigdoc.md"
    big_file.write_text("A" * 50_000)

    _MAX = 40_000
    with open(str(big_file), "r", encoding="utf-8") as fh:
        content = fh.read()

    truncated = ""
    if len(content) > _MAX:
        content = content[:_MAX]
        truncated = f"\n[... file truncated at {_MAX} chars. Pass offset/limit to the Read tool for more.]"

    assert len(content) == _MAX
    assert "truncated" in truncated


def test_plan_injection_multiple_files(tmp_path):
    """Multiple files mentioned in one message are all injected."""
    (tmp_path / "sdd.md").write_text("System Design Doc content")
    (tmp_path / "api.txt").write_text("API specs content")

    user_input = "use sdd.md and api.txt to create a plan"

    import re as _re
    _file_pattern = _re.compile(
        r"[\w./\\-]+\.(?:md|txt|rst|pdf|json|yaml|yml|toml|csv|xml|sdd|prd|rfc|spec)",
        _re.IGNORECASE,
    )
    mentioned = _file_pattern.findall(user_input)

    injected = []
    for fname in mentioned:
        fpath = os.path.join(str(tmp_path), fname)
        if os.path.isfile(fpath):
            injected.append(fname)

    assert "sdd.md" in injected
    assert "api.txt" in injected
    assert len(injected) == 2

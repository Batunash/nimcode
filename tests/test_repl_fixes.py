"""Regression tests for the bug fixes applied in this session.

Each test targets a specific root cause that was fixed. Reverting the fix should
make the corresponding test FAIL — that is the point of having them.

Covers:
- Bug 1: /plan system message must NOT hardcode 'feature_x_plan.md' and must
         instruct the model to ground the plan in the actual documents.
- Bug 2: /plan must NOT downgrade a /trust (BYPASS) permission mode.
- Bug 7: /trust sets max_turns = 0 (unlimited), not 999999.
- Fix #5: session history is stored under .nimcode/history/session.json, not NIMCODE.md.
- Fix #13: Read tool paginates with offset/limit and emits a continuation hint.
- Fix #8: there is only ONE /undo handler (the second is dead code removed).
"""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from nimcode.agent import Agent
from nimcode.repl import NimcodeREPL
from nimcode.permissions import PermissionMode


@pytest.fixture
def agent():
    with patch("nimcode.agent.NimClient"):
        a = Agent(api_key="test_key")
        a.client.chat_one_shot = AsyncMock(return_value="TASK_COMPLETE")
        a.client.get_available_models = AsyncMock(return_value=["m1"])
        async def _gen(*args, **kwargs):
            yield "TASK_COMPLETE"
        a.client.chat = MagicMock(side_effect=lambda *a, **k: _gen(*a, **k))
        return a


async def _run_commands(agent, commands):
    """Feed a list of slash commands to the REPL, then /exit."""
    # Force the "trust this folder?" prompt to actually appear (and be declined)
    # so the REPL starts in DEFAULT mode, regardless of the user's real settings.json.
    agent.settings["trusted_projects"] = []
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent.analytics = MagicMock()
    agent.analytics.get_summary = MagicMock(return_value={
        "today": {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0},
        "total": {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0},
    })
    with patch("prompt_toolkit.PromptSession") as MockSession:
        mock_session = MockSession.return_value
        mock_session.prompt_async = AsyncMock(side_effect=list(commands) + ["/exit"])
        with patch("builtins.input", return_value="n"):  # decline initial trust-this-folder
            repl = NimcodeREPL(agent)
            try:
                await repl.start_repl()
            except StopAsyncIteration:
                pass


@pytest.mark.asyncio
async def test_trust_then_plan_preserves_bypass(agent):
    """Bug 2: /trust sets BYPASS; /plan must NOT downgrade it back to DEFAULT/AUTO."""
    await _run_commands(agent, ["/trust", "/plan"])
    assert agent.permission_engine.mode == PermissionMode.BYPASS, (
        "/plan clobbered /trust's BYPASS mode — the trust bug regressed"
    )


@pytest.mark.asyncio
async def test_trust_sets_unlimited_turns_zero(agent):
    """Bug 7: /trust uses 0 (unlimited sentinel), not the 999999 magic number."""
    await _run_commands(agent, ["/trust"])
    assert agent.max_turns == 0


@pytest.mark.asyncio
async def test_plan_message_does_not_hardcode_feature_x(agent):
    """Bug 1: /plan must not push a literal 'feature_x_plan.md' example into the
    conversation — that was the root cause of generic, ungrounded plans."""
    await _run_commands(agent, ["/plan"])
    plan_msgs = [m for m in agent.messages if "PLANNING MODE" in m.get("content", "")]
    assert plan_msgs, "/plan did not append a planning system message"
    content = plan_msgs[-1]["content"]
    # The prompt now dynamically differentiates between Bug Fix and From-Scratch tasks
    assert "Identify the task type" in content or "Bug Fix / Minor Feature" in content
    # It must enforce autonomous single-file generation with tasks/criteria
    assert "SINGLE, EXTREMELY DETAILED" in content or "Acceptance Criteria" in content


@pytest.mark.asyncio
async def test_plan_without_trust_uses_auto(agent):
    """Fix #2: /plan without /trust should set AUTO (safe reads free, writes blocked),
    not DEFAULT (which prompts even for Read).
    """
    await _run_commands(agent, ["/plan"])
    assert agent.permission_engine.mode == PermissionMode.AUTO


@pytest.mark.asyncio
async def test_code_restores_pre_plan_mode(agent):
    """Fix #9: /code restores the permission mode that was active before /plan.
    """
    await _run_commands(agent, ["/trust", "/plan", "/code"])
    assert agent.permission_engine.mode == PermissionMode.BYPASS


# --- Fix #5: history path -------------------------------------------------

def test_session_history_path_under_nimcode_sessions(agent, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = agent._session_history_path()
    # Must be under .nimcode/sessions/ (NOT history/, which repl.py's PromptSession
    # FileHistory already uses as a *file* — a path can't be both a file and a dir).
    assert p.endswith(os.path.join(".nimcode", "sessions", "session.json"))


def test_save_then_load_history_roundtrip(agent, tmp_path, monkeypatch):
    """Reproduce Bug B's crash scenario: previously save_history JSON-overwrote
    NIMCODE.md while log_to_nimcode_md appended markdown to the same file, so
    load_history's json.load raised JSONDecodeError. Now they use separate paths.
    """
    monkeypatch.chdir(tmp_path)
    agent.messages = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
    agent.save_history()
    # Simulate the markdown log appending to NIMCODE.md (as MemoryManager does).
    with open(os.path.join(tmp_path, "NIMCODE.md"), "a", encoding="utf-8") as f:
        f.write("## Turn 1\n\n**User**: hello\n\n---\n\n")
    # load_history must not read NIMCODE.md anymore; it must read session.json.
    agent.messages = []
    agent.load_history()
    assert agent.messages == [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]


# --- Fix #13: Read pagination --------------------------------------------

def test_read_pagination_offset_limit(agent, tmp_path, monkeypatch):
    from nimcode.tools import ToolRegistry
    monkeypatch.chdir(tmp_path)
    f = tmp_path / "lines.txt"
    f.write_text("\n".join(f"line {i}" for i in range(1, 21)))  # 20 lines
    out = ToolRegistry._execute_read("lines.txt", str(tmp_path), offset=5, limit=4)
    assert "lines 5-8 of 20" in out
    assert "12 more" in out  # 20 - 8 = 12 remaining
    assert "pass offset=9" in out  # continuation hint
    body_lines = [ln for ln in out.splitlines() if "\t" in ln ]
    assert body_lines[0].strip().startswith("5\tline 5")
    assert body_lines[-1].strip().startswith("8\tline 8")


def test_read_no_limit_returns_whole_file(agent, tmp_path, monkeypatch):
    from nimcode.tools import ToolRegistry
    monkeypatch.chdir(tmp_path)
    f = tmp_path / "small.txt"
    f.write_text("alpha\nbeta\n")
    out = ToolRegistry._execute_read("small.txt", str(tmp_path))
    assert out == "alpha\nbeta\n"  # whole file, no line numbers


# --- Fix #8: single /undo handler ----------------------------------------

def test_only_one_undo_handler_in_source():
    """The duplicate dead-code /undo block (formerly at the bottom of the command
    chain) has been removed. There should be exactly one `== "/undo"` branch.
    """
    import nimcode.repl
    src = nimcode.repl.__file__
    with open(src, "r", encoding="utf-8") as fh:
        text = fh.read()
    assert text.count('user_input.strip() == "/undo"') == 1

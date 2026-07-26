import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from nimcode.repl import NimcodeREPL
from nimcode.agent import Agent

@pytest.fixture
def agent():
    with patch("nimcode.agent.NimClient"):
        a = Agent(api_key="test_key")
        a.client.chat_one_shot = AsyncMock(return_value="I am done. TASK_COMPLETE")
        a.client.get_available_models = AsyncMock(return_value=["model1", "model2"])
        a.client.chat = MagicMock()
        return a

def test_repl_properties(agent):
    repl = NimcodeREPL(agent)
    assert repl.mcp == agent.mcp

@pytest.mark.asyncio
async def test_repl_coverage_display(agent):
    # Test coverage display calculation
    with patch("coverage.Coverage") as MockCov:
        mock_cov_instance = MockCov.return_value
        mock_cov_instance.report.return_value = 60.5  # middle coverage -> yellow
        
        # we just want to hit start_repl to execute the coverage part
        commands = ["/exit"]
        with patch("prompt_toolkit.PromptSession") as MockSession:
            mock_session = MockSession.return_value
            mock_session.prompt_async = AsyncMock(side_effect=commands)
            with patch("builtins.input", return_value="y"):
                repl = NimcodeREPL(agent)
                try:
                    await repl.start_repl()
                except StopAsyncIteration:
                    pass

@pytest.mark.asyncio
async def test_repl_history_dir_missing(agent):
    commands = ["/exit"]
    with patch("os.path.exists", return_value=False):
        with patch("os.makedirs") as mock_makedirs:
            with patch("prompt_toolkit.PromptSession") as MockSession:
                mock_session = MockSession.return_value
                mock_session.prompt_async = AsyncMock(side_effect=commands)
                with patch("builtins.input", return_value="y"):
                    repl = NimcodeREPL(agent)
                    try:
                        await repl.start_repl()
                    except StopAsyncIteration:
                        pass
            # Intent: when '.nimcode' is missing, the REPL bootstraps it. We assert
            # the project `.nimcode` dir is created, without pinning an exact call
            # count — save_history (on `/exit`) also creates `.nimcode/sessions/`
            # for the serialized session, which is legitimate expected behavior.
            project_nimcode = os.path.join(os.getcwd(), ".nimcode")
            mock_makedirs.assert_any_call(project_nimcode, exist_ok=True)
            assert mock_makedirs.call_count >= 1

@pytest.mark.asyncio
async def test_repl_exceptions_in_loop(agent):
    commands = [KeyboardInterrupt, EOFError, "/exit"]
    with patch("prompt_toolkit.PromptSession") as MockSession:
        mock_session = MockSession.return_value
        mock_session.prompt_async = AsyncMock(side_effect=commands)
        with patch("builtins.input", return_value="y"):
            repl = NimcodeREPL(agent)
            try:
                await repl.start_repl()
            except StopAsyncIteration:
                pass

@pytest.mark.asyncio
async def test_repl_teleport_success(agent):
    commands = ["/teleport .", "/exit"]
    with patch("prompt_toolkit.PromptSession") as MockSession:
        mock_session = MockSession.return_value
        mock_session.prompt_async = AsyncMock(side_effect=commands)
        with patch("builtins.input", return_value="y"):
            repl = NimcodeREPL(agent)
            try:
                await repl.start_repl()
            except StopAsyncIteration:
                pass

@pytest.mark.asyncio
async def test_repl_buddy_missing_arg(agent):
    commands = ["/buddy", "/exit"]
    with patch("prompt_toolkit.PromptSession") as MockSession:
        mock_session = MockSession.return_value
        mock_session.prompt_async = AsyncMock(side_effect=commands)
        with patch("builtins.input", return_value="y"):
            repl = NimcodeREPL(agent)
            try:
                await repl.start_repl()
            except StopAsyncIteration:
                pass

@pytest.mark.asyncio
async def test_repl_effort_validation(agent):
    commands = ["/effort Invalid", "/effort High", "/exit"]
    with patch("prompt_toolkit.PromptSession") as MockSession:
        mock_session = MockSession.return_value
        mock_session.prompt_async = AsyncMock(side_effect=commands)
        with patch("builtins.input", return_value="y"):
            repl = NimcodeREPL(agent)
            try:
                await repl.start_repl()
            except StopAsyncIteration:
                pass

@pytest.mark.asyncio
async def test_repl_thinking_toggle(agent):
    commands = ["/thinking", "/thinking", "/exit"]
    with patch("prompt_toolkit.PromptSession") as MockSession:
        mock_session = MockSession.return_value
        mock_session.prompt_async = AsyncMock(side_effect=commands)
        with patch("builtins.input", return_value="y"):
            repl = NimcodeREPL(agent)
            try:
                await repl.start_repl()
            except StopAsyncIteration:
                pass

@pytest.mark.asyncio
async def test_repl_testgen_and_vision_and_others(agent):
    commands = ["/testgen my_file.py", "/vision", "/mcp install npx xxx", "/exit"]
    with patch("prompt_toolkit.PromptSession") as MockSession:
        mock_session = MockSession.return_value
        mock_session.prompt_async = AsyncMock(side_effect=commands)
        with patch("builtins.input", return_value="y"):
            # Mock pyautogui and chat_vision for vision
            import sys
            sys.modules['pyautogui'] = MagicMock()
            repl = NimcodeREPL(agent)
            try:
                await repl.start_repl()
            except StopAsyncIteration:
                pass
            sys.modules.pop('pyautogui', None)


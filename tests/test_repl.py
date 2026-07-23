import pytest
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
from nimcode.agent import Agent

@pytest.fixture
def agent():
    with patch("nimcode.agent.NimClient") as mock_client:
        a = Agent(api_key="test_key")
        # Ensure we have a mock for chat_one_shot and chat
        a.client.chat_one_shot = AsyncMock(return_value="I am done. TASK_COMPLETE")
        a.client.get_available_models = AsyncMock(return_value=["model1", "model2"])
        
        async def mock_chat_generator(*args, **kwargs):
            yield "Hello"
            yield " World"
        a.client.chat = MagicMock(side_effect=lambda *args, **kwargs: mock_chat_generator(*args, **kwargs))
        return a

def test_save_load_history(agent):
    agent.messages = [{"role": "user", "content": "hello"}]
    with patch("builtins.open", MagicMock()) as mock_file:
        with patch("json.dump") as mock_dump:
            agent.save_history()
            mock_dump.assert_called_once()
            
def test_save_history_error(agent):
    with patch("builtins.open", side_effect=Exception("Save error")):
        with patch("nimcode.agent.logger.error") as mock_log:
            agent.save_history()
            mock_log.assert_called_once()

def test_load_history(agent):
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", MagicMock()):
            with patch("json.load", return_value=[{"role": "user", "content": "hi"}]):
                agent.load_history()
                assert len(agent.messages) == 1
                assert agent.messages[0]["content"] == "hi"

def test_load_history_error(agent):
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", side_effect=Exception("Load error")):
            with patch("nimcode.agent.logger.error") as mock_log:
                agent.load_history()
                mock_log.assert_called_once()

@pytest.mark.asyncio
async def test_run_complete(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    
    agent._stream_response = AsyncMock(return_value="TASK_COMPLETE")
    
    await agent.run(initial_prompt="Do task")
    assert agent.messages[-1]["content"] == "TASK_COMPLETE"

@pytest.mark.asyncio
async def test_run_error(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    
    agent._stream_response = AsyncMock(side_effect=Exception("Stream error"))
    
    await agent.run(initial_prompt="Do task")
    agent._stream_response.assert_called_once()

@pytest.mark.asyncio
async def test_run_tool_call(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    
    agent._stream_response = AsyncMock(side_effect=["<tool_call>{\"tool\": \"Bash\", \"args\": {}}</tool_call>", "TASK_COMPLETE"])
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.return_value = ("prose", [{"tool": "Bash", "args": {}}])
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=False):
            await agent.run(initial_prompt="Do task")

@pytest.mark.asyncio
async def test_stream_response_success(agent):
    async def mock_chat_generator(msgs):
        yield "Hello"
        yield " World"
    agent.client.chat = mock_chat_generator
    
    res = await agent._stream_response()
    assert res == "Hello World"
    
@pytest.mark.asyncio
async def test_stream_response_empty(agent):
    async def empty_gen(msgs):
        if False: yield ""
    agent.client.chat.return_value = empty_gen([])
    res = await agent._stream_response()
    assert res == ""

@pytest.mark.asyncio
async def test_stream_response_interrupt(agent):
    async def interrupt_gen(msgs):
        raise KeyboardInterrupt()
        yield ""
    agent.client.chat.return_value = interrupt_gen([])
    res = await agent._stream_response()
    assert res == ""

@pytest.mark.asyncio
async def test_start_repl_exit(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    with patch("prompt_toolkit.PromptSession") as MockSession:
        mock_session = MockSession.return_value
        mock_session.prompt_async = AsyncMock(side_effect=["/exit"])
        with patch("builtins.input", return_value="y"):
            from nimcode.repl import NimcodeREPL
            repl = NimcodeREPL(agent)
            await repl.start_repl()

@pytest.mark.asyncio
async def test_start_repl_commands(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    
    # We will feed all commands one by one, then /exit
    commands = [
        "/help",
        "/models",
        "/compact",
        "/clear",
        "/history",
        "/save",
        "/load",
        "/tokens",
        "/config",
        "/theme monokai",
        "/theme",
        "/code",
        "/grill-me",
        "/decompile target",
        "/sql-tune",
        "/terraform-god",
        "/autofix-pr",
        "/thinkback",
        "/guardian",
        "/graph",
        "/review",
        "/commit",
        "/undo",
        "/plan",
        "/teleport target",
        "/teleport",
        "/buddy",
        "/ultraplan",
        "/bughunter",
        "/security-review",
        "/doctor",
        "/swarm",
        "/tdd",
        "/research",
        "/mcp install xxx",
        "/cost",
        "/effort High",
        "/thinking",
        "/testgen",
        "/vision",
        "/voice",
        "/index",
        "/fix",
        "/rewind",
        "/fork",
        "/permissions bypass",
        "/permissions auto",
        "/permissions default",
        "/permissions",
        "dummy_command",
        "/exit"
    ]
    
    with patch("prompt_toolkit.PromptSession") as MockSession:
        mock_session = MockSession.return_value
        mock_session.prompt_async = AsyncMock(side_effect=commands)
        
        with patch("nimcode.agent.Agent._distill_memory", new_callable=AsyncMock) as mock_distill:
            mock_distill.return_value = []
            with patch("builtins.input", return_value="n"): # not trust project initially to trigger prompt
                # Mock get_available_models to avoid TypeError
                agent.client.get_available_models = AsyncMock(return_value=["model1", "model2"])
                # Mock run to avoid actually executing queries
                agent.run = AsyncMock()
                
                class MockDialog:
                    async def run_async(self):
                        return "model1"

                with patch("prompt_toolkit.shortcuts.radiolist_dialog", return_value=MockDialog()):
                    try:
                        from nimcode.repl import NimcodeREPL
                        repl = NimcodeREPL(agent)
                        await repl.start_repl()
                    except StopAsyncIteration:
                        pass


import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from nimcode.repl import NimcodeREPL

@pytest.mark.asyncio
async def test_repl_trust_prompt_yes(agent):
    agent.settings = {"trusted_projects": []}
    commands = ["/exit"]
    with patch("prompt_toolkit.PromptSession") as MockSession:
        mock_session = MockSession.return_value
        mock_session.prompt_async = AsyncMock(side_effect=commands)
        with patch("builtins.input", return_value="y"):
            with patch("nimcode.repl.save_global_setting") as mock_save:
                repl = NimcodeREPL(agent)
                try:
                    await repl.start_repl()
                except StopAsyncIteration:
                    pass
                assert agent.settings["trusted_projects"]
                mock_save.assert_called_once()

@pytest.mark.asyncio
async def test_repl_trust_prompt_no(agent):
    agent.settings = {"trusted_projects": []}
    commands = ["/exit"]
    with patch("prompt_toolkit.PromptSession") as MockSession:
        mock_session = MockSession.return_value
        mock_session.prompt_async = AsyncMock(side_effect=commands)
        with patch("builtins.input", return_value="n"):
            repl = NimcodeREPL(agent)
            try:
                await repl.start_repl()
            except StopAsyncIteration:
                pass
            assert not agent.settings["trusted_projects"]

@pytest.mark.asyncio
async def test_repl_trust_prompt_keyboardinterrupt(agent):
    agent.settings = {"trusted_projects": []}
    commands = ["/exit"]
    with patch("prompt_toolkit.PromptSession") as MockSession:
        mock_session = MockSession.return_value
        mock_session.prompt_async = AsyncMock(side_effect=commands)
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            repl = NimcodeREPL(agent)
            try:
                await repl.start_repl()
            except StopAsyncIteration:
                pass
            assert not agent.settings["trusted_projects"]


@pytest.fixture
def agent():
    with patch("nimcode.agent.NimClient"):
        a = Agent(api_key="test_key")
        a.client.chat_one_shot = AsyncMock(return_value="I am done. TASK_COMPLETE")
        a.client.get_available_models = AsyncMock(return_value=["model1", "model2"])
        a.client.chat = MagicMock()
        return a

def test_repl_properties(agent):
    agent.mcp = MagicMock()
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
            mock_makedirs.assert_called_once()

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
            import sys
            sys.modules['pyautogui'] = MagicMock()
            agent.client.chat_vision = AsyncMock(return_value="vision output")
            repl = NimcodeREPL(agent)
            try:
                await repl.start_repl()
            except StopAsyncIteration:
                pass
            sys.modules.pop('pyautogui', None)

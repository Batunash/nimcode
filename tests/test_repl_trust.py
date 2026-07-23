import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from nimcode.repl import NimcodeREPL
from nimcode.agent import Agent
from nimcode.permissions import PermissionMode

@pytest.fixture
def agent():
    return Agent(api_key="test_key", max_turns=3, permission_mode=PermissionMode.BYPASS)
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
